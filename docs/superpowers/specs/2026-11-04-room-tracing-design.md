# Desain: ekstraksi ruang demi ruang dari vektor PDF

Tanggal: 2026-11-04 · Status: draf untuk disetujui user · Branch: `feat/room-tracing` (berbasis `feat/pdf-input`, belum di-merge)

## 1. Maksud dan alasan

User ingin reviewer hanya memperbaiki sekitar 20% sisa denah. Kenyataannya, pada Ancol p13 hampir semua dinding digambar
ulang. Pengukuran bagian bawah project "Ancol Lt. 2" (v1 otomatis dibanding v8 hasil review user):

- hanya 26 dari 123 dinding otomatis dipertahankan utuh; 97 dihapus, 132 digambar ulang;
- recall panjang dinding 63%, presisi 83%, toleransi 200 mm.

Penyebabnya, dari overlay v1 dan v8:

1. Dinding berada di posisi benar, tetapi terpotong-potong dan tidak tersambung, sehingga menggambar ulang lebih cepat.
2. Deretan rack dan sisa tray terbaca sebagai dinding.
3. Sekitar 37% panjang dinding tidak terdeteksi, kebanyakan sekat tipis.

Akar masalahnya ada di ekstraksi raster. Extractor dituning untuk Gatsu (dinding tebal, sekitar 13 mm/px). Ancol p13
adalah lembar Letter NTS pada sekitar 31 mm/px, sehingga sekat hanya 3–4 px dan semua garis setebal sama.

Uji throwaway pada vektor PDF (2026-11-04, bagian bawah p13, diukur terhadap v8):

| | Pipeline raster | Vektor, pasangan garis sejajar, panjang minimal 900 mm |
|---|---|---|
| Recall dinding | 63% | 81% |
| Presisi dinding | 83% | 79% |
| Ruang cocok (IoU ≥ 0.6, luas ≥ 3 m²) | tidak diukur | 2 dari 12 |

Temuan lain dari uji itu:

- Dinding yang dibentuk tajam dan lurus. Sumber dinding palsu terbesar adalah pasangan anak tangga tray, dan sebagian
  besar tersaring oleh syarat panjang.
- Tiga cara penutupan kasar untuk seluruh denah (closing global, perpanjangan ujung, busur pintu) tidak cukup. Ruang
  bocor lewat celah pintu, celah di sekitar kolom, dan sisi denah yang terpotong bingkai lembar.
- Busur di vektor PDF sudah pecah menjadi potongan sangat kecil (kurva median 64 mm), jadi tidak bisa dibaca sebagai
  satu busur. Detektor raster menemukan 38 busur pintu.
- PDF tidak punya layer CAD (hanya `Watermark`), dan tebal serta warna garis seragam. Dinding hanya bisa dikenali dari
  geometri.

## 2. Tujuan, non-tujuan, anti-tujuan

**Tujuan**

1. Untuk halaman PDF vektor, dinding dibaca dari vektor, bukan dari raster.
2. Ruang dibentuk satu per satu dan harus menutup secara logis. Dinding dan pintu tersambung, tidak dobel.
3. Ruang yang tidak bisa menutup tidak dipaksa. Ruang itu menjadi tugas review dengan lokasi dan sisi yang jelas.
4. Celah yang ambigu bisa dipilihkan oleh Strata dari daftar pilihan yang valid, kalau terbukti menaikkan angka.
5. Semua proses otomatis tetap prosedural dan deterministik, kecuali langkah Strata yang opsional.

**Non-tujuan**

- Fine-tuning, model ML untuk ekstraksi, atau mengganti model Strata.
- Mengirim gambar klien ke layanan cloud. Semua gambar tetap di server.
- Mengubah jalur raster untuk JPEG, PNG, dan PDF scan.
- Memperbaiki deteksi kolom dan tangga. Keduanya tetap dari kandidat raster.
- Multi-lantai, penyelarasan antar lembar, atau SOP untuk klien.
- Modal pemilih halaman dan lambatnya Garis Bantu. Keduanya pekerjaan terpisah yang masih antre.

**Anti-tujuan**

- Hasil Gatsu memburuk.
- Ruang "tertutup" karena dinding karangan yang tidak ada di gambar, kecuali dinding `sheet_cut` (§6.5a).
- Ambang yang hanya cocok untuk Ancol. Gatsu PDF halaman 3 menjadi denah kedua untuk mencegahnya.
- Strata mengeluarkan koordinat atau mengubah spec tanpa pilihan yang disusun sistem.

## 3. Batasan

- Unit mm, sumbu +X timur dan +Y utara. Koordinat PDF (pt) dipetakan ke mm lewat `px_to_mm` tahap 2, yaitu pt → px
  (`PDF_DPI / 72`) → mm. Skala bisa berasal dari estimasi pintu, jadi ambang dalam mm harus tahan galat sekitar ±10%.
- Keluaran harus berbentuk `elements` yang sama dengan `extract_candidate` (`core/extraction/geometry/candidate.py`).
  Format spec tidak berubah. Satu perubahan di tahap 4: kandidat vektor melewati `close_ends`, karena langkah itu bisa
  menutup celah yang sengaja tidak ditutup penelusur.
- Ruang dibentuk ulang dari dinding dan kolom oleh `rebuild_rooms`, juga setiap kali geometri diedit. Jadi poligon hasil
  penelusuran saja tidak cukup: **setiap penutup harus berupa elemen spec yang nyata**, yaitu dinding atau bukaan.
- `floorplan/` dan `data/` tidak di-commit. Test yang butuh PDF klien di-skip kalau file tidak ada (`tests/inputs.py`).
- Strata hanya aktif lewat `LLM_TASKS_ENABLED` dan gerbang di `benchmarks/DECISIONS.md`.

## 4. Pendekatan

| | Pendekatan | Untung | Rugi |
|---|---|---|---|
| **A** | Prosedural: vektor + ruang demi ruang | Presisi CAD, deterministik, bisa dijelaskan, tanpa data latih | Hanya untuk PDF vektor |
| B | Model open-source apa adanya (CubiCasa, 2dplan2strct) | Cepat dicoba, jalan di scan | Gaya gambar berbeda, keluaran kotak atau mask kasar, tetap butuh pasca-proses |
| C | Fine-tuning + pasca-proses prosedural | Paling umum | Butuh ratusan denah berlabel, pelatihan, pemeliharaan |

**User memilih A.** Strata tetap, tanpa perubahan model, dan fine-tuning tidak dibahas.

## 5. Alur

Tahap 3, hanya untuk PDF dengan halaman vektor (`sheet` dan jumlah path ≥ `VECTOR_MIN_PATHS`), menambah satu kandidat
vektor di samping kandidat raster:

1. **Baca:** path halaman menjadi segmen dalam mm, foto diabaikan.
2. **Gabung:** potongan segaris menjadi garis panjang.
3. **Dinding:** pasangan garis sejajar menjadi dinding.
4. **Saring:** tray, rack, dan perangkat dibuang.
5. **Graf:** ujung dinding disambungkan menjadi graf.
6. **Ruang:** ruang ditelusuri satu per satu, dinding diterima, celah ditutup dengan aturan.
7. **Sisa:** celah yang tidak terselesaikan dicatat.

Tahap 4 merakit kandidat seperti biasa. Tahap 5 memilih kandidat vektor kalau ada (§6.6). Ruang yang gagal muncul
sebagai tugas review.

## 6. Detail

Modul baru `core/extraction/vector/`.

### 6.1 Membaca dan menggabung segmen

- Ambil `l`, `re`, `qu` dari `page.get_drawings()`. Path di area `drawing_bbox` saja.
- Segmen horizontal dan vertikal digabung per garis: koordinat berbeda ≤ 12 mm, celah ≤ 40 mm. Nilai ini dari uji.
- Segmen miring ikut digabung per sudut. Spec punya `allow_skew`, dan dinding miring ada di p13.
- Potongan kecil yang membentuk kurva dirangkai menjadi polyline untuk §6.4.

### 6.2 Dinding dari pasangan garis

- Dua garis sejajar berjarak 70–420 mm, tumpang tindih ≥ 300 mm, dan tidak ada garis lain di antaranya, menjadi calon
  dinding. Garis tengahnya adalah sumbu dinding, jaraknya adalah tebal.
- Bidang gelap terisi dengan sisi pendek 70–420 mm menjadi calon dinding langsung (dinding hitam di p13).

### 6.3 Saringan

- Panjang minimal: uji 900 mm memberi presisi 79%, 600 mm memberi 71%. Dinding pendek tetap boleh ada kalau menyambung
  dua dinding lain, misalnya pipi pintu.
- Pola tangga: pasangan yang dilintasi garis pendek berjarak tetap adalah tray.
- Dinding yang berakhir sebagai garis di dalam ruang tertutup, tanpa menyambung ke batas ruang, adalah perangkat dan
  dibuang setelah §6.5.

### 6.4 Pintu

- Sumber utama: polyline kurva vektor yang difit ke lingkaran (`_fit_circle` di `doors.py`), dengan garis daun pintu
  dari pusat ke salah satu ujung (logika `_leaf_share`).
- Cadangan: busur dari detektor raster. Hasilnya digabung, busur yang berdekatan dianggap satu.
- Pintu menempel ke dinding terdekat dan menjadi `opening` seperti sekarang, jadi format spec tidak berubah.

### 6.5 Graf dan penelusuran ruang

- **Graf:** sumbu dinding menjadi graf planar. Ujung yang berdekatan disatukan. Ujung yang menggantung diperpanjang
  sepanjang sumbunya sampai dinding lain, dalam batas jangkauan.
- **Titik awal ruang:** label ruang dari OCR tahap 2, lalu area kosong besar yang belum menjadi ruang.
- **Urutan:** ruang yang paling jelas lebih dulu (batasnya paling banyak dinding yang sudah pasti).
- **Penelusuran:** dari titik awal, cari poligon tertutup terkecil yang memuat titik itu pada graf. Bila terbuka, coba
  penutup berurutan. Setiap penutup menjadi elemen spec, dan alasannya dicatat di `provenance.evidence` dinding:
  1. **Pintu terdeteksi:** dinding penyambung dengan `opening` berjenis pintu.
  2. **Celah segaris selebar pintu (≤ 1400 mm) tanpa busur:** ditutup otomatis sebagai dinding penyambung dengan
     `door_type: "opening"`, mengikuti pola `doors_from_gaps` yang sudah ada. Ruangnya menutup, dan bukaan ini yang
     nanti bisa dipilihkan ulang oleh Strata atau reviewer.
  3. **Kolom di antara dua ujung dinding:** ujung dinding diperpanjang sampai kolom.
  4. **Bingkai lembar (`sheet`):** lihat §6.5a.
- **Penerimaan:** ruang diterima kalau poligonnya tertutup, luasnya masuk akal (≥ 1 m²), dan tidak menimpa ruang yang
  sudah diterima. Dinding ruang yang diterima dikunci dan dipakai ulang oleh ruang tetangga, jadi tidak ada dinding dobel.
- **Gagal:** ruang tidak dipaksa. Tidak ada penutup yang ditambahkan, jadi ujung dinding tetap menggantung dan labelnya
  tetap tanpa ruang. Keadaan itu terbaca langsung dari spec (§6.7).

### 6.5b Revisi 2026-11-05: dari luar ke dalam

Uji pada Ancol menunjukkan penelusuran "poligon terkecil di sekitar label" memilih garis dalam (rel tray, outline PAC,
garis ubin) sebagai tepi ruang. User menyetujui urutan baru. Sebelum §6.5 berjalan, calon dinding disaring:

1. **Dinding kokoh dulu:** calon yang menempel pita tebal pada hasil render (garis tipis hilang setelah opening), atau
   pasangan garis panjang.
2. **Garis di dalam dianggap isi ruang.** Calon lain hanya menjadi sekat kalau bukan cincin sejajar dinding kokoh dan
   menempel dinding kokoh atau sekat yang sudah diterima. Garis tunggal harus menempel di kedua ujung.
3. **Saringan:** deretan garis sejajar berjarak tetap adalah ubin.
4. Ambang disetel terhadap Ancol dan Gatsu p4 bersama-sama.

Gerbang §7 tetap. Target ruang belum tercapai dan dilaporkan apa adanya.

### 6.5a Tepi potongan lembar

Ruang yang terbuka ke tepi denah yang terpotong bingkai lembar ditutup dengan dinding nyata di sepanjang tepi potongan
(keputusan user, 2026-11-04). Hasilnya sama dengan yang digambar user di v8: sekitar 33.7 m di `y` ≈ −71000, tempat 4
dari 12 ruang menutup. Dinding ini ditandai `sheet_cut` di `provenance.evidence`, supaya mudah dikenali dan dihapus.
Ini satu-satunya dinding yang tidak tergambar di denah, dan bukan pelanggaran anti-tujuan "dinding karangan". Syaratnya:
ruang itu benar-benar terbuka ke tepi potongan.

### 6.6 Pemilihan kandidat

Tahap 5 memilih kandidat vektor kalau memenuhi semua syarat berikut, dan skor sweep tidak dipakai untuk mengalahkannya:

- tidak ada error validator;
- minimal 3 ruang;
- jumlah ruangnya tidak kurang dari kandidat raster terbanyak.

Skor sekarang pernah memilih kandidat dengan 1 ruang di atas kandidat dengan 14 ruang. Kalau syarat tidak terpenuhi,
tahap 5 berjalan seperti sekarang, dengan peringatan bahwa jalur vektor tidak dipakai. Parameter
`extract_source: "raster"` memaksa jalur raster untuk perbandingan.

Kolom dan tangga diambil dari kandidat raster 0 (parameter default), karena kandidat terbaik baru diketahui di tahap 5,
sedangkan penelusur butuh kolom di tahap 3. Kandidat vektor dibuat setelah sweep selesai.

### 6.7 Tugas review

- `core/spec/review_tasks.py` mendapat satu jenis tugas baru, `room_open`. Tugas ini dihitung langsung dari spec, seperti
  tugas lain, jadi tidak perlu disimpan dan tidak basi setelah diedit: label ruang tanpa ruang, plus ujung dinding
  menggantung di dekatnya sebagai lokasi sisi yang terbuka.
- Web ikut berubah sedikit: `ReviewTask.kind` di `web/src/api/types.ts` dan pemetaan alat di `TasksPanel`.
- Alasan penutup disimpan di `provenance.evidence` dinding yang sudah ada, jadi tidak ada perubahan schema.

### 6.8 Strata untuk celah ambigu (fase terpisah, setelah §7 tercapai)

Arahnya sudah disepakati, detailnya menyusul setelah jumlah celah yang tersisa diketahui.

- Tugas LLM baru `T5`, prompt di `core/llm_review/prompts/T5/v1.md` (bahasa Inggris).
- Sasarannya bukaan dari penutup 2 di §6.5. Strata memilih salah satu: `door`, `continuous_wall`, `opening`, `unknown`.
- Masukan berupa crop yang sudah di-zoom dengan kotak kontras tinggi. Strata tidak pernah mengeluarkan koordinat.
- Nonaktif secara default, dan hasilnya tetap diterima atau ditolak manusia.
- Gerbang aktivasi, set uji berlabel, titik jalan sebelum jeda review, dan UI terima/tolak ditulis sebagai desain
  tersendiri saat fase ini dimulai. PRD/05 §7.2 baru mendefinisikan gerbang T1–T4.

### 6.9 Pengukuran

- `benchmarks/run_room_tracing_bench.py` menghitung semua angka §7 dan mencetak tabel per denah. Angka dinding memakai
  `wall_metrics(tol_mm=200)` dari `benchmarks/extraction_metrics.py`, supaya gerbang memakai fungsi yang sama dengan
  Gatsu.
- Kunci jawaban Ancol adalah salinan beku spec v8 di `benchmarks/ancol/gt_v8.json`, **git-ignored**, supaya editan user
  berikutnya tidak menggeser angka. Daerah uji adalah bagian bawah: `y` tengah dinding < −38848 mm.
- Gatsu PDF halaman 3 diukur terhadap `benchmarks/gatsu/gt_spec.json`.
- `benchmarks/correction_effort.py` dipakai untuk melaporkan perkiraan menit review sebelum dan sesudah.

## 7. Ukuran keberhasilan

Gerbang lulus, dan merge hanya setelah user menyetujui perbaikannya:

| Denah | Ukuran | Sekarang | Target |
|---|---|---|---|
| Ancol p13 bagian bawah | Recall panjang dinding (`wall_metrics`, 200 mm) | 60.8% | ≥ 85% |
| Ancol p13 bagian bawah | Presisi panjang dinding (`wall_metrics`, 200 mm) | 81.9% | ≥ 85% |
| Ancol p13 bagian bawah | Ruang cocok dengan review (IoU ≥ 0.6, luas ≥ 3 m²) | 2 dari 12 di uji | ≥ 9 dari 12 |
| Ancol p13 bagian bawah | Dinding dobel (segaris, jarak ≤ 100 mm, tumpang tindih > 300 mm) | belum diukur | 0 |
| Ancol p13 | Ruang gagal menutup muncul sebagai tugas review dengan sisi terbuka | tidak ada | semua |
| Gatsu `plan.jpeg` | `tests/extraction/test_gatsu_regression.py` | lolos | tetap lolos |
| Gatsu PDF hal. 3 | Metrik dinding terhadap GT | belum diukur | tidak di bawah lantai `FLOORS` |

Langkah Strata (§6.8) dinilai terpisah dan tidak menjadi syarat gerbang di atas.

## 8. Yang diputuskan user

- Pendekatan A. Strata tetap, tanpa perubahan model. Tidak ada gambar klien yang keluar dari server.
- Fine-tuning tidak dibahas.
- Ruang dikerjakan otomatis satu per satu, supaya setiap ruang terbentuk logis sebelum lanjut ke ruang berikutnya.
- Strata hanya memilih dari daftar pilihan untuk celah yang ambigu.
- Gerbang lulus §7. Branch `feat/room-tracing`, merge setelah perbaikan disetujui user.
- Sisi yang terpotong bingkai lembar ditutup dengan dinding `sheet_cut` (§6.5a), walaupun dinding itu tidak ada di gedung.

## 9. Keputusan saya (bisa dikoreksi)

- **Kandidat vektor menang atas skor sweep bila lolos syarat** (§6.6), karena skor sekarang tidak menghargai ruang yang
  terbentuk.
- **Kolom dan tangga dari kandidat raster 0**, supaya lingkup tetap kecil. Akibatnya kolom palsu dari kotak rack masih
  ada, dan kolom ikut membagi ruang.
- **Setiap penutup berupa dinding atau bukaan nyata, dan tidak ada perubahan schema** (§3, §6.5, §6.7).
- **Celah segaris ≤ 1400 mm tanpa busur ditutup otomatis sebagai bukaan**, supaya ruang menutup tanpa menunggu Strata.
- **`room_open` dihitung langsung dari spec**, jadi tidak ada data samping yang bisa basi.
- **`T5` menjadi fase terpisah** dengan desain sendiri, karena butuh gerbang, set uji, dan UI yang belum ada.
- **Baseline memakai `wall_metrics`**: 60.8% dan 81.9%, sedikit berbeda dari 63% dan 83% di §1 yang dihitung skrip uji.
- **Daerah uji Ancol hanya bagian bawah**, karena hanya bagian itu yang sudah direview. Bagian atas dilihat secara visual.
- **Kunci jawaban Ancol git-ignored**, karena berasal dari gambar klien, walaupun GT Gatsu ter-commit.
- **Gatsu PDF hal. 3 ikut diukur**, supaya ambang tidak hanya cocok untuk Ancol.
- **Strata dikerjakan paling akhir**, karena celah ambigu baru diketahui setelah penelusur ruang jalan.

## 10. Diserahkan ke builder

- Algoritma poligon tertutup terkecil (`shapely.polygonize` pada graf, atau penelusuran wajah graf), selama hasilnya
  memenuhi §6.5.
- Nilai ambang yang tidak disebut di sini, selama terukur pada Ancol dan Gatsu dan tercatat sebagai konstanta bernama.
- Cara mengenali kolom sebagai penutup celah, memakai kolom dari kandidat raster atau bentuk vektor.
- Pembagian file di `core/extraction/vector/`.
- Urutan kerja, dengan syarat §6.5 diukur paling awal, karena itu risiko terbesar.
