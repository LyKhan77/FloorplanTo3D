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
- [x] Inisialisasi git repo. Isi `.gitignore`: `data/`, `.env`, **`server-info.txt`**, `.venv/`, `node_modules/`, `web/dist/`.
- [ ] **Keamanan:** pindahkan kredensial di `server-info.txt` ke password manager, dan pertimbangkan mengganti password yang sudah tersebar (R-15).
- [x] `uv python install 3.12`, `pyproject.toml`, struktur folder sesuai `11-tech-stack.md` §3, ruff, pytest.
- [x] `.env.example` dengan semua variabel dari `02-architecture.md` §7.
- [x] **Smoke test Blender:** `builder/build.py` versi minimal (satu kubus + custom property), lalu export `.glb` dengan extras. Cek extras terbaca dengan pygltflib.
- [x] **Smoke test OCR:** RapidOCR pada `floorplan/plan.jpeg`. Harus terbaca: label grid A–F dan 1–3, angka 6000/4000/28000/12000, serta label ruang (R. MEETING, GUDANG, BATTERY ROOM, …).
- [x] **Smoke test WeasyPrint** (`brew install pango` bila perlu).
- [x] Inisialisasi `web/` (Vite + React + TS + `@carbon/react` g100 + R3F): halaman kosong dengan tema gelap dan satu kubus three.js.
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

**Status M0 (2026-10-26), branch `m0-foundation`:**
- `uv run --env-file .env pytest` → 13 passed, 1 xfailed (OCR hitungan grid). Ruff dan `npm run lint` (oxlint) bersih. Tanpa `--env-file` hanya test WeasyPrint yang gagal, dengan petunjuk.
- Blender: `.glb` dengan extras `spec_id`/`spec_type`, sumbu dan ukuran 1:1 terverifikasi. `BLENDER_BIN` wajib path asli `/Applications/Blender.app/Contents/MacOS/Blender`; symlink Homebrew crash.
- OCR Gatsu: **16/18 (89%)** label grid + angka dimensi setelah dedup antar-pass (hilang: bulatan grid "C" dan "1"; upscale 3× tidak membantu), 9/9 label ruang, dimensi vertikal terbaca. Kriteria ≥ 90% **belum terpenuhi kurang 1 item**: dibawa ke M5 (OCR per crop bulatan grid, `benchmarks/reports/m0-smoke.md`).
- Web: halaman g100 + kubus R3F (React 18, Carbon, font Plex dibundel). Lint memakai oxlint bawaan Vite, bukan ESLint.
- Spike Strata **ditunda ke M6**: Strata tidak aktif (`benchmarks/reports/spike-strata.md`).
- Belum: pemindahan kredensial `server-info.txt` (tindakan pengguna, R-15).

---

## M1 — Spec & Ground Truth Gatsu (5 hari)

**Tujuan:** kontrak data final dan data uji yang benar. Referensi: `03-layout-spec.md`.

### Tugas
- [x] `core/spec/models.py`: model Pydantic untuk meta (termasuk `condition`, `building_outline`), grid, walls, columns (termasuk `kind`), openings, rooms, stairs, objects, provenance.
- [x] `core/spec/derive.py`: field turunan (area, perimeter, luas kotor, bounding_walls, doors, room_id objek/tangga, tinggi tanjakan dan kedalaman injakan).
- [x] `core/spec/ops.py`: semua ops di §11 beserta validasi parameternya. Fungsi `apply(spec, ops) -> spec` bersifat murni.
- [x] `core/spec/validate.py`: aturan V001–V019 + skor. Tiap aturan punya unit test positif dan negatif.
- [x] `core/spec/store.py`: simpan/baca versi append-only + `HEAD`.
- [x] Ekspor JSON Schema ke `schema/`, generate `web/src/types/spec.ts`. Script `make schema` / `uv run python -m core.spec.export_schema`.
- [x] **Alat bantu GT:** `benchmarks/tools/gt_author.py`.
  - Input YAML ringkas berbasis grid, mis. `wall: A1 -> B1, t=200` atau `wall: [6000,6000] -> [16000,6000]`, ditambah pintu per dinding.
  - Output `gt_spec.json` dan overlay GT di atas `plan.jpeg` (memakai skala dari grid).
- [x] **GT Gatsu lengkap** (`benchmarks/gatsu/gt_spec.json`):
  - [x] Grid A–F, 1–3.
  - [x] Semua dinding exterior dan interior, termasuk Capasitor Room dan **pita luar** di luar grid.
  - [x] Semua kolom, termasuk **blok sirip** di pita luar (`kind: pilaster`).
  - [x] **Tangga** (flight, tanjakan, arah naik, bordes) dan lift.
  - [x] **Kondisi existing**: tanpa elemen PROPOSED; dinding yang akan dibongkar tetap ada.
  - [x] `building_outline` per massa bangunan dan luas kotor.
  - [x] Semua pintu (tipe, engsel, arah) dan jendela.
  - [x] Semua ruang beserta nama dan tipe.
- [ ] Review GT oleh orang kedua menggunakan overlay (R-17).

### Kriteria selesai
- GT Gatsu lolos validator **tanpa error**, dengan skor ≥ 0.95.
- Overlay GT tepat di atas denah. Pemeriksaan visual: deviasi garis ≤ 1–2 px.
- Coverage test `core/spec` ≥ 85%.
- `spec.ts` tergenerate dan terkompilasi di `web/`.

**Status M1 (2026-10-26), branch `m1-spec-gt`:**
- `uv run --env-file .env pytest` → 95 passed, 1 xfailed (OCR grid dari M0). Coverage `core/spec` ≥ 95%. Ruff, oxlint, dan `npm run build` bersih.
- `core/spec`: model Pydantic, field turunan, pembentukan ruang dari dinding + pewarisan ID, 18 ops (`apply` murni dan atomik), validator V001–V019, `SpecStore` append-only, ekspor JSON Schema + `web/src/types/{spec,ops}.ts`.
- GT Gatsu (`benchmarks/gatsu/`): 77 dinding, 51 kolom (18 H + 33 pilaster/pier), 19 bukaan, 2 tangga, 48 ruang (25 sel pita luar `outdoor`); RMS kalibrasi 7.6 mm; skor validator 0.993; 2 massa bangunan; luas kotor 563.77 m².
- Bug core yang ditemukan dan sudah diperbaiki: pulau dinding terhitung sebagai massa bangunan, pintu di dinding bersama terdaftar untuk semua ruang, ID yang dihapus bisa dipakai ulang, ujung T memotong ruang seberang, null di op dilaporkan di indeks yang salah, `provenance_log` menumpuk antar-versi, dan merge dinding terbalik tidak membalik engsel.
- **Belum:** review GT oleh orang kedua (R-17). Pertanyaan terbuka ada di `benchmarks/gatsu/NOTES.md`: batas Battery/Ex Mushola, tinggi lantai, arah tangga timur, dan rail pita luar.

**FR terkait:** dasar untuk semua FR. Langsung: V-rules, FR-EX-14.

---

## M2 — Builder & Outputs (7 hari)

**Tujuan:** spec menghasilkan keempat output secara deterministik. Referensi: `06-builder-outputs.md`.

### Tugas
- [x] `core/build_prep/`: spec → `build_input.json`.
  - [x] Tapak dinding per ID, tanpa overlap. *Menyimpang: sudut menjadi milik dinding ber-ID terkecil, tidak dibagi di garis bagi sudut.*
  - [x] Cutter bukaan.
  - [x] Transform kusen dan daun pintu (single/double/sliding/opening/rolling).
  - [x] Poligon lantai per ruang (termasuk lubang kolom), slab per `building_outline`, kolom dan pilaster.
  - [x] Tangga: balok anak tangga pejal per flight + bordes (`06-builder-outputs.md` §4.5b).
  - [x] Objek dengan path template + skala per sumbu.
  - [x] Daftar kamera (top, iso ×4, per ruang).
- [x] `builder/scene/*`: walls (ekstrusi + Boolean EXACT), doors, windows, floors, columns, stairs, objects (linked duplicates), materials, cameras, annotations. *Belum: simbol busur pintu di Annotations dan tint lantai per tipe ruang di render dokumen (kosmetik, ditunda).*
- [x] Konvensi nama + custom properties + `export_extras`.
- [x] Export: `shell.glb`, `layout_full.glb`, `layout.blend`, `layout.fbx`, `layout.obj`.
- [x] Protokol progres `@@PROGRESS` dan exit code.
- [x] `core/templates/make_placeholders.py`: 7 template placeholder (`10-template-contract.md` §6) + `validate.py`.
- [x] `core/verify/`:
  - [x] Cek glb 1:1 (pygltflib).
  - [ ] Cek grid. *Kerangka ada, statusnya `skipped` sampai OCR dimensi tersedia (M5).*
  - [x] IoU top-down dengan mask dinding sederhana dari binarisasi. Mask ini disempurnakan di M5.
- [x] `core/report/`: template Jinja2 (Carbon light untuk cetak), seluruh 12 bagian dokumen, PDF via WeasyPrint.
- [x] CLI: `uv run python -m core.cli build <spec.json> <out_dir>` untuk menjalankan tahap 7–9 tanpa server.
- [x] Test builder: jumlah objek, nama, extras, dimensi. *Dijalankan lewat pytest (subprocess Blender), bukan `builder/tests/run.py`.*

### Kriteria selesai
- GT Gatsu (+ 10 objek placeholder) menghasilkan semua output dalam ≤ 90 detik di M4.
- Cek glb: galat dimensi ≤ 1 mm (NFR-AC-09).
- IoU top-down GT terhadap denah ≥ 0.85. Ini juga memvalidasi GT dan pipeline render.
- `report.html` dan `report.pdf` lengkap dengan render.
- `.glb` terbuka benar di three.js editor/online viewer dan di Blender. Orientasi utara (+Y spec) konsisten.

**Status M2 (2026-10-26), branch `m2-builder`:**
- `uv run --env-file .env pytest` → 145 passed, 2 xfailed (OCR grid dari M0, IoU Gatsu). Ruff bersih.
- `core.cli build`: GT Gatsu + 10 rack placeholder → semua output dalam **6.1 s** (target ≤ 90 s). Cek glb 77 dinding: galat maks **0.001 mm**. Dokumen 16 halaman HTML + PDF dengan 19 render.
- **IoU 0.453, target ≥ 0.85 belum tercapai.** Alignment render dan denah sudah tepat; masalahnya mask denah sederhana yang ikut menghitung furnitur, anak tangga, busur pintu, dan dimensi sebagai dinding. Target dibawa ke M5 (mask dari kandidat ekstraksi). Rincian di `benchmarks/reports/m2-verify.md`.
- Penyimpangan dari rencana: engine render default Workbench (Eevee opsional lewat `--engine`); grid check `skipped` sampai OCR dimensi tersedia di M5; test builder dijalankan lewat pytest (tanpa `builder/tests/run.py`); sudut tapak dinding menjadi milik ID terkecil (bukan dibagi garis bagi sudut).
- Belum dicek manual: membuka `.glb` di viewer three.js online. Konvensi sumbu sudah diverifikasi lewat test glTF dan render.

**FR:** FR-BO-01…07.

---

## M3 — Server & Dashboard (6 hari)

**Tujuan:** pipeline bisa dijalankan dan dipantau dari browser. Referensi: `02-architecture.md`, `08-dashboard.md`, `09-api.md`.

### Tugas — Server
- [x] `server/storage.py`: akses `DATA_DIR` yang aman (anti traversal, tanpa symlink).
- [x] `server/orchestrator.py`: state machine tahap 0–10, run `full`/`from_stage`/`regenerate`, antrean satu worker, pemulihan saat restart, pembatalan.
- [x] Tahap 1–6 berupa **stub** yang melewatkan spec impor, sampai M5/M6 selesai. Tahap 7–9 memanggil builder (M2).
- [x] `server/events.py`: `emit`, `events.jsonl`, `seq` monoton, SSE dengan `Last-Event-ID` + heartbeat.
- [x] Routes: projects, runs, artifacts, specs (termasuk `import`, `validate`, `diff`), regenerate, outputs (ETag), events, templates, profiles, health/config.
- [x] Validasi upload (magic bytes, ukuran) dan format error standar.
- [x] Test integrasi API (pytest + httpx): alur impor → regenerate → output.

### Tugas — Dashboard
- [x] App shell Carbon (Header, SideNav), tema g100, font Plex Sans/Mono, indikator kesehatan.
- [x] Klien API + TanStack Query + hook SSE.
- [x] `/projects` (DataTable), `/projects/new` (form + upload + parameter lanjutan).
- [x] Detail project:
  - [x] Tab Pipeline: timeline tahap (daftar kustom, bukan `ProgressIndicator`) + panel tahap. Panel 7–10 lengkap, panel 0–6 berupa kerangka.
  - [x] Tab Logs (virtualized, filter, follow, unduh).
  - [x] Tab Outputs.
  - [x] Tab Versions (daftar + diff ringkas).
- [x] `/templates` (grid read-only) dan `/system`.
- [x] Komponen `OverlayViewer` (zoom/pan gambar + layer) untuk dipakai M5.

### Kriteria selesai
- Dari dashboard, pengguna bisa membuat project, mengimpor GT Gatsu, lalu menekan Regenerate.
- Log muncul live dengan latensi ≤ 1 detik. Output bisa diunduh, dan dokumen tampil di iframe.
- Restart server di tengah run: run ditandai `interrupted`, dan antrean berlanjut.
- Lighthouse a11y ≥ 90 di halaman daftar dan detail.

**Status M3 (2026-10-26), branch `m3-server`:**
- `uv run --env-file .env pytest` → 202 passed, 2 xfailed (xfail sama dengan M2). Web: Vitest 24 passed; oxlint dan build bersih. Review akhir (opus) menemukan 1 Critical + 8 Important; semua diperbaiki di `c51b41a` dengan test yang gagal dulu.
- Alur browser (Playwright, Vite dev + Uvicorn): buat project "MSC Gatsu L1" → impor GT → v1 muncul di Versions → Regenerate. Tahap 7–10 bergerak live; run selesai `needs_attention` karena IoU 0.453 (diketahui sejak M2). Unduh `shell.glb` → 200 (338 KB). Dokumen tampil di iframe. Indikator Strata merah (server Strata mati), Blender hijau.
- Latensi log (waktu event sampai baris muncul di DOM, 37 event): median **9 ms**, maks **70 ms** (target ≤ 1 s).
- Restart di tengah tahap 7: run ditandai `failed` + `interrupted`, run antrean dari project lain berjalan, dan Regenerate baru menghasilkan v3. Uji ini menemukan dua bug yang sudah diperbaiki. Pertama, proses lama tetap hidup selama dashboard memegang stream SSE, karena graceful shutdown Uvicorn menunggu semua respons selesai. Akibatnya run yang sudah ditandai interrupted masih mempublikasikan output dan dua proses menulis `events.jsonl`. Kedua, browser berhenti reconnect setelah proxy membalas 502. Setelah perbaikan, proses lama keluar dalam 0.3 s tanpa sisa proses Blender, dan dashboard tersambung ulang dari `seq` terakhir.
- Lighthouse a11y: **1.00** di `/projects`, detail project, `/projects/new`, `/templates`, `/system`.
- Penyimpangan: `POST /api/profiles` → 501 (profil parameter baru dipakai M5). Tab Review dan Editor masih placeholder (M6/M4). Pratinjau 3D template ditunda ke M4. `OverlayViewer` sudah ada tetapi belum dipakai halaman mana pun sampai panel tahap M5. Tahap 1–4 ditandai `skipped` ("belum diimplementasi sampai M5").

**FR:** FR-IN-01…03, FR-IN-05, FR-DB-01…09, API.

---

## M4 — Web Editor (11 hari)

**Tujuan:** editor interaktif lengkap di atas shell Gatsu. Referensi: `07-web-editor.md`.

### Tugas
- [x] Viewport R3F: muat `shell.glb` (cache ETag), pemetaan `userData.spec_id`, pencahayaan, grid 600 mm, toggle layer, cutaway.
- [x] Mode Orbit dan Top. Mode Walk (P1).
- [x] Seleksi (raycast) + outline + panel Properties per tipe.
- [x] **Tool ukur:** jarak (snap vertex/edge, kunci sumbu), luas ruang (dari spec), luas bebas (shoelace), tinggi.
- [x] **Tinggi dinding:** global + per dinding, pratinjau skala Z + banner.
- [x] **Library template:** panel kiri, pencarian, kategori, thumbnail.
- [x] **Drag & drop:** ghost, raycast lantai, snap edge/center, tolak di luar ruang.
- [x] **Transform:** pindah, rotasi (90°/15°/bebas), resize per sumbu dengan batas `resizable`, input numerik, duplikat, hapus, kunci, multi-seleksi.
- [x] **Store ops lokal** (Zustand) + reducer TS. Unit test Vitest untuk reducer dan util ukur.
- [x] **Panel koreksi geometri** (`07-web-editor.md` §6b, FR-WE-15), 2 hari:
  - form dinding (ubah/tambah/pisah/gabung/hapus), tambah dinding dengan dua klik di mode Top;
  - form pintu/jendela (ubah/tambah/hapus) dan tangga (ubah/balik arah/hapus);
  - pratinjau 2D oranye, validasi langsung via `/specs/validate`, banner regenerate.
- [x] **Save:** `POST /specs`, tangani 201/409 (rebase sederhana)/422.
- [x] **Regenerate:** progress via SSE, reload shell dengan kamera dan seleksi dipertahankan.
- [x] InstancedMesh untuk template dengan > 20 instance.
- [x] Undo/redo (P1), tabrakan OBB + clearance (P1), pintasan keyboard.

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

**Status M4 (2026-10-26), branch `m4-editor`:**
- Alur kriteria selesai dijalankan di browser (Playwright, project baru `gatsu-editor`, GT diimpor lalu regenerate v1):
  - luas R. MEETING lewat tool "Luas ruang" = 67.48 m² (sama dengan `area_m2`); "Ukur tinggi" pada dinding menampilkan tinggi spec (W2: 3.000 m);
  - GALERY (R29) diubah tipenya menjadi `data_hall`, lalu "Tinggi dinding ruang ini" = 4500 mm (27 dinding pembatas, banner pratinjau tampil);
  - rack-42u, crac-unit, dan ups-cabinet di-drop ke R29 dan di-resize lewat input dimensi (nilai di-clamp ke `step` template);
  - panel Koreksi: W56 dihapus (alasan "duplikat"), satu dinding ditambah dengan dua klik di mode Top, lebar D3 830 → 930 mm. Garis oranye dan banner "Geometri berubah" tampil, panel Masalah menampilkan validasi live;
  - Save → v2, Regenerate dari toolbar (progress build → verify → report → publish, 14.8 s). Shell v2 dimuat ulang di canvas yang sama, seleksi tetap.
  - Hasil di `outputs/v2`: `layout_full.glb` berisi `obj_O1`–`obj_O3`, `report.html` mencantumkan ketiga template, `layout.blend` ditulis ulang, W56 tidak ada lagi di `shell.glb`.
  - Catatan: dinding tambahan kebetulan tepat menumpuk W70 (kedua klik ter-snap ke ujung W70), sehingga builder membuangnya sebagai duplikat (V007 overlap 620 mm).
- Presisi ukur: jarak antar-persimpangan sumbu grid di mode Top = 6000, 6000, dan 6000 mm (spec 6000), galat 0 mm.
- Performa: 500 `rack-42u-600x1200` (satu InstancedMesh) di Chromium dengan GPU (ANGLE Metal, Apple M4): **60 fps** rata-rata dan minimum selama orbit 5 s (dibatasi vsync).
  - Hanya ~190 rack muat di dalam ruang GT tanpa tumpang tindih, sehingga 310 sisanya sengaja ditumpuk (tabrakan hanya peringatan). Ini juga menjadi kasus terburuk untuk deteksi tabrakan: satu edit memakan ~85–100 ms termasuk dua frame.
- Konflik dua tab: B mengubah lebar D2 dan menambah rack, sementara A menghapus D2, memindah O1, lalu Save (v9). Save B → 409 → dialog rebase mendaftar `set_door D2` sebagai gagal. "Terapkan ke v9" membuang op itu saja, lalu Save → v10: rack B (O504) ada, posisi O1 milik A tidak berubah. Tab yang belum punya ops lokal otomatis mengikuti HEAD baru lewat SSE.
- Bug yang ditemukan saat E2E dan sudah diperbaiki dengan test:
  - op `add_object` dengan `label: null` ditolak server;
  - loop dropdown tipe ruang (Downshift + Modal yang selalu ter-mount);
  - tampilan Top miring setelah fokus ruang;
  - progress regenerate ditampilkan sebagai "750%".
- Review akhir (reviewer opus, satu putaran perbaikan): 1 Critical, 5 Important, dan 4 Minor yang dinaikkan ke Important diperbaiki dengan test. Daftarnya:
  - hapus beberapa objek baru sekaligus menghapus objek yang salah;
  - rotasi gizmo lewat ±90°;
  - pintasan huruf di mode Walk dan di dalam dropdown;
  - edit saat Save berjalan hilang;
  - seleksi setelah rebase menunjuk objek tab lain;
  - sumbu gizmo scale pada objek yang dirotasi;
  - objek terkunci masih bisa diedit lewat input angka;
  - "Balik arah naik" pada tangga dua flight;
  - Save ganda.
  10 Minor lain ditunda (lihat laporan akhir M4).
- Suite: pytest 203 passed, 2 xfailed (termasuk fixture paritas reducer klien ↔ `core.spec.ops`); Vitest 140 passed; oxlint dan build bersih.
- **Penyimpangan dari PRD/07:**
  - toggle "kualitas tinggi" (SSAO, §9) tidak dibuat, karena butuh dependensi `postprocessing`;
  - snap objek ke dinding (P1) tidak dibuat;
  - origin grid per ruang (P2) tidak dibuat;
  - "perbarui template ke versi terbaru" (P2) tidak dibuat;
  - di mode Top, klik kiri dipakai untuk marquee, sehingga pan memakai klik kanan;
  - objek tidak bisa diseret langsung di lantai (§7.2); pindah lewat gizmo, input X/Y, atau pintasan.
- Edit pada elemen yang belum disimpan digabung ke op pembuatnya. Aksi yang tidak bisa digabung (memisah atau mengunci elemen baru, dsb.) ditolak dengan "Save dulu".

---

## M5 — Ekstraksi CV (13 hari)

**Tujuan:** upload `plan.jpeg` menghasilkan spec otomatis yang memenuhi target akurasi. Referensi: `04-extraction.md`.

### Tugas
- [x] **Benchmark ekstraksi dulu** (`benchmarks/run_extraction_bench.py`):
  - membandingkan spec dengan GT: skala, galat dinding (median/p95), recall/presisi dinding, recall/lebar/arah pintu, kecocokan ruang dan luas, IoU;
  - output laporan Markdown + JSON.
- [x] Tahap 0: validasi input, parse prompt aturan (regex).
- [x] Tahap 1: rasterisasi PDF, CLAHE, deskew, area gambar, binarisasi.
- [x] Tahap 2: OCR global + klasifikasi teks, deteksi bulatan dan garis grid, skala least squares + RANSAC + cek total, fallback.
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

**Status M5a (2026-10-26), branch `m5-cv`.** Plan: `docs/superpowers/plans/2026-10-26-m5a-benchmark-input-grid.md`. M5 dipecah menjadi M5a (benchmark + tahap 0–2), M5b (tahap 3), dan M5c (tahap 4–5 + integrasi).
- **Benchmark:**
  - `benchmarks/extraction_metrics.py` + `run_extraction_bench.py` mengukur semua metrik NFR-AC-01…08, 10, dan 11 terhadap GT;
  - GT terhadap dirinya sendiri: semua lulus;
  - mode `--grid` dipakai sampai tahap 3–5 ada;
  - laporan `benchmarks/reports/m5a-grid.md`.
- **Tahap 0–2 berjalan otomatis dari upload `plan.jpeg` di dashboard:**
  - tahap 1 butuh 1.8 s, tahap 2 butuh 4.0 s;
  - **skala 25.846 mm/px, galat 0.13%** (NFR-AC-01 ≤ 0.5%);
  - sumbu A–F / 1–3 lengkap, offset tepat (galat 0 mm);
  - "C" dan "1" terbaca lewat OCR per crop bulatan, sehingga kriteria OCR M0 kini 18/18;
  - residu persamaan maks 0.8%.
- **Skala manual** dari panel tahap 2 menjalankan ulang dari tahap 2 (artefak tahap 0–1 disalin dari run sebelumnya). Hasilnya `scale_source manual`, dengan peringatan bila beda > 1% dari hitungan.
- **Ketahanan:**
  - denah diputar 2° diluruskan dengan skala tetap ≤ 0.5%; miring > 5° berakhir `needs_attention`;
  - input PDF dirender 300 dpi ke `input/raster.png`, dan editor/laporan memakainya;
  - `grid.json` identik pada run ulang.
- **Dependensi baru:** `scikit-image` dan `pymupdf`. PyMuPDF berlisensi AGPL; aman untuk pemakaian internal, tetapi perlu dicek sebelum distribusi (R-14).
- **Penyimpangan:**
  - title block tidak dideteksi (tidak ada data uji); hanya border kertas yang dikenali, dan area gambar mengabaikan piksel berwarna anotasi;
  - parser prompt Strata (T0) dipindah ke M6;
  - pemilihan halaman PDF di form (P1) belum dibuat; field `page` sudah dihormati bila dikirim lewat API;
  - ambang keliling bulatan 90% (spec: 60%), karena lingkaran palsu di Gatsu mencapai 81%.
- **Suite:** pytest 236 passed, 1 xfailed (runtime naik ke ~2 menit karena dua test server kini menjalankan tahap 1–2 asli); Vitest 144 passed; ruff, oxlint, dan build bersih.

---

## M6 — Strata Review (6 hari)

**Tujuan:** Strata meningkatkan hasil secara terukur tanpa pernah memperburuknya. Referensi: `05-llm-review.md`.

### Tugas
- [ ] Spike Strata (bila belum dilakukan di M0). **Status 2026-10-26: ditunda dari M0 karena Strata tidak aktif** (`benchmarks/reports/spike-strata.md`). Kerjakan paling awal di M6 mengikuti Task 6 plan M0.
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
