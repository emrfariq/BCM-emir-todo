"""Inisialisasi manual: python init_db.py --create-database --seed."""
import argparse
import re
from datetime import timedelta

import mysql.connector

from config import BASE_DIR, Config
from db import connect
from validation import today, utcnow


def install_schema(conn):
    sql = (BASE_DIR / "database" / "schema.sql").read_text(encoding="utf-8")
    sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    with conn.cursor() as cur:
        for statement in sql.split(";"):
            if statement.strip():
                cur.execute(statement)
    conn.commit()


def seed_database(conn):
    now, day = utcnow(), today()
    with conn.cursor() as cur:
        cur.execute("SELECT (SELECT COUNT(*) FROM tasks) + (SELECT COUNT(*) FROM officers)")
        if cur.fetchone()[0]:
            print("Seed dilewati: database sudah berisi data. Tidak ada data yang ditimpa.")
            return
        officers = []
        for name, position in (("Emir Muhammad Al-Fariq", "Developer Intern"),
                               ("Nadia Putri", "QA Intern"), ("Raka Pratama", "Staf Administrasi")):
            cur.execute("INSERT INTO officers (name, position, created_at, updated_at) VALUES (%s,%s,%s,%s)",
                        (name, position, now, now))
            officers.append(cur.lastrowid)
        examples = [
            ("Menyiapkan dokumentasi aplikasi", "Lengkapi petunjuk setup dan langkah uji singkat.", 0, "in_progress", "high", officers[0], None),
            ("Memeriksa response API tugas", "Jalankan collection Postman untuk alur CRUD.", 0, "pending", "medium", officers[1], None),
            ("Melengkapi rekap pekerjaan", "Perbarui catatan pekerjaan yang belum selesai.", -1, "pending", "high", officers[2], None),
            ("Merapikan tampilan daftar tugas", "Periksa filter dan tampilan pada layar laptop.", 2, "pending", "medium", officers[0], None),
            ("Meninjau kebutuhan modul", "Diskusikan kebutuhan dan catat keputusan.", 1, "pending", "low", None, None),
            ("Membuat skema database", "Tabel tugas dan petugas sudah tersedia.", -2, "done", "high", officers[0], None),
            ("Catatan rapat sebelumnya", "Contoh tugas yang sudah tidak digunakan.", -3, "done", "low", officers[2], now),
        ]
        for title, description, offset, status, priority, officer_id, archived in examples:
            cur.execute("""INSERT INTO tasks (title,description,due_date,status,priority,officer_id,
                        archived_at,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (title, description, day + timedelta(days=offset), status, priority,
                         officer_id, archived, now, now))
    conn.commit()
    print("Data contoh ditambahkan: 3 petugas, 7 tugas.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--create-database", action="store_true", help="Khusus lokal: buat database jika belum ada")
    parser.add_argument("--seed", action="store_true", help="Isi data contoh hanya jika kedua tabel kosong")
    args = parser.parse_args()
    config = {key: getattr(Config, key) for key in dir(Config) if key.startswith("DB_")}
    conn = None
    try:
        if args.create_database:
            name = config["DB_NAME"]
            if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                parser.error("Nama database untuk --create-database hanya boleh huruf, angka, underscore.")
            conn = connect(config, with_database=False)
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.close()
        conn = connect(config)
        print(f"Terhubung ke server {conn.server_info}.")
        install_schema(conn)
        if args.seed:
            seed_database(conn)
        print("Database siap. Jalankan: python app.py")
    except mysql.connector.Error as error:
        if conn is not None and conn.is_connected():
            conn.rollback()
        parser.exit(1, f"Database belum siap (kode {error.errno}). Periksa konfigurasi dan layanan MySQL.\n")
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
