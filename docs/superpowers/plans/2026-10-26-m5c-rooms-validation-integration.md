# M5c — Tahap 4–5: Ruang, Validasi & Pemilihan, Carry-over, Style Profile, Tab Review, IoU Tahap 8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload `plan.jpeg` menjalankan tahap 0–5 secara otomatis sampai spec tersimpan (`spec.vN.json`, `source: pipeline`), lalu tahap 7–10 membangun output dan editor bisa dibuka. Ruang, label, tipe, luas kotor, validasi, pemilihan kandidat, ID stabil, carry-over, style profile, tab Review, dan mask IoU tahap 8 semuanya berjalan, dan semuanya diukur terhadap GT Gatsu.

**Architecture:**
- **Tahap 3 (tambahan):**
  - masking sumbu grid dan garis dimensi (§3.1.2, sisa dari review M5b);
  - kotak lift masuk `elements.json`;
  - setiap kandidat juga menulis `wall_mask.png` dan `line_len_m`.
- **Tahap 4** (`core/extraction/rooms/`). Untuk setiap kandidat yang sukses: `elements.json` dirakit menjadi `Spec` lengkap. Prosesnya: ID deterministik, ruang dari `core/spec/rooms.py` (M4), label OCR + leksikon, tipe tangga/lift/outdoor, dan cek kebocoran. Hasilnya `04_rooms/candidates/<k>/spec.json` + `rooms.png`.
- **Tahap 5** (`core/extraction/select.py`):
  - validasi semua kandidat;
  - kandidat ber-error dibuang, lalu dipilih yang skornya tertinggi;
  - OCR crop untuk ruang tanpa label;
  - carry-over bila HEAD sudah ada (`core/spec/carryover.py`);
  - spec disimpan lewat `SpecStore`;
  - output `overlay_ids.png` beserta layer, `scores.json`, `issues.json`, `chosen.json`, dan `wall_mask.png` dalam piksel asli;
  - status mengikuti ambang skor.
- **Orchestrator:** stub tahap 4–5 diganti implementasi asli. Tahap 8 memakai `wall_mask.png` dari run yang menghasilkan spec, dengan fallback ke mask M2.
- **Dashboard:**
  - panel tahap 4 (tabel ruang + overlay per kandidat);
  - panel tahap 5 (skor per aturan, tabel masalah, tombol "Simpan sebagai profile");
  - tab Review (overlay bernomor berlayer + masalah validator);
  - pilihan profile saat membuat project dan saat menjalankan ulang.

**Tech Stack:** Python 3.12, Shapely 2, OpenCV, NumPy, PyYAML (sudah terpasang), RapidOCR (`ocr_crop` dari M5a), FastAPI, pytest. Dashboard: React + Carbon g100, TanStack Query, Vitest.

**Spec:**
- `PRD/04-extraction.md` §3.1.2, §3.4b (lift), §3.6 (profile), Tahap 4 (langkah 1–7, §4.3 leksikon), Tahap 5 (langkah 1–8, termasuk §4b carry-over);
- `PRD/06-builder-outputs.md` §6 langkah 2 (mask denah dari kandidat terpilih);
- `PRD/08-dashboard.md` (panel tahap 4–5, tab Review);
- `PRD/09-api.md` §2.2 (`POST /runs` dengan `profile_id`, `POST /runs/{id}/continue`) dan §2.8 (Profiles);
- `PRD/03-layout-spec.md` (`Room`, `Meta`, §12 validator);
- `PRD/01-requirements.md` FR-EX-10…14, NFR-AC-01…11, NFR-PF-01, NFR-RL-06;
- `ROADMAP.md` M5 (Tugas dan Kriteria selesai, "Status M5b": galat yang dibawa).

Branch: `m5-cv` (lanjutan M5b). Sesudah plan ini M5 selesai, dan semua metrik yang belum mencapai NFR dibawa ke M7 (aturan Kriteria selesai M5).

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`;
  - test dijalankan dengan `rtk uv run --env-file .env pytest -q`;
  - test yang memakai Gatsu atau pipeline penuh ditandai `@pytest.mark.slow`;
  - skrip ukur yang memakai sweep paralel dijalankan sebagai file dengan guard `if __name__ == "__main__":` (spawn di macOS).
- **Determinisme (NFR-RL-06):**
  - iterasi atas daftar terurut;
  - JSON ditulis dengan `core.extraction.stages.write_json`;
  - spec yang disimpan identik antar-run, kecuali `meta.created_at`, `meta.run_id`, dan `meta.version`/`parent_version`.
- **Koordinat:**
  - tahap 3 bekerja di piksel kerja;
  - spec dalam mm (Y ke atas) lewat `grid.json.px_to_mm`;
  - artefak gambar untuk dashboard memakai piksel kerja (`page.png`), kecuali `wall_mask.png` tahap 5 yang memakai piksel **asli**, sama dengan render tahap 8.
- **Nilai dari spec, salin persis:**
  - ruang < 1 m² atau dengan rasio aspek > 20 dibuang (sudah ada di `core/spec/rooms.py`);
  - label: teks `room_label` di dalam ruang; bila ada beberapa, dipilih skor leksikon tertinggi; teks `annotation` diabaikan;
  - tipe dari leksikon §4.3; tidak cocok → `other`;
  - Levenshtein ≤ 1 untuk kata ≥ 5 huruf;
  - kebocoran: leher < 600 mm tanpa pintu, atau ≥ 2 label berbeda dalam satu ruang;
  - ruang yang memuat flight → `stair`; ruang yang memuat kotak lift → `lift`;
  - pemilihan: kandidat ber-`error` dibuang; skor tertinggi menang; bila selisih ≤ 0.01, dipakai cakupan dinding (`Σ panjang dinding / line_len`) yang lebih tinggi;
  - urutan ID: dinding menurut (y, x) titik `a`; ruang menurut posisi centroid (`rebuild_rooms`);
  - carry-over:
    - dinding cocok bila jarak garis tengah ≤ 200 mm, beda sudut ≤ 3°, dan overlap ≥ 50%; mewarisi ID dan `height`;
    - ruang memakai aturan `rebuild_rooms` (IoU ≥ 0.5 atau ≥ 90% luas lama tercakup); `name`/`type` diwarisi bila `provenance.source` ∈ {`editor`, `manual`, `llm`};
    - pintu/kolom cocok bila pusat ≤ 300 mm;
    - objek disalin, `room_id` dihitung ulang;
    - `meta.defaults` dari HEAD dipertahankan;
    - ID baru melanjutkan nomor tertinggi;
    - edit yang tidak bisa dipindahkan dicatat di `carryover.json`;
  - `overlay_ids.png`: dinding biru, pintu hijau, kolom oranye, ruang diarsir tipis per ruang, label ID ≥ 14 px dengan latar kontras;
  - status tahap 5: skor ≥ 0.8 `succeeded`; 0.6–0.8 `succeeded` + peringatan; < 0.6 `needs_attention`;
  - IoU tahap 8 dihitung terhadap mask dinding kandidat terpilih (S2: isi antara pasangan garis; S1: mask garis tebal), dibatasi area gambar;
  - profile = parameter kandidat terpilih; sweep mulai dari profile ± 1 langkah per dimensi (sudah ada di `sweep_params`).
- **Dependensi:** tidak ada yang baru.
- **Kualitas:** `rtk uv run ruff check .` bersih; dashboard `npm test`, `npm run lint`, dan `npm run build` hijau.

## Review Focus

1. **Plot hitam-putih dengan sumbu grid tergambar di antara dua garis dinding.** Harapan: sumbu terhapus sebelum deteksi, dan dinding tetap di tengah dengan tebal benar. Garis sumbu yang sama tebal dengan dinding tidak disentuh. Test: Task 1 `test_thin_axis_between_wall_lines_is_erased` dan `test_axis_as_thick_as_walls_is_kept`.
2. **Ruang tanpa label OCR** (Gatsu: WC, TOILET, LIFT, TANGGA tidak terbaca pass global). Harapan: OCR crop per ruang menemukan labelnya. Bila tetap tidak ada, ruang bertipe `other` (atau `outdoor` untuk pita luar) dan masuk review lewat V015. Test: Task 6 `test_unlabelled_room_gets_crop_ocr_label`.
3. **Semua kandidat punya error validator, atau tidak ada kandidat sukses.** Harapan: tahap 5 `needs_attention` dengan pesan jelas, tidak ada spec tersimpan, dan `continue` ditolak (409). Test: Task 6 `test_no_valid_candidate_needs_attention_without_spec` dan `test_continue_refused_without_spec`.
4. **Re-ekstraksi setelah pengguna mengedit di editor.** Harapan: ID, tinggi dinding, dan nama/tipe ruang hasil editor dipertahankan; edit pada dinding yang hilang tercatat dan tampil sebagai peringatan. Test: Task 4 `test_editor_edits_survive_reextraction` dan `test_lost_edit_reported`.
5. **Regenerate (tahap 7–10) untuk spec yang dibuat run lain.** Harapan: tahap 8 memakai `wall_mask.png` milik run yang menghasilkan spec (`meta.run_id`). Spec impor tanpa mask memakai mask M2. Test: Task 7 `test_verify_uses_mask_of_spec_run` dan `test_imported_spec_falls_back_to_m2_mask`.

---

### Task 1: Masking sumbu grid dan garis dimensi (PRD/04 §3.1.2)

**Files:**
- Modify: `core/extraction/geometry/masks.py`, `core/extraction/geometry/candidate.py`
- Test: `tests/extraction/geometry/test_masks.py`

**Interfaces:**
- Consumes:
  - `grid_doc["axes"]`: `[{id, label, orientation, px}]`, piksel kerja;
  - `ocr_items` dengan `cls == "dimension"`;
  - `stroke_width(binary)`.
- Produces:
  - `build_masks(binary, colour, ocr_items, drawing_bbox, s, axes: list[dict] = ()) -> dict`. Parameter `axes` baru; `candidate.py` meneruskan `grid_doc["axes"]`.
  - Key baru di dict: `"erased_axes": [axis id]`, sumbu yang benar-benar dihapus.

Aturan (berjalan setelah langkah teks/warna/luar-gambar, sebelum leader):
1. **Sumbu:**
   - Sampel garis sumbu tiap 1 px sepanjang `drawing_bbox`.
   - Sumbu "bertinta" bila ≥ 30% sampel punya tinta dalam ±1 px.
   - Tebal sumbu = median panjang run tinta tegak lurus sumbu pada sampel bertinta.
   - Hapus hanya bila tebal sumbu ≤ 0.75 × `stroke_width`. Yang dihapus: piksel run tegak lurus sumbu yang panjangnya ≤ tebal sumbu + 1. Dengan begitu garis dinding yang memotong sumbu (run panjang) tetap utuh.
   - Garis sumbu yang setebal dinding tidak disentuh, dan pesan dicatat lewat key `erased_axes`.
2. **Garis dimensi:**
   - Segmen Hough (skeleton `work`) yang sejajar sumbu panjang bbox teks `dimension`.
   - Jarak garis ke pusat bbox ≤ 1.5 × tinggi teks.
   - Panjang segmen ≥ lebar teks.
   - Segmen dihapus dengan aturan "tipis" yang sama: hanya piksel dengan run tegak lurus ≤ 0.75 × `stroke_width` + 1.

- [ ] **Step 1: Tulis test yang gagal** (sintetis, `s = 12.5`, dinding garis ganda 4 px, jarak garis 12 px)
  - `test_thin_axis_between_wall_lines_is_erased`:
    - sumbu vertikal 1 px di x = tengah dinding vertikal, memanjang 2× tinggi gambar bangunan;
    - hasil: `"GA" in m["erased_axes"]`, `clean` kosong di x sumbu di luar dinding;
    - `s2_walls(extract_strokes(m["clean"]))` memberi satu dinding di x tengah ± 1 px dengan tebal 150 ± 15 mm.
  - `test_axis_as_thick_as_walls_is_kept`: sumbu 4 px → `erased_axes == []` dan pikselnya masih ada di `clean`.
  - `test_axis_crossing_wall_keeps_the_wall`: sumbu horizontal 1 px memotong dinding vertikal → piksel garis dinding di persilangan tetap ada.
  - `test_dimension_line_under_dimension_text_is_erased`: teks `dimension` "6000" + garis 1 px sejajar 8 px di bawahnya sepanjang 400 px → garis hilang; dinding di dekatnya utuh.
  - `test_gatsu_axes_not_erased` (slow): Gatsu (grid berwarna, sudah dibuang) → `erased_axes == []`, dan metrik kandidat 0 tidak berubah (`wall_recall` ≥ 0.73).

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_masks.py`
  Expected: FAIL (`build_masks` belum menerima `axes`).

- [ ] **Step 3: Implementasi** sesuai aturan di atas di `masks.py` (`_erase_axes(work, axes, w, bbox) -> (work, erased)`, `_erase_dimension_lines(work, texts, w)`); `candidate.py` meneruskan `axes`.

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry` lalu `tests/extraction/test_gatsu_regression.py`.
  Expected: PASS. Floors M5b tetap terpenuhi.

- [ ] **Step 5: Commit**

  `feat(extract): erase thin grid axes and dimension lines before detection (§3.1.2)`

---

### Task 2: Tambahan output tahap 3 — kotak lift, `line_len_m`, `wall_mask.png`

**Files:**
- Modify: `core/extraction/geometry/candidate.py`, `core/extraction/geometry/stairs.py` (`lift_boxes`), `core/extraction/stages.py` (`_candidate_job`)
- Test: `tests/extraction/geometry/test_candidate.py`, `tests/extraction/geometry/test_stairs.py`

**Interfaces:**
- Consumes: `lift_boxes(strokes, s)` (M5b, `stairs.py`); strokes dan raw walls di `extract_candidate`.
- Produces:
  - `elements.json` mendapat `"lifts": [[x0, y0, x1, y1]]` (mm spec, sudut min/max sesudah konversi) dan `"line_len_m": float`.
    - S2: Σ panjang stroke `h`/`v` ≥ 300 mm di `clean` sesudah `stair_mask`, dibagi 2.
    - S1: Σ panjang stroke mask opening.
  - `extract_candidate(...)["_masks"]["wall"]`: uint8 piksel kerja.
    - S2: setiap raw wall S2 (sebelum `postprocess`) diisi sebagai persegi panjang garis tengah ± tebal/2 sepanjang [a, b].
    - S1: mask opening.
    - Di luar `drawing_bbox` + margin 300 mm = 0.
  - `_candidate_job` menulis `candidates/<k>/wall_mask.png` dan menambahkan `line_len_m` ke baris `candidates.json`.
  - `elements_to_spec` tidak berubah. Lift dibaca tahap 4 langsung dari `elements.json`.
  - `lift_boxes` dibuat O(d²): pasangan diagonal dikelompokkan per garis lebih dulu (M5b minor: O(d³), 12.5 s pada cross-hatch). Batas waktu ≤ 0.5 s untuk 300 diagonal acak.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_lift_box_in_elements`: gambar sintetis lift 2000 mm dengan dua diagonal + ruang → `el["lifts"]` satu kotak dengan sisi 2000 ± 50 mm.
  - `test_wall_mask_fills_between_pair_lines`: satu dinding garis ganda → `_masks["wall"]` terisi penuh di antara kedua garis (≥ 95% piksel pita), kosong 3 px di luar.
  - `test_line_len_reported`: kotak 4 dinding garis ganda 4 × 4000 mm → `line_len_m` = 16 ± 0.5.
  - `test_lift_boxes_fast_on_cross_hatch`: 300 diagonal acak (seed 0) → `lift_boxes` < 0.5 s.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/geometry/test_candidate.py tests/extraction/geometry/test_stairs.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus** (perintah sama + `tests/extraction/test_gatsu_regression.py`)

  Expected: PASS. Di Gatsu, kotak lift (sisi X ±1.3 m, M5b) ditemukan di kandidat 0.

- [ ] **Step 5: Commit**

  `feat(extract): lift boxes, line length and wall mask per candidate`

---

### Task 3: Leksikon ruang dan label OCR

**Files:**
- Create: `core/extraction/lexicon.yaml`, `core/extraction/rooms/__init__.py`, `core/extraction/rooms/labels.py`
- Modify: `core/extraction/textclass.py` (`ROOM_WORDS` dibaca dari leksikon, tidak didefinisikan ulang)
- Test: `tests/extraction/rooms/test_labels.py`

**Interfaces:**
- Produces:
  - `lexicon.yaml`: tabel §4.3 apa adanya, `{type: [keyword, ...]}`.
  - `match_type(text: str) -> tuple[str, float]`:
    - teks dinormalisasi: huruf besar, tanpa titik/spasi ganda;
    - skor 1.0 bila kata kunci (tanpa spasi) muncul sebagai substring teks tanpa spasi (menangani "BATTERYROOM");
    - skor 0.8 bila satu token ≥ 5 huruf berjarak Levenshtein ≤ 1 dari kata kunci satu kata ("CAPASITR");
    - selain itu `("other", 0.0)`.
  - `levenshtein(a: str, b: str) -> int`: DP sederhana, tanpa dependensi.
  - `RoomLabel` dipakai dari `core/spec/rooms.py` (`at`, `name`, `type`).
  - `labels_from_ocr(ocr_items: list[dict], px_to_mm: list[float]) -> list[RoomLabel]`:
    - memakai item `cls == "room_label"`;
    - item "generik" (`ROOM`, `R.`, `RUANG`) yang berada ≤ 1.5 tinggi teks tepat di bawah atau di kanan item lain digabung ke item itu sebagai satu nama ("CAPASITOR" + "ROOM" → "CAPASITOR ROOM");
    - item yang teksnya sama persis dengan bbox tumpang tindih (dua pass OCR) dideduplikasi;
    - `at` = pusat bbox gabungan dalam mm; `name` = teks yang dirapikan; `type`/skor dari `match_type`;
    - label bertipe `other` dengan skor 0 tetap dikembalikan (nama tetap berguna), kecuali teksnya < 3 huruf.
  - `best_label(labels: list[RoomLabel]) -> RoomLabel | None`: skor tertinggi, lalu nama terpanjang.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_match_type_lexicon`: "BATTERYROOM" → `battery_room` 1.0; "R.MEETING" → `meeting`; "CAPASITR ROOM" → `capacitor_room` 0.8; "GALERY" → `lobby`; "KM" → `toilet`; "MSC GATSU" → `other`; "WC" → `toilet` (kata < 5 huruf hanya cocok persis).
  - `test_levenshtein`: ("KITTEN", "SITTING") = 3; ("", "AB") = 2.
  - `test_stacked_lines_merge_and_duplicates_drop`: item "CAPASITOR" + "ROOM" di bawahnya → satu label "CAPASITOR ROOM"; dua item "BATTERY" dengan bbox tumpang tindih → satu.
  - `test_gatsu_labels` (slow, `ocr.json` Gatsu dari fixture M5b):
    - tipe yang muncul memuat `pantry`, `meeting`, `storage`, `battery_room`, `mdf`, `ahu_room`, `lobby`, `capacitor_room`;
    - "PRDPDSED" (PROPOSED salah baca) tidak menjadi label bertipe selain `other`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/rooms/test_labels.py`
  Expected: FAIL (modul belum ada).

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus** (perintah sama + `tests/extraction/test_textclass.py`)

  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): room lexicon and OCR room labels`

---

### Task 4: Carry-over terhadap HEAD (§5.4b) dan ID deterministik

**Files:**
- Create: `core/spec/carryover.py`
- Test: `tests/spec/test_carryover.py`

**Interfaces:**
- Consumes: `rebuild_rooms(spec, labels)` (M4), `take_id`, `seed_id_seq`, `derive`.
- Produces:
  - `assign_ids(spec: Spec) -> Spec`:
    - ID baru untuk spec hasil ekstraksi;
    - dinding `W1…` menurut (a.y, a.x);
    - kolom `C…` menurut (center.y, center.x);
    - bukaan `D…`/`N…` menurut (urutan dinding induk, offset);
    - tangga `S…` menurut titik awal flight pertama;
    - ruang dibuat ulang dengan `rebuild_rooms` (spec tanpa ruang → urutan centroid bawaan);
    - semua referensi (`wall_id`, `bounding_walls`, `doors`, `room_id`) dipetakan ulang;
    - `id_seq` di-seed.
  - `carry_over(new: Spec, head: Spec, labels: list[RoomLabel]) -> tuple[Spec, dict]`:
    - mengembalikan spec dengan ID HEAD untuk elemen yang cocok, plus laporan `{"matched": {type: n}, "new": {type: n}, "removed": {type: [id]}, "lost_edits": [{"id", "field", "value"}]}`;
    - `lost_edits`: dinding HEAD dengan `height` tidak `None` yang tidak cocok dengan dinding mana pun, dan ruang HEAD bersumber `editor`/`manual`/`llm` yang tidak cocok;
    - nomor ID baru melanjutkan `head.meta.id_seq`;
    - `meta.defaults` dan objek dari HEAD; `derive` dijalankan di akhir.

- [ ] **Step 1: Tulis test yang gagal** (spec kecil buatan tangan, 2 ruang, 6 dinding, 1 pintu, 1 kolom)
  - `test_assign_ids_order_is_positional`: dinding diacak urutannya → ID identik dengan sebelum diacak; `W1` adalah dinding dengan `a` paling bawah, lalu paling kiri.
  - `test_matching_walls_keep_head_ids`: dinding baru bergeser 150 mm dan miring 2° → mewarisi ID; bergeser 250 mm → ID baru `W7` (lanjutan dari `id_seq` HEAD = 6).
  - `test_editor_edits_survive_reextraction`: HEAD punya `height` 4500 di W2 dan ruang R1 bernama "SERVER A" sumber `editor` → hasil mempertahankan keduanya meskipun label OCR baru "DATA HALL"; ruang R2 bersumber `cv` mengambil label baru.
  - `test_doors_and_columns_match_by_centre`: pusat bergeser 250 mm → ID HEAD; 350 mm → ID baru.
  - `test_objects_copied_and_room_recomputed`: objek HEAD di dalam R1 → tetap ada dengan `room_id` R1.
  - `test_lost_edit_reported`: W2 (height 4500) tidak ada lagi → `lost_edits == [{"id": "W2", "field": "height", "value": 4500}]`.
  - `test_ids_never_reused`: HEAD `id_seq["W"] = 9` (W7–W9 sudah dihapus) → dinding baru tak cocok mendapat `W10`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/spec/test_carryover.py`
  Expected: FAIL (modul belum ada).

- [ ] **Step 3: Implementasi**

  Pencocokan dinding:
  - jarak = jarak tegak lurus kedua ujung dinding baru ke garis dinding HEAD (maksimum);
  - sudut dari vektor a→b, tanpa memedulikan arah;
  - overlap = panjang proyeksi bersama / panjang yang lebih pendek;
  - pasangan diambil greedy dengan urutan (jarak, ID HEAD), tiap elemen dipakai sekali.

- [ ] **Step 4: Jalankan, pastikan lulus** (perintah sama + `tests/spec`)

  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(spec): deterministic extraction IDs and carry-over against HEAD`

---

### Task 5: Tahap 4 — perakitan spec kandidat dan ruang

**Files:**
- Create: `core/extraction/rooms/assemble.py`, `core/extraction/rooms/overlay.py`
- Modify: `core/spec/rooms.py` (pemilihan label), `core/extraction/stages.py` (`stage_rooms`), `server/orchestrator.py` (impl 4)
- Test: `tests/extraction/rooms/test_assemble.py`, `tests/server/test_orchestrator.py`

**Interfaces:**
- Consumes: `elements_to_spec`, `assign_ids` (Task 4), `rebuild_rooms`, `labels_from_ocr`/`best_label` (Task 3), `elements.json` `lifts` (Task 2), `run_params(project_dir, override)`.
- Produces:
  - `assemble_spec(elements: dict, grid_doc: dict, labels: list[RoomLabel], meta_info: dict) -> tuple[Spec, list[dict]]`, mengembalikan (spec, issues).
    - `meta_info` = `{project_id, image: ImageInfo dict, floor_name, site_type, defaults}` dari `input.json` + `run_params`.
    - Langkah:
      1. `elements_to_spec`, lalu meta diisi;
      2. `assign_ids`;
      3. `rebuild_rooms(spec, labels)`; bila satu ruang memuat beberapa label, `best_label` yang dipakai (perbaikan di `rebuild_rooms`: label dipilih dengan `best_label` atas semua label di dalam ruang, bukan `next(...)`);
      4. tipe: ruang yang memuat titik tengah flight → `stair`; ruang yang memuat pusat kotak lift → `lift`; label menang bila tipenya bukan `other`;
      5. ruang tanpa label yang menyentuh `building_outline` (jarak ≤ 1 mm) dan sisi pendek `minimum_rotated_rectangle` ≤ 2000 mm → `outdoor` (pita luar §2b);
      6. kebocoran (§6b) lewat `leak_issues(spec, labels) -> list[dict]` (fungsi terpisah, dipanggil lagi oleh tahap 5 pada spec final agar ID-nya benar):
         - ruang dengan ≥ 2 label bertipe berbeda → issue `ROOM_LEAK` (warning, `element_ids` = ruang);
         - ruang yang terbelah menjadi ≥ 2 bagian ≥ 1 m² setelah erosi 300 mm, tanpa pintu di dalam 600 mm dari leher → `ROOM_LEAK`.
         - Penutupan otomatis dengan dinding sintetis **tidak** dibuat (ruling di plan: perlu geometri leher yang andal; panel koreksi editor menutupnya); cost: ruang bocor tetap satu ruang sampai dikoreksi.
  - `stage_rooms(project_dir: Path, work: Path, progress=None, override=None) -> dict`:
    - untuk setiap baris sukses `03_extract/candidates.json`, menulis `04_rooms/candidates/<k>/spec.json`, `rooms.png` (`render_rooms_overlay`), dan `issues.json`;
    - menulis `04_rooms/candidates.json`: `[{index, error, rooms, labelled, gross_area_m2}]`;
    - status `failed` bila tidak ada kandidat yang bisa dirakit;
    - kandidat yang melempar exception dicatat `error`, tidak menggagalkan tahap.
  - `render_rooms_overlay(page_gray, spec, px_from_mm) -> ndarray`: arsiran tipis per ruang + nama/tipe di `label_pos` atau centroid.
  - `px_from_mm(px_to_mm) -> callable` (invers afine) di `core/extraction/rooms/overlay.py`, dipakai juga Task 6.
  - Orchestrator: `DEFAULT_IMPLS[4] = _rooms`.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_two_rooms_with_labels_and_types`: `elements` sintetis (kotak 8×5 m dibagi dua, satu pintu per ruang) + label "PANTRY" dan "GUDANG" → 2 ruang, tipe `pantry`/`storage`, `doors` terisi, `gross_area_m2` = 40 ± 0.5.
  - `test_stair_and_lift_rooms_typed`: flight di ruang A dan kotak lift di ruang B, tanpa label → tipe `stair` dan `lift`; `stairs[0].room_id` = ruang A.
  - `test_outer_band_is_outdoor`: pita 1200 mm di luar dinding utama → ruang pita bertipe `outdoor`.
  - `test_two_labels_one_room_is_a_leak_warning`: satu ruang memuat "PANTRY" dan "GUDANG" → issue `ROOM_LEAK`.
  - `test_assembled_spec_validates_without_errors`: spec hasil `assemble_spec` lolos `validate()` tanpa `error`.
  - `test_stage_rooms_gatsu` (slow): stage 0–3 Gatsu (fixture M5b) → `stage_rooms` sukses; kandidat 0 punya ≥ 30 ruang, ≥ 8 ruang berlabel, dan ≥ 2 massa `building_outline`.
  - `tests/server/test_orchestrator.py`: test M3 yang mengharapkan tahap 4 `skipped` sekarang mengharapkan `succeeded`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/rooms/test_assemble.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus** (perintah sama + `tests/spec tests/server/test_orchestrator.py`)

  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): stage 4 - candidate specs with rooms, labels, stair/lift/outdoor types, leak warnings`

---

### Task 6: Tahap 5 — validasi, pemilihan, OCR crop, carry-over, penyimpanan, overlay bernomor

**Files:**
- Create: `core/extraction/select.py`, `core/extraction/rooms/overlay_ids.py`
- Modify: `core/extraction/stages.py` (`stage_validate`), `server/orchestrator.py` (impl 5), `server/routes/runs.py` (`continue`)
- Test: `tests/extraction/test_select.py`, `tests/server/test_orchestrator.py`, `tests/server/test_extraction_stages.py`

**Interfaces:**
- Consumes:
  - `validate(spec, ValidationContext(ocr_dimensions, thick_line_length_mm))`, dengan `thick_line_length_mm = line_len_m × 1000` kandidat itu (Task 2);
  - `ocr_crop(image, bbox, scale)` (M5a);
  - `carry_over` (Task 4), `labels_from_ocr` (Task 3);
  - `SpecStore.save_new(spec, "pipeline", run_id, message)`.
- Produces:
  - `ocr_dimensions_from(grid_doc) -> list[tuple[str, str, int]]`: dari `equations_used` (`axis_from`, `axis_to`, `value_mm`).
  - `choose(scored: list[dict]) -> dict | None`: kandidat tanpa error dengan skor tertinggi; bila selisih ≤ 0.01, dipakai cakupan (`Σ panjang dinding mm / (line_len_m × 1000)`) yang lebih tinggi; lalu indeks terkecil.
  - `crop_labels(page_gray, spec, px_from_mm, s) -> list[RoomLabel]`:
    - untuk ruang ≥ 4 m² tanpa nama: `ocr_crop` pada bbox ruang (piksel kerja, inset 2 px, skala 3);
    - teks yang `match_type`-nya bukan `other`, atau ≥ 3 huruf, menjadi label di pusat bbox-nya.
  - `stage_validate(project_dir: Path, work: Path, run_id: str, progress=None, override=None) -> dict`. Output:
    - `scores.json`: `[{index, score, passed, ratios, errors: [code], coverage}]`;
    - `chosen.json`: `{index, params, score, version}`;
    - `issues.json`: masalah validator spec final + `leak_issues` spec final + issue tahap 3 kandidat terpilih (`STAIR_DIR`, `EXISTING_PROPOSED`; posisi mm);
    - `carryover.json`: bila HEAD ada;
    - `overlay_ids.png` beserta `layers/{walls,doors,columns,rooms}.png` (RGBA, piksel kerja);
    - `wall_mask.png`: mask kandidat terpilih di-warp ke piksel asli lewat invers `meta.work_from_original`.
  - Status dan aturan:
    - tidak ada kandidat valid → `needs_attention` "semua kandidat punya error validator (V…)", tanpa spec;
    - skor < 0.6 → spec **tetap disimpan** lalu `needs_attention`, agar `continue` (tahap 6 dari HEAD) bisa jalan (ruling plan; cost: HEAD sementara berisi spec berskor rendah, tetapi tercatat di Versions);
    - 0.6 ≤ skor < 0.8 → `succeeded` + peringatan;
    - `carryover.lost_edits` masuk `warnings`;
    - `ctx.state["version"]` diisi versi baru; `run.spec_version_out` diisi orchestrator.
  - `render_ids_overlay(page_gray, spec, px_from_mm) -> tuple[ndarray, dict[str, ndarray]]` (composite BGR, layer RGBA). Warna dan ukuran label sesuai Global Constraints.
  - `continue`: 409 `no_spec` bila tahap 5 run itu tidak menyimpan spec.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_choose_prefers_score_then_coverage`: skor 0.82 vs 0.815 dengan coverage 0.7 vs 0.9 → yang kedua; 0.82 vs 0.80 → yang pertama; kandidat ber-error tidak pernah dipilih.
  - `test_ocr_dimensions_from_grid`: `equations_used` Gatsu → memuat `("A", "F", 28000)`.
  - `test_unlabelled_room_gets_crop_ocr_label`: halaman sintetis dengan teks "TOILET" 12 px yang dirender `cv2.putText` di dalam ruang 3×3 m → `crop_labels` memberi label `toilet`.
  - `test_no_valid_candidate_needs_attention_without_spec`: semua kandidat dibuat ber-V008 → status `needs_attention`, `SpecStore.head()` None.
  - `test_stage_validate_saves_spec_and_artifacts` (slow, Gatsu tahap 0–4):
    - status ∈ {`succeeded`, `needs_attention`};
    - `spec.v1.json` ada dengan `meta.source == "pipeline"`;
    - semua file output di atas ada; `layers/` berisi 4 PNG RGBA berukuran `page.png`;
    - `wall_mask.png` berukuran gambar asli (1600×945).
  - `test_reextraction_carries_over` (slow): jalankan `stage_validate` dua kali di project yang sama; sebelum run kedua, ubah `height` satu dinding lewat `commit_ops` → v3 mempertahankan ID dan `height` itu; `carryover.json` ada.
  - `tests/server/test_extraction_stages.py::test_continue_refused_without_spec`.
  - `tests/server/test_orchestrator.py`: run penuh tanpa spec impor kini berhenti atau sukses di tahap 5 dengan spec tersimpan; sesuaikan test M3 `test_full_run_without_spec_stops_needs_attention` (timeout 180 s).

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_select.py tests/server`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus** (perintah sama + seluruh suite)

  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): stage 5 - validate and choose candidate, crop OCR labels, carry-over, save spec, numbered overlay`

---

### Task 7: Mask IoU tahap 8 dari kandidat terpilih

**Files:**
- Modify: `core/verify/run.py`, `core/pipeline.py` (`stage_verify`), `server/orchestrator.py` (`_verify`), `core/verify/iou.py` (komentar `ponytail` diperbarui)
- Test: `tests/verify/test_verify.py`, `tests/server/test_orchestrator.py`

**Interfaces:**
- Produces:
  - `run_verify(out_dir, spec, doc, image_path, extra_warnings=None, plan_mask_path: Path | None = None) -> dict`:
    - bila `plan_mask_path` ada, mask itu dipakai (biner > 0);
    - bila tidak, dipakai `plan_wall_mask` (M2) dan dicatat peringatan "mask M2 (tanpa kandidat ekstraksi)";
    - `verify.json` mendapat `"mask_source": "candidate" | "m2"`.
  - `stage_verify(..., plan_mask: Path | None = None)`.
  - Orchestrator `_verify`: `projects/<pid>/runs/<spec.meta.run_id>/stages/05_validate/wall_mask.png` bila `spec.meta.run_id` ada dan file itu ada.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_verify_uses_candidate_mask`: render dan mask sintetis identik → IoU 1.0, `mask_source == "candidate"`.
  - `test_verify_uses_mask_of_spec_run`: run A menyimpan spec + mask; run regenerate B (tahap 7–10) memakai mask run A.
  - `test_imported_spec_falls_back_to_m2_mask`: spec impor (`run_id` None) → `mask_source == "m2"` + peringatan.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/verify tests/server/test_orchestrator.py`
  Expected: FAIL.

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus** (perintah sama)

  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(verify): stage 8 IoU against the chosen candidate's wall mask`

---

### Task 8: Style profile (FR-EX-12, P1)

**Files:**
- Create: `core/extraction/profiles.py`
- Modify:
  - `server/routes/templates.py` (`POST /api/profiles`);
  - `server/routes/runs.py` dan `server/routes/projects.py` (`profile_id`);
  - `server/orchestrator.py` (`start_run(..., profile_id=None)`, disimpan di `run.json`, diteruskan ke `StageContext.profile`);
  - `core/extraction/stages.py` (`stage_extract(..., profile: dict | None = None)` meneruskan ke `sweep_params`)
- Test: `tests/extraction/test_profiles.py`, `tests/server/test_profiles_api.py`

**Interfaces:**
- Produces:
  - Format profile `profiles/<profile_id>.json`: `{profile_id, name, params: {strategy, sauvola_k, t_min, t_max, l_fix}, from_run, created_at}`; `profile_id` = slug nama + 4 hex.
  - `save_profile(storage, name: str, from_run: str) -> dict`:
    - membaca `05_validate/chosen.json` run itu;
    - 404 bila run/tahap 5 tidak ada;
    - 409 bila tahap 5 run itu tidak `succeeded`.
  - `load_profile(storage, profile_id) -> dict`: 404 bila tidak ada.
  - `POST /api/profiles` → 201 + profile; `GET /api/profiles` tetap.
  - `POST /runs` dan `POST /projects` (form field `profile_id`) menerima `profile_id`; profile tak dikenal → 404 sebelum run dibuat.

- [ ] **Step 1: Tulis test yang gagal**
  - `test_save_profile_from_succeeded_run`: run palsu dengan `chosen.json` → file profile berisi `params` itu.
  - `test_save_profile_refuses_unfinished_run`: tahap 5 `needs_attention` → 409.
  - `test_run_with_profile_sweeps_around_it`: `profile_id` → `stage_extract` menerima `params` profile, dan kandidat 0 = parameter profile (`sweep_params` sudah mengurutkan).
  - `test_unknown_profile_404`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_profiles.py tests/server/test_profiles_api.py`
  Expected: FAIL (`POST /api/profiles` masih 501).

- [ ] **Step 3: Implementasi**

- [ ] **Step 4: Jalankan, pastikan lulus** (perintah sama + `tests/server`)

  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(extract): style profiles - save from a run, start a sweep from one`

---

### Task 9: Dashboard — panel tahap 4–5, tab Review, profile

**Files:**
- Modify:
  - `web/src/components/ExtractionStage.tsx` (panel 4 dan 5);
  - `web/src/components/StagePanel.tsx` (`n <= 5` ke `ExtractionStage`);
  - `web/src/pages/ProjectDetailPage.tsx` (tab Review, profile di modal "Dari tahap…");
  - `web/src/pages/NewProjectPage.tsx` (Dropdown profile);
  - `web/src/api/*` (hook `useProfiles`, `useSaveProfile`, `profile_id` pada `useStartRun`/create);
  - `web/src/index.scss`
- Create: `web/src/components/ReviewTab.tsx`
- Test: `web/src/components/ExtractionStage.test.tsx`, `web/src/components/ReviewTab.test.tsx`

**Interfaces:**
- Consumes artefak:
  - `04_rooms/candidates.json`, `04_rooms/candidates/<k>/spec.json`, `rooms.png`;
  - `05_validate/scores.json`, `chosen.json`, `issues.json`, `overlay_ids.png`, `layers/*.png`;
  - `GET/POST /api/profiles`.
- Produces:
  - **Panel 4:**
    - tabel kandidat (radio per baris, pola panel 3: `#`, ruang, berlabel, luas kotor m²);
    - overlay `rooms.png` kandidat terpilih;
    - tabel ruang kandidat terpilih (ID, nama, tipe, luas m²) dari `spec.json`.
  - **Panel 5:**
    - skor besar + `ProgressBar` per aturan dari `ratios` kandidat terpilih (nilai = `1 − ratio`);
    - tabel masalah (kode, severity, elemen, pesan) dari `issues.json`;
    - mengklik elemen membuka tab Review dengan `?tab=review&focus=<id>`;
    - tombol "Simpan sebagai profile" (Modal + `TextInput` nama) hanya bila tahap 5 `succeeded`;
    - penyimpangan (ruling plan): elemen tidak disorot **di overlay** dan tooltip hover ID belum ada; keduanya butuh geometri elemen di klien (dibawa ke M7). Cost: pengguna mencari ID di overlay dengan mata, dibantu label ID ≥ 14 px;
    - peringatan carry-over tampil lewat `warnings` tahap yang sudah dirender `StagePanel`.
  - **Tab Review:**
    - kiri: `OverlayViewer` dengan `src = overlay_ids.png` dan layer dinding/pintu/kolom/ruang;
    - kanan: tabel masalah;
    - parameter `focus` menyorot baris masalah yang merujuk ID itu;
    - banner info "Review Strata tersedia di M6" bila tahap 6 `skipped`;
    - tanpa tahap 5 sukses pada run terakhir: helper "Belum ada hasil validasi".
  - **Profile:** Dropdown "Profile (opsional)" di form project baru dan modal "Dari tahap…". Nilainya dikirim sebagai `profile_id`.

- [ ] **Step 1: Tulis test yang gagal**
  - `stage 4 lists candidates and shows the room table`.
  - `stage 5 shows score, rule bars and issues; save-as-profile posts name and from_run`.
  - `ReviewTab shows numbered overlay with four layers and the issue table`.
  - `ReviewTab focuses the issue row named in ?focus=`.
  - `new project form sends profile_id when a profile is chosen`.

- [ ] **Step 2: Jalankan, pastikan gagal**

  Run: `cd web && rtk npm test -- --run src/components/ExtractionStage.test.tsx src/components/ReviewTab.test.tsx`
  Expected: FAIL.

- [ ] **Step 3: Implementasi** (komponen Carbon yang sudah dipakai: `DataTable`/table biasa seperti panel 3, `ProgressBar`, `Modal`, `TextInput`, `Dropdown`, `InlineNotification`; radio native per baris seperti panel 3)

- [ ] **Step 4: Jalankan, pastikan lulus**

  Run: `cd web && rtk npm test -- --run && rtk npm run lint && rtk npm run build`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `feat(web): stage 4-5 panels, Review tab with numbered overlay, style profile choice`

---

### Task 10: Test regresi, determinisme, waktu, laporan

**Files:**
- Modify: `tests/extraction/test_gatsu_regression.py`
- Create: `tests/extraction/test_gatsu_pipeline.py`, `benchmarks/reports/m5c-spec.md` (+ `.json`)
- Test: file di atas

**Interfaces:**
- Consumes: `stage_input` … `stage_validate` (sesuai urutan), `evaluate(pred, gt)` (benchmark M5a).
- Produces:
  - `test_gatsu_pipeline.py` (slow, satu fixture modul yang menjalankan tahap 0–5 di project sementara):
    - `test_stages_1_to_5_within_two_minutes`: waktu tahap 1–5 ≤ 120 s (NFR-PF-01);
    - `test_spec_meets_floors`: `evaluate(spec, GT)` ≥ floor untuk metrik dinding/pintu/tangga/IoU (nilai M5b) ditambah `room_match`, `gross_area_err`, dan `scale_err`. Floor ruang/luas diisi nilai terukur, dibulatkan ke bawah, di Step 3; yang mencapai NFR memakai ambang NFR;
    - `test_rooms_typed_from_labels`: ≥ 10 ruang bernama dengan tipe benar terhadap GT (dicocokkan IoU ≥ 0.5);
    - `test_rerun_gives_identical_spec` (NFR-RL-06): tahap 3–5 diulang di project kedua → JSON spec identik setelah `meta.created_at`, `run_id`, `version`, dan `parent_version` dibuang;
    - `test_nfr_full` (xfail strict=False): `passed(evaluate(...))` semua True.
  - Laporan `m5c-spec.md`: `python -m benchmarks.run_extraction_bench --spec <spec.v1.json>` hasil pipeline.

- [ ] **Step 1: Tulis test**, dengan floor ruang sementara 0.

- [ ] **Step 2: Jalankan dan catat metriknya**

  Run: `rtk uv run --env-file .env pytest -q tests/extraction/test_gatsu_pipeline.py`
  Expected: PASS dengan floor 0. Catat `room_match`, `gross_area_err`, dan waktu.

- [ ] **Step 3: Set floor ke nilai terukur (dibulatkan ke bawah), jalankan lagi**

  Expected: PASS. Floor yang memenuhi NFR diganti ambang NFR. Floor yang lebih rendah dari NFR dicatat sebagai `Ruling:` di ledger beserta penyebab terukurnya.

- [ ] **Step 4: Tulis laporan** `benchmarks/reports/m5c-spec.md` + `.json`.

- [ ] **Step 5: Commit**

  `test(extract): Gatsu end-to-end spec regression, determinism and stage 1-5 time`

---

### Task 11: End-to-end dashboard dan status M5

**Files:**
- Modify: `ROADMAP.md` (centang tugas M5, "Status M5c", galat yang dibawa ke M7)

- [ ] **Step 1: Jalankan server dev** (uvicorn + Vite yang sudah ada; restart uvicorn agar kode baru dipakai).

- [ ] **Step 2: Upload `floorplan/plan.jpeg` lewat form project baru** (Playwright). Expected:
  - tahap 0–5 selesai tanpa intervensi; panel 4–5 terisi;
  - tahap 7–10 selesai; tab Review menampilkan overlay bernomor;
  - "Buka editor" membuka editor dengan spec v1.

  Bila tahap 5 `needs_attention` (skor < 0.6), "lanjutkan tetap" (`continue`) dipakai, lalu skornya dicatat.

- [ ] **Step 3: Simpan profile dari run itu, jalankan ulang "Dari tahap 3" dengan profile.** Expected: kandidat 0 = parameter profile, dan spec v2 mempertahankan ID v1 (carry-over).

- [ ] **Step 4: Tulis "Status M5c" di ROADMAP.** Isinya:
  - metrik terhadap NFR;
  - waktu tahap 1–5;
  - penyimpangan (penutupan leher otomatis, tooltip hover ID di Review);
  - galat yang dibawa ke M7;
  - angka suite.

  Centang tugas M5 yang selesai.

- [ ] **Step 5: Commit**

  `docs: M5c status (stages 4-5, M5 complete)`
