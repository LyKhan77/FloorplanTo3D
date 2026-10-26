# 04 — Ekstraksi (Tahap 0–5)

Tahap 0–5 sepenuhnya **deterministik** (tanpa LLM), kecuali parse prompt opsional di tahap 0. Semuanya berjalan di CPU. Setiap tahap:
- menerima artefak tahap sebelumnya,
- menulis artefak ke `runs/<run_id>/stages/<nn>_<nama>/`,
- mengirim event `stage.started`, `stage.progress`, `stage.log`, `stage.artifact`, dan `stage.finished`.

## Ringkasan

| Tahap | Input | Output utama | Gagal jika |
|---|---|---|---|
| 0 Input | upload + prompt + parameter | `input.json` | tipe/ukuran tidak valid |
| 1 Preprocess | file asli | `page.png` (grayscale, lurus, terpotong) | file tidak bisa dibaca |
| 2 Grid & skala | `page.png` | `grid.json` (sumbu, `px_to_mm`) | skala tidak bisa ditentukan dan tidak ada fallback |
| 3 Ekstraksi | `page.png`, `grid.json` | K kandidat `elements.json` | semua kandidat kosong |
| 4 Ruang | kandidat | K `rooms.json` | — (ruang kosong hanya menurunkan skor) |
| 5 Validasi | kandidat + ruang | `chosen.json`, `spec.v1.json` | tidak ada kandidat bebas error, atau skor < 0.6 (`needs_attention`) |

---

## Tahap 0 — Input

1. Validasi tipe (cek magic bytes, bukan hanya ekstensi) dan ukuran (≤ `MAX_UPLOAD_MB`).
2. Simpan file asli dan hitung SHA-256.
3. PDF multi-halaman: halaman pertama dipakai secara default. Pengguna bisa memilih halaman di form (P1).
4. Parse prompt menjadi parameter:
   - **Parser aturan** (selalu jalan): regex angka + satuan dekat kata kunci, mis. `tinggi (dinding)? ([\d.,]+) ?(m|mm|cm)`, `lantai \d+`, `data (hall|center)`.
   - **Parser Strata** (jika aktif dan tersedia): JSON schema `PromptParams`. Hasilnya hanya mengisi field yang kosong dari parser aturan.
   - Parameter eksplisit di form selalu menang.
5. Tulis `input.json`: `{prompt, params_explicit, params_parsed, params_final, sha256, filename, page}`.

## Tahap 1 — Preprocess

1. **Rasterisasi.** PDF dirender pada 300 dpi dengan PyMuPDF. Gambar raster dibaca apa adanya. Bila lebar < 2000 px, gambar di-*upscale* 2× (INTER_CUBIC) untuk deteksi saja. Koordinat tetap dicatat relatif ke gambar kerja, dan faktor skalanya disimpan di `meta.json`.
2. **Grayscale + normalisasi kontras** (CLAHE ringan).
3. **Deskew.** Sudut dominan garis panjang diestimasi dengan HoughLinesP pada tepi Canny. Bila |sudut| ∈ (0.2°, 5°], gambar diputar. Bila > 5°, hasilnya `needs_attention` (scan miring di luar cakupan).
4. **Area gambar.** Komponen terhubung terbesar dari garis tebal dideteksi sebagai bingkai bangunan. Title block dan border kertas dibuang bila terdeteksi: persegi panjang besar di tepi, dengan kepadatan teks tinggi. Bagian di luar area kerja **tidak** dibuang, hanya ditandai. Tujuannya agar bulatan grid di luar bangunan tetap terbaca.
5. **Binarisasi.** Adaptive threshold (Sauvola atau Gaussian) menghasilkan `bin.png`. Parameter blok dan `k` termasuk dimensi sweep (lihat tahap 3).

Artefak: `page.png`, `bin.png`, `meta.json` (`{deskew_deg, upscale, work_size, drawing_bbox}`).

## Tahap 2 — Grid & Skala

### 2.1 OCR global

RapidOCR dijalankan pada `page.png`, termasuk teks vertikal: OCR dijalankan juga pada gambar yang diputar 90°. Hasilnya `ocr.json`: daftar `{text, bbox, angle, conf}`. Hasil ini dipakai ulang oleh tahap 3 (masking teks) dan tahap 4 (label ruang).

Klasifikasi teks dengan aturan:

| Kelas | Aturan |
|---|---|
| `grid_label` | 1–2 karakter (`[A-Z]{1,2}` atau `\d{1,2}`) di dalam kontur lingkaran |
| `dimension` | angka 3–6 digit (`\d{3,6}`), opsional dengan satuan. Mis. "6000", "28000". |
| `room_label` | mengandung kata dari leksikon ruang (§4.3), atau huruf kapital ≥ 4 karakter di dalam area bangunan |
| `annotation` | pola MEP/kabel: `NYY`, `\dx\dC`, `ROUTE`, `CABLE`, `PANEL`, `SDP`, `UPS`, `mm²` |
| `proposed` | `PROPOSED`, `NEW`, `RENCANA`, `USULAN`. Menandai elemen yang belum ada (kondisi existing tidak memodelkannya). |
| `dismantle` | `DISMANTLE`, `BONGKAR`, `DEMOLISH`. Menandai elemen yang masih ada sekarang tetapi akan dibongkar (tetap dimodelkan). |
| `stair_dir` | `NK`, `NAIK`, `UP`, `TR`, `TURUN`, `DN`, `DOWN` di dalam/dekat area tangga |
| `other` | sisanya |

### 2.2 Deteksi grid

1. **Bulatan grid**: HoughCircles plus verifikasi kontur, dengan radius pada rentang yang dikalibrasi terhadap tinggi teks. Bulatan harus berisi teks `grid_label`.
2. **Garis sumbu**: untuk tiap bulatan, cari garis panjang (≥ 50% dimensi gambar) yang melewati pusatnya, tegak lurus terhadap tepi gambar terdekat. Garis sumbu biasanya tipis atau putus-putus (dash-dot). Garis putus digabung dengan *line linking* toleransi gap.
3. Kelompokkan menjadi **vertikal** (label huruf, biasanya di atas/bawah) dan **horizontal** (label angka, biasanya kiri/kanan). Konvensi ini tidak dipaksakan: orientasi ditentukan dari arah garis.
4. Urutkan sumbu dan simpan posisinya dalam piksel.

### 2.3 Skala

1. Kumpulkan pasangan **(teks dimensi, segmen dimensi)**. Segmen dimensi adalah garis tipis sejajar dengan tick/arrow di kedua ujung. Teks dimensi berada di tengah dan sejajar dengan segmen.
2. Cocokkan ujung segmen dimensi dengan sumbu grid terdekat (≤ 10 px). Ini menghasilkan persamaan `jarak_px(sumbu_i, sumbu_j) × s = nilai_mm`.
3. Selesaikan `s` (mm/px) dengan **least squares**, pisah untuk sumbu X dan Y (anisotropi ≤ 1% dianggap noise; bila > 1%, dipakai skala terpisah).
4. **Cek silang**: dimensi total (mis. 28000) terhadap jumlah dimensi bagian (6000+6000+4000+6000+6000), dan residu tiap persamaan ≤ 1%. Persamaan dengan residu > 1% dibuang sebagai outlier (RANSAC sederhana).
5. Hasil: `px_to_mm` affine. Origin di sudut kiri-bawah grid, Y dibalik (lihat `03-layout-spec.md` §1).

**Prioritas skala:**
1. **Skala manual dari form selalu menang** (konsisten dengan aturan "parameter eksplisit menang"). Skala hasil hitungan tetap dihitung. Bila selisihnya > 1% dari skala manual, dicatat sebagai peringatan.
2. Bila tidak ada skala manual: skala dari grid + dimensi (langkah 1–4).
3. Bila gagal: satu dimensi total + sumbu ujungnya.
4. Bila tidak ada sama sekali: status `needs_attention` dengan pesan "Skala tidak dapat ditentukan, isi skala manual".

**Gatsu (ekspektasi):** 6 sumbu vertikal A–F dan 3 horizontal 1–3. Dimensi 6000/6000/4000/6000/6000 (total 28000) dan 6000/6000 (total 12000). Skala ≈ 25.85 mm/px pada gambar 1600 px.

Artefak: `ocr.json`, `grid.json` (`{axes[], px_to_mm, residuals, scale_source}`), `overlay.png` (sumbu + label + segmen dimensi terpakai).

## Tahap 3 — Ekstraksi Geometri (dengan Parameter Sweep)

### 3.1 Masking anotasi (sebelum deteksi apa pun)

1. Bbox teks OCR (semua kelas kecuali `grid_label`) diisi putih, dengan dilasi kecil.
2. **Garis dimensi dan sumbu grid** yang terdeteksi di tahap 2 dihapus dari salinan biner.
3. **Hatching/pola padat** (mis. jalur kabel bergaris rapat di Gatsu antara Battery Room dan Capasitor Room): area dengan kepadatan garis pendek paralel tinggi (analisis orientasi lokal) ditandai `hatch_mask`. Area ini tidak dihapus, hanya diberi penalti di skor keyakinan elemen yang melewatinya.
4. **Leader line**: garis tipis yang salah satu ujungnya menyentuh bbox teks `annotation`, `proposed`, atau `dismantle` dihapus. Ujung lain leader dicatat sebagai **titik tunjuk** untuk langkah 6.
5. **Simbol MEP terisi** (`symbol_mask`): blob hitam padat yang **bukan** bentuk dinding, yaitu salah satu dari: rasio aspek < 4, tidak terhubung ke jaringan garis dinding di kedua ujung, atau berada di dalam ruang dan tidak menyentuh dinding lain. Di Gatsu, ini panel/rack/baterai di Battery Room dan area UPS. Blob ini dihapus dari biner sebelum S1, karena S1 (opening morfologi) akan mengira blob tebal sebagai dinding. Uji pada `plan.jpeg` membuktikan risiko ini: filter dinding naif FloorplanToBlender3d hanya menangkap blob panel dan simbol lift, dan tidak menangkap satu pun dinding garis ganda.
6. **Kondisi existing.** Elemen yang ditunjuk teks `proposed` (lewat titik tunjuk leader, atau berada ≤ 1000 mm dari teks itu tanpa leader) tidak dimodelkan: dinding dilewati dan simbol di-mask, lalu dicatat `info` di `issues`. Elemen yang ditunjuk teks `dismantle` tetap dimodelkan, dengan `provenance.evidence.note = "to_be_dismantled"`. Label ruang berawalan `EX` (mis. "EX MUSHOLA") tetap ruang biasa; nama disimpan apa adanya.

### 3.2 Dinding — dua strategi (dimensi sweep)

**Strategi S1 — Solid / poche** (dinding diisi hitam atau hatch padat):
1. Morphological opening dengan kernel persegi `k = round(t_min / mm_per_px)`. `t_min` = tebal dinding minimum yang diharapkan (sweep: 80, 100, 150 mm). Hasilnya mask garis tebal.
2. Skeletonize, lalu vektorisasi skeleton menjadi polyline, lalu disederhanakan (Douglas-Peucker, ε = 0.5 × tebal).
3. Tebal per segmen diambil dari distance transform di sepanjang skeleton (median × 2).

**Strategi S2 — Garis ganda / hollow** (dinding digambar sebagai dua garis tipis sejajar; ini kasus Gatsu):
0. **Perbaikan garis berarah** (tanpa menebalkan): closing morfologi dengan kernel 1-D horizontal dan vertikal sepanjang `L_fix` px, digabung dengan OR. Langkah ini menyambung garis yang putus karena JPEG, antialiasing, atau stroke tipis, tetapi tidak melebarkan garis ke samping, sehingga celah di antara dua garis dinding tetap terbuka. Hanya diterapkan pada salinan untuk deteksi garis. Pengukuran posisi dan tebal tetap memakai biner asli.
1. Deteksi segmen garis dengan LSD (Line Segment Detector) pada biner yang sudah dimask. Fragmen kolinear (offset tegak lurus ≤ 1 px, gap ≤ 3 × stroke) digabung **sebelum** pairing, agar satu sisi dinding yang terputus tetap bisa berpasangan.
2. Snap orientasi ke sumbu grid (±1.5°). Segmen miring disimpan terpisah.
3. **Pairing**: untuk tiap pasangan segmen sejajar dengan jarak `g` ∈ [`t_min`, `t_max`] (sweep `t_max`: 300, 450, 600 mm) dan overlap ≥ 60%, buat dinding dengan garis tengah = rata-rata dan tebal = `g`.
4. Segmen panjang tanpa pasangan dengan ketebalan stroke tinggi (≥ 2× median stroke) diperlakukan sebagai dinding tipis (`partition`, tebal default).
5. **Pasangan sebagian**: bila satu sisi dinding hilang sepanjang ≤ 1500 mm tetapi sisi lainnya kontinu dan kedua ujung bagian itu berpasangan, dinding dianggap kontinu dengan tebal dari bagian yang berpasangan. Keyakinan bagian itu diturunkan.

**Mengapa tidak menebalkan garis secara global (dilasi):** pada Gatsu (≈ 25.85 mm/px), dinding 150 mm hanya berjarak ±6 px antar-garis. Dilasi 2–3 px akan (a) menutup celah itu sehingga dinding garis ganda menjadi blob dan S2 gagal; (b) menempelkan dinding ke teks, busur pintu, dan simbol di dekatnya; (c) menutup celah pintu sehingga pintu hilang; (d) menggeser hasil ukur tebal. Ketebalan dinding di 3D berasal dari jarak pasangan garis yang terukur (atau default per `kind`), **bukan** dari tebal stroke di gambar. Garis yang tipis tidak membuat dinding 3D tipis.

**Pasca-proses (kedua strategi):**
1. Snap ujung ke sumbu grid bila ≤ 150 mm.
2. Gabungkan segmen kolinear yang terputus. Aturan gap tanpa bukti pintu (busur, daun, atau garis sliding):
   - gap ≤ 600 mm: ditutup otomatis (terlalu sempit untuk pintu; kemungkinan garis putus);
   - 600–3000 mm dan diapit ujung dinding yang rapi: kandidat `opening` dengan keyakinan rendah (§3.4.6);
   - di luar itu: dibiarkan terbuka, dan dicek di tahap 4 (kebocoran ruang).
   Gap yang berisi pintu ditangani §3.4.
3. Perpanjang/potong ujung ke dinding tegak lurus terdekat (≤ tebal) untuk membentuk sambungan L/T.
4. Hapus segmen < 300 mm yang tidak terhubung.
5. Klasifikasi `kind`: `exterior` bila berada di kontur luar bangunan, `interior` untuk tebal ≥ 120 mm, dan `partition` untuk sisanya.

### 3.3 Kolom

1. Kandidat dari: (a) blob terisi dengan luas ekuivalen 150–800 mm persegi; (b) template matching simbol H/I (template dibuat dari parameter, beberapa skala); (c) persegi berongga dengan simbol di dalamnya.
2. Prioritas di sekitar perpotongan grid (≤ 300 mm). Kandidat di luar perpotongan diterima hanya dengan skor bentuk tinggi.
3. Gatsu: kolom H di hampir setiap perpotongan grid (A1, B1, C1, …).

### 3.4 Pintu

1. **Deteksi busur**: kontur tipis yang dicocokkan ke lingkaran (algebraic fit). Diterima bila sudut cakupan 60°–100°, radius 500–1300 mm, dan residu fit rendah.
2. **Pusat busur = engsel.** Satu ujung busur menempel pada dinding. Garis dari pusat ke ujung lain (bila ada) adalah daun pintu.
3. **Pasangan dengan dinding**: proyeksikan engsel ke dinding terdekat (≤ tebal + 100 mm). Lebar pintu = radius, dengan toleransi terhadap celah di dinding.
4. **Double**: dua busur dengan pusat di kedua sisi celah yang sama, radius mirip (±15%), dan saling menghadap. Hasilnya `double_swing`, `hinge: both`.
5. **Arah**: `hinge` = ujung celah tempat engsel (relatif a→b). `swing` = sisi dinding tempat busur berada.
6. **Tanpa busur**: celah pada dinding yang lebarnya 600–3000 mm dan diapit ujung dinding rapi. Bila ada garis tipis sejajar di dalam celah, tipe `sliding`. Bila tidak ada, tipe `opening`, dengan keyakinan rendah sehingga diteruskan ke review.
7. Celah pintu **ditutup** saat membentuk dinding kontinu. Dinding tetap satu segmen, dan pintu menjadi `opening` di atasnya.

Gatsu: pintu double di pintu masuk barat (dekat grid A–2), pintu double ke R. Meeting, pintu single ke Gudang/Galery/Battery Room/AHU/MDF, pintu toilet, dan pintu double Capasitor Room.

### 3.4b Tangga

Dikerjakan **sebelum** deteksi dinding final, karena garis anak tangga mudah dianggap partisi.

1. **Kandidat flight**: kelompok ≥ 5 segmen tipis sejajar, panjang hampir sama (±10%, = lebar flight 800–2500 mm), dengan jarak antar-garis teratur (koefisien variasi ≤ 15%, jarak 220–350 mm).
2. Bounding box kelompok = persegi flight. `width` = panjang garis. `risers` = jumlah garis + 1.
3. **Arah naik**: (a) teks `stair_dir` terdekat beserta panah/garis jalan (polyline dengan kepala panah); `NK`/`NAIK`/`UP` = arah panah. (b) Bila tidak ada, flight yang berbatasan dengan bordes dianggap naik **menuju** bordes, dengan keyakinan 0.5. (c) Bila tetap tidak jelas, keyakinan 0.3 dan dicatat di `issues`. Arah dibalik lewat panel koreksi editor bila salah. Strata tidak dipakai untuk tangga di MVP.
4. **Bordes**: area persegi di antara ujung flight yang berdekatan (≤ 1.5 × lebar flight), dibatasi dinding ruang tangga.
5. Garis anak tangga dimasukkan ke `stair_mask` dan dikeluarkan dari kandidat dinding S1/S2. Dinding tepi ruang tangga tetap dideteksi seperti biasa.
6. Simbol lift (persegi dengan silang) di dekatnya menandai ruang `lift`, tanpa geometri tangga.
7. Gatsu: tangga U di sekitar lift antara grid A–B dan 1–2, dengan teks "NK". Tangga kecil di sisi timur dekat grid F–2 juga perlu dicek.

### 3.5 Jendela (P1)

Pola tiga garis tipis sejajar di dalam tebal dinding `exterior`, sepanjang ≥ 600 mm. Lebar sama dengan panjang pola. `sill` dan `height` memakai default.

### 3.6 Parameter Sweep

| Dimensi | Nilai | Catatan |
|---|---|---|
| Strategi dinding | S1, S2 | |
| Binarisasi (Sauvola `k`) | 0.2, 0.34 | |
| `t_min` (mm) | 80, 150 | S1: kernel opening; S2: gap minimum |
| `t_max` (mm) | 450 | S2 |
| `L_fix` (px, perbaikan garis berarah) | 0 (mati), 5 | S2 langkah 0. Nilai dikalikan faktor upscale. |
| Toleransi snap grid (mm) | 150 | tetap |

Kombinasi penuh dibatasi `SWEEP_MAX_CANDIDATES` (default 12). Bila ada style profile, sweep dimulai dari parameter profile, ditambah tetangganya (±1 langkah per dimensi). Kandidat dijalankan paralel (`ProcessPoolExecutor`, jumlah worker = core CPU − 1).

Setiap kandidat menghasilkan `candidates/<k>/elements.json`: walls, columns, openings, dan provenance (`confidence`, `evidence`).

### 3.7 Keyakinan elemen

`confidence` ∈ [0,1] per elemen, kombinasi fitur:
- **Dinding**: kekuatan pasangan (S2) atau kepadatan mask (S1), konektivitas ujung, kesesuaian dengan grid, penalti bila melintasi `hatch_mask` atau dekat teks `annotation`.
- **Pintu**: residu fit busur, kecocokan radius dengan lebar celah, dan ada/tidaknya daun.
- **Kolom**: skor bentuk dan jarak ke perpotongan grid.

Elemen dengan `confidence < 0.6` menjadi **antrean review** tahap 6.

## Tahap 4 — Pembentukan Ruang

1. Bangun **tapak dinding**: buffer tiap garis tengah dinding sebesar tebal/2 (cap flat, join mitre), lalu union semuanya. Bukaan pintu **tidak** memotong tapak, agar ruang tertutup.
2. **Area interior** = poligon kontur luar bangunan (dari dinding `exterior` atau `meta.building_outline`) dikurangi tapak dinding dan tapak kolom. Bangunan terpisah (Gatsu: Capasitor Room di timur grid F) diproses sebagai kontur luar terpisah.
2b. **`building_outline`** = union tapak semua dinding, kolom (termasuk `pilaster`), dan area interior, lalu diambil kontur luarnya per massa bangunan. Di Gatsu, hasilnya mencakup pita luar dengan blok sirip di luar grid. Area antara pita luar dan dinding utama menjadi ruang bertipe `outdoor`/`corridor` sesuai labelnya. Luas kotor (`gross_area_m2`) dihitung dari outline ini.
3. **Polygonize**: setiap komponen poligon hasil pengurangan menjadi kandidat ruang. Kandidat < 1 m² atau dengan rasio aspek > 20 (sisa celah) dibuang. Area sangat tipis digabung ke tetangganya.
4. **Label**: teks OCR `room_label` dipasangkan ke ruang yang memuat pusat bbox-nya. Bila satu ruang memuat beberapa label, dipilih label dengan skor leksikon tertinggi. Teks `annotation` diabaikan.
5. **Tipe**: dipetakan dari leksikon (§4.3). Bila tidak cocok, tipe `other` dan masuk antrean review T3.
6. **Turunan**: `holes` (tapak kolom yang sepenuhnya berada di dalam ruang), `area_m2` (bersih, dikurangi `holes`), `perimeter_m`, `bounding_walls` (dinding yang tapaknya bersentuhan), dan `doors` (pintu yang dinding induknya membatasi ruang).
6b. **Cek kebocoran ruang**: dua area yang seharusnya terpisah bisa menyatu lewat celah dinding yang tidak tertutup. Deteksi: ruang dengan "leher" sempit (lebar < 600 mm, dari erosi poligon) yang tidak memuat pintu, atau ruang yang memuat ≥ 2 label `room_label` berbeda. Penanganan: coba tutup leher dengan dinding sintetis (tebal = median tetangga), lalu terima bila skor validator naik. Bila tidak, catat warning dengan ID ruang agar bisa diperbaiki lewat panel koreksi.
7. **Ruang tangga/lift**: ruang yang memuat flight dari §3.4b diberi tipe `stair` dan dihubungkan ke `stairs[].room_id`. Ruang dengan simbol silang dalam kotak diberi tipe `lift`.

### 4.3 Leksikon ruang (dapat diperluas, `core/extraction/lexicon.yaml`)

| Kata kunci (case-insensitive, toleran typo) | Tipe |
|---|---|
| DATA HALL, SERVER, WHITE SPACE | `data_hall` |
| UPS | `ups_room` |
| BATTERY, BATTERAI, BATERAI | `battery_room` |
| PANEL, LVMDP, SDP, ELECTRICAL, LISTRIK | `electrical_room` |
| MDF, IDF, MMR, MEET ME | `mdf` |
| AHU, CRAC, PAC | `ahu_room` |
| CAPASITOR, CAPACITOR, KAPASITOR | `capacitor_room` |
| MEETING, R. RAPAT, RAPAT | `meeting` |
| GUDANG, STORAGE, STORE | `storage` |
| PANTRY, DAPUR | `pantry` |
| TOILET, WC, KM, LAVATORY | `toilet` |
| MUSHOLA, MUSHOLLA, PRAYER | `prayer_room` |
| GALERY, GALLERY, LOBBY, HALL | `lobby` |
| KORIDOR, CORRIDOR, SELASAR | `corridor` |
| TANGGA, STAIR | `stair` |
| LIFT, ELEVATOR | `lift` |

Pencocokan memakai jarak Levenshtein ≤ 1 untuk kata ≥ 5 huruf, agar toleran terhadap salah baca OCR.

## Tahap 5 — Validasi & Pemilihan Kandidat

1. Untuk setiap kandidat: susun spec sementara, lalu jalankan validator (`03-layout-spec.md` §12).
2. Buang kandidat dengan aturan `error`.
3. Pilih kandidat dengan **skor validator tertinggi**. Bila skor seri (selisih ≤ 0.01), pilih yang cakupan dindingnya (V018) lebih tinggi.
4. Buat spec dari kandidat terpilih (`source: pipeline`). Urutan ID ditentukan secara deterministik: dinding diurut berdasarkan (y, x) titik a, ruang berdasarkan posisi centroid.
   - **4a. Project baru**: simpan sebagai `spec.v1.json`.
   - **4b. Re-ekstraksi (project sudah punya HEAD)**: lakukan **carry-over** terhadap HEAD sebelum disimpan sebagai versi berikutnya:
     - **Pencocokan dinding**: jarak garis tengah ≤ 200 mm, beda sudut ≤ 3°, dan overlap ≥ 50%. Dinding yang cocok **mewarisi ID lama** dan `height` editan.
     - **Pencocokan ruang**: IoU poligon ≥ 0.5. Ruang yang cocok mewarisi ID, `name`, dan `type` bila sumber terakhirnya `editor`/`manual`/`llm`.
     - **Pencocokan pintu/kolom**: jarak pusat ≤ 300 mm, lalu ID diwarisi.
     - **Objek** disalin apa adanya (posisinya dalam mm tidak bergantung pada dinding). `room_id` dihitung ulang.
     - **Default** (`meta.defaults`) dari HEAD dipertahankan.
     - Elemen baru yang tidak cocok mendapat ID baru (melanjutkan nomor tertinggi, tidak pernah memakai ulang).
     - Edit yang tidak bisa dipindahkan (mis. tinggi dinding untuk dinding yang hilang) dicatat di `carryover.json` dan ditampilkan sebagai peringatan di dashboard.
5. Buat **overlay bernomor** `overlay_ids.png` untuk dashboard dan tahap 6. Warna: dinding biru, pintu hijau, kolom oranye, ruang dengan arsiran tipis per ruang. Label ID berukuran ≥ 14 px dengan latar kontras.
6. Simpan `scores.json` (skor + rincian per aturan untuk semua kandidat), `issues.json` (masalah kandidat terpilih), dan `chosen.json`.
7. Ambang batas:
   - skor ≥ 0.8: `succeeded`;
   - 0.6 ≤ skor < 0.8: `succeeded` dengan peringatan, dan tahap 6 diprioritaskan;
   - skor < 0.6: `needs_attention`. Run berhenti, kecuali pengguna memilih "lanjutkan tetap".
8. **Style profile**: bila run berakhir sukses, parameter kandidat terpilih bisa disimpan sebagai profile lewat aksi dashboard "Simpan sebagai profile".

## Mode Gagal yang Diketahui & Penanganan

| Kasus | Gejala | Penanganan |
|---|---|---|
| Resolusi rendah (dinding < 4 px) | S2 gagal pairing | Upscale 2×. Bila tetap gagal, `needs_attention` dengan saran meminta file beresolusi lebih tinggi. |
| Jalur kabel bergaris rapat | Dinding palsu sepanjang jalur kabel | `hatch_mask` menurunkan keyakinan, lalu masuk review T1 |
| Teks menempel ke dinding | Dinding terputus | Masking teks memakai dilasi minimal, lalu langkah gabung kolinear menutup gap |
| Pintu tanpa busur | Pintu tidak terdeteksi | Deteksi celah (§3.4.6), keyakinan rendah, review T2 |
| Ruang terbuka (tanpa dinding penuh) | Dua ruang menyatu | Diterima sebagai satu ruang. Dipisah lewat panel koreksi editor (`add_wall`). |
| Grid tanpa angka dimensi | Skala tidak bisa dihitung | Fallback skala manual |
| Garis dinding putus-putus | Dinding dianggap ada / hilang | Garis putus-putus diklasifikasikan terpisah. Bila ditunjuk teks `dismantle`: dimodelkan (kondisi existing). Bila ditunjuk `proposed` atau tanpa konteks (bisa berarti elemen di atas, mis. balok/kanopi): diabaikan, dicatat `info`. |
| Garis dinding tipis/pudar/putus (JPEG) | Dinding terputus, ruang bocor | Perbaikan garis berarah (S2 langkah 0), gabung fragmen sebelum pairing, pasangan sebagian, aturan gap, cek kebocoran ruang (tahap 4 langkah 6b). Tidak memakai dilasi global. |
| Simbol MEP terisi (panel, rack, baterai) | S1 mengira blob tebal sebagai dinding | `symbol_mask` (§3.1.5) sebelum S1 |
| Garis anak tangga | Dianggap partisi rapat | `stair_mask` (§3.4b) sebelum deteksi dinding |
