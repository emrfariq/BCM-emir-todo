# Jawaban Soal QA — Validasi Response API di Postman

**Pertanyaan:** Dalam pengujian API menggunakan Postman, apa saja komponen utama yang divalidasi pada response API?

## Jawaban

Saat menguji API menggunakan Postman, komponen utama yang saya validasi adalah:

| Komponen | Hal yang diperiksa | Contoh pada API tugas |
| --- | --- | --- |
| **HTTP status code** | Sesuai hasil operasi dan skenario sukses/gagal pada kontrak API | Create valid `201`, validasi gagal `422`, data tidak ada `404`, delete berhasil `204` |
| **Response headers** | Header dan nilainya sesuai kontrak | `Content-Type: application/json` untuk respons JSON; `Location` menunjuk detail tugas baru pada create |
| **Struktur dan tipe data body** | Field wajib, susunan objek/array, tipe data, dan nullable field | `data` berupa array pada daftar; objek pada detail; `id` angka, `title` string, `is_overdue` boolean, `officer` objek atau null |
| **Kebenaran nilai dan aturan bisnis** | Nilai sesuai request, default, dan aturan aplikasi | Judul sesuai input setelah trim, status awal `pending`, hasil filter benar, tugas selesai tidak ditandai terlambat |
| **Error response** | Kode/pesan jelas, format konsisten, rincian field jika relevan | Judul kosong menghasilkan `error.fields.title`; tidak ada stack trace atau kredensial |
| **Response time** | Waktu respons dibandingkan dengan SLA yang disepakati bila tersedia | Pada soal ini tidak ada SLA, sehingga dicatat sebagai observasi, bukan dipaksakan target tertentu |

Selain memeriksa satu response, saya melakukan **request lanjutan** untuk memastikan perubahan data benar-benar terjadi. Status sukses saja belum cukup membuktikan data tersimpan.

## Contoh skenario

### 1. Membuat tugas dengan input valid

Request `POST /api/tasks` dengan judul dan tenggat valid:
- Status harus **201 Created**.
- Header `Content-Type` berisi `application/json` dan `Location` mengarah ke ID yang baru dibuat.
- Body memiliki ID positif, judul/tenggat sesuai input, status `pending`, serta prioritas sesuai input atau default `medium`.
- Kirim `GET /api/tasks/{id}` dan pastikan data yang dikembalikan sesuai hasil create.

### 2. Input tidak valid

Request dengan judul spasi atau tenggat tidak valid:
- Status **422**, sesuai kontrak aplikasi ini.
- Body memiliki `error.code`, pesan, serta rincian field yang gagal.
- Tidak ada data baru yang dibuat atau perubahan parsial pada tugas lama. Untuk update, verifikasi kembali menggunakan GET.

Skenario lain mencakup JSON rusak (**400**), media type salah (**415**), petugas tidak ada (**422**), dan menghapus tugas yang belum diarsipkan (**409**).

### 3. Mengubah status dan menghapus tugas

- PATCH status `done` harus menghasilkan **200** dengan status terbaru; GET daftar Selesai membuktikan perpindahannya.
- Penghapusan permanen dilakukan setelah tugas diarsipkan.
- DELETE sukses menghasilkan **204 No Content** dengan body kosong. Respons ini **tidak diparse sebagai JSON** dan tidak wajib memiliki header Content-Type JSON.
- GET ID yang sama setelah penghapusan harus menghasilkan **404 Not Found**.

## Contoh assertion Postman

Untuk response create:

```javascript
pm.test('Status 201 Created', () => pm.response.to.have.status(201));
pm.test('Header JSON', () => {
  pm.expect(pm.response.headers.get('Content-Type')).to.include('application/json');
});

const task = pm.response.json().data;
pm.test('ID dan status awal valid', () => {
  pm.expect(task.id).to.be.a('number').and.above(0);
  pm.expect(task.status).to.eql('pending');
});
pm.collectionVariables.set('task_id', task.id);
```

Untuk response delete:

```javascript
pm.test('Delete sukses tanpa body', () => {
  pm.response.to.have.status(204);
  pm.expect(pm.response.text()).to.eql('');
});
```

Collection siap pakai berada di `postman/BCM_Emir_Todo.postman_collection.json`. Variabel `base_url` dapat diganti dari localhost ke URL demo tanpa mengubah request satu per satu.
