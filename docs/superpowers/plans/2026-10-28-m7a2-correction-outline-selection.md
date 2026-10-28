# M7a-2 — Upaya Koreksi, Kontur Bangunan Toleran Celah, Pemilihan Kandidat Stabil Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengukur berapa menit koreksi di editor yang dibutuhkan untuk mengubah hasil ekstraksi menjadi spec yang benar (kriteria sukses MVP #2: ≤ 15 menit), lalu menurunkan angka itu lewat dua perbaikan dengan dampak terbesar dari M7a:
- kontur bangunan yang toleran celah, karena rata-rata `gross_area_err` augmentasi ~0.6;
- pemilihan kandidat tahap 5 yang tidak berpindah-pindah.

**Architecture:**
- **Pengukuran:** `benchmarks/correction_effort.py` menghitung operasi editor yang dibutuhkan untuk mengubah spec prediksi menjadi GT (hapus/tambah dinding, pintu, tipe dan nama ruang, tangga). Setiap jenis operasi diberi waktu standar, lalu dijumlah menjadi menit. Angkanya masuk laporan `failure_modes` dan rata-ratanya masuk laporan augmentasi.
- **Kontur:** `core/spec/rooms.form_rooms` menutup celah ≤ 3 m pada gabungan footprint dinding (closing 1500 mm, join mitre) sebelum mengambil shell bangunan.
- **Pemilihan kandidat:** `core/extraction/select.choose` memilih kandidat medoid di antara kandidat valid yang skornya ≤ 0.05 di bawah skor tertinggi, yaitu kandidat dengan kesepakatan dinding rata-rata tertinggi terhadap kandidat valid lain.

**Tech Stack:** Python 3.12, Shapely 2, NumPy, pytest. Tidak ada dependensi baru.

**Spec:**
- `ROADMAP.md` M7, Kriteria selesai 1–2 ("Sisa galat Gatsu terkoreksi lewat panel koreksi ≤ 15 menit");
- `PRD/01-requirements.md` §3 (kriteria sukses MVP), FR-EX-17 (kontur terluar, luas kotor);
- `PRD/04-extraction.md` Tahap 5 (pemilihan kandidat);
- `PRD/03-layout-spec.md` §11 (ops editor, dipakai sebagai model operasi koreksi);
- `benchmarks/reports/m7a-final.md` (mode gagal yang tersisa).

Branch: `m7a2-correction` dari `main` (M7a sudah di-merge).

## Keputusan pengguna (2026-10-28)

- Arah M7 adalah **panel koreksi sebagai jalan utama**: ukur dan perpendek waktu koreksi, dan jangan lagi mengejar akurasi otomatis penuh lewat heuristik tambahan.
- Gatsu adalah satu-satunya denah nyata untuk sementara. Denah gedung lain menyusul dari PM.

## Model waktu koreksi

Asumsi berikut dicatat apa adanya dan bisa dikalibrasi nanti dengan sesi editor yang diukur:

| Operasi editor | Kapan dihitung | Detik |
|---|---|---|
| `delete_wall` | dinding prediksi yang < 50% berimpit dengan GT | 5 |
| `add_wall` | dinding GT yang < 50% tertutup prediksi | 20 |
| `delete_opening` | pintu prediksi tanpa pintu GT ≤ 500 mm | 5 |
| `add_opening` | pintu GT tanpa pintu prediksi ≤ 500 mm | 15 |
| `set_door` | pintu yang cocok tetapi tipe, engsel, arah, atau lebarnya salah | 10 |
| `set_room_type` | ruang GT bertipe ≠ `other`, bila ruang prediksi yang cocok (IoU ≥ 0.5) tipenya beda atau tidak ada ruang yang cocok | 8 |
| `rename_room` | ruang GT bernama, bila nama ruang prediksi yang cocok beda atau tidak ada ruang yang cocok | 8 |
| `set_stair` | flight GT yang jumlah riser atau arahnya salah, atau tidak ada | 20 |

Ruang tidak punya operasi geometri sendiri karena editor membentuk ruang dari dinding. Menambah dan menghapus dinding sudah memperbaiki bentuk ruang. Run yang berhenti (tanpa spec) dihitung sebagai menggambar ulang semua elemen GT.

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`;
  - test dijalankan dengan `rtk uv run --env-file .env pytest -q -m "not strata"`;
  - test Gatsu dan augmentasi ditandai `@pytest.mark.slow`.
- **Gerbang regresi setiap task perubahan `core/`:**
  - `python -m benchmarks.failure_modes --cache benchmarks/.cache/gatsu-gate --fresh` dan `python -m benchmarks.run_augment_bench`;
  - metrik target naik;
  - tidak ada metrik Gatsu atau rata-rata augmentasi yang mundur lebih dari toleransi (0.005 untuk rasio, 5 mm untuk posisi, 0.5 menit untuk upaya koreksi);
  - gagal gerbang → revert perubahan `core/` task itu dan catat sebagai ruling (protokol M7a);
  - ambang `FLOORS` di `tests/extraction/test_gatsu_pipeline.py` dinaikkan ke nilai baru dan tidak pernah dilonggarkan tanpa ruling.
- **Perbaikan harus umum:** tidak boleh ada koordinat, ID, atau teks khusus Gatsu di `core/`. Setiap aturan diuji dengan fixture sintetis dan diberi docstring tentang batasnya.
- **Bahasa dan konvensi:**
  - dokumen dalam bahasa Indonesia dengan istilah teknis Inggris;
  - commit dalam bahasa Inggris dan diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Closing kontur mengisi ceruk atau courtyard asli yang lebarnya < 3 m** (ceruk pintu masuk), sehingga luas kotor kelebihan. Ceruk ≥ 4 m harus tetap terbuka. Test di Task 2.
2. **Closing menyatukan dua massa bangunan yang terpisah < 3 m.** Massa yang berjarak ≥ 4 m harus tetap dua kontur. Test di Task 2.
3. **Kontur yang ditutup membuat ruang serpih** di antara kontur dan dinding yang putus. Serpih tetap harus tersaring oleh `MIN_ROOM_AREA_MM2`/`MAX_ASPECT`, dan pita dengan celah 2 m tetap membentuk ruang bay. Test di Task 2.
4. **Pemilihan medoid dengan hanya 1–2 kandidat valid.** Kesepakatan tidak bermakna di sini, jadi pilihan kembali ke aturan skor lama. Test di Task 3.
5. **Upaya koreksi untuk run yang berhenti** (tanpa spec) harus berupa upaya menggambar ulang semua elemen, bukan 0. Test di Task 1.

---

### Task 1: Metrik upaya koreksi (`benchmarks/correction_effort.py`)

**Files:**
- Create: `benchmarks/correction_effort.py`, `tests/benchmarks/test_correction_effort.py`
- Modify: `benchmarks/failure_modes.py` (laporan dan JSON memuat `effort`), `benchmarks/run_augment_bench.py` (`MEAN_KEYS` + `correction_min`, baris per varian), `benchmarks/reports/m7a2-baseline.*`, `benchmarks/reports/m7a2-augment-baseline.*`

**Interfaces:**
- Consumes: `wall_coverage` (`benchmarks/failure_modes.py`), `_door_geom`/`door_metrics` (pencocokan pintu ≤ 500 mm di `benchmarks/extraction_metrics.py`), `typed_room_count`-style IoU ≥ 0.5 matching.
- Produces:
  - `SECONDS: dict[str, int]` = `{"delete_wall": 5, "add_wall": 20, "delete_opening": 5, "add_opening": 15, "set_door": 10, "set_room_type": 8, "rename_room": 8, "set_stair": 20}`.
  - `correction_ops(pred: Spec | None, gt: Spec) -> dict[str, int]`: jumlah per operasi sesuai tabel "Model waktu koreksi". `pred=None` berarti menggambar ulang semua: `add_wall` = jumlah dinding GT, `add_opening` = jumlah pintu GT, `set_room_type` = ruang GT bertipe ≠ `other`, `rename_room` = ruang GT bernama, `set_stair` = jumlah flight GT.
  - `correction_minutes(ops: dict[str, int]) -> float`: Σ ops × SECONDS / 60, dibulatkan 1 desimal.
  - `failure_modes` menulis `{"effort": {"ops": ..., "minutes": ...}}`. `run_augment_bench` menambah metrik baris `correction_min`, dengan run berhenti dinilai upaya menggambar ulang, dan menambahkan `correction_min` ke `MEAN_KEYS` sebagai metrik lower-is-better.

- [ ] **Step 1: Tulis test yang gagal** (spec kecil dari `tests/spec/fixtures.py`):

```python
def test_identical_spec_needs_no_correction():
    gt = spec_with_rooms()
    assert correction_minutes(correction_ops(gt, gt)) == 0.0

def test_ops_count_each_kind():
    gt = spec_with_rooms()
    pred = gt.model_copy(deep=True)
    pred.walls = [w for w in pred.walls if w.id != "W4"] + [Wall(id="W9", a=(2000, 3000), b=(4000, 3000),
                                                                 thickness=100, kind="partition")]
    pred.openings = [o for o in pred.openings if o.id != "D2"]  # W4 hosts no door; D1 stays on W5
    pred.rooms[0].type = "other"
    ops = correction_ops(pred, gt)
    assert {k: v for k, v in ops.items() if v} == {"add_wall": 1, "delete_wall": 1, "add_opening": 1,
                                                    "set_room_type": 1}
    assert correction_minutes(ops) == round((20 + 5 + 15 + 8) / 60, 1)  # 0.8

def test_stopped_run_costs_a_full_redraw():
    gt = spec_with_rooms()
    ops = correction_ops(None, gt)
    assert ops["add_wall"] == len(gt.walls) and ops["add_opening"] == len(gt.openings)
    assert correction_minutes(ops) > 0
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/benchmarks/test_correction_effort.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementasi** sesuai Interfaces. Integrasikan ke `failure_modes` dan `run_augment_bench`.

- [ ] **Step 4: Jalankan test, lalu baseline**

Run: `rtk uv run --env-file .env pytest tests/benchmarks -q` lalu `rtk uv run --env-file .env python -m benchmarks.failure_modes --cache benchmarks/.cache/gatsu-gate --fresh --out benchmarks/reports/m7a2-baseline` dan `rtk uv run --env-file .env python -m benchmarks.run_augment_bench --workers 8 --out benchmarks/reports/m7a2-augment-baseline`
Expected: test PASS. Laporan baseline mencantumkan menit koreksi Gatsu dan rata-rata menit koreksi augmentasi, dan ini menjadi angka acuan kriteria ≤ 15 menit.

- [ ] **Step 5: Commit**

```bash
rtk git add benchmarks/correction_effort.py benchmarks/failure_modes.py benchmarks/run_augment_bench.py tests/benchmarks/test_correction_effort.py benchmarks/reports/m7a2-*
rtk git commit -m "bench: correction-effort metric (editor minutes to reach the GT)"
```

---

### Task 2: Kontur bangunan toleran celah

**Files:**
- Modify: `core/spec/rooms.py` (`form_rooms`: shell bangunan diambil dari gabungan footprint yang sudah di-closing)
- Test: `tests/spec/test_rooms.py`, `tests/extraction/test_gatsu_pipeline.py` (`FLOORS`)

**Interfaces:**
- Produces:
  - `OUTLINE_CLOSE_MM = 1500`.
  - `_closed(union: Polygon | MultiPolygon) -> Polygon | MultiPolygon`: `union.buffer(1500, join_style="mitre").buffer(-1500, join_style="mitre")` digabung kembali dengan `union`, supaya tidak ada bagian footprint yang hilang.
  - `form_rooms` mengambil `shells` dari `_closed(union)`. `dividers` tidak berubah, karena ruang tetap dibatasi dinding asli. Luas kotor (`derive`) otomatis mengikuti `building_outline`.

Hasil eksperimen (augmentasi M7a, luas dalam m², GT 563.8):
- a00: 536 → 566;
- a08 (rotasi −2°): 149 → 559;
- a18: 168 → 567;
- a12: 121 → 396;
- skala 0.6 tetap gagal karena ekstraksinya runtuh total.

- [ ] **Step 1: Tulis test yang gagal:**

```python
def test_outline_bridges_a_2m_gap_in_the_outer_wall():
    # a 12 x 8 m box whose top wall is missing a 2 m stretch: the outline (and gross area) is still the box
    rooms, outlines = form_rooms(box_with_gap(gap_mm=2000))
    assert len(outlines) == 1 and outlines[0].area == pytest.approx(12_200 * 8_200, rel=0.01)

def test_outline_keeps_a_4m_recess():
    # an entrance recess 4 m wide, 2 m deep: not filled
    _, outlines = form_rooms(box_with_recess(width_mm=4000, depth_mm=2000))
    assert outlines[0].area == pytest.approx(12_200 * 8_200 - 4000 * 2000, rel=0.01)

def test_two_masses_4m_apart_stay_two_outlines():
    _, outlines = form_rooms(two_boxes(gap_mm=4000))
    assert len(outlines) == 2

def test_band_with_a_gap_still_forms_bays_not_slivers():
    rooms, _ = form_rooms(band_with_fins_and_gap(gap_mm=2000))
    assert all(r.area >= 1_000_000 for r in rooms) and len(rooms) >= 3
```

Fixture `box_with_gap` dan sejenisnya dibangun dari `two_room_spec` (pola test `test_band_between_fins_forms_one_room_per_bay` di M7a).

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/spec/test_rooms.py -q`
Expected: FAIL pada test celah 2 m. Test ceruk dan dua massa boleh sudah lolos; keduanya penjaga.

- [ ] **Step 3: Implementasi** sesuai Interfaces.

- [ ] **Step 4: Gerbang.** Jalankan `failure_modes` (`--out benchmarks/reports/m7a2-t2`) dan `run_augment_bench` (`--out benchmarks/reports/m7a2-augment-t2`).
  - Metrik target: rata-rata `gross_area_err` augmentasi dan menit koreksi.
  - Naikkan `FLOORS` bila membaik.
  - Bila gagal gerbang, revert perubahan `core/` dan catat sebagai ruling.

- [ ] **Step 5: Commit**

```bash
rtk git add core/spec/rooms.py tests/spec/test_rooms.py tests/extraction/test_gatsu_pipeline.py benchmarks/reports/m7a2-*t2*
rtk git commit -m "fix(rooms): building outline bridges gaps up to 3 m in the outer walls"
```

---

### Task 3: Pemilihan kandidat tahap 5 yang stabil (medoid)

**Files:**
- Modify: `core/extraction/select.py` (`choose`), `core/extraction/stages.py` (`stage_validate` meneruskan spec kandidat)
- Test: `tests/extraction/test_select.py`

**Interfaces:**
- Produces:
  - `NEAR_TOP = 0.05`.
  - `wall_agreement(a: Spec, b: Spec, tol_mm: float = 150) -> float`: F1 dari dua porsi panjang, yaitu porsi garis tengah dinding `a` yang ≤ tol dari garis tengah dinding `b`, dan sebaliknya. Dihitung dengan Shapely (buffer garis tengah), tanpa impor dari `benchmarks/`.
  - `choose(scored: list[dict], specs: dict[int, Spec] | None = None) -> dict | None`:
    - aturan lama tetap berlaku untuk menyaring kandidat: `passed`, lalu cakupan ≥ 0.6 × cakupan terbaik;
    - bila `specs` ada dan ≥ 3 kandidat valid berada ≤ `NEAR_TOP` dari skor tertinggi, pilih yang rata-rata `wall_agreement`-nya terhadap kandidat dekat-puncak lainnya paling tinggi; seri diputus dengan skor, lalu cakupan, lalu indeks;
    - selain itu, perilaku lama (seri ≤ 0.01 → cakupan → indeks).
  - `stage_validate` memanggil `choose(scored, specs)`.

- [ ] **Step 1: Tulis test yang gagal:**

```python
def test_medoid_beats_a_slightly_higher_outlier():
    # three near-top candidates: 0 and 2 agree, 1 scores 0.015 higher with different walls
    scored = [row(0, 0.855), row(1, 0.871), row(2, 0.850)]
    specs = {0: walls_a(), 1: walls_b(), 2: walls_a_shifted_20mm()}
    assert choose(scored, specs)["index"] == 0

def test_few_candidates_fall_back_to_score():
    scored = [row(0, 0.855), row(1, 0.871)]
    assert choose(scored, {0: walls_a(), 1: walls_b()})["index"] == 1

def test_wall_agreement_symmetric_bounds():
    assert wall_agreement(walls_a(), walls_a()) == pytest.approx(1.0)
    assert wall_agreement(walls_a(), walls_b()) < 0.5
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/extraction/test_select.py -q`
Expected: FAIL (`choose()` tidak menerima `specs`, `wall_agreement` belum ada).

- [ ] **Step 3: Implementasi** sesuai Interfaces.

- [ ] **Step 4: Gerbang** seperti Task 2 (`--out ...m7a2-t3`).
  - Metrik target: menit koreksi Gatsu, serta rata-rata `wall_precision` dan menit koreksi augmentasi.
  - Catat kandidat yang dipilih untuk Gatsu.
  - Bila gagal gerbang, revert perubahan `core/`.

- [ ] **Step 5: Commit**

```bash
rtk git add core/extraction/select.py core/extraction/stages.py tests/extraction/test_select.py tests/extraction/test_gatsu_pipeline.py benchmarks/reports/m7a2-*t3*
rtk git commit -m "fix(extract): stage 5 picks the medoid of the near-top candidates"
```

---

### Task 4: Laporan akhir, menit koreksi vs 15, status

**Files:**
- Create: `benchmarks/reports/m7a2-final.md` + `.json`
- Modify: `ROADMAP.md` (Status M7a-2)

- [ ] **Step 1: Laporan.** `m7a2-final.md` berisi:
  - menit koreksi Gatsu, baseline → akhir, dengan rincian per operasi;
  - rata-rata menit koreksi augmentasi;
  - metrik Gatsu dan rata-rata augmentasi lainnya;
  - kriteria MVP #2 (≤ 15 menit): terpenuhi atau tidak;
  - operasi koreksi terbesar, sebagai masukan pekerjaan editor berikutnya (misalnya "hapus N dinding palsu" → aksi hapus massal).

- [ ] **Step 2: Suite penuh**

Run: `rtk uv run --env-file .env pytest -q -m "not strata" && rtk uv run ruff check . && cd web && rtk npx vitest run && rtk npm run lint && rtk npm run build`
Expected: semua hijau.

- [ ] **Step 3: ROADMAP.** Tulis "Status M7a-2" dengan angka dan sisa pekerjaan.

- [ ] **Step 4: Commit**

```bash
rtk git add benchmarks/reports/m7a2-final.* ROADMAP.md
rtk git commit -m "docs: M7a-2 status and correction-effort report"
```
