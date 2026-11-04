# Floorplan3D

Mengubah denah 2D (gambar atau PDF) menjadi model 3D berskala 1:1: `.blend`, `.glb`, `.fbx`, `.obj`, render, dan dokumen.

Pipeline otomatis membaca grid, skala, dinding, pintu, kolom, tangga, dan ruang (tahap 0–5). Setelah itu pipeline berhenti untuk **review manusia** di editor web. Setelah disetujui, pipeline membangun 3D di Blender dan memverifikasinya (tahap 6–10).

Dokumen produk ada di `PRD/`, rencana dan status milestone di `ROADMAP.md`, dan keputusan benchmark di `benchmarks/DECISIONS.md`.

Untuk agent dan pengembang: `AGENTS.md` (aturan dan konvensi), `WORKFLOW.md` (alur aplikasi dan alur kerja), `CHANGELOG.md` (yang sudah selesai), `todo.md` (tugas yang sedang dikerjakan).

## Kebutuhan

| Komponen | Versi | Catatan |
|---|---|---|
| Python | 3.12 | lewat [uv](https://docs.astral.sh/uv/) |
| Node.js | 20+ | untuk web (`web/`) |
| Blender | 5.2 LTS | `BLENDER_BIN` harus path biner asli, bukan symlink Homebrew |
| Pango (macOS) | Homebrew | untuk PDF laporan (WeasyPrint) |
| Strata (opsional) | server OpenAI-compatible | review LLM tahap 0 dan 6; pipeline tetap jalan tanpa Strata |

## Setup

```bash
uv sync
cd web && npm install && cd ..
cp .env.example .env    # lalu isi nilainya (lihat di bawah)
```

Isi `.env`. File ini di-gitignore, jangan di-commit.

| Kunci | Isi |
|---|---|
| `DATA_DIR` | folder data (project, run, spec, output), mis. `./data` |
| `BLENDER_BIN` | mis. `/Applications/Blender.app/Contents/MacOS/Blender` |
| `BLENDER_RENDER_DEVICE` | `CPU` atau `GPU` |
| `STRATA_BASE_URL`, `STRATA_MODEL` | URL `/v1` dan ID model server Strata (untuk server DGX kantor, ambil dari dokumentasi API DGX internal) |
| `STRATA_API_KEY` | bearer key server Strata, bila servernya mewajibkan (DGX: wajib) |
| `LLM_TASKS_ENABLED` | tugas LLM aktif, saat ini `T0,T3` (lihat `benchmarks/DECISIONS.md`) |
| `DYLD_FALLBACK_LIBRARY_PATH` | macOS: `/opt/homebrew/lib` untuk WeasyPrint |

## Menjalankan aplikasi

Dua terminal:

```bash
# 1: API + pipeline (port 8000)
uv run --env-file .env uvicorn server.app:app --port 8000

# 2: web (port 5173, /api diteruskan ke 8000)
cd web && npm run dev
```

Buka <http://localhost:5173>.

## Alur penggunaan (E2E)

1. **Project baru.** Upload denah, isi prompt (opsional, mis. "tinggi dinding 4.5 m, pintu 2.4 m"), lalu "Mulai pipeline". Toggle "Berhenti untuk review sebelum build 3D" menyala secara default.
   - **PDF multi-halaman** (set gambar CAD dari PM): thumbnail semua halaman tampil, klik halaman denahnya. Satu halaman = satu project. Foto lapangan yang ditempel di denah, bingkai lembar, dan title block dibuang otomatis.
   - **Skala:** dihitung dari dimensi grid bila ada. Denah tanpa dimensi (`SCALE: NTS`) memakai busur pintu dengan **lebar pintu standar** 800 mm, dengan peringatan di tahap 2. Bila ukurannya meleset, ubah "Lebar pintu standar (mm)" (Parameter lanjutan, atau tombol **Ubah lebar pintu** di tahap 2). Lebar pintu yang diisi selalu dipakai, juga bila ada dimensi grid.
   - Cable tray yang tergambar (pola tangga) tidak dibaca sebagai dinding atau kolom.
   - **Jalur vektor (eksperimen):** untuk PDF CAD, toggle di bawah file membaca dinding langsung dari garis PDF dan menelusuri ruang satu per satu. Ruang yang tidak menutup muncul sebagai tugas **Ruang terbuka**. Default tetap jalur raster.
2. **Tunggu tahap 0–5.** Gatsu butuh sekitar 2 menit. Status menjadi **Perlu review**. Bila skor validator terlalu rendah, statusnya **Perlu perhatian**; "Lanjutkan tetap" di tahap 5 melanjutkan tanpa kanvas review.
3. **Buka review.** Di tab Pipeline, buka tahap 5, lalu klik "Buka review". Kanvas review 2D menampilkan hasil ekstraksi di atas gambar asli. Kerjakan daftar **Tugas review** di panel kiri:
   - **Celah terbuka:** klik tugas, lalu klik kedua titik kuning atau tombol "Tutup celah". Centang "Pasang pintu" bila celah itu pintu.
   - **Ruang bocor dan dinding hilang:** pakai Garis bantu (`L`). Tarik garis kasar di atas dinding yang hilang, dan sistem menempelkannya ke garis di gambar. Bila tidak ada garis yang bisa ditempeli, pakai Dinding baru (`W`): klik, klik, berantai, lalu `Esc` untuk berhenti.
   - **Dinding lepas atau palsu:** klik dinding (atau tarik kotak / Shift-klik untuk banyak), lalu tekan `Delete`/`Backspace`. `Ctrl+Z` membatalkan. Untuk mencatat alasan, pakai "Hapus dinding" / "Hapus N dinding" di panel kanan.
   - **Pintu:** pintu digambar oranye, jendela biru. Alat Pintu (`D`): tarik garis dari kusen ke kusen. Di sepanjang dinding, garis itu jadi pintu selebar garis; di atas pintu yang ada, pintu itu dipindah/diubah lebarnya; di celah tanpa dinding, dibuat dinding baru berisi pintu. Klik saja memasang pintu 900 mm. Tipe (`double_swing` untuk pintu ganda), engsel, dan arah buka diubah di panel kanan setelah pintu diklik.
   - **Tangga:** digambar kuning bergaris per anak tangga. Klik untuk mengubah jumlah anak tangga, lebar, atau arah naik. Tangga baru ditambahkan lewat Perbaiki area (`A`).
   - **Tipe ruang:** klik ruang, lalu pilih tipe. Untuk banyak ruang sekaligus, pakai Shift-klik, lalu "Tipe semua ruang".
   - **Perbaiki area dengan prompt (`A`, perlu Strata):** tarik kotak di sekitar area yang salah, lalu tulis instruksi di panel kanan, misalnya "gabungkan dinding dobel", "hapus ini" (pilih dulu dindingnya dengan `V`), "tambah pintu di sini", "sambung sudut W12 ke W13", "ini ruang tangga", "tambah tangga di sini" (tangga yang tergambar dibaca dari gambar; di ruang kosong tangga dirancang muat di ruang, lurus atau U, kuning), "hapus tangga di ruangan ini". Progres tampil di chat (20–40 detik per usulan). Strata bertanya balik bila instruksinya ambigu. Usulan tampil di kanvas: merah dihapus, hijau baru dan menempel ke gambar, kuning baru tapi tidak menempel (periksa posisinya). **Terima** memasukkan usulan ke perubahan yang belum disimpan (satu langkah `Ctrl+Z`), **Tolak** membuangnya. Membalas usulan tanpa Terima/Tolak (misalnya "W901 jangan dihapus, sisanya benar") berarti revisi: Strata mengirim usulan lengkap yang baru.
   - **Isi ruang (generate interior, alat `A` di mode Instalasi & Interior):**
     - **Ruang kosong:** tandai ruang dan tulis "isi ruang ini". Strata bertanya dulu: perangkat apa, berapa rack, containment, CRAC atau in-row cooler. Setelah dijawab, sistem menempatkannya menurut aturan TIA-942/ASHRAE di `core/interior/rules.yaml`:
       - hot/cold aisle 1200/1000 mm, grid 600 mm;
       - jarak ujung baris 1200 mm, jalur pintu dikosongkan;
       - CRAC di dinding ujung baris, containment di atas cold aisle;
       - panel FM-200 dan reader di samping pintu, CCTV di sudut, tabung pemadam per 50 m².
     - **Ruang dengan perangkat tergambar:** klik kotaknya di gambar (jadi `K1`, `K2`, …; Shift-tarik untuk menyesuaikan kotak ke garis), lalu sebut isinya: "K1 itu panel MDB", "K2 baris rack 42U". Posisi dan ukuran diambil dari gambar, dan kotak panjang dipecah jadi satu baris.
     - **Pratinjau:** kuning untuk penempatan dari aturan, hijau untuk penempatan dari gambar, dengan garis arah depan.
     - **Kapasitas:** kalau target tidak muat, chat menyebut kapasitasnya, misalnya "muat 14 dari 16 rack".
     - **Kalibrasi:** aturan per perusahaan atau klien cukup diubah di file `rules.yaml`. Bila denah diedit manual setelah usulan muncul, Terima menolak dengan "usulan usang, kirim ulang". Log sesi ada di `data/projects/<id>/assist/`.
4. **Setujui.** Klik "Setujui & build 3D". Koreksi disimpan sebagai versi spec baru, lalu tahap 6–10 berjalan. Tugas yang belum selesai tercatat di run sebagai `review_open`. Review juga bisa dibatalkan ("Batalkan review"), dan run itu tidak dibangun.
5. **Hasil.** Tab Outputs berisi unduhan model, render, dan dokumen. Tab Versions menyimpan riwayat spec, dan versi mana pun bisa di-regenerate.
6. **Edit lanjutan.** Tab Editor berisi editor 3D (Orbit/Top/Walk) dan editor 2D (Plan 2D). Setelah Save, klik Regenerate untuk membangun ulang.

### Instalasi & Interior: semua perangkat (rack, CRAC, UPS, panel, tray)

Mode **Layout** berisi arsitektur saja (dinding, bukaan, ruang, tangga, kolom). Semua perangkat ada di mode **Instalasi & Interior** (toggle di atas editor). Mode ini tersedia begitu layout punya spec, dan saat pertama dibuka:

- dokumen instalasinya dibuat otomatis;
- objek lama di layout dipindah ke sini sekali (posisi sama; yang sudah ada di instalasi tidak digandakan);
- instalasi otomatis pindah ke versi layout terbaru.

Tinggi plafon dan raised floor diatur di panel Instalasi, atau lewat **Mulai instalasi** di halaman project. Layout tampil, tapi terkunci.

0. **Perangkat:**
   - seret kartu dari **Library** (panel kiri) ke kanvas;
   - klik untuk memilih, seret untuk menggeser, `R` untuk memutar 90°;
   - posisi X/Y/Z, rotasi, dan ukuran diisi angka di panel kanan. Perangkat dinding (panel FM-200, VESDA, CCTV, reader) diberi Z.

   **Isi ruang (`A`)**: tandai ruang atau klik kotak perangkat di gambar (`K1`…), lalu tulis instruksi (lihat Isi ruang di atas).

1. **Rack (`K`):** klik di dalam kotak rack di denah: kotak bergaris maupun gelap/berarsir berisi teks. Ukuran dan arah diambil dari kotak, dan template dipilih otomatis. Kalau klik tidak menemukan kotak, **Shift-tarik** kotak rack sendiri: sisi-sisinya menempel ke garis gambar terdekat (±120 mm).
2. **Tray (`T`):** pilih Data atau Power, klik titik-titik di sepanjang pita tray di denah, lalu Enter. Jalur menempel ke pita, dan lebarnya dibulatkan ke ukuran standar. Kalau tidak ada pita, jalur dipakai seperti digambar.
3. **Drop:** drop ke rack terdekat (≤ 1.5 m) muncul otomatis.
4. **Cek panel kanan:** Properti, Masalah (I001–I010; I009 perangkat di luar ruang atau menabrak dinding, I010 perangkat tumpang tindih), dan Panjang tray per kelas.
5. **Save** (`Ctrl+S`). Hapus tray atau rack wajib diberi alasan.

Kalau layout diubah, instalasi menyusul sendiri saat mode Instalasi & Interior dibuka atau saat Build 3D. Masalah baru, misalnya tray menembus dinding baru, tampil di panel Masalah. Tombol **Rebase** hanya muncul kalau ada perubahan instalasi yang belum disimpan: Save dulu.

**Build 3D instalasi:** setelah Save, klik **Build 3D**. Run "Instalasi" (tahap 7–10, terlihat di tab Pipeline) membangun tray perforated, hanger atau pedestal, drop ke rack, plafon, raised floor, dan sleeve di dinding.
- **Output** ada di `installation_outputs/v<M>/`: `installation.glb`, `layout_installation.glb`, render, dan laporan panjang tray. Output layout tidak berubah.
- **Tampilan 3D:** tombol **3D** di toolbar instalasi, dengan layer Tray data, Tray power, Hanger, Drop, Rack, Plafon, dan Raised floor.
- **Layar penuh:** `F`.
- **Render** memakai EEVEE (`BLENDER_INSTALL_ENGINE`) supaya perforasi terlihat. Di server tanpa GPU, set `BLENDER_INSTALL_ENGINE=BLENDER_WORKBENCH`.

Panduan sesi koreksi berwaktu (untuk kriteria MVP "koreksi ≤ 15 menit") ada di `docs/calibration-correction.md`.

## Template objek

Library berisi 27 perangkat ruang teknis sebagai model low-poly prosedural: rack 42U/48U, rack jaringan 2 tiang, CRAC,
in-row cooler, unit AHU, UPS, ATS, STS, panel MDB, trafo kering, genset, battery rack, kabinet baterai, PDU, tabung
pemadam, bank tabung FM-200, panel kontrol FM-200, panel VESDA, panel alarm kebakaran, kamera CCTV, reader akses, panel
atap dan pintu cold-aisle containment, meja NOC, kursi, dan lemari suku cadang. Panel FM-200, VESDA, alarm kebakaran,
CCTV, dan reader dipasang di dinding (posisi z objek).
Model dibangun prosedural (`core/templates/lowpoly.py`, lisensi milik project). Bangun ulang ke `DATA_DIR` setelah modelnya
diubah:

```bash
uv run --env-file .env python -m core.templates.make_placeholders --out data/templates
```

Versi template naik setiap kali modelnya berubah (sekarang 1.1.0). Objek yang sudah ditempatkan tetap memakai versinya;
objek baru memakai versi terbaru.

## CLI (tanpa server)

```bash
uv run --env-file .env python -m core.cli build <spec.json> <out_dir> [--image denah.jpg] [--templates data/templates]
```

Perintah ini menjalankan tahap 7–9 (build, verifikasi, laporan) dari sebuah spec.

## Tes dan benchmark

```bash
uv run --env-file .env pytest -q -m "not strata"        # Python (tes Blender butuh BLENDER_BIN dan GPU/akses layar)
uv run ruff check core server benchmarks tests
cd web && npx vitest run && npm run lint && npm run build

uv run --env-file .env python -m benchmarks.failure_modes --fresh --out benchmarks/reports/<nama>   # Gatsu
uv run --env-file .env python -m benchmarks.run_augment_bench --fresh --out benchmarks/reports/<nama>   # 30 varian
uv run --env-file .env python -m benchmarks.run_synth_bench --out benchmarks/reports/<nama>   # 20 denah sintetis
```

## Data dan backup

Semua state ada di `DATA_DIR`:
- `projects/<id>/`: input, run (artefak tiap tahap), spec bervalidasi per versi, dan output;
- `templates/`: template objek;
- `profiles/`: profil parameter ekstraksi.

Backup cukup dengan menyalin `DATA_DIR` saat server berhenti. Server menolak start bila server lain memakai `DATA_DIR` yang sama.

## Troubleshooting

| Gejala | Penyebab dan solusi |
|---|---|
| Blender keluar dengan "Bundled Python not found" | `BLENDER_BIN` menunjuk symlink Homebrew; pakai path biner di dalam `Blender.app` |
| Render atau build Blender abort (`SIGABRT`, rc 134) | proses tidak punya akses GPU atau sesi layar (mis. dari job background atau SSH tanpa sesi login). Jalankan dari Terminal di sesi login, atau set `BLENDER_RENDER_DEVICE=CPU` |
| Strata "401 Unauthorized" | `STRATA_API_KEY` kosong atau salah |
| Strata mati | tahap 6 dilewati, dan pipeline tetap selesai (status Strata terlihat di header) |
| Status tidak pernah "Perlu review" | project dibuat dengan toggle review dimatikan (`review_pause: false`), atau skor tahap 5 terlalu rendah sehingga run berhenti di "Perlu perhatian" |
| Tahap 8 "Perlu perhatian": kecocokan gambar di bawah 0.90 | sebagian besar dinding tidak berada di atas garis denah: skala atau posisi model salah. Cek skala di tahap 2. Dinding yang tidak di atas garis gambar disebut per ID di peringatan tahap 8. IoU ke mask ekstraksi hanya info: angkanya wajar turun setelah review |
| Garis bantu: "Tidak ada garis ganda di dekat garis ini" | tarik garis dalam ±250 mm dari garis di gambar, atau pakai Dinding baru |
| PDF laporan gagal di macOS | `brew install pango` dan set `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` |

## Deploy

Satu image Docker berisi API, pipeline, Blender 5.2 (CPU, headless), dan dashboard yang sudah dibuild. Satu port saja: <http://host:8000>.

```bash
# dari root repo; .env dibaca saat run, tidak masuk image
docker compose -f docker/compose.yaml up -d --build
docker compose -f docker/compose.yaml logs -f

# sekali saja di DATA_DIR baru (dan setelah model low-poly berubah): buat template objek
docker compose -f docker/compose.yaml run --rm floorplan3d python -m core.templates.make_placeholders --out /data/templates
```

- **Data:** `DATA_DIR` host di-mount ke `/data` (default `./data`; ganti dengan `FLOORPLAN_DATA_DIR=/path`). Port host diganti dengan `FLOORPLAN_PORT`.
- **Path di container** menimpa nilai dev di `.env`: `DATA_DIR=/data`, `BLENDER_BIN=/opt/blender/blender`, `BLENDER_RENDER_DEVICE=CPU`.
- **Strata:** `STRATA_*` diambil dari `.env`. Bila Strata jalan di host yang sama, pakai `STRATA_BASE_URL=http://host.docker.internal:<port>/v1`.
- **Versi Blender:** dikunci lewat build arg `BLENDER_VERSION` (default `5.2.2`). Blender hanya tersedia untuk linux-x64, jadi di Mac Apple Silicon image berjalan teremulasi dan lebih lambat.

Deploy ke gspe-ai2 (milestone M7c) menunggu SSH key di server. Lihat `ROADMAP.md`.
