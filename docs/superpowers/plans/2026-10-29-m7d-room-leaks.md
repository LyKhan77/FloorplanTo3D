# M7d — Ruang Bocor (PRD/04 §6b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menaikkan `room_match` dengan menutup kebocoran antar-ruang, mode gagal terbesar di Gatsu dan di 20 denah sintetis (M7b): 12–32 ruang terbentuk dari 44–50.

**Architecture:**
- **Pengukuran dulu.** `failure_modes` mendapat atribusi kebocoran: untuk setiap pasangan ruang GT yang menyatu dalam satu ruang prediksi, apa pemisahnya di GT?
  - `door_gap`: bukaan GT di dinding pemisah tidak tertutup tapak dinding prediksi;
  - `wall_missing`: dinding pemisah GT tercakup < 50 %;
  - `other`.
- **Perbaikan sesuai PRD/04 §6b.** Ruang yang memuat ≥ 2 label `room_label` bertipe berbeda ditutup dengan dinding sintetis. Pemotongnya adalah perpanjangan sebuah ujung dinding yang menggantung di dalam ruang itu, sampai ke tepi ruang. Pemotong terpendek dipilih di antara yang memisahkan label-label berbeda tipe. Dinding diterima hanya bila skor validator naik.
- Fungsi baru `close_leaks` dipanggil di `assemble_spec` (tahap 4) setelah ruang dibentuk. `leak_issues` tetap melaporkan kebocoran yang tersisa.
- **Gerbang M7a** (ledger ruling bila gagal → revert):
  - `room_match` Gatsu naik;
  - tidak ada regresi di luar toleransi (0.005 rasio, 5 mm, 0.5 menit) pada Gatsu, rata-rata absolut augmentasi (30 varian), dan rata-rata sintetis (20 varian).
- Bersamaan: perbaikan bug `failure_modes --fresh` tanpa `--cache`.

**Tech Stack:** Python 3.12, Shapely 2, pydantic Spec, pytest.

**Spec:**
- `PRD/04-extraction.md` §4.2 langkah 6b ("coba tutup leher dengan dinding sintetis (tebal = median tetangga), lalu terima bila skor validator naik. Bila tidak, catat warning");
- `PRD/01-requirements.md` NFR-AC-07;
- `ROADMAP.md` M7, "Perbaikan ekstraktor yang **umum**, bukan hardcode untuk Gatsu. Tiap perbaikan diikuti regresi terhadap semua set";
- `benchmarks/reports/m7b-final.md`, mode gagal 1.

Branch: `m7d-room-leaks` dari `main`.

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`.
- **Perintah uji:**
  - test: `rtk uv run --env-file .env pytest -q -m "not strata"`;
  - lint: `rtk uv run ruff check core server benchmarks tests`.
- **Tanpa hardcode Gatsu.** Ambang mengikuti angka PRD: label tipe berbeda; tebal = median tetangga; terima bila skor validator naik.
- **Provenance dinding sintetis:**
  - `source="cv"`, `confidence` 0.5;
  - `evidence={"leak_cut": true, "cut_mm": <panjang>}`;
  - kind `partition`.

  Elemen ini terlihat di tab Review dan dapat dihapus di editor.
- **Protokol gerbang M7a.** Perubahan `core/` yang gagal gerbang di-revert, lalu dicatat sebagai ledger ruling. Laporan disimpan di `benchmarks/reports/m7d-*`.
- **Bahasa:**
  - dokumen dalam bahasa Indonesia dengan istilah teknis Inggris;
  - commit dalam bahasa Inggris dan diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Pemotong yang melintasi pintu yang terdeteksi, kolom, atau tangga:** harus ditolak. Test di Task 2.
2. **Ruang dengan ≥ 2 label bertipe sama** (mis. dua WC): tidak dipotong, karena PRD meminta tipe berbeda. Test di Task 2.
3. **Pemotong yang menurunkan skor validator:** tidak diterima, dan warning `ROOM_LEAK` tetap muncul. Test di Task 2.
4. **Label bertipe `other`:** tidak dihitung, seperti di `leak_issues`. Test di Task 2.
5. **`--fresh` tanpa `--cache`** harus benar-benar menjalankan ulang stage di cache default. Test di Task 3.

---

### Task 1: Atribusi kebocoran

**Files:**
- Modify: `benchmarks/failure_modes.py` (`classify_leaks`, masuk ke JSON/MD/stdout)
- Test: `tests/benchmarks/test_failure_modes.py`

**Interfaces:**
- Produces: `classify_leaks(gt: Spec, pred: Spec) -> list[dict]`. Satu baris per pasangan ruang GT bertetangga yang centroid-nya jatuh dalam satu ruang prediksi yang sama: `{"pred_room", "gt_rooms": [a, b], "cause": "door_gap" | "wall_missing" | "other", "wall": <id GT>}`.
  - **Bertetangga:** tepi kedua ruang GT berjarak ≤ tebal maksimum dinding + 1 mm.
  - **Dinding pemisah:** dinding GT terdekat dengan segmen tepi bersama.
  - **`door_gap`:** dinding pemisah memuat bukaan GT yang pusatnya tidak tertutup tapak dinding prediksi (buffer 30 mm).
  - **`wall_missing`:** `wall_coverage(dinding, pred.walls) < 0.5`.

- [ ] **Step 1: Tulis test yang gagal** (fixture `spec_with_rooms`):
  - `test_leak_through_an_open_door`: prediksi = GT dengan dinding yang memuat D1 dipotong di bukaan → `cause == "door_gap"`.
  - `test_leak_through_a_missing_wall`: prediksi = GT tanpa dinding pemisah yang tidak memuat pintu → `cause == "wall_missing"`.
  - `test_no_leak_no_rows`: `classify_leaks(gt, gt) == []`.
- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Implementasi.** `failure_modes` mencatat `leaks` di dokumen JSON, menambah satu baris "Kebocoran ruang: door_gap N, wall_missing M, other K" di MD, dan menambah hitungannya di stdout.
- [ ] **Step 4: Jalankan, lalu** `rtk uv run --env-file .env python -m benchmarks.failure_modes --fresh --cache benchmarks/.cache/gatsu --out benchmarks/reports/m7d-baseline`. Expected: hitungan per penyebab tercatat; metrik sama dengan `m7a3-gatsu`.
- [ ] **Step 5: Commit** `bench: attribute merged rooms to open door gaps or missing walls`.

---

### Task 2: Dinding sintetis penutup kebocoran (§6b)

**Files:**
- Modify: `core/extraction/rooms/assemble.py` (`close_leaks`, dipanggil di `assemble_spec`)
- Test: `tests/extraction/test_rooms_assemble.py` (atau berkas test assemble yang sudah ada)

**Interfaces:**
- Produces: `close_leaks(spec: Spec, labels: list[RoomLabel]) -> Spec`. Untuk setiap ruang yang memuat label dengan ≥ 2 tipe berbeda (tipe `other` diabaikan):
  1. **Kandidat pemotong:** untuk setiap ujung dinding yang menggantung dan berada di dalam ruang itu atau di tepinya (≤ tebal/2), ambil perpanjangan sepanjang arah dinding dari ujung itu sampai titik pertama pada batas ruang, lalu tambah setengah tebal dinding yang ditemui.
  2. **Kandidat ditolak bila:**
     - melintasi segmen bukaan, jejak kolom, atau flight tangga;
     - lebih panjang dari 6000 mm;
     - tidak memisahkan ruang menjadi bagian-bagian dengan label bertipe berbeda.
  3. **Pilih kandidat terpendek** dan tambahkan sebagai `Wall` (`partition`, tebal = median tebal dinding yang menjadi tepi ruang itu, provenance sesuai Global Constraints).
  4. **Bentuk ulang ruang** dengan `rebuild_rooms(..., pick=best_label, source="cv")`.
  5. **Terima hanya bila `validate(spec).score` naik.** Bila tidak, kembalikan spec sebelumnya.
  6. **Ulangi sampai tidak ada perubahan, maksimum 20 pemotong per spec.**
- `assemble_spec` memanggil `close_leaks` setelah `rebuild_rooms`, sebelum `_type_rooms`.

- [ ] **Step 1: Tulis test yang gagal** (spec kecil buatan; dua ruang `office` dan `storage` disatukan oleh dinding yang terputus dengan ujung menggantung):
  - `test_leak_between_two_room_types_is_closed`: hasil punya dinding baru dengan `evidence["leak_cut"]`, ruang +1, tiap ruang memuat satu tipe.
  - `test_same_type_labels_are_left_alone`: dua label `toilet` → spec tidak berubah.
  - `test_cut_never_crosses_a_door_or_column`: satu-satunya kandidat melintasi bukaan → spec tidak berubah.
  - `test_cut_kept_only_when_the_score_rises`: dengan `validate` dipatch agar skor turun → spec tidak berubah.
  - `test_other_labels_do_not_count`: label `office` dan `other` → spec tidak berubah.
- [ ] **Step 2: Jalankan, pastikan gagal.**
- [ ] **Step 3: Implementasi.**
- [ ] **Step 4: Jalankan test berkas ini, lalu suite `tests/extraction` dan `tests/spec`.** Snapshot Gatsu yang berubah karena perubahan ini: periksa dulu, lalu perbarui dengan ledger ruling.
- [ ] **Step 5: Gerbang M7a.**
  - Jalankan Gatsu `failure_modes --fresh --cache benchmarks/.cache/gatsu --out benchmarks/reports/m7d-t2`.
  - Jalankan `run_augment_bench --fresh --out benchmarks/reports/m7d-augment`.
  - Jalankan `run_synth_bench --out benchmarks/reports/m7d-synth`.
  - Expected: `room_match` Gatsu naik, rata-rata `room_match` sintetis naik, dan tidak ada metrik lain yang mundur melebihi toleransi.
  - Bila gagal: revert `core/`, simpan laporan, dan ledger ruling.
- [ ] **Step 6: Commit** `fix(rooms): close leaks between differently labelled rooms with a synthetic wall (PRD/04 6b)`.

---

### Task 3: `--fresh` tanpa `--cache`

**Files:**
- Modify: `benchmarks/failure_modes.py` (`main`)
- Test: `tests/benchmarks/test_failure_modes.py`

- [ ] **Step 1: Test yang gagal:** `test_fresh_clears_the_default_cache`. Dengan `CACHE` dipatch ke `tmp_path` yang berisi file penanda dan `_gatsu_inputs` dipatch agar berhenti, `main(["--out", …, "--fresh"])` harus menghapus file penanda.
- [ ] **Step 2–4: RED, implementasi** (`shutil.rmtree(a.cache or CACHE, ignore_errors=True)`), **GREEN.**
- [ ] **Step 5: Commit** `fix(bench): failure_modes --fresh reruns the default cache too`.

---

### Task 4: Laporan dan status

**Files:**
- Create: `benchmarks/reports/m7d-final.md`
- Modify: `ROADMAP.md` (Status M7d)

- [ ] **Step 1:** `m7d-final.md`:
  - atribusi kebocoran sebelum dan sesudah;
  - tabel gerbang (Gatsu, rata-rata augmentasi, rata-rata sintetis) sebelum dan sesudah;
  - jumlah dinding sintetis yang diterima;
  - menit koreksi.
- [ ] **Step 2: Suite penuh hijau.**
- [ ] **Step 3: ROADMAP "Status M7d".**
- [ ] **Step 4: Commit** `docs: M7d room-leak results and status`.
