"""BCM Emir Todo — route web dan API di atas fungsi database yang sama."""
import hmac
import logging
import secrets
from datetime import date, datetime, timezone

import mysql.connector
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

import db
from config import Config
from validation import (DUE_FILTERS, JAKARTA, PRIORITIES, STATUSES, VIEWS,
                        parse_filters, today, utcnow, validate_officer, validate_task)


def serialize_task(task):
    data = {key: value for key, value in task.items() if key != "officer_name"}
    for key in ("created_at", "updated_at", "archived_at"):
        data[key] = data[key].isoformat(timespec="seconds") + "Z" if data[key] else None
    data["due_date"] = data["due_date"].isoformat()
    data["officer"] = {"id": task["officer_id"], "name": task["officer_name"]} if task["officer_id"] else None
    data["is_overdue"] = is_overdue(task)
    return data


def is_overdue(task):
    return task["archived_at"] is None and task["status"] != "done" and task["due_date"] < today()


def create_app(test_config=None):
    app = Flask(__name__, static_folder="public", static_url_path="")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    app.teardown_appcontext(db.close_connection)

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return session["csrf_token"]

    @app.context_processor
    def template_globals():
        now = datetime.now(JAKARTA)
        return dict(csrf_token=csrf_token, statuses=STATUSES, priorities=PRIORITIES,
                    views=VIEWS, due_filters=DUE_FILTERS, is_overdue=is_overdue,
                    today=now.date(), current_year=now.year, header_time=now.strftime("%H:%M"))

    @app.template_filter("tanggal")
    def format_date(value):
        if isinstance(value, datetime):
            value = value.replace(tzinfo=timezone.utc).astimezone(JAKARTA)
        return value.strftime("%d/%m/%Y") if isinstance(value, date) else "—"

    @app.before_request
    def protect_writes():
        if request.method not in ("POST", "PATCH", "PUT", "DELETE"):
            return
        if request.path.startswith("/api/"):
            # JSON memerlukan preflight lintas origin; aplikasi tidak membuka CORS.
            # Header tetap wajib pada archive/restore/DELETE meskipun body kosong.
            if not request.is_json:
                abort(415, description="Gunakan header Content-Type: application/json.")
        else:
            supplied = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not supplied.isascii() or not hmac.compare_digest(supplied, expected):
                abort(400, description="Form sudah tidak valid. Muat ulang halaman lalu coba kembali.")

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Halaman berisi token form; jangan dibagikan dari cache antar pengunjung.
        if not request.endpoint or request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    def get_task_or_404(task_id):
        task = db.get_task(task_id)
        if task is None:
            abort(404, description="Tugas tidak ditemukan.")
        return task

    def get_officer_or_404(officer_id):
        officer = db.get_officer(officer_id)
        if officer is None:
            abort(404, description="Petugas tidak ditemukan.")
        return officer

    def check_officer(cleaned, errors):
        officer_id = cleaned.get("officer_id")
        if officer_id is not None and db.get_officer(officer_id) is None:
            errors["officer_id"] = "Petugas tidak ditemukan. Pilih petugas yang masih tersedia."

    def api_error(message, status=422, fields=None):
        error = {"code": "validation_error", "message": message}
        if fields:
            error["fields"] = fields
        return jsonify(error=error), status

    def json_payload():
        payload = request.get_json()  # JSON rusak ditangani sebagai HTTP 400.
        if not isinstance(payload, dict):
            return None
        return payload

    def form_task_data():
        data = {key: request.form.get(key, "") for key in
                ("title", "description", "due_date", "priority", "officer_id")}
        officer = data["officer_id"]
        if not officer:
            data["officer_id"] = None
        elif officer.isascii() and officer.isdigit():
            data["officer_id"] = int(officer)
        return data

    def render_task_form(task, errors=None, editing=False, code=200):
        return render_template("task_form.html", task=task, errors=errors or {},
                               editing=editing, officers=db.list_officers()), code

    def go_to_task(task):
        view = "archived" if task["archived_at"] else "completed" if task["status"] == "done" else "active"
        return redirect(url_for("index", view=view))

    @app.get("/")
    def index():
        try:
            filters = parse_filters(request.args)
        except ValueError as error:
            abort(400, description=str(error))
        return render_template("index.html", filters=filters, tasks=db.list_tasks(filters),
                               counts=db.task_counts(), officers=db.list_officers())

    @app.route("/tasks/new", methods=["GET", "POST"])
    def create_task():
        if request.method == "GET":
            return render_task_form({"due_date": today().isoformat(), "priority": "medium", "officer_id": None})
        raw = form_task_data()
        cleaned, errors = validate_task(raw)
        check_officer(cleaned, errors)
        if errors:
            return render_task_form(raw, errors, code=422)
        db.insert_task(cleaned)
        flash("Tugas berhasil ditambahkan.", "success")
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    def edit_task(task_id):
        task = get_task_or_404(task_id)
        if task["archived_at"]:
            abort(409, description="Pulihkan tugas dari Arsip sebelum mengedit.")
        if request.method == "GET":
            return render_task_form(task, editing=True)
        raw = form_task_data()
        raw["status"] = request.form.get("status", "")
        cleaned, errors = validate_task(raw, partial=True)
        check_officer(cleaned, errors)
        if errors:
            return render_task_form({**task, **raw}, errors, editing=True, code=422)
        db.update_task(task_id, cleaned)
        flash("Perubahan tugas berhasil disimpan.", "success")
        return go_to_task(db.get_task(task_id))

    @app.post("/tasks/<int:task_id>/status")
    def change_status(task_id):
        task = get_task_or_404(task_id)
        if task["archived_at"]:
            abort(409, description="Pulihkan tugas sebelum mengubah status.")
        cleaned, errors = validate_task({"status": request.form.get("status")}, partial=True)
        if errors:
            abort(422, description="Status tugas tidak valid.")
        db.update_task(task_id, cleaned)
        flash("Status tugas berhasil diperbarui.", "success")
        return go_to_task(db.get_task(task_id))

    def move_task(task_id, archive):
        task = get_task_or_404(task_id)
        if bool(task["archived_at"]) == archive:
            abort(409, description="Tugas sudah diarsipkan." if archive else "Tugas tidak berada di Arsip.")
        db.update_task(task_id, {"archived_at": utcnow() if archive else None})
        return db.get_task(task_id)

    @app.post("/tasks/<int:task_id>/archive")
    def archive_task(task_id):
        move_task(task_id, True)
        flash("Tugas dipindahkan ke Arsip. Kamu dapat memulihkannya kapan saja.", "success")
        return redirect(url_for("index", view="archived"))

    @app.post("/tasks/<int:task_id>/restore")
    def restore_task(task_id):
        task = move_task(task_id, False)
        flash("Tugas berhasil dipulihkan.", "success")
        return go_to_task(task)

    @app.post("/tasks/<int:task_id>/delete")
    def remove_task(task_id):
        task = get_task_or_404(task_id)
        if task["archived_at"] is None:
            abort(409, description="Arsipkan tugas sebelum menghapus permanen.")
        db.delete_task(task_id)
        flash("Tugas berhasil dihapus permanen.", "success")
        return redirect(url_for("index", view="archived"))

    @app.route("/officers", methods=["GET", "POST"])
    def officer_list():
        raw, errors, code = {}, {}, 200
        if request.method == "POST":
            raw = request.form
            cleaned, errors = validate_officer(raw)
            if not errors:
                db.save_officer(cleaned)
                flash("Petugas berhasil ditambahkan.", "success")
                return redirect(url_for("officer_list"))
            code = 422
        return render_template("officers.html", officers=db.list_officers(), form=raw, errors=errors), code

    @app.route("/officers/<int:officer_id>/edit", methods=["GET", "POST"])
    def edit_officer(officer_id):
        officer = get_officer_or_404(officer_id)
        errors, code = {}, 200
        if request.method == "POST":
            cleaned, errors = validate_officer(request.form)
            if not errors:
                db.save_officer(cleaned, officer_id)
                flash("Data petugas berhasil diperbarui.", "success")
                return redirect(url_for("officer_list"))
            officer = {**officer, **request.form.to_dict()}
            code = 422
        return render_template("officer_form.html", officer=officer, errors=errors), code

    @app.post("/officers/<int:officer_id>/delete")
    def remove_officer(officer_id):
        get_officer_or_404(officer_id)
        db.delete_officer(officer_id)
        flash("Petugas dihapus. Tugasnya tetap tersimpan sebagai Belum ditugaskan.", "success")
        return redirect(url_for("officer_list"))

    @app.get("/api/tasks")
    def api_list_tasks():
        try:
            filters = parse_filters(request.args)
        except ValueError as error:
            abort(400, description=str(error))
        return jsonify(data=[serialize_task(task) for task in db.list_tasks(filters)])

    @app.get("/api/tasks/<int:task_id>")
    def api_get_task(task_id):
        return jsonify(data=serialize_task(get_task_or_404(task_id)))

    @app.post("/api/tasks")
    def api_create_task():
        payload = json_payload()
        if payload is None:
            return api_error("Body harus berupa objek JSON.")
        cleaned, errors = validate_task(payload)
        check_officer(cleaned, errors)
        if errors:
            return api_error("Periksa kembali input tugas.", fields=errors)
        task_id = db.insert_task(cleaned)
        response = jsonify(data=serialize_task(db.get_task(task_id)))
        response.status_code = 201
        response.headers["Location"] = url_for("api_get_task", task_id=task_id)
        return response

    @app.patch("/api/tasks/<int:task_id>")
    def api_update_task(task_id):
        task = get_task_or_404(task_id)
        if task["archived_at"]:
            abort(409, description="Pulihkan tugas sebelum mengedit.")
        payload = json_payload()
        if payload is None:
            return api_error("Body harus berupa objek JSON.")
        cleaned, errors = validate_task(payload, partial=True)
        check_officer(cleaned, errors)
        if errors:
            return api_error("Periksa kembali input tugas.", fields=errors)
        db.update_task(task_id, cleaned)
        return jsonify(data=serialize_task(db.get_task(task_id)))

    @app.post("/api/tasks/<int:task_id>/archive")
    def api_archive_task(task_id):
        return jsonify(data=serialize_task(move_task(task_id, True)))

    @app.post("/api/tasks/<int:task_id>/restore")
    def api_restore_task(task_id):
        return jsonify(data=serialize_task(move_task(task_id, False)))

    @app.delete("/api/tasks/<int:task_id>")
    def api_delete_task(task_id):
        task = get_task_or_404(task_id)
        if task["archived_at"] is None:
            abort(409, description="Arsipkan tugas sebelum menghapus permanen.")
        db.delete_task(task_id)
        return "", 204

    @app.get("/api/officers")
    def api_list_officers():
        return jsonify(data=[{"id": officer["id"], "name": officer["name"], "position": officer["position"]}
                             for officer in db.list_officers()])

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {
            400: "Request tidak valid. Periksa format JSON atau input.",
            404: "Halaman atau data tidak ditemukan.", 405: "Metode HTTP tidak didukung.",
            413: "Ukuran request terlalu besar.", 500: "Terjadi kesalahan internal. Coba kembali nanti.",
        }
        message = error.description if error.code in (409, 415, 422) else messages.get(error.code, error.description)
        # Pesan validasi filter/form ditentukan sendiri, bukan exception parser.
        if error.code == 400 and error.description != HTTPException.description and not error.description.startswith("The browser"):
            message = error.description
        response = error.get_response()  # Pertahankan header Allow pada 405.
        if request.path.startswith("/api/"):
            response.data = app.json.dumps({"error": {"code": error.name.lower().replace(" ", "_"), "message": message}})
            response.content_type = "application/json"
        else:
            response.data = render_template("error.html", code=error.code, message=message)
            response.content_type = "text/html; charset=utf-8"
        return response

    @app.errorhandler(mysql.connector.Error)
    def database_error(error):
        app.logger.error("Gangguan database, kode=%s", error.errno)
        if isinstance(error, mysql.connector.IntegrityError) and error.errno == 1452:
            if request.path.startswith("/api/"):
                return api_error("Petugas tidak tersedia. Pilih kembali penanggung jawab.", fields={"officer_id": "Petugas tidak ditemukan."})
            return render_template("error.html", code=422, message="Petugas sudah berubah. Muat ulang lalu pilih kembali."), 422
        message = "Database belum dapat diakses. Periksa layanan MySQL dan konfigurasi koneksi, lalu coba kembali."
        if request.path.startswith("/api/"):
            return jsonify(error={"code": "database_unavailable", "message": message}), 503
        return render_template("error.html", code=503, message=message), 503

    return app


logging.basicConfig(level=logging.INFO)
app = create_app()

if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
