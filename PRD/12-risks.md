# 12 — Risiko, Mitigasi & Pertanyaan Terbuka

## 1. Register Risiko

Skala: Kemungkinan (K) dan Dampak (D), masing-masing 1–3. Skor = K × D.

| ID | Risiko | K | D | Skor | Mitigasi | Pemicu pemantauan |
|---|---|---|---|---|---|---|
| R-01 | **Akurasi ekstraksi rendah pada gaya denah yang beragam** | 3 | 3 | 9 | Parameter sweep, dua strategi dinding, grid-first, style profile, koreksi di editor, benchmark per denah | Recall/presisi dinding < 90% pada denah baru |
| R-02 | **Resolusi input rendah.** Gatsu 1600×945 px ≈ 25.85 mm/px, sehingga dinding 150 mm ≈ 6 px dan detail pintu/kolom hanya beberapa piksel. | 3 | 3 | 9 | Upscale 2× untuk deteksi; minta file sumber beresolusi lebih tinggi bila ada; ambang minimal resolusi dengan pesan jelas | Pairing S2 gagal; galat dinding p95 > 150 mm |
| R-03 | **Anotasi MEP dan jalur kabel terdeteksi sebagai dinding** | 3 | 2 | 6 | Masking teks, deteksi hatch, penalti keyakinan, review T1, validator V004/V007 | False positive dinding > 5% |
| R-04 | **OCR salah membaca angka dimensi**, sehingga skala salah | 2 | 3 | 6 | Least squares + RANSAC + cek total; fallback skala manual; tampilkan residu di dashboard | Residu > 0.5%, V013 gagal |
| R-05 | **Deteksi pintu (busur) gagal** pada gambar resolusi rendah atau gaya simbol berbeda | 3 | 2 | 6 | Fallback deteksi celah, review T2, koreksi via ops | Recall pintu < 80% |
| R-06 | **Kualitas Strata IQ2_XS terlalu rendah** untuk tugas vision | 3 | 2 | 6 | Gerbang skor (lantai terjamin), benchmark sebelum aktivasi, crop + bukti teks + voting; usulkan kuantisasi Q4+ atau VLM kecil khusus | Spike: akurasi T1 < baseline |
| R-07 | **Strata tidak tersedia atau GPU berebut** dengan Blender di gspe-ai2 | 2 | 2 | 4 | Tahap 6 `skipped` otomatis; Blender CPU/Workbench di server; antrean satu worker | Healthcheck gagal; render melambat |
| R-08 | **Blender headless di server Linux**: font, GPU, dan dependensi berbeda dari Mac | 2 | 2 | 4 | Docker image di-pin; smoke test builder di CI/image; Workbench sebagai fallback render | Build gagal hanya di server |
| R-09 | **Perubahan API Blender 5.x** (exporter, Boolean, bmesh) | 1 | 2 | 2 | Pin 5.2 LTS; cek versi di `build.py`; test builder | Upgrade Blender |
| R-10 | **Performa web dengan banyak objek** (ratusan rack) | 2 | 2 | 4 | InstancedMesh, tanpa bayangan default, anggaran segitiga template | fps < 45 di laptop uji |
| R-11 | **Template tidak konsisten** (pivot, orientasi, skala) dari alur kerja aset | 2 | 2 | 4 | Kontrak + `validate.py`; template tidak valid disembunyikan | Validasi template gagal |
| R-12 | **Tinggi dinding tidak tersedia di denah 2D** | 3 | 1 | 3 | Default per project dari prompt/form; editable di editor; dicantumkan di dokumen sebagai asumsi | — |
| R-13 | **Bangunan atau struktur terpisah dalam satu denah** (Gatsu: Capasitor Room di luar grid F), serta area luar ruang | 2 | 2 | 4 | Kontur luar terpisah di tahap 4; tipe `outdoor`; uji khusus pada Gatsu | Ruang hilang atau menyatu |
| R-14 | **Lisensi PyMuPDF (AGPL)** | 1 | 2 | 2 | Pemakaian internal di server sendiri umumnya aman; konfirmasi ke legal; alternatif pdf2image/poppler (GPL, proses terpisah) atau pypdfium2 (BSD/Apache) | Rencana distribusi ke luar |
| R-15 | **Keamanan**: `server-info.txt` berisi password plaintext; API tanpa autentikasi | 2 | 3 | 6 | `.gitignore`; pindahkan kredensial ke password manager; ganti password yang sudah tersebar; batasi akses API ke LAN/VPN; autentikasi di backlog | File muncul di repo/commit |
| R-16 | **Scope creep** (interior, MEP, multi-lantai, fotorealisme) | 2 | 2 | 4 | Non-goals eksplisit di `00-overview.md`; backlog pasca-MVP di ROADMAP | Permintaan fitur di luar milestone |
| R-17 | **Ground truth Gatsu memakan waktu atau tidak akurat** | 2 | 3 | 6 | Alat bantu GT (snap grid, overlay); verifikasi silang dengan render top-down; review oleh orang kedua | GT direvisi berulang |
| R-18 | **Dinding non-ortogonal atau lengkung** di denah lain | 2 | 2 | 4 | Segmen miring disimpan terpisah, V006 hanya warning; lengkung didekati segmen; tandai di dokumen | Denah uji dengan dinding miring |
| R-19 | **Hanya satu denah nyata (Gatsu).** Ekstraktor bisa overfit ke gaya Gatsu; klaim "adaptive" belum terbukti. Denah sintetis dibuat dari asumsi kita sendiri, jadi hanya menguji ketahanan, bukan keragaman gaya nyata. | 3 | 3 | 9 | Larangan hardcode per denah (review kode); parameter lewat sweep/profile; set augmentasi + sintetis; panel koreksi sebagai jalan keluar; minta denah baru sesegera mungkin dan jalankan benchmark saat datang | Denah nyata pertama di luar Gatsu gagal > 30% metrik |
| R-20 | **Tangga salah arah atau jumlah tanjakan** (pola garis rapat mirip hatching/partisi) | 2 | 2 | 4 | `stair_mask` sebelum dinding; V019; tombol "Balik arah" di panel koreksi | NFR-AC-10 gagal di Gatsu |

## 2. Asumsi

1. Denah memiliki **grid struktur berlabel dan angka dimensi**. Ini lazim pada gambar kerja data center. Tanpa grid, dibutuhkan skala manual.
2. Satu file denah = satu lantai = satu project.
3. Denah tidak diputar lebih dari 5° dan tidak terdistorsi perspektif.
4. Pengguna mengakses dari LAN/VPN internal dengan browser desktop modern.
5. Template aset tersedia dari alur kerja terpisah. Sampai alur kerja itu siap, dipakai template placeholder.
6. Volume awal: puluhan denah, bukan ribuan. Satu worker Blender cukup.

## 3. Pertanyaan Terbuka

| # | Pertanyaan | Mengapa penting | Default bila belum dijawab |
|---|---|---|---|
| Q-01 | Berapa tinggi dinding default per tipe site (data hall dengan raised floor vs. ruang kantor)? | Memengaruhi semua output 3D | 3000 mm; dapat diubah per project |
| Q-02 | Apakah raised floor dan plafon perlu dimodelkan (tinggi lantai jadi ≠ slab)? | Mengubah z = 0 dan tinggi bersih | Tidak (non-goal MVP) |
| Q-03 | ~~Berapa banyak denah uji tersedia?~~ **Terjawab 2026-10-26:** hanya Gatsu (gambar). Ketahanan diuji dengan augmentasi + denah sintetis (R-19). | — | — |
| Q-04 | Apakah kuantisasi Strata bisa dinaikkan (Q4+), atau bisa ditambah VLM kecil khusus vision di server yang sama? | Menaikkan langit-langit kualitas tahap 6 | Tetap IQ2_XS |
| Q-05 | Apakah perlu autentikasi atau pembatasan per pengguna sebelum dipakai lebih luas? | Keamanan dan audit trail | Tidak di MVP |
| Q-06 | Apakah dokumen map 3D punya format atau kop perusahaan yang harus diikuti? | Template laporan | Format netral Carbon light |
| Q-07 | ~~Apakah pintu perlu bisa diedit di web editor?~~ **Terjawab 2026-10-26:** ya, dinding/pintu/tangga lewat panel koreksi numerik (FR-WE-15). | — | — |
| Q-08 | Apakah file sumber beresolusi lebih tinggi (PDF asli export CAD) bisa diminta untuk Gatsu? | R-02: akurasi | Pakai `plan.jpeg` 1600 px |
| Q-09 | Apakah output perlu format lain (IFC, DWG/DXF 2D dari spec)? | Interoperabilitas dengan tim arsitek/MEP | Tidak di MVP (backlog) |
| Q-10 | Apakah ada aturan penamaan rack/aisle standar perusahaan untuk label objek? | Label di editor dan dokumen | Bebas |
