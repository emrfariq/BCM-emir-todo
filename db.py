"""Query SQL sederhana. Satu koneksi per request, selalu ditutup saat selesai."""
from contextlib import contextmanager

import mysql.connector
from flask import current_app, g

from validation import today, utcnow


def connect(config, with_database=True):
    options = {
        "host": config["DB_HOST"], "port": config["DB_PORT"],
        "user": config["DB_USER"], "password": config["DB_PASSWORD"],
        "connection_timeout": config["DB_CONNECT_TIMEOUT"],
        "charset": "utf8mb4", "collation": "utf8mb4_unicode_ci",
        "use_pure": True, "autocommit": False,
    }
    if with_database:
        options["database"] = config["DB_NAME"]
    if config.get("DB_SSL_DISABLED"):
        options["ssl_disabled"] = True
    if config.get("DB_SSL_CA"):
        options["ssl_ca"] = config["DB_SSL_CA"]
    if config.get("DB_SSL_VERIFY"):
        options.update(ssl_verify_cert=True, ssl_verify_identity=True)
    return mysql.connector.connect(**options)


def get_connection():
    if "db" not in g:
        g.db = connect(current_app.config)
    return g.db


def close_connection(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def cursor(write=False):
    conn = get_connection()
    cur = conn.cursor(dictionary=True, buffered=True)
    try:
        yield cur
        if write:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()


TASK_SELECT = """
    SELECT t.*, o.name AS officer_name
    FROM tasks t LEFT JOIN officers o ON o.id = t.officer_id
"""


def get_task(task_id):
    with cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE t.id = %s", (task_id,))
        return cur.fetchone()


def list_tasks(filters):
    clauses, params = [], []
    view = filters["view"]
    if view == "archived":
        clauses.append("t.archived_at IS NOT NULL")
    else:
        clauses.append("t.archived_at IS NULL")
        clauses.append("t.status = 'done'" if view == "completed" else "t.status <> 'done'")
    if filters["status"]:
        clauses.append("t.status = %s")
        params.append(filters["status"])
    due = filters["due"]
    if due != "all":
        operator = {"overdue": "<", "today": "=", "upcoming": ">"}[due]
        clauses.append(f"t.due_date {operator} %s")
        params.append(today())
    officer = filters["officer_id"]
    if officer == "none":
        clauses.append("t.officer_id IS NULL")
    elif officer:
        clauses.append("t.officer_id = %s")
        params.append(int(officer))
    if filters["q"]:
        # LOCATE memperlakukan % dan _ sebagai teks biasa, bukan wildcard.
        clauses.append("LOCATE(LOWER(%s), LOWER(t.title)) > 0")
        params.append(filters["q"])
    with cursor() as cur:
        cur.execute(TASK_SELECT + " WHERE " + " AND ".join(clauses)
                    + " ORDER BY t.due_date ASC, t.id DESC", tuple(params))
        return cur.fetchall()


def task_counts():
    with cursor() as cur:
        cur.execute("""SELECT
            COALESCE(SUM(archived_at IS NULL AND status <> 'done'), 0) AS active,
            COALESCE(SUM(archived_at IS NULL AND status = 'done'), 0) AS completed,
            COALESCE(SUM(archived_at IS NOT NULL), 0) AS archived,
            COALESCE(SUM(archived_at IS NULL AND status <> 'done' AND due_date < %s), 0) AS overdue
            FROM tasks""", (today(),))
        return cur.fetchone()


def insert_task(data):
    now = utcnow()
    with cursor(write=True) as cur:
        cur.execute("""INSERT INTO tasks
            (title, description, due_date, status, priority, officer_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (data["title"], data["description"], data["due_date"], data["status"],
                     data["priority"], data["officer_id"], now, now))
        return cur.lastrowid


def update_task(task_id, data):
    # Nama kolom hanya berasal dari allowlist internal, bukan input pengguna.
    allowed = {"title", "description", "due_date", "status", "priority", "officer_id", "archived_at"}
    fields = {key: value for key, value in data.items() if key in allowed}
    fields["updated_at"] = utcnow()
    with cursor(write=True) as cur:
        cur.execute("UPDATE tasks SET " + ", ".join(f"{key} = %s" for key in fields)
                    + " WHERE id = %s", (*fields.values(), task_id))


def delete_task(task_id):
    with cursor(write=True) as cur:
        cur.execute("DELETE FROM tasks WHERE id = %s AND archived_at IS NOT NULL", (task_id,))
        return cur.rowcount


def list_officers():
    with cursor() as cur:
        cur.execute("SELECT * FROM officers ORDER BY name ASC, id ASC")
        return cur.fetchall()


def get_officer(officer_id):
    with cursor() as cur:
        cur.execute("SELECT * FROM officers WHERE id = %s", (officer_id,))
        return cur.fetchone()


def save_officer(data, officer_id=None):
    now = utcnow()
    with cursor(write=True) as cur:
        if officer_id is None:
            cur.execute("""INSERT INTO officers (name, position, created_at, updated_at)
                        VALUES (%s, %s, %s, %s)""", (data["name"], data["position"], now, now))
            return cur.lastrowid
        cur.execute("UPDATE officers SET name = %s, position = %s, updated_at = %s WHERE id = %s",
                    (data["name"], data["position"], now, officer_id))
        return officer_id


def delete_officer(officer_id):
    with cursor(write=True) as cur:
        # Perbarui timestamp tugas yang penugasannya ikut berubah.
        cur.execute("UPDATE tasks SET updated_at = %s WHERE officer_id = %s", (utcnow(), officer_id))
        cur.execute("DELETE FROM officers WHERE id = %s", (officer_id,))
