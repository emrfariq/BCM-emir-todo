# BCM Emir Todo

Modul web sederhana untuk mencatat dan mengelola tugas harian. Dibuat untuk tes **BCM Developer Intern**, menggunakan **Python Flask + MySQL**, dengan halaman HTML Jinja2 dan CSS lokal tanpa build frontend.

## Fitur

- Tambah, lihat, edit, dan ubah status tugas: **Belum dikerjakan → Progres → Selesai**, dengan perpindahan bebas.
- Tenggat wajib, penanda terlambat, prioritas Rendah/Sedang/Tinggi, dan penanggung jawab opsional.
- Pencarian judul serta filter status, tenggat, dan petugas yang dapat dikombinasikan.
- Halaman Tugas Aktif, Selesai, dan Arsip. Arsip dapat dipulihkan; hapus permanen hanya dari Arsip.
- Kelola petugas; menghapus petugas tidak menghapus tugasnya.
- REST API dan collection Postman berisi alur sukses serta input tidak valid.

Demo memakai satu daftar bersama tanpa login. Petugas adalah daftar nama, bukan akun. Tugas tetap tersimpan saat hari berganti; judul boleh berulang. Perhitungan hari ini menggunakan **Asia/Jakarta**. Gunakan data contoh untuk demo publik.

## 1. Menjalankan di Windows / XAMPP

### Prasyarat

- **Python 3.12** dan XAMPP dengan MySQL/MariaDB aktif di port `3306`.
- Database lokal sudah diuji pada **MariaDB 10.4.32 (XAMPP)**. Skema ditujukan untuk MySQL 5.5+/8 serta MariaDB 10.4; verifikasi pada MySQL hosting dilakukan setelah koneksinya tersedia.
- Dependensi yang diuji: Flask 3.1.3, mysql-connector-python 9.7.0, python-dotenv 1.2.4, tzdata 2026.6.

Buka PowerShell dari folder project:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Jika `.env` sudah tersedia dan sesuai, tidak perlu menyalin ulang. Aktivasi virtual environment tidak wajib karena perintah menggunakan interpreter `.venv` secara langsung.

Isi `.env` untuk XAMPP standar:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=bcm_emir_todo
DB_CONNECT_TIMEOUT=10
SECRET_KEY=isi-dengan-kunci-acak
FLASK_DEBUG=0
```

Jika root XAMPP memakai password, isi `DB_PASSWORD` sesuai konfigurasi lokal. Buat kunci sesi dengan perintah berikut, kemudian salin hasilnya ke `SECRET_KEY`:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

### Buat database, tabel, dan data contoh

1. Nyalakan **MySQL** di XAMPP Control Panel. Apache hanya diperlukan jika memakai phpMyAdmin.
2. Jalankan:

```powershell
.\.venv\Scripts\python.exe init_db.py --create-database --seed
.\.venv\Scripts\python.exe app.py
```

3. Buka **http://127.0.0.1:5000**. Hentikan server dengan `Ctrl+C`.

### Cara cepat untuk menjalankan kembali / demo interview

Setelah instalasi dan database siap, nyalakan MySQL XAMPP lalu **klik dua kali `run.bat`** di folder project. Bisa juga dari terminal root project:

```powershell
.\run.bat
```

Script memilih konfigurasi lokal `.env` dan interpreter Python `.venv` secara otomatis. Buka **http://127.0.0.1:5000** dan biarkan jendela server tetap terbuka selama demo. Hentikan dengan `Ctrl+C`.

`--create-database` membuat database lokal jika belum tersedia. `--seed` menambahkan 3 petugas dan 7 tugas hanya jika kedua tabel kosong. Script tidak menghapus data yang sudah ada dan tidak dijalankan otomatis saat startup.

**Alternatif phpMyAdmin:** buat database `bcm_emir_todo` dengan collation `utf8mb4_unicode_ci`, pilih database tersebut, lalu impor `database/schema.sql`. Untuk data contoh, jalankan `init_db.py --seed` tanpa `--create-database`.

## 2. Alur penggunaan singkat

1. Pilih **Tambah tugas**, isi judul dan tenggat, lalu simpan. Prioritas default Sedang, status awal Belum dikerjakan.
2. Muat ulang halaman untuk memastikan tugas tersimpan. Pilih nama **Emir** pada filter petugas jika ingin melihat tugas yang ditugaskan kepadanya.
3. Edit detail atau ubah status dari dropdown pada baris tugas, lalu tekan tombol **↵** di samping dropdown untuk menyimpan.
4. Tugas Selesai tampil pada halaman tersendiri dan dapat dibuka kembali.
5. Pilih **Arsipkan**, lalu konfirmasi. Di Arsip, pilih **Pulihkan** atau **Hapus** permanen.
6. Tambah/edit/hapus nama melalui **Petugas**. Tugas milik petugas yang dihapus menjadi Belum ditugaskan.

Tenggat terdekat tampil lebih dahulu, lalu ID terbaru jika tanggal sama. Filter **Semua tenggat** berlaku pada halaman yang sedang dibuka, bukan seluruh halaman sekaligus. Ringkasan angka di atas daftar menunjukkan keseluruhan data dan tidak mengikuti filter. Prioritas hanya penanda, bukan pengurutan tambahan.

## 3. Pengujian API menggunakan Postman

1. Jalankan aplikasi lokal.
2. Import `postman/BCM_Emir_Todo.postman_collection.json` ke Postman.
3. Pada collection → **Variables**, isi `base_url` dengan `http://127.0.0.1:5000`, tanpa `/` terakhir.
4. Jalankan seluruh collection **berurutan** melalui Collection Runner. Tidak perlu environment Postman terpisah.

Collection mengambil ID petugas jika ada, membuat satu tugas uji, menyimpan `task_id` otomatis, memverifikasi perubahan status dan arsip, menguji input tidak valid, kemudian menghapus tugas uji. Jangan hanya menjalankan request terakhir karena ID diperoleh dari create. Jika proses berhenti di tengah, tugas berjudul `Postman - tugas uji ...` dapat diarsipkan dan dihapus manual.

Assertion memeriksa status HTTP, header, tipe/struktur JSON, nilai data, error, serta konsistensi perubahan lewat request lanjutan. Response time dicatat sebagai observasi; soal tidak menentukan SLA.

### Endpoint

| Method | Path | Keterangan | Sukses |
| --- | --- | --- | --- |
| GET | `/api/tasks` | Daftar dan filter | 200 |
| GET | `/api/tasks/{id}` | Detail, termasuk arsip | 200 |
| POST | `/api/tasks` | Buat tugas | 201 + `Location` |
| PATCH | `/api/tasks/{id}` | Ubah sebagian field/status tugas nonarsip | 200 |
| POST | `/api/tasks/{id}/archive` | Arsipkan | 200 |
| POST | `/api/tasks/{id}/restore` | Pulihkan | 200 |
| DELETE | `/api/tasks/{id}` | Hapus permanen tugas arsip | 204, body kosong |
| GET | `/api/officers` | Pilihan ID petugas | 200 |

**Seluruh request tulis API wajib mengirim `Content-Type: application/json`**, termasuk archive, restore, dan DELETE yang tidak memerlukan body. API tidak memerlukan token CSRF form web dan tidak membuka CORS lintas origin.

Contoh create:

```http
POST /api/tasks
Content-Type: application/json
```

```json
{
  "title": "Menyiapkan laporan harian",
  "description": "Rekap pekerjaan untuk rapat tim.",
  "due_date": "2026-11-10",
  "priority": "high",
  "officer_id": null
}
```

Contoh sebagian respons `201`:

```json
{
  "data": {
    "id": 8,
    "title": "Menyiapkan laporan harian",
    "description": "Rekap pekerjaan untuk rapat tim.",
    "due_date": "2026-11-10",
    "status": "pending",
    "priority": "high",
    "officer_id": null,
    "officer": null,
    "archived_at": null,
    "created_at": "2026-11-09T03:00:00Z",
    "updated_at": "2026-11-09T03:00:00Z",
    "is_overdue": false
  }
}
```

Nilai ID/waktu dan penanda terlambat bergantung pada data serta hari saat aplikasi dijalankan.

Contoh PATCH: `{"status":"done"}`. Field yang tidak dikirim tetap sama. `null` boleh mengosongkan `description` dan `officer_id`; tenggat dan judul tidak boleh kosong. Field `status` hanya diterima saat PATCH; create selalu `pending`.

Filter daftar: `view=active|completed|archived` (default active), `status=pending|in_progress|done` sesuai halaman, `due=all|overdue|today|upcoming`, `officer_id=<id>|none`, `q=<judul>`. Contoh:

```text
/api/tasks?view=active&status=pending&due=today&officer_id=none&q=laporan
```

Error menggunakan bentuk konsisten, contohnya:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Periksa kembali input tugas.",
    "fields": {"title": "Judul wajib diisi."}
  }
}
```

| Kode | Kondisi |
| --- | --- |
| 400 | JSON rusak atau filter tidak valid |
| 404 | ID/endpoint tidak ada, termasuk tugas terhapus |
| 405 | Method tidak didukung |
| 409 | Edit tugas arsip, hapus nonarsip, archive/restore pada keadaan yang salah |
| 413 | Request lebih besar dari 64 KiB |
| 415 | Request tulis tanpa media type JSON |
| 422 | Validasi field/payload gagal; PATCH kosong atau field tidak dikenal |
| 503 | Database tidak dapat diakses |
| 500 | Kesalahan internal tak terduga |

## 4. Hosting gratis: Vercel + MySQL online

**Vercel menjalankan aplikasi Flask, bukan server MySQL XAMPP.** `localhost` di Vercel bukan laptop kamu. Dibutuhkan database MySQL online yang dapat menerima koneksi remote. Data lokal dan online terpisah, tidak otomatis sinkron.

Panduan langkah demi langkah ada di **[docs/KONFIGURASI_DATABASE.md](docs/KONFIGURASI_DATABASE.md)**. Konfigurasi yang disiapkan mendukung **FreeSQLDatabase** sebagai opsi gratis; pembuatan akun dan detail koneksi diambil dari panel/email penyedia. Verifikasi kuota dan ketersediaan paket pada akun ketika mendaftar.

Ringkasnya:
1. Daftar database MySQL gratis, lalu impor skema/seed menggunakan koneksi hosting.
2. Push source ke repo. `.env`, `.venv`, dan `dev-plan/` sudah diabaikan oleh `.gitignore`.
3. Import repo di Vercel. Entrypoint `app.py` mengekspor instance Flask `app`; `pyproject.toml` memilih Python 3.12. Gunakan deteksi Flask bawaan; tidak perlu start command `python app.py`, Docker, atau rewrite lama.
4. Isi environment variables Vercel sesuai `.env.hosting.example`, termasuk **SECRET_KEY acak baru**. Jangan set `ENV_FILE` di Vercel; environment variables dibaca langsung.
5. Deploy/redeploy. Ganti `base_url` Postman ke URL demo dan jalankan collection.

Aset lokal berada di `public/`: Flask melayaninya saat lokal dan Vercel melayaninya sebagai aset statis. Build/import aplikasi tidak membutuhkan koneksi database. Tabel/data dibuat secara manual, bukan setiap deploy.

## 5. Struktur singkat

```text
app.py               Route HTML/API, CSRF, error handling, serialisasi
config.py            Konfigurasi dari .env / environment Vercel
db.py                Koneksi per request dan query SQL berparameter
validation.py        Validasi bersama dan aturan tanggal/filter
init_db.py           Inisialisasi tabel dan seed manual
database/schema.sql  Tabel officers dan tasks beserta relasinya
templates/           Halaman Jinja2
public/              CSS, JavaScript ringan, favicon
postman/             Collection pengujian API
tests/               Integration test dengan database terpisah
docs/                Konfigurasi DB, jawaban QA, panduan wawancara
```

Relasi: **officers (1) → tasks (N)**. `tasks.officer_id` nullable, foreign key `ON DELETE SET NULL`. `archived_at` memisahkan arsip dari status pengerjaan. Waktu audit disimpan UTC; tenggat berupa DATE tanpa zona waktu.

## 6. Verifikasi otomatis

Dengan MySQL XAMPP aktif dan user lokal memiliki izin membuat database:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tes membuat database `bcm_emir_test_<acak>` dan menghapus database tersebut setelah selesai. Database demo `bcm_emir_todo` tidak dipakai untuk pengujian ini. Jangan jalankan integration test dengan kredensial hosting terbatas.

Tes mencakup persistensi, validasi/rollback logis, filter gabungan, status, arsip/pulih/hapus, petugas, form CSRF, escaping HTML, response error, dan seed yang aman dijalankan ulang. Collection Postman menguji request HTTP dan assertion-nya secara terpisah.

Hasil verifikasi lokal: **16 integration test lolos**, serta **24 request dan 109 assertion collection lolos** menggunakan Newman pada server Flask lokal. Data contoh tetap 3 petugas dan 7 tugas setelah pengujian. Pengujian Vercel dan MySQL hosting masih memerlukan akun serta konfigurasi online kandidat.

## 7. Troubleshooting

| Kendala | Tindakan |
| --- | --- |
| Halaman/API 503 | Nyalakan MySQL, periksa host/port/user/password/nama database, lalu jalankan `init_db.py` |
| `Access denied` / kode 1045 saat init | Sesuaikan username/password `.env` dengan database yang dipakai |
| Database belum ada / kode 1049 | Lokal: gunakan `--create-database`; hosting: gunakan nama yang disediakan panel |
| Tabel belum ada | Jalankan `init_db.py` menggunakan konfigurasi database yang benar |
| Port 5000 dipakai | Hentikan server lama, atau `.\.venv\Scripts\python.exe -m flask --app app run --port 5001`; sesuaikan `base_url` |
| Form 400 setelah restart | Muat ulang form. Token CSRF/sesi lama mungkin tidak cocok; simpan SECRET_KEY tetap di `.env` |
| API 415 | Kirim `Content-Type: application/json`, juga untuk DELETE/archive/restore |
| API 409 saat hapus | Arsipkan tugas dahulu; tugas arsip harus dipulihkan sebelum diedit |
| Hari/tenggat salah di server online | Aplikasi memakai Asia/Jakarta dari `tzdata`; pastikan dependensi terpasang dan format tenggat `YYYY-MM-DD` |
| Koneksi hosting gagal | Gunakan port dari penyedia; periksa izin remote, status layanan, serta pengaturan TLS/CA. Lihat panduan database |
| Perubahan environment Vercel belum berlaku | Buat deployment baru/redeploy setelah menyimpan variabel |

## Dokumentasi lainnya

- [Jawaban soal QA](docs/JAWABAN_QA.md)

Referensi teknologi: [Flask](https://flask.palletsprojects.com/), [MySQL Connector/Python](https://dev.mysql.com/doc/connector-python/en/), [Flask di Vercel](https://vercel.com/docs/frameworks/backend/flask).
