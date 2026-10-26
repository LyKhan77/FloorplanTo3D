# M5a — Benchmark Ekstraksi + Tahap 0–2 (Input, Preprocess, Grid & Skala) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload `plan.jpeg` (atau PDF) menjalankan tahap 0–2 secara otomatis. Hasilnya `grid.json` dengan sumbu A–F / 1–3 dan skala yang galatnya ≤ 0.5% terhadap GT. Benchmark ekstraksi siap mengukur semua metrik NFR-AC terhadap GT.

**Architecture:**
- Kode ekstraksi berupa library murni di `core/extraction/`: `params.py`, `preprocess.py`, `textclass.py`, `grid.py`, `scale.py`, dan `stages.py` (perekat per tahap yang menulis artefak).
- Orchestrator server (`server/orchestrator.py`) hanya membungkus `stages.py` ke impl tahap 0–2.
- Benchmark ada di `benchmarks/extraction_metrics.py` (fungsi murni) dan `benchmarks/run_extraction_bench.py` (CLI, laporan Markdown + JSON).
- Tahap 3–5 tetap stub sampai M5b/M5c. Tahap 5 tetap memakai spec impor bila ada.

**Tech Stack:** Python 3.12 (uv), OpenCV, NumPy, **scikit-image (baru, Sauvola)**, **PyMuPDF (baru, rasterisasi PDF)**, RapidOCR (sudah ada), Shapely, pytest. Dashboard: React + Carbon g100, Vitest.

**Spec:**
- `PRD/04-extraction.md` Ringkasan, tahap 0–2, §2.1 tabel kelas teks;
- `PRD/01-requirements.md` FR-IN-04, FR-EX-01…04, FR-EX-13, NFR-AC-01…11 (definisi metrik benchmark), NFR-PF-01, NFR-RL-06;
- `PRD/03-layout-spec.md` §1 (sumbu, `px_to_mm`);
- `ROADMAP.md` M5;
- `benchmarks/gatsu/NOTES.md` (interpretasi GT).

Branch: `m5-cv`, dibuat dari `m4-editor`. M5 dipecah menjadi tiga plan berurutan:
- **M5a** (plan ini): benchmark + tahap 0–2;
- **M5b**: tahap 3 (masking, kondisi existing, tangga, dinding S1/S2, kolom, pintu, keyakinan, sweep);
- **M5c**: tahap 4–5, carry-over, style profile, tab Review, IoU tahap 8, regresi.

Plan M5b ditulis setelah M5a selesai, karena hasil grid/skala dan benchmark menentukan tuning tahap 3.

## Global Constraints

- **Lingkungan kerja:** semua perintah shell diawali `rtk`. Jangan membaca atau meng-commit `server-info.txt`. Test Python dijalankan dengan `rtk uv run --env-file .env pytest -q`.
- **Determinisme (NFR-RL-06):** tahap 0–2 deterministik. Tidak ada `random` tanpa seed tetap; iterasi selalu atas daftar terurut. Dua run dengan input yang sama menghasilkan `grid.json` yang identik byte per byte. JSON ditulis dengan `json.dumps(..., indent=1, sort_keys=True)` dan float dibulatkan 4 desimal.
- **Koordinat:**
  - Semua tahap bekerja di **piksel gambar kerja**: gambar asli setelah deskew dan upscale.
  - `meta.json` menyimpan `work_from_original` (affine 2×3).
  - Spec akhir memakai `px_to_mm` terhadap **piksel gambar asli**, yaitu `grid.json.px_to_mm_original` = `px_to_mm_work ∘ work_from_original`. Konsisten dengan GT dan overlay laporan.
  - `px_to_mm` = 6 float `[a, b, c, d, e, f]`, dengan `x_mm = a·u + b·v + c` dan `y_mm = d·u + e·v + f`. Origin di sumbu vertikal paling kiri dan sumbu horizontal paling bawah. Y dibalik (PRD/03 §1).
- **Batas dan ambang dari spec:**
  - deskew: diputar bila |sudut| ∈ (0.2°, 5°]; bila > 5°, `needs_attention`;
  - upscale 2× (INTER_CUBIC) bila lebar < 2000 px;
  - rasterisasi PDF 300 dpi;
  - residu persamaan skala ≤ 1% (selebihnya outlier);
  - anisotropi ≤ 1% berarti satu skala (rata-rata); bila > 1%, skala X dan Y terpisah;
  - skala manual menang, dengan peringatan bila beda > 1%;
  - ujung segmen dimensi dicocokkan ke sumbu ≤ 10 px (piksel asli).
- **Pesan dari spec, salin persis:**
  - "Skala tidak dapat ditentukan, isi skala manual";
  - "Gambar miring > 5°; scan di luar cakupan".
- **Dependensi baru:** hanya `scikit-image` dan `pymupdf`. Lisensi PyMuPDF (AGPL) dicatat di ROADMAP sebagai catatan R-14.
- **Di luar lingkup M5a (dicatat di ROADMAP):**
  - parser prompt Strata (T0, M6);
  - deteksi title block. Gatsu tidak punya title block, jadi tidak ada data uji; yang dibuat hanya pengenalan border kertas;
  - pemilihan halaman PDF di form (P1). Field `page` sudah dihormati bila dikirim.
- **Kualitas:** `rtk uv run ruff check .` bersih. Test lambat (OCR/gambar nyata, > 10 s) ditandai `@pytest.mark.slow`. Dashboard: `npm test`, `npm run lint`, dan `npm run build` hijau.

## Review Focus

1. **Label bulatan grid tidak terbaca OCR global** (Gatsu: "C" dan "1"). Harapan: OCR per crop bulatan, lalu inferensi urutan dari tetangga; label akhir persis A–F dan 1–3. Test: Task 5 `test_gatsu_bubbles_labels_and_positions`.
2. **Gambar sedikit miring (0.2°–5°) atau sangat miring (> 5°).** Harapan: diluruskan dengan skala tetap ≤ 0.5%, atau `needs_attention` dengan pesan spec. Test: Task 3 `test_deskew_rotates_small_tilt_and_refuses_large`, Task 7 `test_tilted_plan_keeps_scale`.
3. **Denah tanpa angka dimensi, atau dimensi yang salah baca.** Harapan: outlier dibuang; tanpa persamaan sah, `needs_attention` "Skala tidak dapat ditentukan, isi skala manual", kecuali ada skala manual. Test: Task 6 `test_outlier_equation_dropped`, `test_no_dimensions_needs_attention`, `test_manual_scale_wins_with_warning`.
4. **Input PDF.** Harapan: halaman `page` (default 1) dirender 300 dpi, `px_to_mm` merujuk ke raster itu, dan editor/laporan memakai raster tersebut. Test: Task 3 `test_pdf_rasterized_at_300dpi_and_page_selected`, Task 7 `test_input_image_falls_back_to_raster`.
5. **Run ulang dengan input sama.** Harapan: `grid.json` identik. Test: Task 7 `test_stages_0_2_are_deterministic`.

---

### Task 1: Benchmark metrik ekstraksi (spec vs GT)

**Files:**
- Create: `benchmarks/extraction_metrics.py`, `benchmarks/run_extraction_bench.py`
- Test: `tests/benchmarks/test_extraction_metrics.py`

**Interfaces:**
- Consumes: `Spec` (`core/spec/models.py`), `wall_footprint` dan `column_footprint` (`core/spec/derive.py`), `stair_metrics` bila perlu.
- Produces:
  - `THRESHOLDS: dict[str, float]` dari NFR-AC:
    - `scale_err ≤ 0.005`;
    - `wall_pos_median_mm ≤ 50`, `wall_pos_p95_mm ≤ 150`;
    - `wall_recall ≥ 0.95`, `wall_precision ≥ 0.95`;
    - `door_recall ≥ 0.90`, `door_width_ok ≥ 0.90`, `door_dir_ok ≥ 0.80`;
    - `room_match ≥ 0.90`;
    - `wall_iou ≥ 0.85`;
    - `stair_risers_ok = 1.0`, `stair_dir_ok = 1.0`, `stair_pos_ok = 1.0`;
    - `gross_area_err ≤ 0.01`.
  - `scale_metrics(mm_per_px: float, gt: Spec) -> dict`, mengembalikan `{scale_err}`.
  - `grid_metrics(axes: list[dict], gt: Spec) -> dict`. `axes` = `[{label, orientation, offset}]` (mm). Hasilnya `{axes_found, axes_expected, label_ok, offset_max_err_mm}`.
  - `wall_metrics(pred: Spec, gt: Spec, tol_mm=150, angle_deg=5) -> dict`. Sampling garis tengah tiap 50 mm. Sampel GT terdeteksi bila ada dinding prediksi dengan sudut ≤ 5° yang jaraknya ≤ tol. Hasilnya:
    - `wall_recall` (panjang GT tertutup / panjang GT);
    - `wall_precision` (sebaliknya);
    - `wall_pos_median_mm` dan `wall_pos_p95_mm` (jarak sampel prediksi yang cocok ke garis tengah GT terdekat).
  - `door_metrics(pred, gt, match_mm=500) -> dict`. Pencocokan greedy berdasarkan jarak pusat bukaan (titik tengah segmen bukaan di dinding, mm), satu-satu. Hasilnya `{door_recall, door_width_ok, door_dir_ok}`.
    - Arah dibandingkan dalam koordinat dunia: posisi engsel (titik ujung bukaan sisi `hinge`; `both` cocok dengan `both`) dan sisi ayun (tanda normal dunia dari `swing`). Dengan begitu dinding yang a→b-nya terbalik tidak dihukum.
  - `room_metrics(pred, gt) -> dict`. Pencocokan satu-satu greedy berdasarkan IoU poligon ≥ 0.5. Ruang cocok bila galat luas ≤ 3%. Hasilnya `{room_match (cocok / jumlah GT), rooms_pred, rooms_gt, area_err_max}`.
  - `wall_iou(pred, gt) -> float`. IoU luas union tapak dinding + kolom (Shapely, eksak, tanpa raster).
  - `stair_metrics_cmp(pred, gt) -> dict`. Tiap flight GT dicocokkan ke flight prediksi dengan titik tengah terdekat. Hasilnya:
    - `stair_risers_ok` (|Δ| ≤ 1);
    - `stair_dir_ok` (dot product arah start→end > 0);
    - `stair_pos_ok` (jarak titik tengah ≤ 100 mm).
    - Bila GT tanpa tangga, nilainya `None`.
  - `gross_area_metrics(pred, gt) -> dict`, mengembalikan `{gross_area_err}`.
  - `evaluate(pred: Spec, gt: Spec) -> dict` = gabungan semua di atas, ditambah `passed: dict[str, bool]` per metrik terhadap `THRESHOLDS`.
  - CLI: `uv run python -m benchmarks.run_extraction_bench --spec <spec.json> | --grid <grid.json> [--gt benchmarks/gatsu/gt_spec.json] --out benchmarks/reports/extraction`. Menulis `<out>.json` dan `<out>.md` (tabel metrik | nilai | ambang | ✓/✗).
    - `--grid` hanya menghitung `scale_metrics` + `grid_metrics` dari `grid.json` (`mm_per_px`, `axes`). Mode ini dipakai sampai tahap 3–5 ada.

- [ ] **Step 1: Tulis test yang gagal**

`test_extraction_metrics.py` memuat GT (`benchmarks/gatsu/gt_spec.json`):
- `test_gt_against_itself_is_perfect`: `evaluate(gt, gt)` menghasilkan nilai berikut, dan semua `passed` bernilai `True`:
  - `wall_recall == wall_precision == 1.0`;
  - `wall_pos_median_mm == 0`;
  - `door_recall == 1.0`;
  - `room_match == 1.0`;
  - `wall_iou == 1.0`;
  - `gross_area_err == 0`.
- `test_shifted_walls_raise_position_error`: semua dinding digeser +100 mm di X lewat `core.spec.ops.apply(move_wall …)` atau edit langsung model. Harapan:
  - `wall_pos_median_mm` ≈ 100 untuk dinding vertikal;
  - recall tetap 1.0 (tol 150);
  - geser +200 mm → recall turun di bawah 0.95.
- `test_missing_wall_lowers_recall_not_precision`: hapus W1 (dinding terpanjang). Recall turun sebesar panjangnya / total; precision tetap 1.0.
- `test_flipped_swing_counts_as_wrong_direction`: tukar `swing` satu pintu GT → `door_dir_ok == (n−1)/n`. Membalik a/b dinding inangnya (sekaligus mencerminkan `hinge`/`swing` dan offset, seperti merge di ops) → tetap `door_dir_ok == 1.0`.
- `test_stairs_and_scale_and_grid`: membalik flight S1 → `stair_dir_ok < 1.0`. `scale_metrics(gt.meta.mm_per_px * 1.004, gt)["scale_err"] ≈ 0.004` (lulus); × 1.006 → gagal. `grid_metrics` dengan offset GT → `label_ok` True dan `offset_max_err_mm == 0`.
- `test_cli_writes_markdown_and_json` (tmp_path): `--spec benchmarks/gatsu/gt_spec.json` menghasilkan file `.md` yang berisi baris `wall_recall` dan file `.json` dengan `passed`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest -q tests/benchmarks/test_extraction_metrics.py`
Expected: FAIL (modul tidak ada).

- [ ] **Step 3: Implementasi** `benchmarks/extraction_metrics.py` dan `benchmarks/run_extraction_bench.py` sesuai Interfaces.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `rtk uv run --env-file .env pytest -q tests/benchmarks/test_extraction_metrics.py && rtk uv run ruff check benchmarks`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add benchmarks/extraction_metrics.py benchmarks/run_extraction_bench.py tests/benchmarks/test_extraction_metrics.py
rtk git commit -m "feat(bench): extraction metrics against ground truth with markdown/json report"
```

---

### Task 2: Tahap 0 — parameter (parser aturan) dan `input.json`

**Files:**
- Create: `core/extraction/params.py`
- Test: `tests/extraction/test_params.py` (buat juga `tests/extraction/__init__.py`)

**Interfaces:**
- Produces:
  - `parse_prompt(prompt: str) -> dict`. Regex aturan PRD/04 tahap 0.4:
    - `tinggi (dinding)? <n> (m|mm|cm)` → `wall_height` (mm, int);
    - `tinggi pintu <n> <unit>` → `door_height`;
    - `tebal (dinding)? <n> <unit>` → `wall_thickness`;
    - `lantai (\d+)` → `floor_name: "Lantai N"`;
    - `data (hall|center)` → `site_type: "data_center"`;
    - `skala <n> mm/px` → `mm_per_px` (float).
    - Angka memakai koma atau titik desimal; case-insensitive. Kata "pintu" tidak ikut menjadi `wall_height`.
  - `merge_params(explicit: dict, parsed: dict) -> dict`: parameter eksplisit menang, dan hanya key yang dikenal yang dipakai (`wall_height`, `door_height`, `wall_thickness`, `floor_name`, `site_type`, `mm_per_px`, `use_strata`).
  - `input_doc(upload: dict) -> dict`. `upload` = isi `input/input.json` saat upload. Hasilnya dokumen PRD tahap 0.5: `{prompt, params_explicit, params_parsed, params_final, sha256, filename, page}`, dengan `page` default 1.

- [ ] **Step 1: Tulis test yang gagal**
- `test_parse_prompt_units`:
  - `"Tinggi dinding 4,5 m, lantai 2, data hall"` → `{wall_height: 4500, floor_name: "Lantai 2", site_type: "data_center"}`;
  - `"tinggi 450 cm"` → `wall_height 4500`;
  - `"tinggi pintu 2100 mm"` → `{door_height: 2100}` tanpa `wall_height`;
  - `"skala 25.8 mm/px"` → `mm_per_px 25.8`;
  - `""` → `{}`.
- `test_explicit_params_win`: `merge_params({"wall_height": 3000}, {"wall_height": 4500, "floor_name": "Lantai 2"})` → `{wall_height: 3000, floor_name: "Lantai 2"}`. Key tidak dikenal dibuang.
- `test_input_doc_shape`: semua key PRD ada, dan `page` default 1.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_params.py`
Expected: FAIL.

- [ ] **Step 3: Implementasi** `core/extraction/params.py`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_params.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add core/extraction/params.py tests/extraction
rtk git commit -m "feat(extract): stage 0 rule-based prompt parser and input document"
```

---

### Task 3: Tahap 1 — preprocess (rasterisasi, upscale, CLAHE, deskew, area gambar, binarisasi)

**Files:**
- Modify: `pyproject.toml` (+`scikit-image`, +`pymupdf`), `uv.lock`
- Create: `core/extraction/preprocess.py`
- Test: `tests/extraction/test_preprocess.py`

**Interfaces:**
- Produces:
  - `load_raster(path: Path, page: int = 1) -> np.ndarray`. JPEG/PNG dibaca dengan `cv2.imread`: alpha dibuang dengan latar putih, lalu dikonversi ke BGR. PDF dirender dengan `fitz` pada 300 dpi (`matrix = fitz.Matrix(300/72, 300/72)`) dari halaman `page` (1-based). `page` di luar jangkauan → `ValueError("page N not in 1..M")`.
  - `estimate_skew(gray: np.ndarray) -> float`, dalam derajat (CCW positif). Prosesnya:
    1. tepi Canny (50, 150);
    2. `HoughLinesP` (`threshold=80`, `minLineLength = 0.1·min(h, w)`, `maxLineGap=5`);
    3. sudut setiap garis dilipat ke (−45°, 45°];
    4. hasilnya median berbobot panjang.
  - `deskew(gray, angle) -> tuple[np.ndarray, np.ndarray]` → (gambar, matriks 2×3). Diputar di sekitar pusat, dan ukuran kanvas diperbesar agar tidak ada yang terpotong. Latar putih.
  - `drawing_bbox(binary: np.ndarray) -> tuple[int, int, int, int]` = bbox komponen terhubung terbesar dari mask garis (setelah closing 3×3). Bila bbox itu menutupi ≥ 90% luas halaman (border kertas), dipakai komponen terbesar berikutnya.
  - `binarize(gray, k: float = 0.2, window: int = 25) -> np.ndarray`. Memakai `skimage.filters.threshold_sauvola`. Hasilnya `uint8` dengan **tinta = 255, latar = 0**. Nilai `window` dibuat ganjil.
  - `preprocess(raster_bgr: np.ndarray) -> PreprocessResult`, dataclass berisi:
    - `page` (gray kerja), `binary`;
    - `meta = {deskew_deg, upscale, work_size: [w, h], original_size: [w, h], drawing_bbox, work_from_original: [6 floats]}`;
    - `status: "succeeded" | "needs_attention"`, `message`.

    Urutan langkah:
    1. grayscale;
    2. upscale 2× bila lebar < 2000;
    3. CLAHE (`clipLimit=2.0`, `tileGridSize=(8, 8)`);
    4. estimasi skew: |a| ≤ 0.2° tidak diputar; > 5° hasilnya `needs_attention`, "Gambar miring > 5°; scan di luar cakupan";
    5. binarize dengan `window = 25 × upscale` (dibuat ganjil);
    6. `drawing_bbox`.

    `work_from_original` = komposisi skala upscale dan rotasi deskew.

- [ ] **Step 1: Tulis test yang gagal**
- `test_gatsu_preprocess_meta` (slow):
  - `plan.jpeg` → `upscale == 2`, `work_size == [3200, 1890]`, `abs(deskew_deg) ≤ 0.2`;
  - `work_from_original ≈ [2, 0, 0, 0, 2, 0]`;
  - `drawing_bbox` memuat bangunan: dalam piksel asli kira-kira x ∈ [95, 1390], y ∈ [30, 700], toleransi 15 px. Bulatan grid berada di luar bbox.
  - `binary` hanya berisi {0, 255}, dan tinta < 25% piksel.
- `test_deskew_rotates_small_tilt_and_refuses_large`:
  - `plan.jpeg` diputar 2° (`cv2.warpAffine`, latar putih) → `deskew_deg` ≈ −2 ± 0.3, status `succeeded`;
  - diputar 8° → `needs_attention` dengan pesan persis.
- `test_pdf_rasterized_at_300dpi_and_page_selected` (tmp_path):
  - PDF 2 halaman dibuat dengan `fitz`, ukuran A4 portrait 595×842 pt. Halaman 2 berisi gambar plan.
  - `load_raster(pdf, page=2)` → ukuran ≈ (2480 × 3508) ± 2, dan bukan halaman kosong (std > 10).
  - `page=3` → `ValueError`.
- `test_png_with_alpha_flattened_on_white`: PNG RGBA transparan → hasilnya 3 kanal dan piksel transparan menjadi 255.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv add scikit-image pymupdf && rtk uv run --env-file .env pytest -q tests/extraction/test_preprocess.py`
Expected: FAIL (modul tidak ada).

- [ ] **Step 3: Implementasi** `core/extraction/preprocess.py`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_preprocess.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add pyproject.toml uv.lock core/extraction/preprocess.py tests/extraction/test_preprocess.py
rtk git commit -m "feat(extract): stage 1 preprocess - raster/PDF, upscale, CLAHE, deskew, drawing area, Sauvola"
```

---

### Task 4: Tahap 2a — OCR di gambar kerja dan klasifikasi teks

**Files:**
- Modify: `core/extraction/ocr.py` (tambah `ocr_crop`)
- Create: `core/extraction/textclass.py`
- Test: `tests/extraction/test_textclass.py`

**Interfaces:**
- Consumes: `run_ocr(image, upscale)` dan `OcrItem` (`core/extraction/ocr.py`).
- Produces:
  - `ocr_crop(image: np.ndarray, bbox: BBox, scale: float = 4.0) -> list[OcrItem]`: OCR satu crop yang diperbesar `scale`, dengan bbox dikembalikan ke koordinat `image`. Dipakai untuk label bulatan di Task 5.
  - `TEXT_CLASSES = ("grid_label", "dimension", "room_label", "annotation", "proposed", "dismantle", "stair_dir", "other")`.
  - `classify_text(item: OcrItem, *, in_circle: bool, in_building: bool) -> str`. Aturan tabel PRD/04 §2.1, dicek berurutan:
    1. `grid_label` bila `in_circle` dan teks `^[A-Z]{1,2}$|^\d{1,2}$`;
    2. `proposed`: `PROPOSED|NEW|RENCANA|USULAN`;
    3. `dismantle`: `DISMANTLE|BONGKAR|DEMOLISH`;
    4. `annotation`: `NYY|\dx\d+C|ROUTE|CABLE|PANEL|SDP|UPS|mm²|MM2`;
    5. `dimension`: `^\d{3,6}$` (setelah membuang spasi dan titik ribuan);
    6. `stair_dir`: kata utuh `NK|NAIK|UP|TR|TURUN|DN|DOWN`;
    7. `room_label`: cocok leksikon (daftar kata kunci PRD/04 §4.3, salin ke `ROOM_WORDS`), atau huruf kapital ≥ 4 karakter dengan `in_building`;
    8. selain itu `other`.

    Urutan ini membuat "PROPOSED NEW PANEL SDP" menjadi `proposed` (penanda kondisi existing lebih penting daripada `annotation`). Leksikon lengkap dengan Levenshtein dikerjakan di M5c (tahap 4); di sini cukup kecocokan kata.
  - `ocr_page(page_gray: np.ndarray, upscale_done: float) -> list[OcrItem]` = `run_ocr(page, upscale=max(1.0, 2.0 / upscale_done))`, sehingga gambar Gatsu yang sudah 2× tidak diperbesar lagi.

- [ ] **Step 1: Tulis test yang gagal**
- `test_classify_rules` (tanpa OCR, `OcrItem` buatan):
  - `"C"` dengan `in_circle` → `grid_label`; `"C"` tanpa `in_circle` → `other`;
  - `"6000"` → `dimension`;
  - `"R. MEETING"` dengan `in_building` → `room_label`;
  - `"NYY 4x1Cx185mm"` → `annotation`;
  - `"PROPOSED NEW PANEL SDP"` → `proposed`;
  - `"DISMANTLE THE WALL"` → `dismantle`;
  - `"NK"` → `stair_dir`;
  - `"MSC GATSU LANTAI 1"` tanpa `in_building` → `other`.
- `test_gatsu_page_ocr_classes` (slow): `ocr_page` pada `page` hasil `preprocess(plan.jpeg)`, dengan klasifikasi `in_circle=False`. Harapan:
  - kelas `dimension` memuat ≥ 8 dari 9 nilai dimensi (`DIMS` di `tests/test_ocr_smoke.py`);
  - `room_label` memuat MEETING, GUDANG, PANTRY, GALERY, BATTERY;
  - `proposed` muncul ≥ 2 kali;
  - `stair_dir` memuat "NK".

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_textclass.py`
Expected: FAIL.

- [ ] **Step 3: Implementasi** `textclass.py` dan `ocr_crop`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_textclass.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add core/extraction/ocr.py core/extraction/textclass.py tests/extraction/test_textclass.py
rtk git commit -m "feat(extract): OCR on the working page and rule-based text classes"
```

---

### Task 5: Tahap 2b — bulatan grid, label, dan posisi sumbu

**Files:**
- Create: `core/extraction/grid.py`
- Modify: `tests/test_ocr_smoke.py` (hapus `xfail`; test dipindah ke label hasil bulatan)
- Test: `tests/extraction/test_grid.py`

**Interfaces:**
- Consumes: `ocr_crop`, `classify_text`, `OcrItem` (Task 4); `page` dan `binary` (Task 3).
- Produces:
  - `Bubble = {cx: float, cy: float, r: float, label: str | None, label_source: "ocr" | "crop" | "inferred"}`.
  - `find_bubbles(page_gray: np.ndarray, ocr: list[OcrItem]) -> list[Bubble]`. Prosesnya:
    1. `cv2.HoughCircles` (`HOUGH_GRADIENT`, `dp=1`, `minDist=2r_min`, `param1=100`, `param2=30`) dengan radius dalam `[r_lo, r_hi]` = `[0.6, 2.5] × h_text`. `h_text` = median tinggi bbox OCR teks berkarakter tunggal; bila tidak ada, tinggi semua bbox.
    2. Verifikasi: ≥ 60% dari 72 titik sampel di keliling (±2 px) adalah tinta di `binary`, **dan** bagian dalam (radius 0.75r) bertinta < 35%.
    3. Label diambil dari OCR global yang pusat bbox-nya ada di dalam lingkaran (kelas `grid_label`). Bila kosong, dipakai `ocr_crop` kotak 1.5r di sekitar pusat.
    4. Bulatan diurutkan (cy, cx).
  - `group_axes(bubbles: list[Bubble]) -> tuple[list[Bubble], list[Bubble]]` → (sumbu vertikal, sumbu horizontal). Bulatan yang deret-nya sejajar horizontal (|Δcy| ≤ r untuk ≥ 2 bulatan) menandai sumbu **vertikal** (posisi = cx). Deret yang sejajar vertikal (|Δcx| ≤ r) menandai sumbu **horizontal** (posisi = cy). Deret sejenis yang ganda (bulatan atas dan bawah) digabung menurut label, atau menurut posisi bila ≤ r. Setiap kelompok diurutkan menurut posisi.
  - `infer_labels(group: list[Bubble]) -> list[Bubble]`. Label yang kosong, atau tidak cocok pola kelompoknya, diisi dari urutan:
    - kelompok huruf memakai abjad berurutan dari tetangga terdekat yang terbaca (A, B, ?, D → C);
    - kelompok angka memakai bilangan berurutan; arah naik dan turun dikenali dari dua label yang terbaca.

    Bila kurang dari dua label terbaca dan bertentangan, label tetap `None` dan dicatat sebagai warning. `label_source` = `inferred`. Label yang terbaca tetapi melanggar urutan (mis. "3" dibaca "C" di kelompok angka) diganti, dengan warning.
  - `detect_grid(page_gray, binary, ocr) -> dict` = `{vertical: [{label, px, bubble}], horizontal: [...], warnings: [...]}`.

- [ ] **Step 1: Tulis test yang gagal**
- `test_gatsu_bubbles_labels_and_positions` (slow): `detect_grid` pada hasil `preprocess(plan.jpeg)` (koordinat kerja = 2× asli). Harapan:
  - label vertikal persis `["A", "B", "C", "D", "E", "F"]`, posisi px kerja = 2 × `GRID_PX_X` (`benchmarks/gatsu/gt_px.py`) ± 4 px;
  - label horizontal persis `["1", "2", "3"]` (urut dari atas), posisi px kerja = 2 × `GRID_PX_Y` ± 4 px;
  - sumbu C memakai 2 × 663.0 ± 6 px, karena di GT posisi C hasil interpolasi.
- `test_infer_labels_fills_gaps_and_fixes_misreads` (tanpa OCR): kelompok huruf `[A, B, None, D]` → C; kelompok angka `["1", "C", "3"]` → `["1", "2", "3"]` dengan satu warning; kelompok `[None, None]` → tetap `None` dengan warning.
- `test_ocr_smoke.py::test_gatsu_grid_and_dimensions_readable`: lepas `xfail`; label grid diambil dari `detect_grid`. Harapan 18/18 label grid + dimensi (kriteria M0 ≥ 90% kini terpenuhi).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_grid.py tests/test_ocr_smoke.py`
Expected: FAIL.

- [ ] **Step 3: Implementasi** `core/extraction/grid.py`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_grid.py tests/test_ocr_smoke.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add core/extraction/grid.py tests/extraction/test_grid.py tests/test_ocr_smoke.py
rtk git commit -m "feat(extract): grid bubbles with per-crop OCR, sequence inference and axis positions"
```

---

### Task 6: Tahap 2c — skala (persamaan dimensi, RANSAC, least squares, prioritas) dan `px_to_mm`

**Files:**
- Create: `core/extraction/scale.py`
- Test: `tests/extraction/test_scale.py`

**Interfaces:**
- Consumes: `detect_grid` (Task 5), `OcrItem` dan kelas `dimension` (Task 4).
- Produces:
  - `Equation = {value_mm: int, axis_from: str, axis_to: str, px: float, orientation: "x" | "y", text_bbox}`.
  - `dimension_equations(grid: dict, dims: list[OcrItem]) -> list[Equation]`.
    - Teks `angle 0` mengukur sepanjang X dengan sumbu vertikal; `angle 90` sepanjang Y dengan sumbu horizontal.
    - Hipotesis awal: pasangan sumbu **bertetangga** yang mengapit pusat teks.
    - Teks yang tidak diapit dua sumbu diabaikan.
  - `solve_scale(eqs: list[Equation]) -> dict`. Mengembalikan `{sx, sy, isotropic: bool, used: [Equation], dropped: [Equation], residuals: [float]}`. Prosesnya:
    1. Skala awal per orientasi = median `value/px`.
    2. Persamaan dengan residu > 1% diuji ulang terhadap **semua** pasangan sumbu (i < j) yang mengapit teks. Pasangan dengan prediksi terdekat dipakai bila residunya ≤ 1%. Langkah ini menangkap dimensi total, mis. 28000 = A–F.
    3. Persamaan yang tetap > 1% dibuang (`dropped`).
    4. Least squares per orientasi, lalu cek anisotropi ≤ 1% → `sx = sy` = rata-rata berbobot jumlah persamaan.
    5. Cek silang total: untuk tiap persamaan dengan pasangan tidak bertetangga, jumlah nilai persamaan bertetangga yang terpakai di antara kedua sumbunya harus sama dengan nilainya (±1%). Bila tidak, dicatat di warnings.
  - `axis_offsets(grid: dict, used: list[Equation], sx: float, sy: float) -> dict[str, int]`. Offset mm tiap sumbu relatif ke sumbu pertama (vertikal: paling kiri; horizontal: paling **bawah**, karena Y dibalik).
    - Dipakai jumlah kumulatif nilai dimensi bertetangga bila rantainya lengkap sampai sumbu itu.
    - Selain itu `round(px_dist · s / 10) · 10`.
  - `scale_from(grid, dims, manual_mm_per_px: float | None) -> dict` (`grid.json`):
    - `axes: [{id: "G"+label, label, orientation, offset, px}]` (offset mm, px kerja);
    - `px_to_mm` (kerja), `mm_per_px` = √|det|;
    - `scale_source`: `manual` | `grid_dimensions` | `total_length`;
    - `residuals`, `equations_used`, `equations_dropped`, `warnings`;
    - `status`, `message`.

    Prioritas skala sesuai PRD/04 §2.3:
    1. Skala manual menang. Skala hitungan tetap dihitung; bila beda > 1%, dicatat warning `"skala manual X berbeda Y% dari skala hasil hitung Z"`.
    2. Tanpa skala manual: persamaan grid + dimensi, `scale_source: grid_dimensions`.
    3. Bila hanya satu persamaan yang lolos dan pasangannya tidak bertetangga: `total_length`.
    4. Tanpa persamaan dan tanpa manual: `status: needs_attention`, message "Skala tidak dapat ditentukan, isi skala manual".

    `px_to_mm` = `[sx, 0, −sx·x0, 0, −sy, sy·y0]`, dengan x0 = px sumbu vertikal pertama dan y0 = px sumbu horizontal paling bawah. Ini konsisten dengan `axis_offsets`.
  - `compose_original(px_to_mm_work: list[float], work_from_original: list[float]) -> list[float]` = affine komposisi untuk piksel asli.

- [ ] **Step 1: Tulis test yang gagal**
- Synthetic (tanpa gambar): grid vertikal di px 0, 240, 480, 640, 880, 1120 dan horizontal 0, 240, 480. Teks dimensi 6000/6000/4000/6000/6000 di antara sumbu bertetangga, serta 28000 di tengah A–F (posisinya di antara C dan D).
  - `test_chain_and_total_solve`: `sx == 25.0 ± 1e-9`; persamaan 28000 dipakai dengan pasangan A–F; offset persis {A: 0, B: 6000, C: 12000, D: 16000, E: 22000, F: 28000}.
  - `test_outlier_equation_dropped`: tambah teks "9000" di antara A–B → masuk `dropped`, dan `sx` tetap 25.0.
  - `test_anisotropy_over_1pct_keeps_separate_scales`: sumbu Y dengan skala 25.5 (beda 2%) → `isotropic False`, `sx 25.0`, `sy 25.5`.
  - `test_manual_scale_wins_with_warning`: `manual_mm_per_px = 26.0` → `scale_source manual`, `mm_per_px 26.0`, satu warning berisi "berbeda".
  - `test_no_dimensions_needs_attention`: tanpa teks dimensi dan tanpa manual → `needs_attention` dengan message persis. Dengan manual 25.0 → `succeeded`.
  - `test_compose_original`: `work_from_original = [2, 0, 0, 0, 2, 0]` → `px_to_mm_original` = sx·2 pada piksel asli.
- `test_gatsu_scale_within_half_percent` (slow, pipeline Task 3 → 4 → 5 → 6 pada plan.jpeg):
  - `mm_per_px` dari `px_to_mm_original` berada dalam ±0.5% dari GT 25.8127 (`scale_metrics` Task 1);
  - offset sumbu persis GT (A 0 … F 28000; 3 → 0, 2 → 6000, 1 → 12000);
  - `scale_source grid_dimensions`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_scale.py`
Expected: FAIL.

- [ ] **Step 3: Implementasi** `core/extraction/scale.py`.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_scale.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add core/extraction/scale.py tests/extraction/test_scale.py
rtk git commit -m "feat(extract): scale from dimension chains with outlier removal, priorities and px_to_mm"
```

---

### Task 7: Perekat tahap 0–2, artefak, dan orchestrator

**Files:**
- Create: `core/extraction/stages.py`, `core/extraction/overlay.py`
- Modify:
  - `server/orchestrator.py`: impl 0–2 asli; pesan `_validate` "no spec yet: import a spec (automatic extraction of walls/rooms arrives in M5b/M5c)";
  - `server/projects.py`: `input_image` fallback ke `input/raster.png`;
  - `server/routes/runs.py`: teruskan `params_override` ke `start_run`.
- Test: `tests/extraction/test_stages.py`, `tests/server/test_extraction_stages.py`

**Interfaces:**
- Consumes: Task 2–6.
- Produces:
  - `stage_input(project_dir: Path, work: Path) -> dict`. Menulis `work/input.json` (`input_doc` Task 2) dan mengembalikan result `{status, metrics: {type, page}}`.
  - `stage_preprocess(project_dir, work) -> dict`:
    - memuat `input/original.*` lewat `load_raster` dengan `page` dari input doc;
    - bila PDF, menyimpan raster asli ke `project_dir/input/raster.png`;
    - menulis `page.png`, `bin.png`, dan `meta.json`;
    - metrics `{deskew_deg, upscale, work_w, work_h}`.
  - `stage_grid(project_dir, work, prev: Path) -> dict`, dengan `prev` = folder `stages/`:
    - menjalankan OCR, klasifikasi (dengan `in_circle` dari bulatan dan `in_building` dari `drawing_bbox`), `detect_grid`, dan `scale_from` (manual dari `params_final.mm_per_px`);
    - menulis `ocr.json` (`[{text, bbox, angle, conf, cls}]`), `grid.json` (Task 6 ditambah `px_to_mm_original`), dan `overlay.png`;
    - metrics `{axes_v, axes_h, mm_per_px, scale_source, residual_max_pct}`; warnings dari grid dan skala; status/message dari Task 6.
  - `render_grid_overlay(page_gray, grid_doc, equations) -> np.ndarray`, digambar di atas `page.png` dalam BGR:
    - sumbu garis putus magenta (255, 0, 255) di sepanjang gambar;
    - label bulatan ≥ 14 px dengan latar putih;
    - segmen persamaan yang dipakai hijau, yang dibuang merah.
  - Orchestrator: `DEFAULT_IMPLS` 0, 1, 2 memanggil fungsi di atas dengan `ctx.project_dir`, `ctx.work_dir`, dan `ctx.work_dir.parent`. `ctx.emit_progress` dipanggil di batas sub-langkah (OCR 30%, grid 60%, skala 90%). Tahap 3–4 tetap `_not_yet("M5b")`.
  - **`params_override`** (body `POST /runs` M3, sebelumnya diabaikan):
    - `start_run(pid, kind, from_stage=None, params_override=None)` menyimpannya di `run.json`;
    - `StageContext` mendapat field `params_override: dict`;
    - `run_params(project_dir, override) -> dict` di `stages.py` = `merge_params({**upload.params, **override}, parse_prompt(upload.prompt))`. Fungsi ini dipakai `stage_input` dan dihitung ulang oleh `stage_grid`, sehingga override tetap berlaku walau tahap 0 tidak dijalankan ulang.
  - **Run `from_stage` 1–5:** sebelum tahap pertama jalan, `seed_previous_stages(run_dir, source_run_dir, upto=from_stage − 1)` menyalin folder tahap `00_…` sampai `(from_stage−1)_…` dari run terakhir yang memilikinya. Dengan begitu tahap 2 menemukan `01_preprocess/page.png`. Bila tidak ada run sumber, `from_stage` di-clamp ke 0.

- [ ] **Step 1: Tulis test yang gagal**
- `tests/extraction/test_stages.py` (slow), memakai folder project buatan di tmp_path yang berisi `input/original.jpg` (plan.jpeg) dan `input/input.json`:
  - `test_stages_0_2_write_artifacts`: `stage_input` → `stage_preprocess` → `stage_grid`. Semua file artefak PRD ada; `grid.json.mm_per_px` dalam 0.5%; `overlay.png` berukuran sama dengan `page.png`.
  - `test_stages_0_2_are_deterministic`: dua folder run → `grid.json` dan `meta.json` identik byte per byte.
  - `test_tilted_plan_keeps_scale`: plan diputar 2° → skala tetap dalam 0.5% dan 6 + 3 sumbu ditemukan.
  - `test_input_image_falls_back_to_raster`: project PDF (dibuat dari plan.jpeg dengan fitz) → setelah `stage_preprocess`, `input_image(storage, pid)` mengembalikan `input/raster.png`.
- `tests/server/test_extraction_stages.py` (slow): `app_factory` dengan stage 7–10 diganti stub cepat. Upload `plan.jpeg` dengan `start=true`, tunggu run selesai. Harapan:
  - status tahap 0, 1, 2 = `succeeded`;
  - `metrics.axes_v == 6`;
  - artefak `02_grid/grid.json` bisa diambil lewat `GET /runs/{rid}/artifacts/02_grid/grid.json`;
  - run berakhir `needs_attention` di tahap 5 dengan pesan baru (belum ada spec).
- `test_from_stage_2_rerun_uses_previous_artifacts_and_override` (slow): setelah run di atas, `POST /runs {kind: "from_stage", from_stage: 2, params_override: {mm_per_px: 26.5}}`. Harapan:
  - tahap 0–1 `skipped`, tahap 2 `succeeded`;
  - `grid.json.scale_source == "manual"`, `mm_per_px == 26.5`, dengan warning beda > 1%;
  - folder `00_input` dan `01_preprocess` ada di run baru (hasil salinan).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_stages.py tests/server/test_extraction_stages.py`
Expected: FAIL.

- [ ] **Step 3: Implementasi** `stages.py`, `overlay.py`, dan perubahan orchestrator/projects.

- [ ] **Step 4: Jalankan, pastikan lulus, lalu seluruh suite**

Run: `rtk uv run --env-file .env pytest -q`
Expected: PASS. Test server M3 yang lama tetap hijau; tahap 1–2 pada project impor-spec tetap jalan dan tidak menghalangi regenerate.

- [ ] **Step 5: Commit**

```bash
rtk git add core/extraction server tests
rtk git commit -m "feat(extract): stages 0-2 wired into the orchestrator with artifacts and grid overlay"
```

---

### Task 8: Dashboard — panel tahap 0–2

**Files:**
- Modify: `web/src/components/StagePanel.tsx`
- Create: `web/src/components/ExtractionStage.tsx`
- Test: `web/src/components/ExtractionStage.test.tsx`

**Interfaces:**
- Consumes: `GET /api/projects/{id}/runs/{rid}/stages/{n}` (`artifacts`) dan `/artifacts/{path}` (M3).
- Produces: `<ExtractionStage projectId run n />` untuk n ∈ {0, 1, 2}. Isinya:
  - **Tahap 0:** prompt, `params_final` (tabel key/nilai) dari `00_input/input.json`.
  - **Tahap 1:** gambar `01_preprocess/page.png`, info `deskew_deg` / `upscale` / `work_size`.
  - **Tahap 2:**
    - gambar `02_grid/overlay.png`;
    - ringkasan `mm/px` (3 desimal), `scale_source`, jumlah sumbu V/H, dan residu maks;
    - daftar warnings sebagai `InlineNotification` warning;
    - tombol "Isi skala manual" membuka modal dengan input "Skala manual (mm per px)" (> 0). "Jalankan" memanggil `useStartRun` dengan `{kind: "from_stage", from_stage: 2, params_override: {mm_per_px}}`. Body itu sudah didukung route M3 dan dipakai orchestrator sejak Task 7.
    - Bila `needs_attention`, pesan tahap tampil sebagai error dan tombol itu ditonjolkan (`kind="primary"`).
  - Teks "Ekstraksi otomatis tersedia di M5." hanya untuk n 3–5, diganti menjadi "Tersedia di M5b/M5c".

- [ ] **Step 1: Tulis test yang gagal**

Mock `api.get`.
- `test stage 2 shows overlay, scale and warnings`: metrics `{mm_per_px: 25.8127, scale_source: 'grid_dimensions', axes_v: 6, axes_h: 3}` dan satu warning. Harapan: teks `25.813 mm/px`, `6 × 3 sumbu`, `<img>` dengan `src` yang berakhiran `02_grid/overlay.png`, dan warning tampil.
- `test needs_attention offers manual scale`: klik "Isi skala manual", isi 26.5, lalu "Jalankan" → `api.post` dipanggil dengan `/api/projects/p1/runs` dan body `{kind: 'from_stage', from_stage: 2, params_override: {mm_per_px: 26.5}}`. Isian 0 ditolak inline.
- `test stage 0 lists final params`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test -- ExtractionStage`
Expected: FAIL.

- [ ] **Step 3: Implementasi**, lalu sambungkan di StagePanel untuk n ≤ 2.

- [ ] **Step 4: Jalankan, pastikan lulus**

Run: `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src && rtk git commit -m "feat(web): stage 0-2 panels with grid overlay, scale and manual-scale rerun"
```

---

### Task 9: Verifikasi end-to-end, benchmark skala, dan status di ROADMAP

- [ ] **Step 1: E2E lewat dashboard (Playwright MCP).** Jalankan uvicorn + Vite seperti M4 Task 15. Buat project baru dari `plan.jpeg` lewat halaman "Project baru".
  - Tahap 0–2 harus `succeeded`. Overlay grid menampilkan A–F dan 1–3 tepat di bulatan.
  - Run berhenti di tahap 5 dengan pesan "belum ada spec".
  - Waktu tahap 1 + 2 dicatat (NFR-PF-01: anggaran total tahap 1–5 ≤ 2 menit).
  - Screenshot `.playwright-mcp/m5a-grid.png`.
- [ ] **Step 2: Benchmark skala.** `rtk uv run python -m benchmarks.run_extraction_bench --grid <run>/stages/02_grid/grid.json --out benchmarks/reports/m5a-grid`. Expected: `scale_err ≤ 0.005`, `label_ok`, dan `offset_max_err_mm == 0`. Commit laporan Markdown dan JSON.
- [ ] **Step 3: Skala manual.** Di panel tahap 2, klik "Isi skala manual", isi 26.5, lalu Jalankan. Expected: run baru dengan tahap 0–1 `skipped`, tahap 2 `scale_source manual` dengan warning beda > 1%.
- [ ] **Step 4: Suite penuh + lint.**
  - Run: `rtk uv run --env-file .env pytest -q && rtk uv run ruff check . && cd web && rtk npm test && rtk npm run lint && rtk npm run build`
  - Expected: semua hijau.
- [ ] **Step 5: ROADMAP.** Centang tugas M5 yang benar-benar selesai: benchmark, tahap 0, tahap 1, dan tahap 2. Tulis blok "Status M5a" yang memuat:
  - skala dan galatnya;
  - label sumbu;
  - waktu tahap 1–2;
  - catatan lisensi PyMuPDF (R-14);
  - penyimpangan: title block tidak dideteksi, parser Strata ke M6, pemilihan halaman di form P1.

```bash
rtk git add ROADMAP.md benchmarks/reports && rtk git commit -m "docs: M5a status (benchmark + stages 0-2)"
```
