# M5b — Tahap 3: Ekstraksi Geometri (masking, kondisi existing, tangga, dinding, kolom, pintu, keyakinan, sweep) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tahap 3 pipeline menghasilkan K kandidat `elements.json` (dinding, kolom, bukaan, tangga) dari `page.png` + `grid.json`, dan benchmark Gatsu mengukur akurasinya terhadap GT, lengkap dengan ambang minimum yang dijaga test regresi.

**Architecture:**
- Semua kode tahap 3 ada di `core/extraction/geometry/`, satu modul per tanggung jawab:
  - `masks.py`;
  - `strokes.py`;
  - `stairs.py`;
  - `walls_s2.py`, `walls_s1.py`, `postprocess.py`;
  - `columns.py`, `doors.py`;
  - `confidence.py`;
  - `candidate.py` (rakit satu kandidat);
  - `sweep.py` (K kandidat paralel).
- Detektor bekerja di **piksel kerja**. Kandidat dikonversi ke **mm spec** lewat `grid.json.px_to_mm` (kerja) saat dirakit.
- `elements_to_spec()` mengubah kandidat menjadi `Spec` parsial (tanpa ruang). Dengan begitu benchmark M5a sudah bisa menilai dinding, pintu, tangga, dan IoU sebelum tahap 4–5 (M5c) ada.

**Tech Stack:** Python 3.12, OpenCV 5 (HoughLinesP, morfologi, kontur), scikit-image (skeletonize), NumPy, Shapely, `concurrent.futures.ProcessPoolExecutor`, pytest. Dashboard: React + Carbon g100, Vitest.

**Spec:**
- `PRD/04-extraction.md` §3 (3.1–3.7) dan tabel "Mode Gagal";
- `PRD/01-requirements.md` FR-EX-05…07, FR-EX-09, FR-EX-11, FR-EX-15, FR-EX-16, FR-EX-17 (bagian pilaster), NFR-AC-02…06, NFR-AC-08, NFR-AC-10, NFR-PF-01, NFR-RL-06;
- `PRD/03-layout-spec.md` (model `Wall`/`Column`/`Opening`/`Stair`);
- `benchmarks/gatsu/NOTES.md`;
- `ROADMAP.md` M5.

Branch: `m5-cv` (lanjutan M5a). M5c (tahap 4–5, carry-over, style profile, tab Review) menyusul setelah plan ini.

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`;
  - test dijalankan dengan `rtk uv run --env-file .env pytest -q`;
  - test yang memakai gambar Gatsu atau sweep penuh ditandai `@pytest.mark.slow`.
- **Determinisme (NFR-RL-06):**
  - iterasi selalu atas daftar terurut;
  - hasil `ProcessPoolExecutor` diurutkan menurut indeks kandidat;
  - JSON ditulis dengan `core.extraction.stages.write_json` (key terurut, 4 desimal).
- **Koordinat:**
  - detektor memakai piksel kerja dan `mm_per_px_work` (`s`) dari `grid.json`;
  - `elements.json` dalam **mm spec** (int, dibulatkan), dikonversi lewat `grid.json.px_to_mm` (kerja);
  - semua ambang ditulis dalam mm dan dikonversi dengan `s`.
- **Nilai dari spec, salin persis:**
  - snap orientasi ±1.5°;
  - pairing S2: `g` ∈ [`t_min`, `t_max`], overlap ≥ 60%;
  - pasangan sebagian ≤ 1500 mm;
  - snap ujung ke sumbu grid ≤ 150 mm;
  - gap ≤ 600 mm ditutup; 600–3000 mm yang diapit ujung rapi menjadi kandidat `opening`;
  - hapus segmen < 300 mm yang tidak terhubung;
  - `kind`: `exterior` di kontur luar, `interior` bila tebal ≥ 120 mm, selain itu `partition`;
  - kolom: luas ekuivalen 150–800 mm persegi, prioritas ≤ 300 mm dari perpotongan grid;
  - busur pintu: cakupan 60°–100°, radius 500–1300 mm; double: radius ±15%;
  - flight tangga: ≥ 5 segmen sejajar, panjang ±10% (800–2500 mm), jarak 220–350 mm dengan CV ≤ 15%; bordes ≤ 1.5 × lebar flight;
  - arah naik: teks `stair_dir` + panah; bila tidak ada, menuju bordes (keyakinan 0.5); bila tetap tidak jelas, keyakinan 0.3 dan dicatat di `issues`;
  - kondisi existing: elemen yang ditunjuk `proposed` (lewat leader, atau ≤ 1000 mm tanpa leader) tidak dimodelkan dan dicatat `info`; `dismantle` → `evidence.note = "to_be_dismantled"`;
  - elemen dengan `confidence < 0.6` masuk antrean review;
  - sweep: S1/S2 × Sauvola k {0.2, 0.34} × `t_min` {80, 150} × `t_max` {450} × `L_fix` {0, 5} (`L_fix` dikalikan faktor upscale); dibatasi `settings.sweep_max_candidates` (default 12); worker = `os.cpu_count() − 1`.
- **Penyimpangan dari spec (dicatat di ROADMAP):**
  - S2 mendeteksi stroke dengan **skeleton + `cv2.HoughLinesP`**, bukan LSD. Spike pada Gatsu: LSD memberi dua tepi untuk setiap garis 4 px (empat segmen per dinding), sedangkan skeleton memberi satu garis tengah per stroke (x = 1863 / 1875, jarak 12 px = 155 mm);
  - jendela (P1, §3.5) tidak dibuat; GT Gatsu juga tanpa jendela;
  - tangga hanya untuk flight lurus;
  - kolom bulat tidak dideteksi; Gatsu hanya punya H dan persegi.
- **Warna anotasi:** piksel jenuh (HSV S > 60, dari tahap 1) dibuang sebelum deteksi dinding. Di Gatsu, grid, dimensi, dan simbol MEP digambar berwarna; dinding hitam.
- **Dependensi:** tidak ada yang baru.
- **Kualitas:** `rtk uv run ruff check .` bersih; dashboard `npm test`, `npm run lint`, dan `npm run build` hijau.

## Review Focus

1. **Teks yang menempel ke dinding.** Harapan: masking memakai dilasi minimal (2 px), dan gabung kolinear menutup celahnya sehingga dinding tetap satu segmen. Test: Task 7 `test_text_gap_closed_by_collinear_merge`.
2. **Jalur kabel bergaris rapat** (Gatsu, di bawah Battery/AHU/MDF ke Capasitor Room). Harapan: tidak menjadi dinding berkeyakinan ≥ 0.6. Test: Task 10 `test_cable_trench_has_no_confident_wall`.
3. **Garis anak tangga.** Harapan: masuk `stair_mask`, tidak menjadi partisi. Test: Task 4 `test_treads_become_a_flight_not_walls`.
4. **Pintu tanpa busur** (hanya celah 600–3000 mm). Harapan: `opening` berkeyakinan rendah (< 0.6). Test: Task 9 `test_gap_without_arc_is_low_confidence_opening`.
5. **Simbol MEP terisi** (panel/rack/baterai di Battery Room). Harapan: masuk `symbol_mask`, tidak menjadi dinding S1/S2. Test: Task 2 `test_filled_symbol_masked` dan Task 6 `test_s1_ignores_filled_symbol`.

---

### Task 1: Kontrak `elements.json`, `elements_to_spec`, mask warna tahap 1, benchmark `--elements`

**Files:**
- Create: `core/extraction/geometry/__init__.py`, `core/extraction/geometry/elements.py`
- Modify:
  - `core/extraction/preprocess.py`: `PreprocessResult.colour` (uint8 0/255, frame kerja);
  - `core/extraction/stages.py`: `stage_preprocess` menulis `colour.png`;
  - `benchmarks/run_extraction_bench.py`: mode `--elements <elements.json> --grid <grid.json>`.
- Test: `tests/extraction/geometry/test_elements.py` (buat juga `tests/extraction/geometry/__init__.py`)

**Interfaces:**
- Produces:
  - Skema `elements.json`:
    - `walls`: `[{a: [x, y], b: [x, y], thickness, kind, strategy: "S1" | "S2" | "post", confidence, evidence}]`;
    - `columns`: `[{center, size: [w, d], shape: "rect" | "h_section", rotation, kind: "structural" | "pilaster", confidence, grid_ref: [vx, hy] | null}]`;
    - `openings`: `[{wall: <indeks di walls>, category: "door", offset, width, door_type, hinge, swing, confidence, evidence}]`;
    - `stairs`: `[{flights: [{start, end, width, risers}], landings: [[[x, y], …]], confidence, direction_source: "text" | "landing" | "unknown"}]`;
    - `issues`: `[{code, severity, message, at: [x, y] | null}]`;
    - `params`: parameter kandidat.

    Semua koordinat dalam mm int.
  - `to_mm(px_to_mm: list[float], u: float, v: float) -> tuple[int, int]` (dibulatkan).
  - `elements_to_spec(elements: dict, grid_doc: dict, project_id: str = "extract") -> Spec`:
    - ID sementara: `W1…`, `C1…`, `D1…`, `S1…` sesuai urutan;
    - `wall` (indeks) dipetakan ke `wall_id`;
    - `meta`: `px_to_mm = grid_doc["px_to_mm_original"]`, `mm_per_px`, dan `scale_source`;
    - grid axes dari `grid_doc["axes"]`;
    - `rooms = []`;
    - provenance `source: "cv"` dengan `confidence`;
    - elemen yang ditolak validasi model (mis. panjang 0) dibuang.
  - Benchmark `--elements`: memanggil `wall_metrics`, `door_metrics`, `stair_metrics_cmp`, dan `wall_iou` pada spec parsial. `scale_metrics` diambil dari grid.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_elements_to_spec_maps_ids_and_mm`: elements buatan berisi 2 dinding, 1 pintu di dinding indeks 1, 1 kolom, dan 1 tangga. Harapan:
    - `spec.openings[0].wall_id == "W2"`;
    - koordinat sama persis dengan input;
    - `spec.walls[0].provenance.confidence == 0.8`;
    - `spec.rooms == []`;
    - meta `px_to_mm == grid["px_to_mm_original"]`.
  - `test_to_mm_rounds_with_work_affine`: `to_mm([12.5, 0, -100, 0, -12.5, 500], 10, 10) == (25, 375)`.
  - `test_preprocess_exports_colour_mask` (slow): `preprocess(plan.jpeg).colour` berukuran sama dengan `page`, memuat piksel bulatan grid magenta (pusat bulatan A ± 2r bernilai 255), dan dinding hitam bernilai 0.
  - `test_cli_elements_mode` (tmp_path): elements dari GT (dinding/pintu/kolom/tangga GT dikonversi ke skema) → `wall_recall == 1.0` di JSON keluaran.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_elements.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_elements.py tests/extraction/test_preprocess.py tests/extraction/test_stages.py`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): elements contract, partial spec for benchmarking, colour mask artefact`

---

### Task 2: Masking anotasi (teks, warna, di luar gambar, leader + titik tunjuk, simbol terisi, hatch)

**Files:**
- Create: `core/extraction/geometry/masks.py`
- Test: `tests/extraction/geometry/test_masks.py`

**Interfaces:**
- Consumes: `ocr.json` (item + `cls`), `bin.png`, `colour.png`, `meta.drawing_bbox`.
- Produces:
  - `Masks = {clean: ndarray (biner hasil masking), symbol: ndarray, hatch: ndarray, pointers: [{cls: "proposed" | "dismantle" | "annotation", text_bbox, point: [u, v]}]}`.
  - `build_masks(binary, colour, ocr_items: list[dict], drawing_bbox, s: float) -> Masks`. Urutan PRD §3.1:
    1. Bbox teks semua kelas kecuali `grid_label` diisi 0 dengan dilasi 2 px.
    2. Piksel `colour` (didilasi 1 px) diisi 0.
    3. Di luar `drawing_bbox` + margin 300 mm diisi 0. Ini hanya untuk deteksi; artefak asli tidak diubah.
    4. **Leader:** segmen `HoughLinesP` pada skeleton `binary` asli dengan panjang ≥ 300 mm, yang salah satu ujungnya ≤ 6 px dari bbox teks `annotation`/`proposed`/`dismantle`. Segmen dihapus (dilukis 0 selebar 3 px), dan ujung lainnya dicatat sebagai `pointers`.
    5. **`symbol_mask`:** komponen hasil opening `clean` dengan kernel persegi `2·w_stroke + 1` (`w_stroke` = median 2× distance transform pada skeleton). Komponen masuk bila luasnya ≥ (300 mm)² / s² dan rasio aspek bbox < 4. Komponen itu dihapus dari `clean`.
    6. **`hatch_mask`:** grid sel 600 mm. Sel bertanda hatch bila memuat ≥ 6 segmen Hough pendek (< 600 mm) yang sejajar (±10°). Sel tetangga dihubungkan dengan closing. `hatch_mask` tidak menghapus apa pun.
  - `stroke_width(binary) -> float`.

- [ ] **Step 1: Tulis test yang gagal**

  Semua test kecuali yang terakhir memakai gambar sintetis 600×400, `s = 12.5`.
  - `test_text_masked_with_small_dilation`: garis dinding lewat 5 px di samping bbox teks → garis tetap ada di `clean`; isi bbox = 0.
  - `test_colour_and_outside_removed`.
  - `test_leader_removed_and_pointer_recorded`: teks "PROPOSED" + garis diagonal 400 mm dari pojok bbox → garis hilang, dan `pointers[0].point` ≈ ujung jauh ± 2 px dengan `cls proposed`.
  - `test_filled_symbol_masked`: persegi hitam 40×40 px di dalam "ruang" (4 dinding garis ganda) → masuk `symbol`, hilang dari `clean`, dan keempat dinding garis ganda tetap utuh.
  - `test_hatch_marks_dense_short_parallel_lines`: 20 garis pendek sejajar rapat → `hatch` > 0 di area itu; satu dinding panjang tidak bertanda.
  - `test_gatsu_masks` (slow):
    - teks "R. MEETING" tidak ada lagi di `clean` (kepadatan tinta bbox = 0);
    - blob Battery Room (piksel asli ≈ (870, 520)) masuk `symbol`;
    - `pointers` memuat ≥ 2 item `proposed`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_masks.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): annotation masking - text, colour, leaders with pointers, filled symbols, hatch`

---

### Task 3: Stroke garis (skeleton, Hough, snap orientasi, gabung fragmen, perbaikan berarah)

**Files:**
- Create: `core/extraction/geometry/strokes.py`
- Test: `tests/extraction/geometry/test_strokes.py`

**Interfaces:**
- Produces:
  - `Stroke = {orient: "h" | "v" | "o", c: float, a: float, b: float, p0: [u, v], p1: [u, v], width: float}`:
    - untuk `h`: `c` = y, interval [a, b] di x;
    - untuk `v`: `c` = x, interval [a, b] di y;
    - `o` (miring) hanya memakai `p0`/`p1`;
    - `width` = tebal stroke rata-rata (2 × distance transform pada skeleton).
  - `directional_close(binary, l_fix: int) -> ndarray`: closing 1-D horizontal OR vertikal sepanjang `l_fix` px; `l_fix = 0` berarti tanpa perubahan.
  - `extract_strokes(clean, l_fix: int, s: float, axis_angle_deg: float = 0.0) -> list[Stroke]`:
    1. skeleton dari `directional_close(clean, l_fix)`;
    2. `HoughLinesP(rho=1, theta=π/360, threshold=15, minLineLength=max(12, 150 mm / s), maxLineGap=3)`;
    3. snap ke `h`/`v` bila ≤ 1.5° dari sumbu grid, selebihnya `o`;
    4. gabung fragmen kolinear: offset ≤ 1.5 px dan gap ≤ 3 × median `width`;
    5. `width` diukur dari biner **asli**, bukan hasil closing.

    Hasil diurutkan (orient, c, a).

- [ ] **Step 1: Tulis test yang gagal**
  - `test_double_line_wall_gives_two_strokes`: dua garis 4 px berjarak 12 px, panjang 300 px → dua stroke `v` dengan `c` ±1 dari pusat garis, panjang ≥ 290, dan `width` ≈ 4 ± 1.
  - `test_fragments_merged_and_jpeg_breaks_fixed`: garis dengan 3 putus 2 px → satu stroke (dengan `l_fix` 5, juga dengan 0 karena gap ≤ 3w).
  - `test_slanted_kept_separately`: garis 20° → `orient "o"`.
  - `test_directional_close_keeps_gap_between_wall_lines`: dua garis berjarak 6 px tidak menyatu setelah `directional_close(…, 5)`.
  - `test_gatsu_w50_strokes` (slow): stroke `v` di x ≈ 1863 dan 1875 (piksel kerja), masing-masing ±2, menutup y 227–730 ± 10.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_strokes.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): skeleton strokes with grid-aligned snapping and fragment merge`

---

### Task 4: Tangga (flight, tanjakan, arah naik, bordes, `stair_mask`, simbol lift)

**Files:**
- Create: `core/extraction/geometry/stairs.py`
- Test: `tests/extraction/geometry/test_stairs.py`

**Interfaces:**
- Consumes: `Stroke` (Task 3), item OCR `stair_dir`.
- Produces:
  - `find_flights(strokes, s) -> list[dict]`. Kelompok ≥ 5 stroke `h` (atau ≥ 5 stroke `v`) yang:
    - panjangnya sama ±10% dalam [800, 2500] mm;
    - intervalnya saling overlap ≥ 80%;
    - jarak berurutan dalam [220, 350] mm dengan CV ≤ 15%.

    Flight = `{tread_axis: "h" | "v", lines: [Stroke], width_mm, risers = len(lines) + 1, rect: [u0, v0, u1, v1]}`. Kelompok dibentuk dengan menyapu stroke terurut menurut `c`.
  - `find_landings(flights, clean, s) -> list[polygon_px]`: area persegi di antara ujung dua flight yang berdekatan (≤ 1.5 × lebar), dibatasi garis tinta terdekat.
  - `direction(flight, stair_texts, landings, binary) -> tuple[start_px, end_px, source, confidence]`:
    1. Teks `stair_dir` ≤ 1.5 × lebar flight dari rect: polyline jalan (stroke tipis memanjang di tengah flight, ujung berkepala panah = blob segitiga) menentukan arah. `NK`/`NAIK`/`UP` = searah panah; `TR`/`TURUN`/`DN`/`DOWN` = berlawanan. Hasilnya `source "text"`, confidence 0.9. Tanpa panah: teks ada di ujung **awal** flight.
    2. Bila tidak ada teks: menuju bordes, `source "landing"`, confidence 0.5.
    3. Selain itu: arah sumbu positif, `source "unknown"`, confidence 0.3, ditambah issue `{code: "STAIR_DIR", severity: "warning"}`.
  - `stair_mask(flights, shape) -> ndarray` = rect flight didilasi 1 × jarak antar-garis.
  - `stairs_from(flights, landings, …) -> list[dict]` dalam format `elements.stairs` (piksel; dikonversi di Task 10). Flight yang berbagi bordes menjadi satu `stair`.
  - `lift_boxes(clean, s) -> list[rect_px]`: persegi 1500–3000 mm dengan dua diagonal (garis `o` ±45° dari pojok ke pojok).

- [ ] **Step 1: Tulis test yang gagal**
  - `test_treads_become_a_flight_not_walls` (sintetis, `s = 12.5`):
    - 14 garis horizontal tipis 2 px, panjang 1200 mm (96 px), berjarak 280 mm (22.4 px);
    - harapan: satu flight, `risers 15`, `width_mm` 1200 ± 25;
    - `stair_mask` menutup semua garis;
    - `extract_strokes(clean & ~stair_mask)` tidak memuat stroke di area itu.
  - `test_direction_from_nk_text_and_landing_fallback`:
    - flight vertikal + teks "NK" di ujung bawah → `start` di bawah, `source text`;
    - tanpa teks tetapi ada bordes di atas → menuju atas, `source landing`, confidence 0.5;
    - tanpa keduanya → confidence 0.3 dan satu issue `STAIR_DIR`.
  - `test_irregular_spacing_rejected`: CV 30% → tidak ada flight.
  - `test_gatsu_stair_s1` (slow): dari stroke Gatsu (setelah mask Task 2):
    - ≥ 2 flight di sekitar S1 (rect piksel asli x 205–420, y 180–330);
    - masing-masing `risers` 15 ± 1;
    - flight barat naik ke utara (`source text`, dari "NK" + walking line);
    - lift box ditemukan di sekitar (300, 250) piksel asli.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_stairs.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): straight stair flights, risers, up direction, landings, stair mask, lift box`

---

### Task 5: Dinding S2 (garis ganda) dengan pairing berbasis interval

**Files:**
- Create: `core/extraction/geometry/walls_s2.py`
- Test: `tests/extraction/geometry/test_walls_s2.py`

**Interfaces:**
- Consumes: `Stroke` (Task 3).
- Produces:
  - `RawWall = {orient, c, a, b, p0, p1, thickness_mm, strategy, evidence: {pair_overlap, partial_mm, from: [stroke idx]}}` (piksel, kecuali `thickness_mm`).
  - `pair_strokes(strokes, s, t_min_mm, t_max_mm) -> list[RawWall]`. Algoritmanya:

    ```
    tiap stroke punya daftar interval bebas (awalnya [a, b])
    kandidat = semua pasangan (i, j) dengan orient sama (h atau v), c_j > c_i, g = c_j - c_i ∈ [t_min/s, t_max/s],
               dan overlap interval asli ≥ 60% dari yang lebih pendek
    urutkan kandidat menurut (g, c_i, a_i)  # pasangan terdekat dulu: skin lebih dulu daripada skin+rail
    untuk tiap kandidat: overlap = irisan interval bebas i dan j
        bila panjang overlap ≥ 300 mm / s: buat dinding (c = c_i + g/2, [overlap], thickness = g·s),
        lalu hapus overlap dari interval bebas kedua stroke
    ```

    Stroke `o` dipasangkan dengan cara sama pada koordinat yang diputar ke arah stroke, dengan toleransi sudut 1.5°.
  - `unpaired_partitions(strokes, free_intervals, s, median_width) -> list[RawWall]`: sisa interval bebas sepanjang ≥ 1000 mm dengan `width` ≥ 2 × median → dinding `partition` dengan tebal `defaults.wall_thickness` (100 mm bila tidak ada).
  - `partial_pairs(walls, strokes_free, s) -> list[RawWall]`: dua dinding segaris (c ±2 px, tebal ±20%) yang dipisah celah ≤ 1500 mm, dan satu sisinya kontinu melewati celah itu → disambung dengan `evidence.partial_mm = gap`.

- [ ] **Step 1: Tulis test yang gagal** (sintetis `s = 12.5`; garis 4 px)
  - `test_pairs_double_line_with_measured_thickness`: dua garis berjarak 12 px → satu dinding, thickness 150 ± 13, `c` di tengah.
  - `test_long_line_pairs_with_several_partners`: satu garis panjang 0–600 px berpasangan dengan dua garis pendek di sisi berlawanan (0–250 dan 350–600) → dua dinding, dan tidak ada interval yang dipakai dua kali.
  - `test_three_parallel_lines_pair_nearest_first`: garis di c = 0, 9, 19 px (skin 110 mm + rail) → pasangan (0, 9), lalu garis 19 tetap bebas, atau berpasangan dengan garis lain bila ada. Tidak pernah ada pasangan (0, 19) selama 9 masih bebas.
  - `test_partial_side_missing_up_to_1500mm`: satu sisi hilang 1000 mm di tengah → satu dinding dengan `partial_mm ≈ 1000`; hilang 2000 mm → dua dinding.
  - `test_thick_unpaired_line_is_partition`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_walls_s2.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): S2 double-line walls with interval pairing, partitions and partial pairs`

---

### Task 6: Dinding S1 (solid/poche)

**Files:**
- Create: `core/extraction/geometry/walls_s1.py`
- Test: `tests/extraction/geometry/test_walls_s1.py`

**Interfaces:**
- Produces: `solid_walls(clean, symbol_mask, s, t_min_mm) -> list[RawWall]`. Langkahnya:
  1. opening kernel persegi `k = round(t_min / s)`, setelah `symbol_mask` dihapus;
  2. skeleton;
  3. vektorisasi dengan `HoughLinesP` pada skeleton, lalu disederhanakan (`cv2.approxPolyDP`, ε = 0.5 × tebal);
  4. tebal per segmen = median distance transform di sepanjang skeleton × 2 × `s`.

  `strategy "S1"`. Format sama dengan `RawWall`.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_s1_poche_wall`: persegi panjang hitam 20×300 px (`s = 10`) → satu dinding tebal 200 ± 20 mm, panjang ≥ 2700 mm.
  - `test_s1_ignores_thin_double_lines`: dinding garis ganda 4 px → kosong (`t_min` 80 mm = 8 px).
  - `test_s1_ignores_filled_symbol`: blob yang ada di `symbol_mask` → kosong.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_walls_s1.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): S1 solid wall strategy`

---

### Task 7: Pasca-proses dinding dan kondisi existing

**Files:**
- Create: `core/extraction/geometry/postprocess.py`
- Test: `tests/extraction/geometry/test_postprocess.py`

**Interfaces:**
- Consumes: `RawWall` (Task 5/6), `grid.json` axes (px kerja), `pointers` (Task 2).
- Produces:
  - `merge_collinear(walls, s, max_gap_mm=600) -> tuple[list[RawWall], list[dict]]`. Mengembalikan (dinding, `gap_openings`). Dinding segaris (c ±2 px, tebal ±25%, orient sama) digabung bila gap ≤ 600 mm. Gap 600–3000 mm yang diapit ujung rapi (kedua ujung tidak menyentuh dinding lain) dicatat sebagai `gap_openings: [{wall_index, offset_mm, width_mm}]` dan kedua dinding disambung. Di luar itu dibiarkan.
  - `snap_to_grid(walls, axes_px, s, tol_mm=150) -> list[RawWall]`: garis tengah (`c`) dan ujung (`a`/`b`) di-snap ke sumbu grid sejenis bila ≤ 150 mm.
  - `join_ends(walls, s) -> list[RawWall]`: ujung diperpanjang atau dipotong ke garis tengah dinding tegak lurus terdekat bila jaraknya ≤ tebal dinding itu, membentuk L/T.
  - `drop_short(walls, s, min_mm=300) -> list[RawWall]`: membuang dinding < 300 mm yang kedua ujungnya tidak menyentuh dinding lain.
  - `classify_kind(walls, s) -> list[RawWall]`:
    - `exterior` bila dinding berada di kontur luar union tapak dinding (buffer tebal/2, ≤ tebal dari batas luar);
    - `interior` bila tebal ≥ 120 mm;
    - selain itu `partition`.
  - `apply_existing(walls, symbols, pointers, s) -> tuple[list[RawWall], list[dict]]`. Mengembalikan (dinding, issues):
    - dinding yang ditunjuk `pointers` `proposed` (titik ≤ tebal + 100 mm dari dinding), atau berjarak ≤ 1000 mm dari bbox teks `proposed` yang tidak punya leader, dibuang, dengan issue `{code: "EXISTING_PROPOSED", severity: "info"}`;
    - yang ditunjuk `dismantle` mendapat `evidence.note = "to_be_dismantled"`.
  - `postprocess(raw, axes_px, pointers, s) -> tuple[list[RawWall], list[dict], list[dict]]` = merge → snap → join → drop → classify → existing. Mengembalikan (dinding, gap_openings, issues).

- [ ] **Step 1: Tulis test yang gagal** (sintetis, `s = 12.5`)
  - `test_text_gap_closed_by_collinear_merge`: dua dinding segaris dengan celah 400 mm → satu dinding. Celah 900 mm dengan ujung rapi → satu dinding + satu `gap_opening` lebar 900 ± 15. Celah 3500 mm → dua dinding.
  - `test_snap_and_join_make_l_and_t`: dinding vertikal yang ujungnya kurang 80 mm dari dinding horizontal → ujung tepat di garis tengah dinding horizontal. Garis tengah 100 mm dari sumbu grid → di-snap ke sumbu.
  - `test_short_isolated_dropped_connected_kept`.
  - `test_kind_classification`: kotak 4 dinding tebal 150 + satu partisi 100 di dalam → 4 `exterior` + 1 `partition`. Dinding dalam 150 → `interior`.
  - `test_proposed_wall_skipped_dismantle_kept`: pointer `proposed` di atas dinding A → A hilang + issue info. Pointer `dismantle` di dinding B → B tetap dengan note.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_postprocess.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): wall post-processing (merge, snap, L/T joins, kinds) and existing-condition rules`

---

### Task 8: Kolom dan pilaster

**Files:**
- Create: `core/extraction/geometry/columns.py`
- Test: `tests/extraction/geometry/test_columns.py`

**Interfaces:**
- Produces:
  - `find_columns(binary_clean, axes_px, walls, s) -> list[dict]`, dalam format `elements.columns` (piksel; dikonversi di Task 10). Kandidat:
    - **(a) blob terisi** dengan luas ekuivalen (√luas) 150–800 mm → `rect`;
    - **(b) bentuk H:** komponen tertutup di jendela 1000 mm sekitar perpotongan grid, dengan bbox 150–800 mm per sisi dan rasio isi bbox 0.35–0.8 → `h_section`, size = bbox;
    - **(c) persegi berongga:** kontur dengan 4 sudut (`approxPolyDP`), sisi 150–800 mm, dan bagian dalam memuat simbol → `rect`.
  - Prioritas: kandidat ≤ 300 mm dari perpotongan grid diterima dengan `grid_ref` dan confidence 0.9. Kandidat di luar perpotongan hanya diterima bila skor bentuk ≥ 0.8 (confidence 0.6).
  - `find_pilasters(binary_clean, walls, s) -> list[dict]`: persegi berongga kecil (sisi 150–1200 mm) yang menempel ke dinding `exterior` di luar kontur bangunan, atau pada pita luar. Hasilnya `kind "pilaster"`, `rect`.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_h_column_at_grid_crossing` (sintetis): simbol H 40×40 px di perpotongan sumbu → `h_section`, `grid_ref` benar, size 520 ± 40 mm (`s = 13`).
  - `test_filled_blob_off_grid_needs_high_shape_score`.
  - `test_pilaster_on_exterior_band`.
  - `test_gatsu_structural_columns` (slow): ≥ 16 dari 18 kolom `structural` GT punya kolom terdeteksi ≤ 300 mm dari pusatnya. Jumlah pilaster dilaporkan, tanpa ambang.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_columns.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): columns (H, filled, hollow) near grid crossings and pilasters`

---

### Task 9: Pintu (busur, engsel, ayun, double, celah tanpa busur)

**Files:**
- Create: `core/extraction/geometry/doors.py`
- Test: `tests/extraction/geometry/test_doors.py`

**Interfaces:**
- Consumes: skeleton `clean` dikurangi piksel stroke lurus (Task 3), dinding pasca-proses, dan `gap_openings` (Task 7).
- Produces:
  - `find_arcs(skeleton_curves, s) -> list[{center, radius_px, start_angle, end_angle, residual}]`. Komponen skeleton lengkung difit lingkaran (algebraic/Kåsa). Busur diterima bila cakupan 60°–100°, radius 500–1300 mm, dan residu RMS ≤ 0.08 × radius.
  - `doors_from_arcs(arcs, walls, s) -> list[dict]`:
    - engsel = pusat busur, diproyeksikan ke dinding terdekat (≤ tebal + 100 mm);
    - lebar = radius;
    - offset dari a dinding dihitung ke sisi terdekat;
    - `hinge` = ujung bukaan tempat engsel, relatif a→b (`start`/`end`);
    - `swing` = sisi dinding tempat busur berada (`left` = kiri a→b);
    - dua busur dengan pusat di kedua sisi celah yang sama, radius ±15%, dan saling menghadap → satu pintu `double_swing`, `hinge "both"`, lebar = jarak antar-engsel;
    - confidence dari residu, kecocokan radius dengan celah, dan adanya daun (garis dari engsel ke ujung busur).
  - `doors_from_gaps(gap_openings, binary, walls, s) -> list[dict]`: celah tanpa busur. Bila ada garis tipis sejajar di dalam celah → `sliding`, confidence 0.55; selain itu `opening`, confidence 0.4.
  - Pintu yang tumpang tindih dengan pintu busur (> 50% lebar) dari celah dibuang.

- [ ] **Step 1: Tulis test yang gagal** (sintetis `s = 12.5`)
  - `test_single_swing_door_hinge_and_swing`: dinding horizontal a→b ke timur, busur 90° radius 900 mm, engsel di ujung barat celah, busur di utara (kiri a→b) → `single_swing`, `hinge "start"`, `swing "left"`, width 900 ± 30, offset tepat ±30.
  - `test_double_door_from_two_facing_arcs` → `double_swing`, `hinge both`, width ≈ 1800.
  - `test_gap_without_arc_is_low_confidence_opening` → `opening`, confidence < 0.6.
  - `test_arc_outside_radius_range_rejected`: radius 1600 mm → tidak ada pintu.
  - `test_gatsu_doors` (slow): `door_metrics` (`elements_to_spec`) mencatat `door_recall` di ledger. Ambang di Task 13.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_doors.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): doors from swing arcs (hinge, swing, double) and arc-less gaps`

---

### Task 10: Keyakinan elemen dan perakitan satu kandidat

**Files:**
- Create: `core/extraction/geometry/confidence.py`, `core/extraction/geometry/candidate.py`
- Test: `tests/extraction/geometry/test_candidate.py`

**Interfaces:**
- Produces:
  - `wall_confidence(w, hatch, ocr_items, axes_px, s) -> float`. Rata-rata berbobot:
    - kekuatan pasangan (S2 `pair_overlap`, atau kepadatan mask untuk S1) 0.35;
    - konektivitas ujung (0, 0.5, 1 untuk 0/1/2 ujung terhubung) 0.25;
    - kesesuaian grid (garis tengah ≤ 150 mm dari sumbu, atau sejajar sumbu) 0.2;
    - bukan partial (1 − `partial_mm` / 1500) 0.2.

    Setelah itu dikurangi:
    - 0.3 × fraksi panjang di dalam `hatch`;
    - 0.15 bila ≤ 300 mm dari teks `annotation`.

    Hasil di-clip ke [0, 1].
  - `door_confidence` dan `column_confidence` sesuai §3.7: residu fit, kecocokan radius dengan celah, dan daun untuk pintu; skor bentuk dan jarak ke perpotongan untuk kolom.
  - `CandidateParams = {strategy: "S1" | "S2", sauvola_k, t_min, t_max, l_fix}`.
  - `extract_candidate(page_gray, colour, ocr_items, grid_doc, meta, params, defaults) -> dict`. Mengembalikan `elements` (mm), ditambah `masks` (ndarray, tidak ditulis ke JSON). Urutannya:
    1. binarize ulang (`binarize(page, k)`) bila k ≠ 0.2; selain itu pakai `bin.png`;
    2. `build_masks`;
    3. `extract_strokes`;
    4. tangga (dan `stair_mask` dikurangkan);
    5. S1 atau S2;
    6. `postprocess`;
    7. kolom dan pilaster;
    8. pintu;
    9. keyakinan;
    10. konversi ke mm lewat `to_mm(grid_doc["px_to_mm"], …)`.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_confidence_penalises_hatch_and_dangling`: dinding sama di dalam vs di luar `hatch` → selisih ≥ 0.25. Dinding dengan 0 ujung terhubung < dinding dengan 2 ujung terhubung.
  - `test_cable_trench_has_no_confident_wall` (slow, Gatsu S2 k 0.2 t_min 80): tidak ada dinding berkeyakinan ≥ 0.6 yang garis tengahnya berada di pita trench GT (piksel asli y 598–613, x 830–1580).
  - `test_gatsu_candidate_runs_and_is_plausible` (slow):
    - kandidat S2 default menghasilkan ≥ 60 dinding, ≥ 10 pintu, ≥ 1 tangga, dan ≥ 16 kolom;
    - `elements_to_spec` valid (pydantic);
    - waktu < 20 s.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_candidate.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: perintah yang sama.
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): element confidence and single-candidate assembly`

---

### Task 11: Parameter sweep, tahap 3 di orchestrator, artefak, dan overlay

**Files:**
- Create: `core/extraction/geometry/sweep.py`, `core/extraction/geometry/overlay.py`
- Modify:
  - `core/extraction/stages.py`: `stage_extract`;
  - `server/orchestrator.py`: impl 3 = `stage_extract`; impl 4 tetap `_not_yet("M5c")`.
- Test: `tests/extraction/geometry/test_sweep.py`, `tests/extraction/test_stages.py` (tambahan)

**Interfaces:**
- Produces:
  - `sweep_params(max_candidates: int, profile: dict | None = None) -> list[CandidateParams]`. Urutan deterministik:
    - strategi (S2, S1) × k (0.2, 0.34) × t_min (80, 150) × t_max (450) × l_fix (0, 5);
    - dipotong ke `max_candidates`;
    - S2 lebih dulu, karena Gatsu bergaris ganda dan S1 adalah cadangan untuk denah poche;
    - `profile` (M5c) mengurutkan parameter profile beserta tetangganya ke depan.
  - `run_sweep(inputs, params_list, workers) -> list[dict]`: `ProcessPoolExecutor(max_workers = max(1, os.cpu_count() − 1))`, hasil diurutkan menurut indeks. Kandidat yang melempar exception dicatat sebagai `{error}` dan tidak menghentikan kandidat lain.
  - `render_elements_overlay(page_gray, elements_px) -> ndarray`:
    - dinding biru (255, 0, 0), dan dinding berkeyakinan < 0.6 oranye;
    - pintu hijau, kolom oranye (0, 140, 255), tangga ungu;
    - mask hatch/simbol diarsir abu-abu.
  - `stage_extract(project_dir, work, settings_max: int, progress) -> dict`. Menulis:
    - `candidates/<k>/elements.json` dan `candidates/<k>/overlay.png`;
    - `candidates.json` = `[{index, params, counts: {walls, doors, columns, stairs}, wall_len_m, low_conf, error}]`;
    - `masks/{stair,hatch,symbol}.png` dari kandidat 0.

    Status `failed` "semua kandidat kosong" bila tidak ada kandidat dengan dinding. Metrics `{candidates, best_wall_len_m, seconds}`.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_sweep_params_order_and_cap`: `max = 12` → 12 parameter, yang pertama `{S2, 0.2, 80, 450, 0}`, tanpa duplikat. `max = 50` → 16.
  - `test_failing_candidate_does_not_stop_others`: fungsi kandidat palsu melempar error untuk indeks 1 → hasil berisi 3 item, dan item 1 punya `error`.
  - `test_stage_extract_writes_candidates_and_is_deterministic` (slow): `stage_extract` dua kali pada folder run yang sama dari M5a, dengan `max = 4`:
    - `candidates.json` dan setiap `elements.json` identik byte per byte;
    - waktu tahap 3 untuk 12 kandidat < 90 s di mesin ini; dicatat di ledger.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_sweep.py tests/extraction/test_stages.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi** (orchestrator: impl 3 memanggil `stage_extract(ctx.project_dir, ctx.work_dir, ctx.settings.sweep_max_candidates, ctx.emit_progress)`)

- [ ] **Step 4: Jalankan, pastikan lulus, lalu seluruh suite**

  Run: `rtk uv run --env-file .env pytest -q`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): parallel parameter sweep as stage 3 with candidate artefacts and overlays`

---

### Task 12: Dashboard — panel tahap 3

**Files:**
- Modify: `web/src/components/ExtractionStage.tsx`, `web/src/components/StagePanel.tsx`
- Test: `web/src/components/ExtractionStage.test.tsx` (tambahan)

**Interfaces:**
- Consumes: `03_extract/candidates.json` dan `03_extract/candidates/<k>/overlay.png` lewat artifacts API.
- Produces:
  - panel tahap 3 berisi tabel kandidat: indeks, strategi, k, t_min, l_fix, jumlah dinding/pintu/kolom/tangga, panjang dinding (m), jumlah keyakinan rendah, dan error;
  - memilih baris menampilkan overlay kandidat itu;
  - keterangan warna di bawah gambar.

- [ ] **Step 1: Tulis test yang gagal**

  `test stage 3 lists candidates and switches overlay`: dua kandidat → klik baris 2 → `src` overlay berakhiran `candidates/1/overlay.png`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `cd web && rtk npm test -- ExtractionStage`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(web): stage 3 candidate table with per-candidate overlay`

---

### Task 13: Benchmark Gatsu, tuning, ambang regresi, E2E, dan status di ROADMAP

**Files:**
- Create: `tests/extraction/test_gatsu_regression.py`, `benchmarks/reports/m5b-elements.md` (+ `.json`)
- Modify: `ROADMAP.md`

- [ ] **Step 1: Ukur.**
  - Jalankan tahap 0–3 pada `plan.jpeg`, lalu benchmark `--elements` untuk **setiap** kandidat.
  - Simpan laporan kandidat terbaik (menurut `wall_recall + wall_precision`) ke `benchmarks/reports/m5b-elements.md`.
  - Tabel lengkap per kandidat dicatat di ledger.
- [ ] **Step 2: Tuning terbatas.**
  - Untuk setiap metrik di bawah ambang regresi, analisis sumber galatnya: overlay merah/biru antara dinding GT dan prediksi, digambar di `benchmarks/reports/m5b-diff.png`.
  - Perbaiki penyebab terbesar (mask, pairing, gabung, atau ambang) dengan test sintetis baru (RED → GREEN) di task terkait.
  - Maksimal 3 putaran.
- [ ] **Step 3: Test regresi** `tests/extraction/test_gatsu_regression.py` (slow):
  - Kandidat terbaik Gatsu harus memenuhi **ambang regresi** M5b:

    | Metrik | Ambang regresi |
    |---|---|
    | `wall_recall` | ≥ 0.85 |
    | `wall_precision` | ≥ 0.85 |
    | `wall_pos_median_mm` | ≤ 50 |
    | `wall_pos_p95_mm` | ≤ 150 |
    | `door_recall` | ≥ 0.70 |
    | `door_width_ok` | ≥ 0.60 |
    | `door_dir_ok` | ≥ 0.60 |
    | `stair_risers_ok` | ≥ 0.66 |
    | `stair_dir_ok` | ≥ 0.66 |
    | `wall_iou` | ≥ 0.75 |
    | Kolom structural | ≥ 16/18 |

  - Test terpisah `test_gatsu_meets_nfr` memakai ambang NFR penuh (`THRESHOLDS`), ditandai `xfail(strict=False)`. Hasilnya dilaporkan, bukan diblokir.
  - Bila ambang regresi tidak tercapai setelah Step 2: ambang diturunkan ke nilai terukur (dibulatkan ke bawah 0.01) dengan `Ruling:` yang menyebut galat dan penyebabnya, sesuai ROADMAP M5 ("catat galatnya … bawa ke M7").
- [ ] **Step 4: E2E dashboard.**
  - Upload `plan.jpeg` → tahap 0–3 `succeeded`, tabel kandidat dan overlay tampil, lalu run berhenti di tahap 5 ("belum ada spec", sampai M5c).
  - Catat waktu tahap 1–3 (anggaran NFR-PF-01 ≤ 2 menit untuk tahap 1–5).
  - Screenshot `.playwright-mcp/m5b-candidates.png`.
- [ ] **Step 5: Suite penuh + lint.**

  Run: `rtk uv run --env-file .env pytest -q && rtk uv run ruff check . && cd web && rtk npm test && rtk npm run lint && rtk npm run build`
  Expected: hijau.
- [ ] **Step 6: ROADMAP.**
  - Centang sub-tugas tahap 3 yang selesai.
  - Tulis "Status M5b" yang memuat:
    - metrik terbaik terhadap NFR;
    - waktu;
    - penyimpangan (Hough skeleton menggantikan LSD, jendela P1, tangga lurus saja, kolom bulat);
    - galat yang dibawa ke M5c/M7.
  - Commit: `docs: M5b status (stage 3 geometry)`.
