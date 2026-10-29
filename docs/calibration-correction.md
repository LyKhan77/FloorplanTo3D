# Kalibrasi menit koreksi (sesi editor berwaktu)

Menit koreksi di `benchmarks/correction_effort.py` berasal dari model detik per operasi (`SECONDS` untuk kerja satu-per-satu, `BULK_SECONDS` untuk aksi massal M7a-3). Model ini belum diukur pada orang sungguhan. Kriteria MVP #2 ("sisa galat Gatsu terkoreksi lewat panel koreksi ≤ 15 menit") baru dianggap terpenuhi setelah satu sesi berwaktu memastikan angkanya.

## Persiapan

1. Jalankan server (`uvicorn server.app:app --port 8000`) dan web (`cd web && npm run dev`).
2. Buat project baru dari `floorplan/plan.jpeg` dengan "Berhenti untuk review sebelum build 3D" menyala (default), lalu tunggu status **Perlu review**. Jangan memakai project lama; spec awalnya harus hasil kode saat ini.
3. Siapkan pembanding:
   - `benchmarks/reports/m7a3-gatsu.png` (overlay GT vs prediksi);
   - `benchmarks/gatsu/gt_spec.json` (GT).
4. Siapkan stopwatch dengan lap, dan lembar pencatatan di bawah.

## Sesi

1. Di tab Pipeline, buka tahap 5, lalu klik **Buka review**. Kanvas review 2D (mode Plan 2D) tampil dengan gambar asli di bawahnya. Mulai stopwatch.
2. Koreksi dengan urutan daftar **Tugas review** (panel kiri), dan catat lap setiap kali jenis pekerjaan berganti:
   1. **Celah terbuka:** klik tugas, lalu klik kedua titik kuning (atau tombol "Tutup celah"). "Pasang pintu" menyala bila celah itu memang pintu;
   2. **Ruang bocor dan dinding yang hilang:** alat Garis bantu, lalu tarik garis kasar di atas dinding yang hilang (≤ 250 mm dari garis di gambar). Sistem menempelkannya ke garis ganda, atau ke garis tunggal dengan tebal default. Dinding yang tidak terlihat di gambar digambar dengan "Klik dua titik" berantai seperti sebelumnya;
   3. **Dinding lepas dan dinding palsu:** marquee atau Shift-klik, lalu "Hapus N dinding" dengan satu alasan;
   3. **Pintu:** tambah, hapus, atau atur tipe dan arah;
   4. **Simpan:** ruang dibentuk ulang langsung di kanvas; Simpan membuat versi baru;
   5. **Tipe ruang:** Shift-klik beberapa ruang bertipe sama, lalu pilih "Tipe semua ruang";
   6. **Nama ruang dan tangga.**
3. Hentikan stopwatch bila kedua syarat ini terpenuhi:
   - skor validator setelah Save setara dengan GT (tidak ada error);
   - cek visual terhadap overlay tidak menemukan dinding, pintu, atau ruang yang masih salah.
4. Simpan versi akhir, catat nomor versinya, lalu klik **Setujui & build 3D**.

## Lembar pencatatan

| Jenis pekerjaan | Jumlah elemen | Jumlah aksi (klik tombol aksi) | Menit (lap) |
|---|---|---|---|
| Hapus dinding (`delete_wall`) | | | |
| Tutup celah (`gap_closures`) | | | |
| Garis bantu (`add_wall` via snap) | | | |
| Tambah dinding manual (`add_wall`) | | | |
| Pintu: tambah, hapus, atur (`add_opening`, `delete_opening`, `set_door`) | | | |
| Tipe ruang (`set_room_type`) | | jumlah tipe berbeda | |
| Nama ruang (`rename_room`) | | | |
| Tangga (`set_stair`) | | | |
| **Total** | | | |

Catat juga:
- versi spec awal dan akhir;
- siapa yang mengoreksi, dan apakah orang itu sudah pernah memakai editor;
- hambatan yang memakan waktu di luar operasi (misalnya mencari elemen kecil, atau zoom).

## Memperbarui model

Hitung detik per elemen dan per aksi dari lembar, lalu perbarui konstanta di `benchmarks/correction_effort.py`:

- **`BULK_SECONDS["select"]`** = (menit hapus dinding × 60 − jumlah aksi hapus × `BULK_SECONDS["action"]`) / jumlah dinding dihapus. Bila hanya ada satu aksi, pakai `action` = 10 dan hitung `select` dari sisanya.
- **`BULK_SECONDS["add_wall"]`** = menit tambah dinding manual × 60 / jumlah dinding ditambah.
- **`REVIEW_SECONDS["gap"]`** dan **`REVIEW_SECONDS["guide_line"]`** = menit lap masing-masing × 60 / jumlah aksi.
- **Tipe ruang:** pakai rumus yang sama dengan hapus dinding, dengan jumlah tipe berbeda sebagai jumlah aksi.
- **`SECONDS`** untuk pintu, nama ruang, dan tangga = menit × 60 / jumlah elemen.

Setelah memperbarui:
1. Jalankan `uv run --env-file .env python -m benchmarks.failure_modes --fresh --cache <folder baru> --out benchmarks/reports/<nama>`. Pakai `--cache` ke folder baru: tanpa `--cache`, `--fresh` tidak menjalankan ulang stage.
2. Bandingkan `minutes_bulk` dengan menit stopwatch. Bila selisihnya lebih dari 20 %, catat penyebabnya di `benchmarks/DECISIONS.md`.
3. Perbarui test `test_time_model` di `tests/benchmarks/test_correction_effort.py` dengan konstanta baru.
