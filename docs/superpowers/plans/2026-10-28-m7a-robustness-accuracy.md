# M7a — Ketahanan & Akurasi Ekstraksi (Set Augmentasi, Atribusi Galat, Perbaikan Ekstraktor) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- Membuktikan pipeline tahan terhadap variasi gambar, lewat ±30 varian augmentasi `plan.jpeg` dengan GT yang sudah diketahui.
- Menaikkan akurasi Gatsu lewat perbaikan ekstraktor yang **umum**, dengan dinding dan ruang lebih dulu.

Setiap perbaikan diukur lewat atribusi galat dan dijaga gerbang regresi di Gatsu dan set augmentasi.

**Architecture:**
- **Pengukuran:**
  - `benchmarks/failure_modes.py` mengatribusikan setiap galat Gatsu ke penyebabnya:
    - dinding GT yang terlewat: satu sisi, ganda tapi tidak berpasangan, samar, atau terhapus mask;
    - dinding palsu: per wilayah (hatch, simbol, teks, tangga);
    - ruang: bocor, atau pita luar tidak terpecah.
  - `benchmarks/augment/` membuat varian deterministik dan menjalankan tahap 0–5 per varian, lalu menilai varian **relatif terhadap hasil Gatsu asli**.
- **Perbaikan:** satu task per mode gagal, diurutkan dari panjang dinding atau jumlah ruang yang dipulihkan (data atribusi 2026-10-28). Setiap task:
  1. mengisolasi satu kasus Gatsu menjadi fixture sintetis (RED);
  2. menerapkan aturan umum;
  3. lolos gerbang: metrik target naik, tidak ada metrik Gatsu yang mundur, dan tingkat lolos augmentasi tidak turun.

**Tech Stack:** Python 3.12, OpenCV, NumPy, Shapely 2, scikit-image (sudah terpasang), pytest. Tidak ada dependensi baru.

**Spec:**
- `ROADMAP.md` M7, bagian "Tugas — Ketahanan" dan Kriteria selesai 1–2;
- `PRD/01-requirements.md` §3 (kriteria sukses MVP) dan NFR-AC-01…11;
- `PRD/04-extraction.md` §3 (tahap 3: masks, S1/S2, postprocess), Tahap 4 (ruang, pita luar §2b, FR-EX-17);
- `benchmarks/extraction_metrics.py` (`THRESHOLDS`, `LOWER_IS_BETTER`, `evaluate`).

Branch: `m7-hardening` dari `main` (M0–M6 sudah di-merge). M7 dipecah menjadi tiga plan:
- **M7a:** plan ini;
- **M7b:** denah sintetis;
- **M7c:** Docker dan deploy ke gspe-ai2 lewat SSH key yang dipasang pengguna.

## Keputusan pengguna (2026-10-28)

- **Kriteria set augmentasi** ("≥ 80% varian mencapai ≥ 90% target") dinilai **relatif ke hasil Gatsu asli**:
  - varian lolos bila setiap metriknya ≥ 0.9 × nilai Gatsu asli;
  - untuk metrik lower-is-better, syaratnya ≤ nilai asli / 0.9;
  - akurasi absolut terhadap NFR dikejar lewat perbaikan ekstraktor, bukan lewat syarat ini.
- **Deploy (M7c):** pengguna memasang SSH key ke gspe-ai2. `server-info.txt` tidak pernah dibaca.

## Data atribusi awal (Gatsu, spec tahap 5, 2026-10-28)

- **Metrik saat ini:**

  | Metrik | Nilai | Target NFR |
  |---|---|---|
  | `wall_recall` | 0.766 | 0.95 |
  | `wall_precision` | 0.80 | 0.95 |
  | `door_recall` | 0.42 | 0.90 |
  | `room_match` | 0.02 | 0.90 |
  | `wall_iou` | 0.51 | 0.85 |
  | `gross_area_err` | 0.03 | 0.01 |

  Jumlah ruang 22 vs 48 GT; jumlah pintu 30 vs 19 GT.
- **Dinding GT terlewat:** 20 dari 77 (109 m dari 469 m):
  - **9 satu sisi:** hanya satu garis muka bertinta. Kebanyakan dinding luar panjang yang berbatasan dengan pita luar, misalnya W11/W13 sepanjang 13 m.
  - **6 bergaris ganda tapi tidak berpasangan:** kedua muka ada di `clean`, tetapi stroke-nya terputus-putus (contoh W53, W72, W32).
  - **4 samar** (low wall / partisi), dan **1 terhapus mask** (W67).
- **Dinding palsu:** 67 dari 147 dinding prediksi (84 m), menumpuk di area MEP padat (Battery/UPS, jalur kabel) dan tangga.
- **Ruang:** 25 dari 48 ruang GT bertipe `outdoor` (kotak pita luar di antara sirip). Ruang dalam bocor dan menyatu karena dinding yang terlewat (contoh: dinding bawah R. MEETING di grid 2).

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`;
  - test dijalankan dengan `rtk uv run --env-file .env pytest -q -m "not strata"`;
  - test yang memakai Gatsu atau set augmentasi ditandai `@pytest.mark.slow`.
- **Perbaikan harus umum:**
  - tidak boleh ada koordinat, ID, atau teks khusus Gatsu di `core/`;
  - setiap aturan baru diuji dengan fixture sintetis (`np.zeros` + `cv2.line`) yang mereproduksi polanya;
  - setiap aturan baru diberi `ponytail:` atau docstring yang menyebut batasnya.
- **Gerbang regresi setiap task perbaikan:**
  1. metrik target task naik di Gatsu;
  2. tidak ada metrik `evaluate` Gatsu yang mundur lebih dari toleransi;
  3. tingkat lolos set augmentasi tidak turun;
  4. waktu tahap 1–5 Gatsu ≤ 120 s (NFR-PF-01);
  5. determinisme tetap (NFR-RL-06).

  Toleransi mundur: 0.005 untuk rasio, 5 mm untuk posisi. Ambang di `test_gatsu_pipeline.FLOORS` dinaikkan ke nilai terukur yang baru (dibulatkan ke bawah) di akhir task.
- **Bahasa dan konvensi:**
  - dokumen dalam bahasa Indonesia dengan istilah teknis Inggris;
  - commit dalam bahasa Inggris dan diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Varian yang tahap 2-nya gagal membaca skala atau grid** (resolusi 0.6×, JPEG q 40). Varian dihitung gagal dengan alasan tercatat; runner tidak berhenti dan tidak memakai skala default diam-diam. Test di Task 2.
2. **Aturan dinding satu sisi menerima garis panjang yang bukan dinding** (jalur kabel, garis dimensi yang lolos penghapus, sumbu grid). Syarat kedua ujung bersambung ke dinding lain harus menolak garis berujung bebas. Test di Task 3.
3. **Pemasangan stroke terputus menggabungkan dua dinding sejajar yang berbeda.** Dua partisi berdekatan (jarak < `t_max`) tidak boleh dipasangkan silang. Test di Task 4.
4. **Pemecahan pita luar membuat ruang `outdoor` dari ruang dalam yang sempit** (koridor, shaft). Hanya ruang yang menyentuh kontur terluar yang boleh dipecah. Test di Task 5.
5. **Penyaringan dinding palsu di area MEP menghapus dinding asli yang melewati area hatch** (dinding ruang baterai). Penyaringan hanya untuk garis tanpa sambungan dan berkeyakinan rendah. Test di Task 6.

---

### Task 1: Atribusi galat (`benchmarks/failure_modes.py`)

**Files:**
- Create: `benchmarks/failure_modes.py`, `tests/benchmarks/test_failure_modes.py`, `benchmarks/reports/m7a-baseline.md` + `.json`

**Interfaces:**
- Consumes: `evaluate`, `_samples`, `_nearest` (`benchmarks/extraction_metrics.py`); `build_masks` (`core/extraction/geometry/masks.py`); `extract_strokes`; `gatsu_stages` (`benchmarks/llm_items.py`).
- Produces:
  - `wall_coverage(w: Wall, ref: list[Wall], tol_mm: float = 150, angle_deg: float = 5) -> float`: porsi garis `w` yang ≤ tol dari dinding `ref` yang sejajar.
  - `ink_profile(img: np.ndarray, w: Wall, to_px, offsets_mm: tuple[float, ...]) -> tuple[float, ...]`: porsi 40 titik sampel (5–95% panjang) yang mengenai tinta dalam jendela 3×3, per offset normal.
  - `classify_missed(gt: Spec, pred: Spec, binary, clean, to_px) -> list[dict]`:
    - mencakup dinding GT dengan `wall_coverage < 0.5`;
    - `mode`:
      - `single`: hanya satu muka atau tengah ≥ 0.6;
      - `double`: kedua muka ≥ 0.6 di `binary` dan di `clean`;
      - `erased`: ≥ 0.6 di `binary`, < 0.6 di `clean`;
      - `faint`: selain itu;
    - field: `{id, kind, thickness, length_mm, mode, ink_binary, ink_clean}`.
  - `classify_false(pred: Spec, gt: Spec, masks: dict, texts_mm: list, to_px) -> list[dict]`:
    - mencakup dinding prediksi dengan `wall_coverage < 0.5` terhadap GT;
    - `region` adalah wilayah pertama yang berlaku, dengan urutan:
      - `hatch`: porsi sampel di `masks["hatch"]` ≥ 0.3;
      - `symbol`: porsi di `masks["symbol"]` ≥ 0.3;
      - `text`: teks OCR ≤ 600 mm;
      - `stair`: porsi di mask tangga ≥ 0.3;
      - `free_end`: kedua ujung tidak bersambung;
      - `other`.
  - `classify_rooms(gt: Spec, pred: Spec) -> dict`: `{"outdoor_gt", "outdoor_matched", "inner_gt", "inner_matched", "merged": [[gt ids] per pred room covering ≥ 2 GT rooms by ≥ 50% area]}`.
  - `python -m benchmarks.failure_modes --out benchmarks/reports/m7a-<name>` menulis `.md` + `.json` + `.png`. Gambar `.png` menandai yang terlewat (magenta), palsu (merah), benar (hijau), dan ruang `outdoor` GT (biru).

- [ ] **Step 1: Tulis test yang gagal** (fixture sintetis 600×600 px, 10 mm/px):

```python
def test_classify_missed_modes():
    # GT W1 drawn as two face lines (double, but no pred wall), W2 one face only, W3 nothing on the page,
    # W4 drawn in `binary` but absent from `clean` (erased)
    modes = {r["id"]: r["mode"] for r in classify_missed(gt, pred_empty, binary, clean, to_px)}
    assert modes == {"W1": "double", "W2": "single", "W3": "faint", "W4": "erased"}

def test_classify_false_regions():
    regions = {r["id"]: r["region"] for r in classify_false(pred, gt, masks, texts_mm, to_px)}
    assert regions["W9"] == "hatch" and regions["W8"] == "free_end"

def test_classify_rooms_counts_merges():
    out = classify_rooms(gt_two_rooms_plus_band, pred_one_room)
    assert out["inner_gt"] == 2 and out["merged"] == [["R1", "R2"]] and out["outdoor_gt"] == 1

def test_wall_coverage_partial():
    assert wall_coverage(half_overlapping, [ref]) == pytest.approx(0.5, abs=0.05)
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/benchmarks/test_failure_modes.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementasi** sesuai Interfaces. Masks dibangun ulang dengan `build_masks` dan params kandidat terpilih (`05_validate/chosen.json`).

- [ ] **Step 4: Jalankan test, pastikan lolos, lalu tulis baseline**

Run: `rtk uv run --env-file .env pytest tests/benchmarks/test_failure_modes.py -q` lalu `rtk uv run --env-file .env python -m benchmarks.failure_modes --out benchmarks/reports/m7a-baseline`
Expected: test PASS. Laporan baseline mencantumkan 20 terlewat (9 single, 6 double, 4 faint, 1 erased), 67 palsu dengan rincian per wilayah, serta 25 `outdoor` dan 23 ruang dalam GT. Bila angkanya berbeda dari data awal di atas, catat sebagai ruling dan pakai angka laporan.

- [ ] **Step 5: Commit**

```bash
rtk git add benchmarks/failure_modes.py tests/benchmarks/test_failure_modes.py benchmarks/reports/m7a-baseline.*
rtk git commit -m "bench: attribute Gatsu extraction errors to failure modes"
```

---

### Task 2: Set augmentasi dan runner (`benchmarks/augment/`)

**Files:**
- Create: `benchmarks/augment/__init__.py`, `benchmarks/augment/variants.py`, `benchmarks/run_augment_bench.py`, `tests/benchmarks/test_augment.py`, `benchmarks/reports/m7a-augment-baseline.md` + `.json`
- Modify: `.gitignore` (`benchmarks/.cache/augment/`)

**Interfaces:**
- Produces:
  - `VARIANTS: list[dict]`: 30 varian deterministik (seed tetap). Setiap varian `{"id": "a01", "scale": float, "jpeg_q": int, "rotate_deg": float, "margin_px": int, "blur": float, "noise": float}`:
    - `scale` ∈ {0.6, 0.75, 1.0, 1.5, 2.0};
    - `jpeg_q` ∈ {40, 60, 80, 95};
    - `rotate_deg` ∈ [−2, 2];
    - `margin_px` ∈ {−40, 0, 80} (negatif = crop ke dalam);
    - `blur` σ ∈ {0, 0.6, 1.0};
    - `noise` σ ∈ {0, 4, 8}.

    Varian `a00` adalah identitas (gambar asli).
  - `render_variant(img: np.ndarray, v: dict) -> np.ndarray`, dengan urutan: rotasi (`warpAffine`, border putih), margin, skala (`INTER_AREA` / `INTER_CUBIC`), blur, noise, lalu encode JPEG q.
  - **GT varian = GT Gatsu tanpa perubahan.** Frame mm pipeline berjangkar pada sumbu grid dan skala dari dimensi, jadi transformasi gambar tidak mengubah koordinat mm. Hanya artefak berbasis piksel yang ikut bertransformasi, dan runner tidak memakainya.
  - `relative_pass(metrics: dict, base: dict) -> tuple[bool, list[str]]`:
    - lolos bila setiap metrik di `THRESHOLDS` yang punya nilai di keduanya memenuhi `v ≥ 0.9 × base`, atau `v ≤ base / 0.9` untuk `LOWER_IS_BETTER`;
    - mengembalikan daftar metrik yang gagal;
    - metrik dengan base 0 dilewati (tidak bisa relatif).
  - `python -m benchmarks.run_augment_bench [--variants a00,a05] [--workers N] [--out benchmarks/reports/m7a-augment-<name>]`:
    - menjalankan tahap 0–5 per varian di `benchmarks/.cache/augment/<id>/`;
    - mengulang varian yang cache-nya lebih tua dari HEAD kode (`git rev-parse HEAD` dicatat per varian);
    - per varian: metrik, status tahap 2 dan 5, waktu, `relative_pass` terhadap `a00`;
    - ringkasan: tingkat lolos, plus metrik yang paling sering gagal.
  - Varian dengan tahap 2 atau 5 `failed`/`needs_attention` tanpa spec dihitung **gagal** dengan `reason` tercatat (Review Focus 1).

- [ ] **Step 1: Tulis test yang gagal:**

```python
def test_variants_are_deterministic_and_identity_first():
    assert len(VARIANTS) == 30 and VARIANTS[0] == {"id": "a00", "scale": 1.0, "jpeg_q": 95, "rotate_deg": 0.0,
                                                   "margin_px": 0, "blur": 0.0, "noise": 0.0}
    assert VARIANTS == variants_from_seed()  # same list on every call

def test_render_variant_scale_and_white_border():
    out = render_variant(np.full((100, 200), 255, np.uint8), {"id": "x", "scale": 0.5, "jpeg_q": 95, "rotate_deg": 2.0,
                                                            "margin_px": 10, "blur": 0.0, "noise": 0.0})
    assert out.shape[:2] == (60, 110) and out[0, 0] > 240

def test_relative_pass_rules():
    base = {"wall_recall": 0.8, "gross_area_err": 0.03, "room_match": 0.0}
    assert relative_pass({"wall_recall": 0.73, "gross_area_err": 0.033, "room_match": 0.0}, base) == (True, [])
    assert relative_pass({"wall_recall": 0.70, "gross_area_err": 0.04, "room_match": 0.0}, base) == \
        (False, ["gross_area_err", "wall_recall"])

def test_failed_stage_counts_as_failed(tmp_path, monkeypatch):  # stage 2 needs_attention -> no spec
    row = run_variant(variant, tmp_path, stage_fns=fake_failing_grid)
    assert row["passed"] is False and row["reason"].startswith("stage 2")
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/benchmarks/test_augment.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementasi** sesuai Interfaces. `run_variant` memakai runner tahap 0–5 yang sama dengan `benchmarks/llm_items.gatsu_stages`. Runner itu diekstrak menjadi `run_stages(project_dir: Path, image_bytes: bytes, filename: str) -> Path` di `benchmarks/llm_items.py` dan dipakai oleh keduanya. Paralelisme berjalan per varian, dengan sweep tahap 3 di setiap varian memakai 1 worker (`SWEEP_WORKERS=1` lewat env var) supaya CPU tidak oversubscribe.

- [ ] **Step 4: Jalankan test, pastikan lolos, lalu jalankan baseline**

Run: `rtk uv run --env-file .env python -m benchmarks.run_augment_bench --out benchmarks/reports/m7a-augment-baseline`
Expected: 30 baris dengan tingkat lolos tercatat. Waktu dicatat; perkiraan 30 × 25 s dibagi jumlah worker.

- [ ] **Step 5: Commit**

```bash
rtk git add benchmarks/augment benchmarks/run_augment_bench.py benchmarks/llm_items.py tests/benchmarks/test_augment.py benchmarks/reports/m7a-augment-baseline.* .gitignore
rtk git commit -m "bench: 30-variant augmentation set with relative pass rule"
```

---

### Protokol task perbaikan (Task 3–6)

Setiap task perbaikan mengikuti langkah yang sama:

1. **Diagnosa.** Pakai superpowers:systematic-debugging. Jalankan `benchmarks/failure_modes.py`, pilih dua kasus Gatsu dari mode target, lalu telusuri di tahap mana kasus itu hilang atau muncul: mask → stroke → pairing → postprocess → assemble. Tulis akar penyebabnya di ledger.
2. **RED.** Tulis fixture sintetis yang mereproduksi pola itu, plus fixture "jangan tersentuh" dari Review Focus task. Jalankan dan pastikan gagal.
3. **GREEN.** Terapkan aturan umum yang paling kecil.
4. **Gerbang** (Global Constraints):
   - jalankan `failure_modes` dan `run_augment_bench`, lalu bandingkan dengan laporan sebelumnya;
   - naikkan `FLOORS` di `test_gatsu_pipeline.py` ke nilai terukur yang baru;
   - laporan `benchmarks/reports/m7a-<task>.md` mencatat sebelum/sesudah.
5. **Gerbang gagal.** Bila metrik target tidak naik, atau ada metrik yang mundur dan tidak bisa diperbaiki dengan aturan umum, revert perubahan `core/` task ini, catat temuannya sebagai ruling, lalu lanjut ke task berikutnya.

---

### Task 3: Dinding satu sisi (9 dinding, ~50 m)

**Files:**
- Modify: `core/extraction/geometry/walls_s2.py` (atau `postprocess.py`, sesuai diagnosa)
- Test: `tests/extraction/geometry/test_walls_s2.py`, `tests/extraction/test_gatsu_pipeline.py`

**Hipotesis awal** (diagnosa yang menentukan):
- Dinding luar yang berbatasan dengan pita luar hanya punya satu garis muka.
- S2 butuh pasangan, dan `unpaired_partitions` mewajibkan garis ≥ 2 × median lebar, sehingga garis muka tunggal yang setebal garis biasa selalu dibuang.

**Arah aturan:** garis tak berpasangan yang panjang (≥ 1000 mm) **dan bersambung ke dinding di kedua ujung** (atau dibatasi kontur pita luar) menjadi dinding. Tebalnya default proyek, dan garis muka menentukan sisi dinding: pusat digeser setengah tebal ke arah dalam bangunan.

**Test wajib:**
- `test_single_face_wall_between_two_walls_is_kept` (RED lalu GREEN);
- `test_single_line_with_free_end_is_not_a_wall`: garis 3 m dengan satu ujung bebas tetap dibuang (Review Focus 2);
- `test_single_line_on_grid_axis_is_not_a_wall`.

**Metrik target:** `wall_recall`.

- [ ] Langkah 1–5 sesuai protokol, lalu commit `fix(extract): single-face walls joined at both ends`.

---

### Task 4: Garis ganda terputus yang tidak berpasangan (6 dinding)

**Files:**
- Modify: `core/extraction/geometry/walls_s2.py` (`pair_strokes`, sesuai diagnosa)
- Test: `tests/extraction/geometry/test_walls_s2.py`

**Hipotesis awal:** kedua muka ada, tetapi stroke-nya terputus di titik yang berbeda di tiap sisi (contoh W53: 224–611 dan 622–741 vs 280–524 dan 553–667). Pemasangan per interval kehilangan bagian yang tidak tumpang tindih, atau sebuah muka sudah "diklaim" pasangan lain.

**Arah aturan:** sambungkan stroke kolinear dengan celah ≤ 2 × tebal garis sebelum pemasangan, atau pasangkan per interval gabungan. Dua partisi sejajar yang berdekatan tetap tidak boleh dipasangkan silang (Review Focus 3).

**Test wajib:**
- `test_fragmented_faces_pair_into_one_wall`;
- `test_two_adjacent_partitions_stay_two_walls`.

**Metrik target:** `wall_recall`, `wall_iou`.

- [ ] Langkah 1–5 sesuai protokol, lalu commit `fix(extract): pair fragmented double-line walls`.

---

### Task 5: Ruang pita luar (`outdoor`) dan ruang dalam yang menyatu

**Files:**
- Modify: `core/extraction/rooms/assemble.py` (dan/atau `core/extraction/geometry/columns.py` untuk sirip/pilaster, sesuai diagnosa)
- Test: `tests/extraction/rooms/test_assemble.py`

**Hipotesis awal:**
- 25 ruang `outdoor` GT adalah kotak pita luar yang dibatasi sirip (dinding pendek atau pilaster tegak lurus di antara dua garis luar).
- Prediksi tidak membentuk sirip sebagai batas ruang, sehingga pita menjadi satu ruang panjang atau ikut ruang lain.
- Ruang dalam menyatu karena dinding yang terlewat; ini sebagian sudah diperbaiki Task 3–4.

Ukur ulang `classify_rooms` setelah Task 3–4, sebelum mendiagnosa.

**Arah aturan:** sirip yang terdeteksi (kolom/pilaster atau dinding pendek antara dua garis pita) memotong ruang pita menjadi ruang-ruang `outdoor`. Pemotongan hanya untuk ruang yang menyentuh kontur terluar (FR-EX-17, PRD/04 §2b).

**Test wajib:**
- `test_band_split_by_fins_into_outdoor_rooms`;
- `test_narrow_inner_corridor_is_not_split` (Review Focus 4).

**Metrik target:** `room_match`, `rooms_pred` mendekati `rooms_gt`.

- [ ] Langkah 1–5 sesuai protokol, lalu commit `fix(rooms): split the outer band at fins into outdoor rooms`.

---

### Task 6: Dinding palsu di area MEP padat

**Files:**
- Modify: `core/extraction/geometry/postprocess.py` atau `confidence.py` (sesuai diagnosa)
- Test: `tests/extraction/geometry/test_postprocess.py`

**Hipotesis awal:** 67 dinding palsu (84 m) adalah garis pendek tanpa sambungan di area hatch, simbol peralatan, jalur kabel berlabel, dan tangga. Rincian per wilayah diambil dari laporan Task 1.

**Arah aturan:** buang garis yang memenuhi semua syarat berikut:
- tidak bersambung di kedua ujung;
- berada di wilayah `hatch`/`symbol`/`stair`, atau ≤ 600 mm dari teks kelas `annotation`;
- berkeyakinan < 0.5.

Dinding yang bersambung tidak pernah dibuang aturan ini (Review Focus 5).

**Test wajib:**
- `test_free_short_line_in_hatch_is_dropped`;
- `test_connected_wall_through_hatch_is_kept`.

**Metrik target:** `wall_precision`, tanpa `wall_recall` mundur.

- [ ] Langkah 1–5 sesuai protokol, lalu commit `fix(extract): drop free-ended clutter lines in MEP areas`.

---

### Task 7: Style profile Gatsu, regresi, dan status M7a

**Files:**
- Create: `benchmarks/gatsu/style_profile.json`, `benchmarks/reports/m7a-final.md` + `.json`
- Modify: `tests/extraction/test_gatsu_pipeline.py` (`FLOORS`, `TYPED_FLOOR`), `ROADMAP.md` (M7: tugas ketahanan + "Status M7a")

**Interfaces:**
- `benchmarks/gatsu/style_profile.json`: format `core/extraction/profiles.py` (`{"id": "gatsu", "params": <params kandidat terpilih Gatsu>, "from_run": null, "note": ...}`), dibuat dengan `save_profile` dari run Gatsu terakhir.
- `test_gatsu_style_profile_is_valid`: file itu adalah JSON profile yang sah. Bentuknya sama dengan yang ditulis `save_profile` dan bisa disalin ke `DATA_DIR/profiles/` untuk dipakai server. `sweep_params(12, profile)` menaruh params-nya di posisi pertama.

- [ ] **Step 1: Test profile (RED lalu GREEN), lalu tulis file profile.**

- [ ] **Step 2: Laporan akhir.**
  - Jalankan `failure_modes` dan `run_augment_bench` final.
  - Isi `m7a-final.md`: metrik Gatsu baseline → final per metrik dibandingkan NFR, tingkat lolos augmentasi baseline → final, mode gagal yang tersisa, dan perbaikan yang di-revert beserta alasannya.

- [ ] **Step 3: Suite penuh**

Run: `rtk uv run --env-file .env pytest -q -m "not strata" && rtk uv run ruff check . && cd web && rtk npx vitest run && rtk npm run lint && rtk npm run build`
Expected: semua hijau.

- [ ] **Step 4: ROADMAP.** Centang tugas ketahanan yang selesai. Tulis "Status M7a" dengan angka, kriteria selesai 1–2 terpenuhi atau tidak (jujur), dan sisa galat untuk panel koreksi.

- [ ] **Step 5: Commit**

```bash
rtk git add benchmarks/gatsu/style_profile.json benchmarks/reports/m7a-final.* tests ROADMAP.md
rtk git commit -m "docs: M7a status, Gatsu style profile and final robustness report"
```
