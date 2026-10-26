# 01 — Requirements

Setiap kebutuhan punya ID agar bisa dirujuk dari ROADMAP dan test.

Prioritas:
- **P0**: wajib untuk MVP.
- **P1**: penting, bisa menyusul di akhir MVP.
- **P2**: setelah MVP.

## 1. Kebutuhan Fungsional

### 1.1 Input & Project

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-IN-01 | Pengguna membuat project dengan meng-upload satu file denah: JPEG, PNG, atau PDF (satu halaman dipilih bila multi-halaman). | P0 |
| FR-IN-02 | Pengguna mengisi prompt teks bebas (mis. "data hall, tinggi dinding 4.5 m"). | P0 |
| FR-IN-03 | Pengguna bisa mengisi parameter eksplisit yang menimpa hasil parsing prompt: tinggi dinding default, tinggi pintu default, tebal dinding default, nama lantai, dan skala manual (opsional). | P0 |
| FR-IN-04 | Prompt diurai menjadi parameter terstruktur. Jika Strata tidak tersedia, dipakai parser aturan sederhana (regex angka + satuan) dan nilai default. | P1 |
| FR-IN-05 | Sistem menyimpan file asli tanpa perubahan beserta hash SHA-256-nya. | P0 |
| FR-IN-06 | PDF vektor terdeteksi otomatis. Bila vektor, teks dan path dibaca langsung sebagai input tambahan untuk tahap 2–3. | P2 |

### 1.2 Pipeline Ekstraksi (Tahap 1–5)

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-EX-01 | Preprocess: rasterisasi PDF (300 dpi), grayscale, deskew (≤ ±5°), dan deteksi area gambar (membuang border dan title block). | P0 |
| FR-EX-02 | Deteksi grid struktur: bulatan sumbu beserta labelnya (A–F, 1–3, dst.) dan garis sumbu. | P0 |
| FR-EX-03 | Hitung skala mm/px dari angka dimensi dan jarak grid, dengan cek silang konsistensi (residu ≤ 1%). | P0 |
| FR-EX-04 | Skala manual dari pengguna (bila diisi) selalu menang atas skala hasil hitungan, dengan peringatan bila selisih > 1%. Tanpa skala manual: grid + dimensi, lalu dimensi total. Bila semua gagal, pipeline berhenti dengan status `needs_attention`. | P0 |
| FR-EX-05 | Deteksi dinding, baik dinding solid (poche) maupun dinding garis ganda (hollow). | P0 |
| FR-EX-06 | Deteksi kolom, termasuk simbol kolom baja/H di titik grid. | P0 |
| FR-EX-07 | Deteksi pintu **dari denah**: posisi, lebar, tipe (single, double, sliding, opening tanpa daun), sisi engsel, dan arah buka. | P0 |
| FR-EX-08 | Deteksi jendela pada dinding luar. | P1 |
| FR-EX-09 | Filter anotasi non-arsitektur: jalur kabel, leader teks, garis dimensi, hatching, simbol MEP. | P0 |
| FR-EX-10 | Pembentukan ruang: poligon tertutup, label dari OCR, dan luas dihitung otomatis. | P0 |
| FR-EX-11 | Parameter sweep: minimal 2 strategi dinding × beberapa set parameter. Kandidat dengan skor validator terbaik dipilih. | P0 |
| FR-EX-12 | Style profile: parameter pemenang disimpan dan bisa dipilih sebagai titik awal sweep. | P1 |
| FR-EX-13 | Setiap tahap menyimpan artefak (gambar overlay + JSON) yang bisa dilihat di dashboard. | P0 |
| FR-EX-14 | Validator menghasilkan skor 0–1 dan daftar masalah yang merujuk ID elemen. | P0 |
| FR-EX-15 | Deteksi **tangga**: flight (lebar, jumlah tanjakan, arah naik) dan bordes, lalu disimpan sebagai geometri di `stairs`. | P0 |
| FR-EX-16 | **Kondisi existing**: elemen bertanda PROPOSED/NEW tidak dimodelkan; elemen bertanda dismantle/bongkar tetap dimodelkan. | P0 |
| FR-EX-17 | **Kontur terluar** bangunan mencakup pita luar dan blok sirip; blok kecil dimodelkan sebagai kolom `pilaster`. Luas kotor dihitung dari kontur ini. | P0 |

### 1.3 Review LLM (Tahap 6)

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-LLM-01 | Strata hanya memproses elemen berkeyakinan rendah atau elemen yang ditandai validator. | P0 |
| FR-LLM-02 | Input ke Strata berupa overlay bernomor, crop zoom per elemen, dan fitur numerik dalam teks. | P0 |
| FR-LLM-03 | Output Strata wajib lolos JSON schema. Output tidak valid di-retry maksimal 2 kali, lalu diabaikan. | P0 |
| FR-LLM-04 | Perubahan dilakukan hanya lewat tool spec yang terdaftar (lihat `05-llm-review.md`). | P0 |
| FR-LLM-05 | Gerbang skor: perubahan yang menurunkan skor validator ditolak dan dicatat. | P0 |
| FR-LLM-06 | Self-consistency voting (default 3 suara) untuk tugas klasifikasi. | P1 |
| FR-LLM-07 | Tiap jenis tugas LLM punya flag aktif/nonaktif. Flag hanya boleh aktif jika lolos benchmark. | P0 |
| FR-LLM-08 | Jika Strata tidak tersedia (healthcheck gagal / timeout), tahap 6 ditandai `skipped` dan pipeline lanjut. | P0 |
| FR-LLM-09 | Semua prompt, respons, dan keputusan gerbang tersimpan sebagai transkrip per run. | P0 |
| FR-LLM-10 | Panel chat eskalasi (Tingkat 2). | P2 |

### 1.4 Build & Output (Tahap 7–9)

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-BO-01 | Builder Blender headless membangun shell dari spec: dinding (dengan potongan bukaan), lantai per ruang, slab per massa bangunan, kolom dan pilaster, kusen dan daun pintu parametrik, jendela, serta tangga (anak tangga pejal + bordes). | P0 |
| FR-BO-02 | Objek template di spec ikut ditempatkan di `.blend` dan di export lengkap. | P0 |
| FR-BO-03 | Setiap objek Blender diberi nama sesuai ID spec (`wall_W12`, `door_D3`, `room_R2`, `obj_O5`). Properti `spec_id` dan `spec_type` diekspor sebagai glTF extras. | P0 |
| FR-BO-04 | Output: `layout.blend`, `shell.glb`, `layout_full.glb`, `layout.fbx`, `layout.obj`. | P0 (glb/blend), P1 (fbx/obj) |
| FR-BO-05 | Verifikasi: render top-down ortografik dibandingkan dengan mask dinding denah (IoU), ditambah cek jarak grid. | P0 |
| FR-BO-06 | Dokumen map 3D (HTML + PDF) berisi denah asli, overlay, render isometrik, render per ruang, tabel ruang, jadwal pintu, ringkasan dinding, metadata, dan peringatan. | P0 (HTML), P1 (PDF) |
| FR-BO-07 | Regenerate dari spec versi tertentu menghasilkan output baru tanpa menimpa output versi lama. | P0 |

### 1.5 Web Editor

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-WE-01 | Memuat `shell.glb`, spec, dan library template untuk project dan versi yang dipilih. | P0 |
| FR-WE-02 | Mode tampilan: orbit, top ortografik, dan first-person walk (WASD + mouse). | P0 (orbit/top), P1 (walk) |
| FR-WE-03 | Ukur jarak titik ke titik, dengan snap ke vertex dan edge. | P0 |
| FR-WE-04 | Ukur luas ruang (klik ruang, nilai diambil dari spec) dan luas poligon bebas di lantai. | P0 |
| FR-WE-05 | Ukur tinggi vertikal (lantai ke titik). | P0 |
| FR-WE-06 | Ubah tinggi dinding global atau per dinding, dengan pratinjau langsung. Hasil final didapat setelah regenerate. | P0 |
| FR-WE-07 | Drag & drop template dari library ke lantai, dengan snap grid 600 mm (bisa dimatikan). | P0 |
| FR-WE-08 | Pindah, rotasi (kelipatan 90° dan bebas), dan resize objek sesuai batas di `template.json`. | P0 |
| FR-WE-09 | Panel properti numerik (posisi, rotasi, dimensi dalam mm). | P0 |
| FR-WE-10 | Peringatan tabrakan: objek dengan objek, dan objek dengan dinding atau kolom. | P1 |
| FR-WE-11 | Undo/redo lokal. | P1 |
| FR-WE-12 | Save mengirim daftar operasi ke server dan membuat spec versi baru. Konflik versi ditolak dengan pesan jelas. | P0 |
| FR-WE-13 | Tombol Regenerate memantau status job dan memuat ulang hasilnya. | P0 |
| FR-WE-14 | Pintu bisa dibuka/ditutup dengan klik (animasi rotasi di pivot engsel). | P2 |
| FR-WE-15 | **Panel koreksi geometri** numerik: ubah/tambah/hapus/pisah/gabung dinding, ubah/tambah/hapus pintu dan jendela, ubah/hapus tangga. Pratinjau 2D + validasi langsung; hasil 3D setelah regenerate. | P0 |

### 1.6 Dashboard

| ID | Kebutuhan | Prio |
|---|---|---|
| FR-DB-01 | Halaman daftar project: nama, status, tahap aktif, skor validator, IoU, waktu update. | P0 |
| FR-DB-02 | Form project baru: upload, prompt, parameter. | P0 |
| FR-DB-03 | Detail project: timeline tahap 0–10 dengan status dan durasi. | P0 |
| FR-DB-04 | Log live via SSE, bisa difilter per tahap dan level, dan tetap tersedia setelah run selesai. | P0 |
| FR-DB-05 | Viewer artefak per tahap: overlay, tabel masalah validator, skor kandidat sweep, transkrip Strata. | P0 |
| FR-DB-06 | Tab Editor (web editor tertanam), tab Outputs (unduhan per versi), tab Versions (riwayat spec + diff ringkas). | P0 |
| FR-DB-07 | Aksi: jalankan ulang dari tahap tertentu, batalkan run, regenerate. | P0 |
| FR-DB-08 | Indikator kesehatan: status Strata, status worker Blender, panjang antrean. | P0 |
| FR-DB-09 | Dark mode (Carbon g100) sebagai tema default. | P0 |

## 2. Kebutuhan Non-Fungsional

### 2.1 Akurasi (diukur pada Gatsu terhadap ground truth)

| ID | Metrik | Target MVP |
|---|---|---|
| NFR-AC-01 | Galat skala (mm/px) terhadap nilai sebenarnya | ≤ 0.5% |
| NFR-AC-02 | Galat posisi garis tengah dinding | median ≤ 50 mm, p95 ≤ 150 mm |
| NFR-AC-03 | Recall dinding (panjang dinding GT yang terdeteksi) | ≥ 95% |
| NFR-AC-04 | Presisi dinding (panjang dinding terdeteksi yang benar) | ≥ 95% |
| NFR-AC-05 | Recall pintu | ≥ 90%; lebar pintu ±100 mm |
| NFR-AC-06 | Arah buka dan sisi engsel pintu benar | ≥ 80% |
| NFR-AC-07 | Ruang: jumlah ruang benar dan galat luas per ruang | ≥ 90% ruang cocok; galat luas ≤ 3% |
| NFR-AC-08 | IoU top-down (mask dinding) | ≥ 0.85 |
| NFR-AC-09 | Ekspor 1:1: dimensi di `.glb` sama dengan spec | galat ≤ 1 mm |
| NFR-AC-10 | Tangga: jumlah tanjakan per flight dan arah naik | tanjakan ±1; arah benar 100%; posisi flight ≤ 100 mm |
| NFR-AC-11 | Luas kotor bangunan (termasuk pita luar) | galat ≤ 1% |

Saat ini hanya Gatsu yang tersedia sebagai denah nyata. Ketahanan diukur dengan **set uji turunan Gatsu** (lihat §3 kriteria 2). Target untuk denah nyata lain ditetapkan saat denah dan GT-nya tersedia, dengan target awal 80% dari target Gatsu.

### 2.2 Performa (di Apple M4 16 GB, tanpa waktu Strata)

| ID | Metrik | Target |
|---|---|---|
| NFR-PF-01 | Tahap 1–5 termasuk sweep (≤ 12 kandidat) | ≤ 2 menit |
| NFR-PF-02 | Regenerate (tahap 7–10) untuk shell ≤ 300 dinding + ≤ 500 objek | ≤ 90 detik |
| NFR-PF-03 | Tahap 6 (Strata) | dibatasi ≤ 10 menit per run (konfigurasi) |
| NFR-PF-04 | Web editor: 60 fps orbit untuk shell + 500 objek di laptop iGPU | ≥ 45 fps |
| NFR-PF-05 | Ukuran `shell.glb` untuk satu lantai | ≤ 20 MB |
| NFR-PF-06 | Latensi event log ke dashboard | ≤ 1 detik |

### 2.3 Keandalan & Operasional

| ID | Kebutuhan |
|---|---|
| NFR-RL-01 | Pipeline tetap selesai (dengan peringatan) ketika Strata mati atau timeout. |
| NFR-RL-02 | Run yang gagal bisa dilanjutkan dari tahap terakhir yang sukses, karena artefak tahap disimpan. |
| NFR-RL-03 | Spec bersifat append-only: versi lama tidak pernah ditimpa. |
| NFR-RL-04 | Satu job Blender berjalan pada satu waktu. Job lain mengantre. |
| NFR-RL-05 | Semua event pipeline tercatat di `events.jsonl` per project. |
| NFR-RL-06 | Run yang sama dengan input, parameter, dan versi kode yang sama menghasilkan spec yang identik, dengan pengecualian tahap 6 (LLM). |

### 2.4 Keamanan

| ID | Kebutuhan |
|---|---|
| NFR-SC-01 | MVP hanya diakses dari LAN/VPN internal. |
| NFR-SC-02 | Tidak ada kredensial di repo. `server-info.txt` dan `.env` masuk `.gitignore`. |
| NFR-SC-03 | Upload dibatasi tipe (JPEG/PNG/PDF) dan ukuran (≤ 50 MB). Nama file disanitasi. |
| NFR-SC-04 | Path artefak divalidasi agar tidak keluar dari folder project (anti path traversal). |
| NFR-SC-05 | Builder Blender hanya mengeksekusi script milik repo, tidak pernah kode dari LLM. |

### 2.5 Kompatibilitas

| ID | Kebutuhan |
|---|---|
| NFR-CP-01 | Browser: Chrome/Edge versi terbaru (desktop). Firefox best effort. |
| NFR-CP-02 | Lebar layar minimal 1056 px untuk editor. Dashboard tetap terbaca di 672 px (read-only). |
| NFR-CP-03 | Blender 5.2 LTS (pinned). |
| NFR-CP-04 | `.glb` bisa dibuka di three.js, Blender, dan viewer glTF standar. |

## 3. Kriteria Sukses MVP

MVP dinyatakan selesai bila **semua** kondisi berikut terpenuhi:

1. Gatsu diproses end-to-end dari upload sampai keempat output, tanpa edit manual, dan memenuhi NFR-AC-01 s.d. NFR-AC-11.
2. **Ketahanan pada set uji turunan Gatsu** (hanya satu denah nyata yang tersedia):
   - **Augmentasi** `plan.jpeg` (resolusi 0.6×–2×, kualitas JPEG 40–95, rotasi ±2°, crop margin, sedikit blur/noise): ≥ 80% varian mencapai ≥ 90% target akurasi Gatsu.
   - **Denah sintetis** hasil render dari GT Gatsu yang dimodifikasi (P1, `benchmarks/synth/`): hasilnya dilaporkan, target ≥ 70% varian mencapai ≥ 80% target. Tidak memblokir MVP.
   - Sisa galat Gatsu bisa dikoreksi lewat panel koreksi editor (FR-WE-15) dalam ≤ 15 menit.
3. Di web editor, pengguna bisa mengukur luas ruang dan tinggi dinding, mengubah tinggi dinding, menempatkan dan me-resize ≥ 3 jenis template, mengoreksi satu dinding dan satu pintu lewat panel koreksi, menyimpan, lalu regenerate. Hasilnya muncul di `.blend`, `.glb`, dan dokumen.
4. Dashboard menampilkan progres, log live, artefak, dan versi untuk setiap run.
5. Ketika Strata dimatikan, pipeline tetap selesai dan tahap 6 berstatus `skipped`.
6. Benchmark Strata terdokumentasi. Setiap tugas LLM yang aktif terbukti mengalahkan baseline CV.
