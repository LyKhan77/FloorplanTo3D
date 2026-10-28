# M7b — Denah Sintetis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Membuat set denah sintetis dari GT Gatsu: setiap varian adalah GT yang diubah secara acak lalu dirender sebagai gambar 2D bergaya CAD, sehingga GT-nya diketahui pasti. Set ini dijalankan lewat stage 0–5, lalu hasilnya dilaporkan terhadap kriteria PRD/01 §3: "≥ 70% varian mencapai ≥ 80% target".

**Architecture:**
- **`benchmarks/synth/perturb.py`.** Mengubah spec GT secara murni dan deterministik per seed:
  - jarak grid: lebar tiap bay dipetakan piecewise-linear;
  - cermin kiri-kanan;
  - hapus dinding partisi;
  - tambah partisi yang membelah satu ruang;
  - campuran tipe pintu;
  - geser tangga.

  Ruang dibentuk ulang dari dinding dengan `core.spec.rooms.rebuild_rooms`, memakai label GT yang ikut dipindahkan. Setelah itu `derive` dijalankan.
- **`benchmarks/synth/render.py`.** Menggambar spec ke raster dengan OpenCV dan Pillow, meniru gaya `plan.jpeg`:
  - garis ganda dinding: kontur union jejak dinding, dengan celah di setiap bukaan;
  - busur dan daun pintu;
  - kolom;
  - anak tangga;
  - bulatan grid magenta dan rantai dimensi;
  - label ruang;
  - anotasi MEP acak (teks dengan garis penunjuk);
  - simbol panel terisi.

  Render juga mengembalikan mm/px.
- **`benchmarks/run_synth_bench.py`.** Untuk tiap varian: render, `llm_items.run_stages`, selaraskan dengan `best_shift`, lalu `evaluate` dan menit koreksi. Kemudian lulus/gagal terhadap 80% target NFR, ditambah laporan JSON dan Markdown.

**Tech Stack:** Python 3.12, numpy, OpenCV, Pillow 13 (`ImageFont.load_default(size=…)`), Shapely 2, pydantic Spec, pytest.

**Spec:**
- `PRD/01-requirements.md` §3 kriteria 2 ("Denah sintetis … target ≥ 70% varian mencapai ≥ 80% target. Tidak memblokir MVP") dan NFR-AC-01…11;
- `ROADMAP.md` M7, tugas "Denah sintetis" (jenis perubahan dan unsur render);
- `PRD/12-risks.md` R-19: sintetis menguji ketahanan, bukan keragaman gaya nyata;
- `PRD/04-extraction.md` §2.2–2.3: grid dari bulatan dan label OCR; skala dari rantai dimensi di antara sumbu.

Branch: `m7b-synthetic` dari `main`.

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`;
  - test: `rtk uv run --env-file .env pytest -q -m "not strata"`, dan lint `rtk uv run ruff check benchmarks tests`.
- **Batas cakupan:**
  - tidak mengubah `core/`; M7b hanya alat ukur;
  - perbaikan ekstraktor yang ditemukan lewat set ini masuk milestone berikutnya dengan protokol gerbang (ledger ruling).
- **Hardcode:**
  - tidak ada hardcode Gatsu di `perturb`/`render` selain membaca `benchmarks/gatsu/gt_spec.json` sebagai bahan dasar;
  - semua angka acak berasal dari `numpy.random.default_rng(seed)`.
- **Konvensi grid:** sumbu vertikal paling kiri ber-offset 0 dan berlabel urut A, B, …; sumbu horizontal paling bawah ber-offset 0. Frame stage 2 berangkat dari sumbu-sumbu itu, sehingga frame GT dan prediksi sama.
- **Kriteria lulus varian:**
  - **"≥ 80% target":** setiap metrik `SUMMARY_KEYS` (`wall_recall`, `wall_precision`, `wall_iou`, `door_recall`, `room_match`, `gross_area_err`) memenuhi ≥ 0.8 × ambang `THRESHOLDS` (higher-is-better), atau ≤ ambang / 0.8 (lower-is-better);
  - run yang berhenti dihitung gagal.
- **Bahasa:**
  - laporan dalam bahasa Indonesia dengan istilah teknis Inggris;
  - commit dalam bahasa Inggris dan diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Bukaan yang keluar dari dindingnya setelah bay menyempit** (offset + lebar > panjang dinding). Pintu digeser masuk, atau dibuang bila dinding terlalu pendek. GT tidak boleh memuat pintu yang mustahil. Test di Task 1.
2. **Cermin.** Sisi buka pintu (`swing`) berbalik, `hinge` tetap, label sumbu tetap A dari kiri, dan semua koordinat tetap di frame yang sama. Test di Task 1.
3. **Partisi tambahan** tidak boleh memotong pintu, tangga, atau kolom, dan kedua ujungnya harus menyentuh dinding lain (tidak menggantung). Test di Task 1.
4. **Render bisa dibaca stage 2:** 6 sumbu vertikal A–F dan 3 horizontal terbaca, dengan galat skala ≤ 0.5 % pada varian tanpa perubahan. Test di Task 2.
5. **Teks render tidak ikut dicerminkan:** label dan dimensi selalu terbaca normal. Teks vertikal dimensi Y diputar 90°. Test di Task 2 lewat pembacaan OCR stage 2.

---

### Task 1: Perubahan GT (`perturb`)

**Files:**
- Create: `benchmarks/synth/__init__.py`, `benchmarks/synth/perturb.py`
- Test: `tests/benchmarks/test_synth.py`

**Interfaces:**
- Produces:
  - `load_base() -> Spec`: GT Gatsu.
  - `perturb(base: Spec, seed: int, ops: dict | None = None) -> tuple[Spec, dict]`: mengembalikan (GT varian, ringkasan perubahan). Isi `ops` (`None` = diundi dari seed):
    - `bays: list[int]`: lebar tiap bay sumbu vertikal lalu horizontal, kelipatan 500 mm, 0.75×–1.25× aslinya;
    - `mirror: bool`;
    - `drop_partitions: int`, 0–3: hanya dinding `partition`/`interior` tanpa bukaan;
    - `add_partitions: int`, 0–2;
    - `door_types: int`: jumlah pintu yang tipenya diundi ulang di antara `single_swing`, `double_swing`, `sliding`;
    - `stair_shift: tuple[int, int]` (mm).
  - Ruang dibentuk ulang dengan `rebuild_rooms(spec, labels)`. `labels` adalah `RoomLabel` dari `label_pos`/`name`/`type` ruang GT bernama, yang ikut dipindahkan. Setelah itu `derive`.
  - `meta.mm_per_px` belum diisi (diisi render).
- Pemetaan bay: titik di antara dua sumbu bergeser secara linear. Titik di luar sumbu terluar bergeser kaku mengikuti sumbu terluar. Tebal dinding, ukuran kolom, dan lebar pintu tetap. Offset pintu dihitung ulang dari pusat pintu yang dipetakan.

- [ ] **Step 1: Tulis test yang gagal:**

```python
def test_no_ops_keeps_geometry():          # perturb(base, 0, NO_OPS) -> walls/openings/columns equal base, rooms 48
def test_same_seed_same_spec():            # perturb(base, 7) == perturb(base, 7) (model_dump)
def test_bays_move_axes_and_walls_on_them():  # ops bays [5000]*5 + [7000]*2 -> axis offsets 0,5000,..,25000 / 0,7000,14000;
                                           # a GT wall end lying on axis B (x=6000) lies on x=5000
def test_mirror_flips_swing_keeps_frame(): # mirror -> every door swing flipped, hinge equal; axis A offset 0 still leftmost;
                                           # x of every wall end in [min_x, max_x] of base mirrored about the A..F span
def test_dropped_partitions_host_no_openings():  # drop 3 -> 3 fewer walls, none of them hosted an opening; rooms rebuilt
def test_added_partition_splits_a_room():  # add 1 -> one more wall (kind partition, thickness 100), both ends connected
                                           # (core.spec.derive.endpoint_connected), crosses no opening/stair/column; rooms +1
def test_openings_stay_on_their_walls():   # any seed 0..19: offset >= 0 and offset + width <= wall length for every opening
def test_variants_validate_without_errors():  # seeds 0..19: validate(spec) has no issue with severity "error"
```

- [ ] **Step 2: Jalankan, pastikan gagal.** `rtk uv run --env-file .env pytest -q tests/benchmarks/test_synth.py` → FAIL (modul belum ada).
- [ ] **Step 3: Implementasi** `perturb.py` sesuai Interfaces. Urutan operasi:
  1. bays;
  2. cermin;
  3. hapus partisi;
  4. tambah partisi;
  5. tipe pintu;
  6. tangga;
  7. `rebuild_rooms`;
  8. `derive`.

  Aturan per operasi:
  - **Tambah partisi:** pilih ruang ≥ 15 m² yang tidak memuat tangga. Tarik garis di centroid tegak lurus sisi panjang `minimum_rotated_rectangle`, potong ke ruang, lalu perpanjang tiap ujung setengah tebal dinding induk. Tolak bila garisnya memotong segmen pintu, jejak kolom, atau tangga; coba ruang berikutnya.
  - **Tipe pintu:** `double_swing` → `hinge="both"`; `single_swing` → `hinge` diundi `start`/`end`; `sliding` → `hinge=None`.
- [ ] **Step 4: Jalankan, pastikan lolos.** Lalu lint.
- [ ] **Step 5: Commit** `bench: synthetic plan variants from the Gatsu GT (perturb)`.

---

### Task 2: Render bergaya CAD

**Files:**
- Create: `benchmarks/synth/render.py`
- Test: `tests/benchmarks/test_synth.py` (tambahan)

**Interfaces:**
- Consumes: `perturb`, `load_base` (Task 1).
- Produces: `render(spec: Spec, seed: int, mm_per_px: float = 25.0) -> tuple[np.ndarray, Spec]`. Hasilnya (gambar BGR uint8, spec yang sama dengan `meta.mm_per_px = mm_per_px`). Margin halaman 150 px.
- Gaya (dari `floorplan/plan.jpeg`):

  | Unsur | Gaya |
  |---|---|
  | Latar | putih |
  | Dinding | hitam 1 px: kontur luar dan dalam dari union jejak dinding (`wall_footprint`) dikurangi persegi bukaan |
  | Pintu `single_swing` | daun garis + busur 90° |
  | Pintu `double_swing` | dua daun + dua busur |
  | Pintu `sliding` | dua persegi tipis sejajar |
  | Jendela | tiga garis sejajar di celah |
  | Kolom | `rect` outline; `h_section` simbol I |
  | Tangga | garis anak tangga sejumlah `risers` sepanjang flight, dengan panah arah naik |
  | Grid | bulatan magenta (BGR 255,0,255) radius 20 px dengan label hitam 22 px di bawah (A…) dan kiri (1…), garis tipis magenta dari bulatan ke tepi bangunan |
  | Dimensi | rantai cyan (BGR 255,255,0) dengan teks hitam 14 px per bay dan satu total; teks dimensi Y diputar 90° |
  | Label ruang | `name` di `label_pos`, 16 px |
  | Anotasi MEP | 3–8 blok teks acak (misalnya "ROUTE CABLE NYY 4x1Cx95mm") dengan garis penunjuk ke dalam bangunan |
  | Panel | 2–5 persegi hitam terisi 600×300 mm di dalam ruang acak |

- [ ] **Step 1: Tulis test yang gagal:**

```python
def test_render_draws_double_lines_and_door_gaps():  # base render: a 200 mm wall's centre pixel is white, its two
                                                    # faces have ink; the centre of D1's opening on its wall has no ink
def test_render_text_reads_upright():               # stage_grid on the s00 render: OCR reads "28000" and "12000"
@pytest.mark.slow
def test_stage2_reads_the_rendered_grid(tmp_path):  # run_stages(.., overrides stop after 02_grid) on base render:
    # vertical labels == list("ABCDEF"), horizontal == ["1","2","3"], abs(mm_per_px/25 - 1) <= 0.005
```

- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Implementasi** `render.py`. Teks memakai `PIL.ImageFont.load_default(size=…)` yang digambar pada canvas PIL, lalu dikonversi ke BGR. px dihitung dari mm dengan `x_px = margin + (x − min_x) / s` dan `y_px = margin + (max_y − y) / s` (Y ke atas).
- [ ] **Step 4: Jalankan, pastikan lolos** (termasuk `-m slow` untuk test stage 2). Bila stage 2 gagal membaca render, sesuaikan gaya render, bukan `core/`. Simpan contoh `benchmarks/reports/m7b-synth-s00.png` untuk pemeriksaan visual.
- [ ] **Step 5: Commit** `bench: CAD-style renderer for synthetic plans`.

---

### Task 3: Runner benchmark sintetis

**Files:**
- Create: `benchmarks/run_synth_bench.py`
- Test: `tests/benchmarks/test_synth.py` (tambahan)

**Interfaces:**
- Consumes:
  - `perturb`, `render` (Task 1–2);
  - `benchmarks.llm_items.run_stages`;
  - `benchmarks.run_augment_bench.best_shift`, `translate`, `SUMMARY_KEYS`;
  - `benchmarks.extraction_metrics.evaluate`, `THRESHOLDS`, `LOWER_IS_BETTER`;
  - `benchmarks.correction_effort.capped_minutes`.
- Produces:
  - `target_pass(metrics: dict, share: float = 0.8) -> tuple[bool, list[str]]`: lulus bila setiap `SUMMARY_KEYS` memenuhi `share` × target, ditambah daftar metrik yang gagal. Metrik yang hilang dihitung gagal.
  - `variants(n: int = 20) -> list[dict]`: `s00` = tanpa perubahan, lalu `s01…sNN` dengan seed 1…n; tiap varian memuat `ops` hasil undian.
  - `run_variant(v: dict, root: Path, stage_overrides: dict | None = None) -> dict`. Baris hasilnya memuat `id`, `ops`, `metrics`, `passed`, `failed_metrics`, `reason`, `correction_min`, `correction_min_bulk`, `shift_mm`, `seconds`.
  - CLI `python -m benchmarks.run_synth_bench --out benchmarks/reports/m7b-synth [--n 20] [--variants s00,s03]` menulis `.json` dan `.md` (tabel per varian, laju lulus, metrik yang paling sering gagal, rata-rata metrik, menit). Bila laju lulus < 70 %, laporan menyebut "target ≥ 70 % belum tercapai".

- [ ] **Step 1: Tulis test yang gagal:**

```python
def test_target_pass_uses_80_percent_of_nfr():
    ok = {"wall_recall": 0.76, "wall_precision": 0.76, "wall_iou": 0.68, "door_recall": 0.72, "room_match": 0.72,
          "gross_area_err": 0.0125}
    assert target_pass(ok) == (True, [])
    assert target_pass({**ok, "room_match": 0.71}) == (False, ["room_match"])
    assert target_pass({**ok, "gross_area_err": 0.013})[1] == ["gross_area_err"]
def test_variants_start_with_the_unchanged_render():  # variants(3)[0]["id"] == "s00" and its ops are the no-op set; ids s01..s03
def test_stopped_variant_fails_with_reason(tmp_path): # stage 2 override raising -> passed False, "stage 2 failed" in reason,
                                                      # correction_min == redraw minutes of that variant's GT
```

- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Implementasi** `run_synth_bench.py`. GT varian = spec hasil `render` (sudah ber-`mm_per_px`). Prediksi diselaraskan dengan `best_shift` seperti augmentasi. Gambar disimpan ke `root/<id>/input.png` agar bisa diperiksa.
- [ ] **Step 4: Jalankan, pastikan lolos.** Lalu lint.
- [ ] **Step 5: Commit** `bench: synthetic-plan benchmark runner and NFR-share pass rule`.

---

### Task 4: Jalankan set, laporan, status

**Files:**
- Create: `benchmarks/reports/m7b-synth.json`, `.md`, `benchmarks/reports/m7b-synth-s00.png` dan satu contoh varian berubah (`m7b-synth-sNN.png`)
- Modify: `ROADMAP.md` (centang tugas "Denah sintetis", tambah "Status M7b"), `PRD/01-requirements.md` §3 bila definisi "≥ 80% target" perlu ditulis

- [ ] **Step 1:** `rtk uv run --env-file .env python -m benchmarks.run_synth_bench --out benchmarks/reports/m7b-synth --n 20`. Expected: 21 baris; laju lulus dan metrik yang paling sering gagal tercatat.
- [ ] **Step 2: Analisis singkat di laporan.**
  - Bandingkan `s00` (render tanpa perubahan) dengan Gatsu asli (`benchmarks/reports/m7a3-gatsu.json`). Selisihnya adalah efek gaya render.
  - Bandingkan `s01…s20` dengan `s00`. Selisihnya adalah efek perubahan geometri.
  - Sebutkan 3 mode gagal teratas sebagai kandidat perbaikan umum untuk milestone berikutnya.
- [ ] **Step 3: Suite penuh** (Python, ruff) hijau.
- [ ] **Step 4: ROADMAP "Status M7b".** Isinya:
  - laju lulus terhadap target ≥ 70 %;
  - rata-rata metrik dan menit koreksi;
  - batasan R-19: gaya render adalah asumsi kita sendiri.
- [ ] **Step 5: Commit** `docs: M7b synthetic-plan results and status`.
