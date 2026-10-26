# ROADMAP — Floorplan 2D → 3D Pipeline (MVP)

> Versi 1.1 · 2026-10-26 · Acuan: `PRD/` · Kasus utama: MSC Gatsu Lantai 1

## 1. Strategi Urutan

Prinsip urutan: **risiko terbesar (ekstraksi dari gambar) tidak boleh menghambat bagian lain.**

1. **Spec + ground truth Gatsu dibuat lebih dulu.** GT berfungsi sebagai data uji untuk builder dan editor, sekaligus patokan akurasi ekstraksi.
2. **Builder, server/dashboard, dan editor dibangun di atas GT.** Produk bisa didemokan end-to-end (impor spec → 3D → edit → regenerate) sebelum ekstraksi otomatis selesai.
3. **Ekstraksi CV dikerjakan sesudahnya**, diukur langsung terhadap GT.
4. **Strata diaktifkan terakhir**, hanya untuk tugas yang lolos benchmark.
5. **Ketahanan dan deploy.** Hanya Gatsu yang tersedia, jadi ketahanan dibuktikan dengan varian augmentasi dan denah sintetis turunan Gatsu. Denah nyata baru langsung masuk benchmark begitu tersedia.

```
M0 Fondasi & Spike
  └─► M1 Spec & GT Gatsu
        ├─► M2 Builder & Outputs ─┬─► M3 Server & Dashboard ─► M4 Web Editor ──┐
        │                         │                                            │
        └─► M5 Ekstraksi CV ──────┴──────────────────────────► M6 Strata ──────┴─► M7 Ketahanan & Deploy
```

**Jalur kritis (1 developer):** M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7.
**Dengan 2 developer:**
- **Track A** (CV/backend): M1 → M2 → M5 → M6.
- **Track B** (web): M3 (mulai dari mock API setelah M1) → M4.
- Keduanya bertemu di M7.

## 2. Ringkasan Milestone

| # | Milestone | Hasil utama | Estimasi (hari kerja, 1 dev) | Demo |
|---|---|---|---|---|
| M0 | Fondasi & Spike | Repo siap; Blender, OCR, dan Strata terbukti jalan | 3 | — |
| M1 | Spec & Ground Truth Gatsu | Skema spec (termasuk tangga), ops, validator, GT Gatsu terverifikasi | 5 | Overlay GT di atas denah |
| M2 | Builder & Outputs | GT menjadi `.blend`/`.glb`/`.fbx`/`.obj` + dokumen map | 7 | **Demo 1**: model 3D 1:1 Gatsu + dokumen |
| M3 | Server & Dashboard | API, orchestrator, SSE, dashboard g100 | 6 | Dashboard: impor spec → regenerate → log live → unduh |
| M4 | Web Editor | Ukur, tinggi dinding, drag & drop, resize, panel koreksi, save, regenerate | 11 | **Demo 2**: editor interaktif Gatsu |
| M5 | Ekstraksi CV | Tahap 0–5 otomatis (termasuk tangga, kondisi existing) + benchmark terhadap GT | 13 | **Demo 3**: upload `plan.jpeg` → 3D otomatis |
| M6 | Strata Review | Tahap 6 dengan gerbang + benchmark LLM | 6 | Tab Review dengan keputusan Strata |
| M7 | Ketahanan & Deploy | Set augmentasi + denah sintetis, style profile, Docker di gspe-ai2 | 7 | **Demo MVP** |
| | **Total** | | **58 hari ≈ 12 minggu** (1 dev) · **≈ 8 minggu** (2 dev) | |

Estimasi sudah termasuk test dan dokumentasi per milestone, dan belum termasuk buffer. Tambahkan buffer **20%** untuk M5 dan M7 karena ketidakpastiannya tertinggi.

---

## M0 — Fondasi & Spike (3 hari)

**Tujuan:** memastikan semua komponen dasar bisa jalan di Mac M4, dan mengukur kemampuan nyata Strata sedini mungkin.

### Tugas
- [ ] Inisialisasi git repo. Isi `.gitignore`: `data/`, `.env`, **`server-info.txt`**, `.venv/`, `node_modules/`, `web/dist/`.
- [ ] **Keamanan:** pindahkan kredensial di `server-info.txt` ke password manager, dan pertimbangkan mengganti password yang sudah tersebar (R-15).
- [ ] `uv python install 3.12`, `pyproject.toml`, struktur folder sesuai `11-tech-stack.md` §3, ruff, pytest.
- [ ] `.env.example` dengan semua variabel dari `02-architecture.md` §7.
- [ ] **Smoke test Blender:** `builder/build.py` versi minimal (satu kubus + custom property), lalu export `.glb` dengan extras. Cek extras terbaca dengan pygltflib.
- [ ] **Smoke test OCR:** RapidOCR pada `floorplan/plan.jpeg`. Harus terbaca: label grid A–F dan 1–3, angka 6000/4000/28000/12000, serta label ruang (R. MEETING, GUDANG, BATTERY ROOM, …).
- [ ] **Smoke test WeasyPrint** (`brew install pango` bila perlu).
- [ ] Inisialisasi `web/` (Vite + React + TS + `@carbon/react` g100 + R3F): halaman kosong dengan tema gelap dan satu kubus three.js.
- [ ] **Spike Strata** (`05-llm-review.md` §8), dengan syarat Strata dinyalakan:
  - [ ] Siapkan 20 crop Gatsu berlabel manual.
  - [ ] Uji T1/T2 dalam 4 varian: ± bukti teks, ± few-shot.
  - [ ] Ukur akurasi, latensi, tingkat JSON invalid, dan apakah server memperkecil gambar.
  - [ ] Tulis laporan `benchmarks/reports/spike-strata.md`.

### Kriteria selesai
- `uv run pytest` hijau. `npm run dev` menampilkan halaman g100 dengan kubus 3D.
- Blender headless menghasilkan `.glb` dengan extras yang terbaca.
- OCR membaca ≥ 90% label grid dan angka dimensi Gatsu.
- Laporan spike Strata ada. Bila Strata belum bisa dinyalakan, spike dipindah ke awal M6 dan dicatat.

---

## M1 — Spec & Ground Truth Gatsu (5 hari)

**Tujuan:** kontrak data final dan data uji yang benar. Referensi: `03-layout-spec.md`.

### Tugas
- [ ] `core/spec/models.py`: model Pydantic untuk meta (termasuk `condition`, `building_outline`), grid, walls, columns (termasuk `kind`), openings, rooms, stairs, objects, provenance.
- [ ] `core/spec/derive.py`: field turunan (area, perimeter, luas kotor, bounding_walls, doors, room_id objek/tangga, tinggi tanjakan dan kedalaman injakan).
- [ ] `core/spec/ops.py`: semua ops di §11 beserta validasi parameternya. Fungsi `apply(spec, ops) -> spec` bersifat murni.
- [ ] `core/spec/validate.py`: aturan V001–V019 + skor. Tiap aturan punya unit test positif dan negatif.
- [ ] `core/spec/store.py`: simpan/baca versi append-only + `HEAD`.
- [ ] Ekspor JSON Schema ke `schema/`, generate `web/src/types/spec.ts`. Script `make schema` / `uv run python -m core.spec.export_schema`.
- [ ] **Alat bantu GT:** `benchmarks/tools/gt_author.py`.
  - Input YAML ringkas berbasis grid, mis. `wall: A1 -> B1, t=200` atau `wall: [6000,6000] -> [16000,6000]`, ditambah pintu per dinding.
  - Output `gt_spec.json` dan overlay GT di atas `plan.jpeg` (memakai skala dari grid).
- [ ] **GT Gatsu lengkap** (`benchmarks/gatsu/gt_spec.json`):
  - [ ] Grid A–F, 1–3.
  - [ ] Semua dinding exterior dan interior, termasuk Capasitor Room dan **pita luar** di luar grid.
  - [ ] Semua kolom, termasuk **blok sirip** di pita luar (`kind: pilaster`).
  - [ ] **Tangga** (flight, tanjakan, arah naik, bordes) dan lift.
  - [ ] **Kondisi existing**: tanpa elemen PROPOSED; dinding yang akan dibongkar tetap ada.
  - [ ] `building_outline` per massa bangunan dan luas kotor.
  - [ ] Semua pintu (tipe, engsel, arah) dan jendela.
  - [ ] Semua ruang beserta nama dan tipe.
- [ ] Review GT oleh orang kedua menggunakan overlay (R-17).

### Kriteria selesai
- GT Gatsu lolos validator **tanpa error**, dengan skor ≥ 0.95.
- Overlay GT tepat di atas denah. Pemeriksaan visual: deviasi garis ≤ 1–2 px.
- Coverage test `core/spec` ≥ 85%.
- `spec.ts` tergenerate dan terkompilasi di `web/`.

**FR terkait:** dasar untuk semua FR. Langsung: V-rules, FR-EX-14.

---

## M2 — Builder & Outputs (7 hari)

**Tujuan:** spec menghasilkan keempat output secara deterministik. Referensi: `06-builder-outputs.md`.

### Tugas
- [ ] `core/build_prep/`: spec → `build_input.json`.
  - [ ] Tapak dinding per ID, dengan sambungan dibagi di garis bagi sudut, tanpa overlap.
  - [ ] Cutter bukaan.
  - [ ] Transform kusen dan daun pintu (single/double/sliding/opening/rolling).
  - [ ] Poligon lantai per ruang (termasuk lubang kolom), slab per `building_outline`, kolom dan pilaster.
  - [ ] Tangga: balok anak tangga pejal per flight + bordes (`06-builder-outputs.md` §4.5b).
  - [ ] Objek dengan path template + skala per sumbu.
  - [ ] Daftar kamera (top, iso ×4, per ruang).
- [ ] `builder/scene/*`: walls (ekstrusi + Boolean EXACT), doors, windows, floors, columns, stairs, objects (linked duplicates), materials, cameras, annotations.
- [ ] Konvensi nama + custom properties + `export_extras`.
- [ ] Export: `shell.glb`, `layout_full.glb`, `layout.blend`, `layout.fbx`, `layout.obj`.
- [ ] Protokol progres `@@PROGRESS` dan exit code.
- [ ] `core/templates/make_placeholders.py`: 7 template placeholder (`10-template-contract.md` §6) + `validate.py`.
- [ ] `core/verify/`:
  - [ ] Cek glb 1:1 (pygltflib).
  - [ ] Cek grid.
  - [ ] IoU top-down dengan mask dinding sederhana dari binarisasi. Mask ini disempurnakan di M5.
- [ ] `core/report/`: template Jinja2 (Carbon light untuk cetak), seluruh 12 bagian dokumen, PDF via WeasyPrint.
- [ ] CLI: `uv run python -m core.cli build <spec.json> <out_dir>` untuk menjalankan tahap 7–9 tanpa server.
- [ ] Test builder (`blender -b -P builder/tests/run.py`): jumlah objek, nama, extras, dimensi.

### Kriteria selesai
- GT Gatsu (+ 10 objek placeholder) menghasilkan semua output dalam ≤ 90 detik di M4.
- Cek glb: galat dimensi ≤ 1 mm (NFR-AC-09).
- IoU top-down GT terhadap denah ≥ 0.85. Ini juga memvalidasi GT dan pipeline render.
- `report.html` dan `report.pdf` lengkap dengan render.
- `.glb` terbuka benar di three.js editor/online viewer dan di Blender. Orientasi utara (+Y spec) konsisten.

**FR:** FR-BO-01…07.

---

## M3 — Server & Dashboard (6 hari)

**Tujuan:** pipeline bisa dijalankan dan dipantau dari browser. Referensi: `02-architecture.md`, `08-dashboard.md`, `09-api.md`.

### Tugas — Server
- [ ] `server/storage.py`: akses `DATA_DIR` yang aman (anti traversal, tanpa symlink).
- [ ] `server/orchestrator.py`: state machine tahap 0–10, run `full`/`from_stage`/`regenerate`, antrean satu worker, pemulihan saat restart, pembatalan.
- [ ] Tahap 1–6 berupa **stub** yang melewatkan spec impor, sampai M5/M6 selesai. Tahap 7–9 memanggil builder (M2).
- [ ] `server/events.py`: `emit`, `events.jsonl`, `seq` monoton, SSE dengan `Last-Event-ID` + heartbeat.
- [ ] Routes: projects, runs, artifacts, specs (termasuk `import`, `validate`, `diff`), regenerate, outputs (ETag), events, templates, profiles, health/config.
- [ ] Validasi upload (magic bytes, ukuran) dan format error standar.
- [ ] Test integrasi API (pytest + httpx): alur impor → regenerate → output.

### Tugas — Dashboard
- [ ] App shell Carbon (Header, SideNav), tema g100, font Plex Sans/Mono, indikator kesehatan.
- [ ] Klien API + TanStack Query + hook SSE.
- [ ] `/projects` (DataTable), `/projects/new` (form + upload + parameter lanjutan).
- [ ] Detail project:
  - [ ] Tab Pipeline: `ProgressIndicator` + panel tahap. Panel 7–10 lengkap, panel 0–6 berupa kerangka.
  - [ ] Tab Logs (virtualized, filter, follow, unduh).
  - [ ] Tab Outputs.
  - [ ] Tab Versions (daftar + diff ringkas).
- [ ] `/templates` (grid read-only) dan `/system`.
- [ ] Komponen `OverlayViewer` (zoom/pan gambar + layer) untuk dipakai M5.

### Kriteria selesai
- Dari dashboard, pengguna bisa membuat project, mengimpor GT Gatsu, lalu menekan Regenerate.
- Log muncul live dengan latensi ≤ 1 detik. Output bisa diunduh, dan dokumen tampil di iframe.
- Restart server di tengah run: run ditandai `interrupted`, dan antrean berlanjut.
- Lighthouse a11y ≥ 90 di halaman daftar dan detail.

**FR:** FR-IN-01…03, FR-IN-05, FR-DB-01…09, API.

---

## M4 — Web Editor (11 hari)

**Tujuan:** editor interaktif lengkap di atas shell Gatsu. Referensi: `07-web-editor.md`.

### Tugas
- [ ] Viewport R3F: muat `shell.glb` (cache ETag), pemetaan `userData.spec_id`, pencahayaan, grid 600 mm, toggle layer, cutaway.
- [ ] Mode Orbit dan Top. Mode Walk (P1).
- [ ] Seleksi (raycast) + outline + panel Properties per tipe.
- [ ] **Tool ukur:** jarak (snap vertex/edge, kunci sumbu), luas ruang (dari spec), luas bebas (shoelace), tinggi.
- [ ] **Tinggi dinding:** global + per dinding, pratinjau skala Z + banner.
- [ ] **Library template:** panel kiri, pencarian, kategori, thumbnail.
- [ ] **Drag & drop:** ghost, raycast lantai, snap edge/center, tolak di luar ruang.
- [ ] **Transform:** pindah, rotasi (90°/15°/bebas), resize per sumbu dengan batas `resizable`, input numerik, duplikat, hapus, kunci, multi-seleksi.
- [ ] **Store ops lokal** (Zustand) + reducer TS. Unit test Vitest untuk reducer dan util ukur.
- [ ] **Panel koreksi geometri** (`07-web-editor.md` §6b, FR-WE-15), 2 hari:
  - form dinding (ubah/tambah/pisah/gabung/hapus), tambah dinding dengan dua klik di mode Top;
  - form pintu/jendela (ubah/tambah/hapus) dan tangga (ubah/balik arah/hapus);
  - pratinjau 2D oranye, validasi langsung via `/specs/validate`, banner regenerate.
- [ ] **Save:** `POST /specs`, tangani 201/409 (rebase sederhana)/422.
- [ ] **Regenerate:** progress via SSE, reload shell dengan kamera dan seleksi dipertahankan.
- [ ] InstancedMesh untuk template dengan > 20 instance.
- [ ] Undo/redo (P1), tabrakan OBB + clearance (P1), pintasan keyboard.

### Kriteria selesai
- Kriteria sukses MVP #3 terpenuhi pada GT Gatsu:
  - mengukur luas R. MEETING (sesuai spec) dan tinggi dinding;
  - mengubah tinggi data hall;
  - menempatkan dan me-resize ≥ 3 jenis template;
  - menghapus satu dinding palsu, menambah satu dinding, dan mengubah lebar satu pintu lewat panel koreksi;
  - Save, lalu Regenerate. Perubahan muncul di `.blend`, `layout_full.glb`, dan tabel objek dokumen.
- Hasil ukur jarak antar-sumbu grid di editor sama dengan spec (±1 mm).
- ≥ 45 fps dengan 500 rack di laptop uji (NFR-PF-04).
- Konflik versi (dua tab mengedit) ditangani tanpa kehilangan ops lokal.

**FR:** FR-WE-01…13, FR-WE-15.

---

## M5 — Ekstraksi CV (13 hari)

**Tujuan:** upload `plan.jpeg` menghasilkan spec otomatis yang memenuhi target akurasi. Referensi: `04-extraction.md`.

### Tugas
- [ ] **Benchmark ekstraksi dulu** (`benchmarks/run_extraction_bench.py`):
  - membandingkan spec dengan GT: skala, galat dinding (median/p95), recall/presisi dinding, recall/lebar/arah pintu, kecocokan ruang dan luas, IoU;
  - output laporan Markdown + JSON.
- [ ] Tahap 0: validasi input, parse prompt aturan (regex).
- [ ] Tahap 1: rasterisasi PDF, CLAHE, deskew, area gambar, binarisasi.
- [ ] Tahap 2: OCR global + klasifikasi teks, deteksi bulatan dan garis grid, skala least squares + RANSAC + cek total, fallback.
- [ ] Tahap 3:
  - [ ] Masking anotasi (teks, dimensi, sumbu, hatch, leader, **simbol MEP terisi**).
  - [ ] Kondisi existing: kelas teks `proposed`/`dismantle`, titik tunjuk leader, pengecualian elemen PROPOSED.
  - [ ] **Tangga** (`04-extraction.md` §3.4b): flight, tanjakan, arah naik, bordes, `stair_mask`.
  - [ ] Dinding S1 dan S2.
  - [ ] Pasca-proses (snap, gabung kolinear, sambungan L/T).
  - [ ] Kolom, pintu (busur + celah), jendela (P1).
  - [ ] Skor keyakinan.
- [ ] Parameter sweep paralel + batas kandidat.
- [ ] Tahap 4: tapak dinding, area interior, polygonize, kontur terpisah (Capasitor Room), `building_outline` + luas kotor, label OCR + leksikon + Levenshtein, ruang tangga/lift.
- [ ] Tahap 5: validasi semua kandidat, pemilihan, ID stabil deterministik, `overlay_ids.png`, ambang status.
- [ ] Carry-over saat re-ekstraksi (`04-extraction.md` §5.4b): pencocokan dinding/ruang/pintu/kolom, pewarisan ID dan edit, salin objek, `carryover.json`, peringatan di dashboard.
- [ ] Style profile: simpan/muat + sweep di sekitar profile (P1).
- [ ] Ganti stub tahap 0–5 di orchestrator dengan implementasi asli. Lengkapi panel dashboard tahap 0–5 dan tab Review (overlay + masalah, tanpa Strata).
- [ ] Sempurnakan mask IoU tahap 8 memakai mask kandidat terpilih.
- [ ] Test regresi: `plan.jpeg` → metrik ≥ ambang (pytest, ditandai `slow`).

### Kriteria selesai
- Gatsu memenuhi **NFR-AC-01 s.d. NFR-AC-08, NFR-AC-10, NFR-AC-11** tanpa Strata dan tanpa edit manual.
  - Bila satu metrik belum tercapai setelah 13 hari + buffer: catat galatnya, pastikan koreksi lewat panel koreksi ≤ 15 menit, dan bawa ke M7.
- Tahap 1–5 ≤ 2 menit di M4 (NFR-PF-01).
- Run berulang menghasilkan spec identik (NFR-RL-06).
- Upload `plan.jpeg` dari dashboard berjalan end-to-end sampai editor.

**FR:** FR-IN-04 (aturan), FR-EX-01…14.

---

## M6 — Strata Review (6 hari)

**Tujuan:** Strata meningkatkan hasil secara terukur tanpa pernah memperburuknya. Referensi: `05-llm-review.md`.

### Tugas
- [ ] Spike Strata (bila belum dilakukan di M0).
- [ ] `core/llm_review/client.py`: SDK openai, healthcheck, timeout, retry JSON invalid, pencatatan token dan latensi.
- [ ] Pembuat crop zoom + thumbnail konteks + bukti teks.
- [ ] Tugas T0 (parse prompt), T1, T2, T3: prompt berversi, schema output, voting.
- [ ] T4: definisi tool (subset ops), loop tool calling, umpan balik penolakan.
- [ ] Harness: routing elemen, gerbang Fase A/B, batas waktu dan iterasi, `spec.v2` (`source: llm`).
- [ ] `transcript.jsonl` + `decisions.json` + event `llm.decision`.
- [ ] **Benchmark LLM:**
  - [ ] Bangun item dari Gatsu (T1 ≥ 40, T2 ≥ 20, T3 ≥ 20).
  - [ ] Pisahkan few-shot dari item evaluasi.
  - [ ] Buat `run_llm_bench.py`, laporan, dan `DECISIONS.md`.
- [ ] Flag `LLM_TASKS_ENABLED` diisi sesuai hasil benchmark.
- [ ] Dashboard: tab Review menampilkan tabel keputusan, crop + respons mentah, banner `skipped`. Halaman `/system` menampilkan status Strata dan tugas aktif.

### Kriteria selesai
- Laporan benchmark T0–T4 ada. Setiap tugas yang aktif memenuhi syarat `05-llm-review.md` §7.2.
- Pada Gatsu, metrik akurasi akhir dengan Strata ≥ tanpa Strata untuk semua metrik.
- Strata dimatikan: tahap 6 `skipped`, pipeline selesai (kriteria sukses MVP #5).
- Tahap 6 ≤ 10 menit.

**FR:** FR-IN-04 (Strata), FR-LLM-01…09.

---

## M7 — Ketahanan & Deploy (7 hari)

**Tujuan:** membuktikan pipeline tahan terhadap variasi gambar walaupun hanya ada satu denah nyata, lalu men-deploy-nya.

### Tugas — Ketahanan
- [ ] **Set augmentasi** (`benchmarks/augment/`, 1 hari): ±30 varian `plan.jpeg` (resolusi 0.6×–2×, JPEG q 40–95, rotasi ±2°, crop margin, blur/noise ringan). GT ditransformasi dengan matriks yang sama. Jalankan benchmark, lalu analisis mode gagal.
- [ ] **Denah sintetis** (`benchmarks/synth/`, P1, 3 hari): ubah GT Gatsu secara acak (jarak grid, partisi tambah/hapus, cermin, campuran tipe pintu, posisi tangga), lalu render 2D bergaya denah CAD (dinding garis ganda, busur pintu, bulatan grid, teks dimensi, anotasi MEP acak, simbol panel terisi). GT tiap varian otomatis diketahui.
- [ ] Perbaikan ekstraktor yang **umum**, bukan hardcode untuk Gatsu. Tiap perbaikan diikuti regresi terhadap semua set.
- [ ] Simpan style profile Gatsu.
- [ ] Bila denah nyata baru datang selama M7: buat GT ringkas dengan `gt_author.py` dan masukkan ke benchmark.

### Tugas — Deploy
- [ ] `docker/Dockerfile`: Ubuntu + Blender 5.2 LTS (pinned) + Python 3.12 + deps + font Plex. Web dibuild statis dan disajikan FastAPI.
- [ ] `docker/compose.yaml`: volume `DATA_DIR`, akses ke Strata host, `BLENDER_RENDER_DEVICE=CPU`.
- [ ] Deploy ke gspe-ai2 (`/home/gspe-ai2/project_AI/floorplan3d/`). Smoke test: Gatsu end-to-end di server.
- [ ] Uji kontensi: run pipeline bersamaan dengan beban Strata. Pastikan tidak ada OOM atau VRAM penuh.
- [ ] `README.md`: setup dev, menjalankan pipeline/CLI, deploy, backup `DATA_DIR`, troubleshooting.

### Kriteria selesai (= kriteria sukses MVP, `01-requirements.md` §3)
1. Gatsu end-to-end memenuhi NFR-AC.
2. Set augmentasi: ≥ 80% varian mencapai ≥ 90% target. Hasil denah sintetis dilaporkan. Sisa galat Gatsu terkoreksi lewat panel koreksi ≤ 15 menit.
3. Fitur editor lengkap (M4) berjalan di server.
4. Dashboard memantau semua run.
5. Pipeline tahan terhadap Strata mati.
6. Benchmark Strata terdokumentasi.

---

## 3. Definition of Done (berlaku untuk semua tugas)

- Kode lolos lint (ruff / ESLint) dan test terkait hijau.
- Logika non-trivial punya minimal satu test yang gagal bila logikanya rusak.
- Event/log yang relevan dikirim (untuk tahap pipeline).
- Dokumen PRD diperbarui bila perilaku menyimpang dari spesifikasi.
- Tidak ada kredensial di kode atau commit.

## 4. Metrik yang Dipantau Sepanjang Proyek

| Metrik | Sumber | Mulai |
|---|---|---|
| Akurasi ekstraksi per denah (NFR-AC-*) | `run_extraction_bench.py` | M5 |
| Akurasi tugas LLM vs baseline | `run_llm_bench.py` | M6 |
| Durasi per tahap | `run.json` | M3 |
| IoU top-down | `verify.json` | M2 |
| fps editor (500 objek) | uji manual / Playwright | M4 |

## 5. Backlog Pasca-MVP (urut prioritas usulan)

1. **Panel chat eskalasi (Tingkat 2)**: Strata + tool spec + render headless (FR-LLM-10).
2. **Autentikasi** dan audit pengguna (Q-05).
3. **Edit geometri langsung di viewport**: seret vertex dinding, geser pintu dengan mouse, pratinjau 3D di klien.
4. **PDF vektor**: ekstraksi langsung dari path/teks (FR-IN-06).
4b. **Strategi S3, segmentasi terlatih**: fine-tune UNet pada denah sintetis + denah nyata berlabel (≥ 20 denah), dipakai sebagai kandidat tambahan di sweep, bukan pengganti (ADR-8).
5. **Animasi buka pintu** di editor (FR-WE-14).
6. **Raised floor dan plafon** (Q-02).
7. **Multi-lantai**: penumpukan beberapa denah dalam satu gedung.
8. **Ekspor tambahan**: DXF 2D dari spec, IFC (Q-09).
9. **Integrasi alur kerja aset**: publish template langsung ke registry + upload template dari dashboard.
10. **Skalabilitas**: SQLite/PostgreSQL untuk indeks, Redis + worker paralel.
11. **Dukungan scan miring/foto**: rektifikasi perspektif.
12. **Upgrade model**: Strata Q4+ atau VLM khusus vision, lalu jalankan ulang benchmark dan pertimbangkan tugas baru (Q-04).
