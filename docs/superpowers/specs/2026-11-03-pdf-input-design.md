# Desain: input denah dari PDF CAD multi-halaman

Tanggal: 2026-11-03 · Status: draf untuk disetujui user · Branch usulan: `feat/pdf-input`

## 1. Maksud dan alasan

PM mengirim denah sebagai PDF hasil ekspor CAD, multi-halaman. Hanya sebagian halaman yang berupa denah bersih yang
layak jadi input. Contohnya `floorplan/WP1 - APD - ANCOL, JAKARTA (12JKU0508)_R04_22-09-2026_Full signed.pdf`:
39 halaman, dan denah Lt.2 Gedung A, B, C ada di halaman 13. Sejauh ini pipeline baru tervalidasi di Gatsu
(`plan.jpeg`, yang ternyata potongan halaman 3 PDF Gatsu). Gatsu dianggap lolos MVP.

Tujuannya: user bisa membuat project langsung dari PDF seperti itu, tanpa memotong gambar sendiri, dan pipeline
berjalan sampai review tanpa harus mengisi skala.

Temuan dari PDF Ancol, diuji di sesi brainstorm 2026-11-03 dengan script throwaway:

- PDF berupa **vektor**, bukan scan. Teksnya sudah menjadi garis (tidak ada lapisan teks), dan semua garis punya tebal
  yang sama (0.38). Membaca vektor langsung tidak memberi semantik dinding.
- Setiap halaman berukuran Letter dan memuat title block, bingkai dengan grid referensi lembar A–L/1–8, dan panah
  utara.
- Halaman denah ditempeli **foto lapangan**, 13 foto di p13. Garis di bawah foto tetap utuh. Menghapus foto di level
  PDF memunculkan kembali dinding, pintu dan teks. Yang tersisa hanya garis bingkai tipis di tepi tiap foto.
- p13 bertanda `SCALE: NTS` dan tidak punya bubble grid maupun rantai dimensi, sehingga stage 2 berhenti dengan
  `needs_attention`.
- Estimasi skala dari pintu (52 busur di p13, median jari-jari 26.1 px pada 300 dpi):
  - dengan asumsi daun pintu 800 mm, hasilnya 30.7 mm/px;
  - skala dari label luas ruang (`LUAS 16.6 M2`, dst.) sekitar 30 mm/px ±7%;
  - selisih keduanya +2%.
- Baseline p13 dengan skala manual menghasilkan 231 kolom, hampir semuanya palsu, berasal dari anak tangga **cable
  tray**. Dengan tray dimasking (template matching), kolom turun ke 54 dan dinding mengikuti dinding asli.
- `drawing_bbox` (`core/extraction/preprocess.py:95`) memilih komponen ink terbesar:
  - pada p13 di 300 dpi hasilnya benar;
  - di 600 dpi ia memilih bingkai lembar, sehingga title block ikut masuk;
  - pada gambar yang sudah dipotong, ia hanya memilih satu blok gedung.

## 2. Tujuan, non-tujuan, anti-tujuan

**Tujuan**

1. **Pemilih halaman.** Setelah memilih PDF di "Project baru", user melihat thumbnail semua halaman dan mengklik
   satu. Satu halaman menjadi satu project.
2. **Pembersihan PDF vektor:**
   - foto yang ditempel dihapus sebelum rasterisasi;
   - bingkai foto dihapus;
   - area gambar terpilih tepat di gedung (title block dan bingkai lembar terbuang).
3. **Skala tanpa dimensi.** Kalau stage 2 tidak menemukan skala dari dimensi grid, skala diperkirakan dari busur
   pintu dengan asumsi **lebar daun pintu standar** (parameter baru, default **800 mm**). Pipeline jalan terus dengan
   peringatan.
4. **Koreksi skala hanya lewat kolom "Lebar pintu standar (mm)".** Kolom ini menggantikan input mm/px di form "Project
   baru" dan modal "Isi skala manual".
5. **Cable tray tidak terbaca sebagai arsitektur.** Pola tangga tray dimasking di stage 3, seperti hatch dan simbol.

**Non-tujuan**

- Multi-lantai dalam satu project. Project tetap satu denah, dan pengelompokan cukup lewat nama project.
- Menyelaraskan posisi antar lantai atau antar lembar, termasuk lembar perbesaran ke denah induk.
- Deteksi otomatis halaman mana yang berisi denah.
- Kalibrasi dua titik.
- Membaca dinding atau teks langsung dari vektor PDF. Snap dinding ke vektor (pendekatan C) bisa jadi perbaikan
  setelah ini.
- **Penutupan ruang di Ancol.** Di p13, ujung dinding berhenti sebelum bertemu dinding lain (V004 sekitar 230),
  sehingga ruang tidak terbentuk. Ini fase debug terpisah sesudah desain ini, termasuk menandai ruang "parsial" yang
  terpotong bingkai lembar.
- Upload multi-halaman sekaligus (multi-select, beberapa project).

**Anti-tujuan**

- Hasil Gatsu memburuk. Benchmark Gatsu (`benchmarks/run_extraction_bench.py`) tidak boleh turun.
- PDF hasil scan (satu gambar sehalaman) kehilangan denahnya karena foto ikut dihapus.
- User harus mengetik angka mm/px.

## 3. Batasan

- pymupdf sudah ada (`load_raster`). Redaction gambar memakai `apply_redactions(images=PDF_REDACT_IMAGE_REMOVE,
  graphics=PDF_REDACT_LINE_ART_NONE, text=PDF_REDACT_TEXT_NONE)`, sudah diuji di pymupdf yang terpasang.
- Server target gspe-ai2 diakses lewat jaringan. PDF Ancol 18 MB, Gatsu 6.7 MB.
- Unit mm. Skala yang disimpan tetap `mm_per_px` di ruang pixel kerja (`scale_from` di `core/extraction/scale.py`).
- Form "Project baru" (`web/src/pages/NewProjectPage.tsx`) saat ini **tidak punya** isian halaman. PDF selalu
  dirasterkan di halaman 1, walaupun API `POST /api/projects` sudah menerima `page`.

## 4. Pendekatan

Dipertimbangkan di sesi brainstorm:

| | Pendekatan | Untung | Rugi |
|---|---|---|---|
| **A** | Perluas jalur raster yang ada: langkah khusus PDF di `load_raster`, pemilih halaman, fallback skala dari pintu, mask tray | Perubahan kecil dan terkumpul; semua yang terbukti di Gatsu tetap dipakai; fallback pintu juga berlaku untuk JPEG tanpa skala | Akurasi geometri tetap dibatasi raster |
| B | Extractor vektor baru (dinding dari path PDF) | Koordinat presisi CAD | Tebal garis seragam, tidak ada layer, teks berupa garis; dinding, rack, tray dan arsir sama-sama "garis hitam"; pada dasarnya membangun ulang stage 3–4 |
| C | A, lalu snap dinding hasil raster ke garis vektor terdekat | Presisi mendekati CAD | Baru masuk akal setelah A terbukti |

**User memilih A.** C dicatat sebagai perbaikan lanjutan.

## 5. Alur

1. User membuka "Project baru" dan memilih file PDF.
2. Web mengirim PDF ke `POST /api/pdf/pages` dan menampilkan thumbnail semua halaman dalam grid. User mengklik satu
   halaman, dan halaman 1 terpilih sebagai default.
3. "Buat project" mengirim file beserta `page` (sudah didukung API) dan parameter lain, termasuk
   `door_leaf_width` kalau diubah.
4. Stage 1:
   - `load_raster` menghapus foto, merasterkan, lalu menghapus bingkai foto;
   - `preprocess` mencari area gambar dengan `drawing_bbox` yang sudah diperbaiki.
5. Stage 2:
   - dimensi grid ditemukan: perilaku sekarang;
   - tidak ditemukan: estimasi dari pintu. Status `succeeded`, `scale_source: "door_estimate"`, plus peringatan;
   - tidak ada cukup pintu: `needs_attention`.
6. Stage 3: mask tray ikut membersihkan `clean`, sama seperti hatch dan simbol.
7. Panel stage 2 di web menampilkan peringatan dan tombol "Ubah lebar pintu". Tombol itu menjalankan ulang dari
   stage 2 dengan `params_override: {door_leaf_width}`.

## 6. Detail

### 6.1 Pemilih halaman

- **Endpoint `POST /api/pdf/pages`** (multipart `file`). Endpoint ini stateless: tidak membuat project dan tidak
  menyimpan file.
  - Balikan: `{"page_count": n, "pages": [{"page": 1, "thumb": "data:image/png;base64,…"}]}`.
  - Lebar thumbnail sekitar 240 px.
  - Batas ukuran sama dengan upload project (`max_upload_mb`).
  - File yang bukan PDF dibalas 400.
- **Web.** Kalau file adalah PDF, preview gambar diganti grid thumbnail yang bisa diklik (Carbon `SelectableTile`
  atau sejenisnya). Nomor halaman terpilih dikirim sebagai `page`. Untuk JPEG/PNG tidak ada yang berubah.
- File PDF terkirim dua kali: sekali untuk thumbnail, sekali untuk membuat project.

### 6.2 Pembersihan PDF (`load_raster`)

- Sebelum rasterisasi, hapus setiap gambar yang rect-nya lebih kecil dari **50% luas halaman**. Gambar sebesar
  halaman (PDF scan) tidak disentuh. Logo dan tanda tangan di title block ikut terhapus, dan itu tidak masalah.
- Setelah rasterisasi, timpa garis tepi setiap rect gambar yang dihapus dengan putih. Tebalnya sekitar 3 px pada
  300 dpi, diskalakan mengikuti dpi.
- Leader magenta dari foto sudah dibuang oleh colour mask `preprocess`, jadi tidak perlu langkah tambahan.
- `input/raster.png` (dipakai editor dan report) adalah raster yang sudah bersih.

### 6.3 `drawing_bbox`

Perilaku yang dituntut:

- **Bingkai lembar dilewati.** Bingkai adalah komponen yang bbox-nya memuat komponen gedung dan ink-nya jarang. Ini
  berlaku juga di 600 dpi, saat bingkai lebih kecil dari 90% halaman.
- **Area gambar adalah gabungan bbox semua komponen gedung yang cukup besar**, bukan hanya komponen terbesar.
  Blok-blok gedung yang terpisah (Gedung A/B di atas dan Gedung B/C di bawah p13) harus ikut semua.
- Title block tidak ikut.
- `plan.jpeg` Gatsu tetap menghasilkan bbox yang sama dengan sekarang.

### 6.4 Skala dari pintu (stage 2)

- **Parameter baru `door_leaf_width`:**
  - satuan mm, default 800;
  - ditambahkan ke `KNOWN` di `core/extraction/params.py`;
  - prompt parser boleh mengenali "lebar pintu 900 mm".
- **Kapan dipakai** (keputusan user, 2026-11-03):
  - `door_leaf_width` diisi **sengaja** oleh user (form "Project baru" atau `params_override` dari tombol "Ubah
    lebar pintu"): estimasi dari pintu **selalu** dipakai, mengalahkan dimensi grid dan `mm_per_px` yang tersimpan
    (project lama, prompt parser, override lama);
  - tidak diisi: urutan tetap `mm_per_px` → dimensi grid → estimasi pintu dengan default 800 mm.

  Dengan begitu tombol "Ubah lebar pintu" selalu punya efek, termasuk saat dimensi grid salah baca.
- **Cara menghitung:**
  - kerangka garis lengkung di dalam `drawing_bbox`, yaitu skeleton dikurangi goresan horizontal dan vertikal yang
    panjang;
  - busur difit ke lingkaran dengan logika `core/extraction/geometry/doors.py` (`find_arcs`/`_arc`), tetapi tanpa
    filter `RADIUS_MM` karena skala belum diketahui. Filter cakupan sudut (`COVER_DEG`) dan residu tetap dipakai;
  - skala = `door_leaf_width / median(radius_px)`.
- **Minimal 3 busur.** Kalau kurang, status `needs_attention` dengan pesan "Skala tidak dapat ditentukan: tidak ada
  dimensi maupun pintu". Batas ini diterima user: tidak ada jalan keluar lain di UI.
- **Keluaran:**
  - `scale_source: "door_estimate"`;
  - peringatan "Skala diperkirakan dari N pintu (lebar pintu {w} mm). Ubah lebar pintu bila ukuran tidak sesuai.";
  - metrik `doors_used` dan `door_radius_px`.
- Tidak ada sumbu grid, jadi `axes` kosong. Jalur ini sudah berjalan di run uji dengan skala manual (`axes_v: 0`).

### 6.5 Mask cable tray (stage 3)

- **Tempat:** `build_masks` di `core/extraction/geometry/masks.py`, di samping hatch dan simbol. Area tray dihapus
  dari `clean` sebelum dinding dan kolom diekstrak. Mask disimpan sebagai `03_extract/masks/tray.png`.
- **Detektor:** template matching pola tangga tray.
  - Template **dibuat secara prosedural** dari ukuran dalam mm: lebar tray, jarak dan tebal anak tangga, tebal rel,
    bentuk anak tangga (garis atau kotak). Template digambar pada `s` dari run, lalu dicocokkan horizontal dan
    vertikal (diputar 90°).
  - Tidak ada potongan gambar klien yang di-commit (AGENTS.md: gambar klien tidak masuk git).
  - Dua gaya awal, ukurannya diambil dari p13 Ancol: tangga tebal (jalur kabel utama) dan tangga tipis dengan anak
    tangga kotak.
  - Spike memakai potongan asli dengan ambang `TM_CCOEFF_NORMED` 0.6. Ambang untuk template prosedural ditentukan
    ulang terhadap p13.
- **Hasil di spike** (B, 600 dpi): kolom 231 → 54, dan dinding mengikuti dinding asli. Salah tangkap yang terlihat
  ada di anak tangga **tangga** di tengah. Area tangga yang sudah dideteksi (`find_flights`/`stair_mask`) harus
  dikecualikan dari mask tray.
- Detektor ini tidak generik: gaya tray lain perlu sampel lain. Batas ini harus ditandai komentar `ponytail:`.

### 6.6 Web

- **"Project baru":**
  - grid thumbnail untuk PDF;
  - isian "Skala (mm/px)" di bagian lanjutan diganti "Lebar pintu standar (mm)", placeholder 800.
- **Panel stage 2** (`web/src/components/ExtractionStage.tsx`):
  - modal "Isi skala manual" diganti modal "Lebar pintu standar (mm)" yang menjalankan ulang dari stage 2 dengan
    `params_override: {door_leaf_width}`;
  - tombolnya selalu ada, seperti tombol sekarang: primary saat `needs_attention` atau `door_estimate`, tertiary
    selain itu;
  - kalau `scale_source` adalah `door_estimate`, tampilkan peringatannya.
- Teks UI dalam bahasa Indonesia.

## 7. Ukuran keberhasilan

Untuk Ancol p13, project baru dari PDF dengan halaman 13 dipilih lewat thumbnail:

- Pipeline jalan sampai review tanpa input skala. Skala berada dalam ±5% dari 30.7 mm/px (300 dpi), atau setara di
  dpi lain.
- `input/raster.png` tidak berisi foto, dan tidak ada kotak bekas bingkai foto yang terbaca sebagai dinding.
- `drawing_bbox` mencakup seluruh gedung (A, B, C) dan tidak mencakup title block, baik di 300 maupun 600 dpi.
- Kolom terdeteksi turun dari 231 ke sekitar 60 atau kurang.

Untuk Gatsu:

- `plan.jpeg` dan PDF Gatsu halaman 3 memakai skala dari dimensi grid (`scale_source` bukan `door_estimate`).
- Benchmark extraction Gatsu tidak turun.

Semua bug fix dan fitur punya test (TDD, AGENTS.md).

## 8. Yang diputuskan user

- User memilih sendiri halaman denah. Tidak ada deteksi otomatis.
- Satu denah = satu project. Hasil rekonstruksi tiap denah terpisah dan tidak digabung.
- Tanpa skala, skala diperkirakan dari pintu. Satu-satunya koreksi adalah kolom "lebar pintu standar", default 800 mm.
  Tidak ada kalibrasi dua titik.
- Lebar pintu yang diisi sengaja oleh user selalu menang atas dimensi grid dan `mm_per_px` tersimpan. Denah tanpa
  dimensi dengan kurang dari 3 pintu diterima sebagai batas.
- Pendekatan A. Uji pakai Ancol p13; Gatsu dianggap lolos MVP.
- Penutupan ruang Ancol menjadi fase debug terpisah, dikerjakan setelah ini.

## 9. Keputusan saya (bisa dikoreksi)

- **Thumbnail lewat endpoint stateless**, bukan pdf.js di browser (tidak menambah dependency web) dan bukan "project
  dibuat dulu lalu pilih halaman" (tidak mengubah model project). Harganya: PDF terkirim dua kali.
- **Batas 50% luas halaman** untuk membedakan foto tempelan dari PDF scan.
- **Parameter `mm_per_px` tetap ada di backend** (benchmark, prompt parser "skala X mm/px"), hanya hilang dari UI. Ini
  jalan keluar tersembunyi untuk denah tanpa dimensi dan tanpa pintu.
- **Mask tray di stage 3**, tempat skala sudah diketahui, sehingga sampel bisa diskalakan. Bukan di preprocess.
- **Thumbnail default memilih halaman 1**, karena user mungkin hanya punya PDF satu halaman.
- **Template tray prosedural**, bukan potongan gambar, supaya tidak ada gambar klien di git.
- **`scale_source` mendapat nilai `"door_estimate"`.** Literal di `core/spec/models.py` ditambah, lalu
  `python -m core.spec.export_schema` dan `npm run gen:types`.
- **Mask tray jalan di setiap denah, tanpa setting.** Regresi dijaga oleh benchmark Gatsu.

## 10. Diserahkan ke builder

- **Resolusi rasterisasi PDF (`PDF_DPI`).** Bandingkan p13 di 300 dan 600 dpi setelah pembersihan dan mask tray.
  Tetap di 300 kecuali 600 jelas lebih baik: dinding lebih tepat di dinding asli dan V004/V005 turun. 600 dpi membuat
  stage 3 sekitar 3–4 kali lebih lambat (36 dtk vs 11 dtk per run di spike).
- Aturan persis `drawing_bbox` (§6.3), selama perilaku yang dituntut terpenuhi.
- Cara mengurangi goresan lurus pada estimasi pintu, selama median busurnya stabil (spike: p25–p75 24.2–27.0 px).
- Komponen Carbon untuk grid thumbnail.
- Benchmark atau test regresi untuk p13. `floorplan/` tidak di-commit, jadi test yang butuh PDF Ancol di-skip kalau
  file tidak ada, mengikuti pola test Gatsu.
