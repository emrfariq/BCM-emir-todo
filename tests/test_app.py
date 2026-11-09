"""Integration test memakai database terpisah dan nama acak, bukan data demo."""
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

import mysql.connector

import db
from app import create_app
from config import Config
from init_db import install_schema, seed_database
from validation import today


class AppIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = {key: getattr(Config, key) for key in dir(Config) if key.startswith("DB_")}
        # Nama dibuat sendiri, tidak menerima nama database pengguna untuk DROP.
        cls.database_name = "bcm_emir_test_" + uuid4().hex[:12]
        cls.config["DB_NAME"] = cls.database_name
        cls.admin = db.connect(cls.config, with_database=False)
        with cls.admin.cursor() as cur:
            cur.execute(f"CREATE DATABASE `{cls.database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cls.conn = db.connect(cls.config)
        install_schema(cls.conn)
        cls.app = create_app({**cls.config, "TESTING": True, "SECRET_KEY": "test-key", "SESSION_COOKIE_SECURE": False})

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        with cls.admin.cursor() as cur:
            cur.execute(f"DROP DATABASE `{cls.database_name}`")
        cls.admin.close()

    def setUp(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM tasks")
            cur.execute("DELETE FROM officers")
        self.conn.commit()
        self.client = self.app.test_client()
        with self.app.app_context():
            self.officer_id = db.save_officer({"name": "Emir Uji", "position": "Intern"})
        self.payload = {"title": "Tugas integration", "due_date": today().isoformat(), "officer_id": self.officer_id}
        self.json_header = {"Content-Type": "application/json"}

    def create_task(self, **changes):
        response = self.client.post("/api/tasks", json={**self.payload, **changes})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.json["data"]

    def csrf(self):
        self.client.get("/tasks/new")
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def test_create_persists_across_clients_and_sets_location(self):
        response = self.client.post("/api/tasks", json=self.payload)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.headers["Location"].endswith(str(response.json["data"]["id"])))
        task = self.app.test_client().get(response.headers["Location"]).json["data"]
        self.assertEqual(task["title"], self.payload["title"])
        self.assertEqual(task["priority"], "medium")
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["officer"]["name"], "Emir Uji")
        self.assertTrue(task["created_at"].endswith("Z"))

    def test_status_moves_between_active_completed(self):
        task = self.create_task()
        url = f"/api/tasks/{task['id']}"
        response = self.client.patch(url, json={"status": "done"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/tasks").json["data"], [])
        self.assertEqual(self.client.get("/api/tasks?view=completed").json["data"][0]["id"], task["id"])
        self.client.patch(url, json={"status": "in_progress"})
        self.assertEqual(self.client.get("/api/tasks").json["data"][0]["status"], "in_progress")

    def test_archive_restore_delete_lifecycle(self):
        task = self.create_task()
        url = f"/api/tasks/{task['id']}"
        self.assertEqual(self.client.delete(url, headers=self.json_header).status_code, 409)
        self.assertEqual(self.client.post(url + "/restore", headers=self.json_header).status_code, 409)
        archive = self.client.post(url + "/archive", headers=self.json_header)
        self.assertIsNotNone(archive.json["data"]["archived_at"])
        self.assertEqual(self.client.get("/api/tasks").json["data"], [])
        self.assertEqual(len(self.client.get("/api/tasks?view=archived").json["data"]), 1)
        self.assertEqual(self.client.patch(url, json={"title": "Tidak boleh"}).status_code, 409)
        self.assertEqual(self.client.post(url + "/archive", headers=self.json_header).status_code, 409)
        restored = self.client.post(url + "/restore", headers=self.json_header).json["data"]
        self.assertIsNone(restored["archived_at"])
        self.assertEqual(restored["status"], "pending")
        self.client.post(url + "/archive", headers=self.json_header)
        deleted = self.client.delete(url, headers=self.json_header)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.data, b"")
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_restore_completed_returns_to_completed(self):
        task = self.create_task()
        url = f"/api/tasks/{task['id']}"
        self.client.patch(url, json={"status": "done"})
        self.client.post(url + "/archive", headers=self.json_header)
        self.client.post(url + "/restore", headers=self.json_header)
        self.assertEqual(len(self.client.get("/api/tasks?view=completed").json["data"]), 1)

    def test_validation_rejects_wrong_types_unknown_fields_and_dates(self):
        invalid = [
            {"title": "   "}, {"title": "x" * 121}, {"title": 123},
            {"description": "x" * 1001}, {"due_date": None}, {"due_date": ""},
            {"due_date": "2026-02-30"}, {"due_date": "20261109"},
            {"priority": "urgent"}, {"priority": None}, {"officer_id": True},
            {"officer_id": "1"}, {"officer_id": 4294967295},
            {"status": "done"}, {"extra": "unknown"},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                response = self.client.post("/api/tasks", json={**self.payload, **changes})
                self.assertEqual(response.status_code, 422)
                self.assertIn("fields", response.json["error"])
        self.assertEqual(self.client.get("/api/tasks").json["data"], [])

    def test_failed_patch_does_not_partially_change_data(self):
        task = self.create_task(description="Teks lama")
        url = f"/api/tasks/{task['id']}"
        self.assertEqual(self.client.patch(url, json={"title": "Baru", "due_date": None}).status_code, 422)
        current = self.client.get(url).json["data"]
        self.assertEqual(current["title"], self.payload["title"])
        self.assertEqual(self.client.patch(url, json={}).status_code, 422)
        self.assertEqual(self.client.patch(url, json={"status": "invalid"}).status_code, 422)
        self.assertEqual(self.client.patch(url, json={"id": 3}).status_code, 422)
        cleared = self.client.patch(url, json={"description": None, "officer_id": None}).json["data"]
        self.assertIsNone(cleared["description"])
        self.assertIsNone(cleared["officer"])

    def test_json_media_types_and_method_errors(self):
        self.assertEqual(self.client.post("/api/tasks", data="{}").status_code, 415)
        malformed = self.client.post("/api/tasks", data="{broken", headers=self.json_header)
        self.assertEqual(malformed.status_code, 400)
        self.assertTrue(malformed.is_json)
        for payload in ([], "text", 7, None):
            response = self.client.post("/api/tasks", data=__import__("json").dumps(payload), headers=self.json_header)
            self.assertEqual(response.status_code, 422)
        response = self.client.put("/api/tasks", json={})
        self.assertEqual(response.status_code, 405)
        self.assertIn("GET", response.headers["Allow"])
        self.assertTrue(self.client.get("/api/missing").is_json)

    def test_combined_filters_literal_search_and_order(self):
        yesterday = (today() - timedelta(days=1)).isoformat()
        first = self.create_task(title="100%_Laporan", due_date=yesterday, officer_id=None)
        second = self.create_task(title="Laporan rutin", due_date=yesterday)
        self.create_task(title="Hari ini")
        tasks = self.client.get("/api/tasks?due=overdue").json["data"]
        self.assertEqual([row["id"] for row in tasks], [second["id"], first["id"]])
        tasks = self.client.get("/api/tasks?due=overdue&officer_id=none&q=%25_&status=pending").json["data"]
        self.assertEqual([row["id"] for row in tasks], [first["id"]])
        self.assertEqual(len(self.client.get(f"/api/tasks?officer_id={self.officer_id}&q=LAPORAN").json["data"]), 1)
        self.assertEqual(self.client.get("/api/tasks?q=' OR 1=1 --").json["data"], [])

    def test_invalid_filters(self):
        for query in ("view=wrong", "status=done", "view=completed&status=pending", "due=invalid",
                      "view=archived&due=overdue", "officer_id=-1", "officer_id=0", "officer_id=abc"):
            with self.subTest(query=query):
                response = self.client.get("/api/tasks?" + query)
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.is_json)

    def test_overdue_follows_calendar_and_excludes_done_archived(self):
        fixed = date(2026, 11, 9)
        with patch("validation.today", return_value=fixed), patch("db.today", return_value=fixed), patch("app.today", return_value=fixed):
            late = self.create_task(due_date="2026-11-08")
            on_time = self.create_task(due_date="2026-11-09")
            self.assertTrue(late["is_overdue"])
            self.assertFalse(on_time["is_overdue"])
            url = f"/api/tasks/{late['id']}"
            self.assertFalse(self.client.patch(url, json={"status": "done"}).json["data"]["is_overdue"])
            self.client.patch(url, json={"status": "pending"})
            self.assertFalse(self.client.post(url + "/archive", headers=self.json_header).json["data"]["is_overdue"])

    def test_duplicate_titles_are_allowed(self):
        one, two = self.create_task(), self.create_task()
        self.assertNotEqual(one["id"], two["id"])

    def test_web_csrf_create_edit_status_and_archive(self):
        self.assertEqual(self.client.post("/tasks/new", data=self.payload).status_code, 400)
        self.assertEqual(self.client.post("/tasks/new", data={"csrf_token": "日本語"}).status_code, 400)
        token = self.csrf()
        form = {**self.payload, "csrf_token": token, "priority": "high", "description": "Catatan"}
        response = self.client.post("/tasks/new", data=form)
        self.assertEqual(response.status_code, 302)
        task = self.client.get("/api/tasks").json["data"][0]
        task_id = task["id"]
        self.assertEqual(self.client.get(f"/tasks/{task_id}/edit").status_code, 200)
        invalid = self.client.post(f"/tasks/{task_id}/edit", data={**form, "title": "Nilai tetap terlihat", "due_date": "", "status": "pending"})
        self.assertEqual(invalid.status_code, 422)
        self.assertIn(b"Nilai tetap terlihat", invalid.data)
        response = self.client.post(f"/tasks/{task_id}/edit", data={**form, "title": "Judul baru", "status": "in_progress"})
        self.assertEqual(response.status_code, 302)
        response = self.client.post(f"/tasks/{task_id}/status", data={"csrf_token": token, "status": "done"})
        self.assertIn("view=completed", response.headers["Location"])
        self.client.post(f"/tasks/{task_id}/archive", data={"csrf_token": token})
        self.assertEqual(self.client.get("/?view=archived").status_code, 200)
        self.assertEqual(self.client.get(f"/tasks/{task_id}/edit").status_code, 409)
        self.client.post(f"/tasks/{task_id}/restore", data={"csrf_token": token})
        self.client.post(f"/tasks/{task_id}/archive", data={"csrf_token": token})
        self.assertEqual(self.client.post(f"/tasks/{task_id}/delete", data={"csrf_token": token}).status_code, 302)
        self.assertEqual(self.client.get(f"/api/tasks/{task_id}").status_code, 404)

    def test_web_officer_crud_preserves_tasks(self):
        token = self.csrf()
        created = self.client.post("/officers", data={"name": "Petugas baru", "position": "QA", "csrf_token": token})
        self.assertEqual(created.status_code, 302)
        officer = next(row for row in self.client.get("/api/officers").json["data"] if row["name"] == "Petugas baru")
        task = self.create_task(officer_id=officer["id"])
        edit_url = f"/officers/{officer['id']}/edit"
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        self.client.post(edit_url, data={"name": "Nama diperbarui", "position": "", "csrf_token": token})
        self.assertEqual(self.client.get(f"/api/tasks/{task['id']}").json["data"]["officer"]["name"], "Nama diperbarui")
        self.client.post(f"/officers/{officer['id']}/delete", data={"csrf_token": token})
        task = self.client.get(f"/api/tasks/{task['id']}").json["data"]
        self.assertIsNone(task["officer_id"])
        self.assertEqual(task["title"], self.payload["title"])
        self.assertEqual(self.client.post("/officers", data={"name": " ", "csrf_token": token}).status_code, 422)

    def test_pages_assets_escaping_and_error_headers(self):
        task = self.create_task(title='<script>alert("x")</script>')
        for path in ("/", "/?view=completed", "/?view=archived", "/officers", "/tasks/new", "/app.css", "/app.js", "/favicon.svg"):
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
        html = self.client.get("/")
        self.assertIn(b"&lt;script&gt;", html.data)
        self.assertNotIn(b'<script>alert("x")</script>', html.data)
        self.assertEqual(html.headers["Cache-Control"], "no-store")
        self.assertEqual(html.headers["X-Content-Type-Options"], "nosniff")
        response = self.client.get("/missing-page")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.is_json)
        # Endpoint API tanpa JSON tidak dapat dipakai oleh form lintas situs.
        self.assertEqual(self.client.post(f"/api/tasks/{task['id']}/archive").status_code, 415)

    def test_database_failure_is_sanitized(self):
        with patch("db.connect", side_effect=mysql.connector.Error("password=do-not-show", errno=2003)):
            response = self.client.get("/api/tasks")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("do-not-show", response.get_data(as_text=True))
            response = self.client.get("/")
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b"Traceback", response.data)

    def test_seed_is_repeat_safe(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM officers")
        self.conn.commit()
        seed_database(self.conn)
        seed_database(self.conn)
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tasks")
            self.assertEqual(cur.fetchone()[0], 7)
            cur.execute("SELECT COUNT(*) FROM officers")
            self.assertEqual(cur.fetchone()[0], 3)
        self.conn.commit()


if __name__ == "__main__":
    unittest.main()
