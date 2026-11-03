# Desain: generate interior (isi ruang dengan perangkat data center)

Tanggal: 2026-11-03 · Status: draf untuk disetujui user · Branch: `generate-interior` (di atas `lowpoly-assets`)

## 1. Maksud dan alasan

Tujuan produk adalah mensimulasikan pemasangan perangkat data center perusahaan untuk klien. Sekarang objek diletakkan
satu per satu dari Library, sehingga mengisi data hall dengan puluhan rack lambat dan mudah melanggar clearance.

Fitur ini: user menandai ruang, Strata **bertanya dulu** perangkat apa dan berapa, lalu sistem menempatkannya
**secara logis menurut aturan teknis**. User melihat pratinjau, lalu Terima/Tolak/revisi seperti Perbaiki area.

**Spike 2026-11-03** (Battery Room Gatsu: deteksi kotak, klasifikasi ukuran, lalu Strata pada crop bernomor):
- teks di kabinet terbaca sebagian ("PANEL 3", "UPS … 200kVA");
- area kosong yang dibatasi garis dianggap perangkat, potongan arsiran dianggap battery rack (bias tipe ruang), dan
  unit AC dinding dianggap panel;
- akurasinya sekitar sepertiga.

Kesimpulan (keputusan user): v1 tidak menebak perangkat tergambar secara otomatis.

## 2. Tujuan, non-tujuan, anti-tujuan

**Tujuan (v1)**
- **Ruang kosong → mesin tata letak deterministik** dengan default TIA-942/ASHRAE (§6.2), dikalibrasi lewat satu file
  profil.
- **Perangkat tergambar → ditunjuk user:**
  - user mengklik kotak di gambar (snap kotak yang sama dengan alat Rack, termasuk kotak gelap/berarsir) dan menyebut
    isinya ("ini UPS", "baris ini rack 42U");
  - posisi dan ukuran diambil dari gambar, Strata memetakan ucapan ke template.
- **Strata bertanya dulu** perangkat apa dan berapa, dengan usulan default per tipe ruang (§6.1). Strata hanya memilih
  template dan jumlah, tidak pernah koordinat.
- **Pratinjau 2D** footprint objek, arah depan, dan zona clearance. Hasil dari aturan ditandai kuning, dari gambar hijau.
- **Validasi objek:** tumpang tindih, clearance terlanggar, menghalangi pintu, di luar ruang.
- **Kapasitas:** bila target tidak muat, chat menyebut kapasitas maksimal.
- Library: 16 template low-poly (branch `lowpoly-assets`). Perangkat dinding (panel FM-200, CCTV, reader) ditempatkan
  dengan Z.

**Non-tujuan (v1)**
- Deteksi otomatis semua perangkat tergambar beserta labelnya (v2, setelah denah data center nyata dari PM).
- Furnitur ruang non-teknis (kantor, meeting, pantry).
- Optimasi termal (CFD) dan perhitungan beban daya/pendinginan selain rasio sederhana.
- Jalur tray otomatis (lapisan instalasi tetap manual).

**Anti-tujuan**
- Objek menembus dinding, kolom, atau ruang lain; menutup pintu atau jalur evakuasi.
- Strata mengarang posisi.
- Penempatan tanpa review.

## 3. Batasan

- Sama dengan Perbaiki area:
  - Strata lewat `ask_json`, sesi dan SSE di `core/assist` dan `server/routes/assist.py`;
  - Terima menjadi op `add_object` di pending ops (satu undo), lalu Save seperti biasa.
- Objek: `PlacedObject {template_id, template_version, position [x, y, z], rotation (derajat), dims}`. Depan template =
  +y pada rotation 0 (`PRD/10-template-contract.md`).
- Template diambil dari registry (versi terbaru yang valid). Clearance dari `template.json` (rack: depan 1200, belakang
  1000).
- Validasi template membatasi aset ≤ 8 material.
- UI berbahasa Indonesia; prompt sistem berbahasa Inggris.

## 4. Pendekatan

| | Pendekatan | Trade-off | Keputusan |
|---|---|---|---|
| A | **Strata memilih isi, mesin aturan menempatkan** | Posisi selalu sah dan bisa dijelaskan; aturan harus ditulis | **dipilih** |
| B | Strata memberi koordinat tiap objek | Cepat dibuat, tetapi spike Perbaiki area dan interior menunjukkan koordinat LLM tidak bisa dipercaya | ditolak |
| C | Deteksi otomatis semua perangkat tergambar | Akurasi spike sekitar sepertiga; belum ada data kalibrasi | ditunda ke v2 (keputusan user) |

## 5. Alur

1. User memakai alat `A` (Perbaiki area) dan menandai ruang, atau mengklik kotak perangkat di gambar. Klik di dalam
   kotak gambar menambah "kotak tergambar" bernomor (K1, K2, …) ke konteks; tarik kotak tetap menandai area.
2. User menulis instruksi, misalnya "isi ruang ini" atau "K1–K3 itu UPS, K4 battery rack".
3. Strata:
   - instruksi isi tanpa rincian → **bertanya** dengan usulan default sesuai tipe ruang (§6.1): "Data hall 8 × 12 m:
     usul 2 baris rack 42U dengan cold-aisle containment, 2 CRAC, 2 PDU, CCTV, reader. Berapa rack? Pakai containment?
     CRAC atau in-row cooler?";
   - jawaban user → rencana `fill_room` (§6.3);
   - kotak tergambar → rencana `place_drawn` (§6.3).
4. Mesin tata letak (§6.2) atau penempatan dari gambar (§6.4) menghasilkan op `add_object`, lalu divalidasi (§6.5). Ada
   satu putaran revisi bila ada error validasi atau template tidak dikenal. Target yang tidak muat bukan error: kapasitas
   maksimal langsung ditempatkan dan disebut di chat.
5. Pratinjau di kanvas dan ringkasan di chat: jumlah per template, kapasitas, catatan pelanggaran.
6. Terima / Tolak / balas untuk revisi (sama dengan Perbaiki area).

## 6. Detail

### 6.1 Isi default per tipe ruang (usulan Strata saat bertanya)

| Tipe ruang | Isi default |
|---|---|
| `data_hall` | baris rack 42U berpasangan (cold aisle di tengah), containment atap + pintu, pendingin (CRAC di dinding ujung hot aisle; atau in-row cooler 1 per 4 rack), 1 PDU per baris, CCTV di sudut, reader di pintu, panel FM-200 di dekat pintu, tabung pemadam |
| `ups_room` | UPS + ATS + MDB berjajar di satu dinding, tabung pemadam |
| `battery_room` | baris battery rack, tabung pemadam |
| `electrical_room` | MDB, ATS, tabung pemadam |
| `mdf` | rack jaringan 2 tiang, tabung pemadam |
| lainnya | Strata bertanya; tidak ada default |

### 6.2 Mesin tata letak (ruang kosong)

**Masukan:**
- poligon ruang (spec kerja) dikurangi kolom dan dinding;
- zona pintu: busur daun pintu + jalur 1200 mm ke dalam ruang;
- objek yang sudah ada di ruang (dihindari);
- template dan jumlah dari rencana;
- profil aturan.

**Profil** `core/interior/rules.yaml`. Semua nilai bisa dikalibrasi tanpa mengubah kode:

| Kunci | Default | Sumber |
|---|---|---|
| `cold_aisle_mm` | 1200 | TIA-942 (2 ubin) |
| `hot_aisle_mm` | 1000 | TIA-942 / ASHRAE |
| `grid_mm` | 600 | ubin raised floor |
| `row_end_clear_mm` | 1200 | jalur servis/evakuasi |
| `wall_clear_mm` | 1000 | ruang kerja (front/back clearance template berlaku bila lebih besar) |
| `max_row_len` | 12 rack | lorong silang setelahnya |
| `door_clear_mm` | 1200 | jalur masuk |
| `inrow_per_racks` | 4 | rasio pendinginan |
| `pdu_per_row` | 1 | ujung baris |
| `electrical_front_mm` | 1000 | NEC 110.26 (ruang kerja panel) |
| `fm200_z_mm`, `reader_z_mm` | 1400, 1100 | tinggi pasang |
| `cctv_below_ceiling_mm` | 300 | plafon = `ceiling_height` instalasi, atau tinggi dinding |

**Algoritme data hall:**
1. Coba orientasi baris 0° dan 90° (sejajar sisi panjang/pendek bounding box ruang). Untuk tiap orientasi, coba offset
   grid 600 mm dalam satu modul (pasangan baris + lorong).
2. Isi pasangan baris berhadapan: rack depan menghadap cold aisle. Potong baris di zona pintu, kolom, dan
   `row_end_clear_mm` dari dinding. Pecah baris yang lebih dari `max_row_len` dengan lorong silang.
3. Pilih susunan dengan rack terbanyak. Bila seri, pilih yang lebih dekat ke target, lalu yang barisnya lebih panjang.
   Bila target user lebih kecil dari kapasitas, isi dari baris terdekat ke pintu dan sisakan sisanya kosong. Bila
   target lebih besar, tempatkan kapasitas maksimal dan sebut di chat.
4. Pendingin:
   - CRAC di dinding yang tegak lurus hot aisle, menghadap lorong;
   - atau in-row cooler disisipkan setiap `inrow_per_racks` rack, menggantikan posisi rack.
5. PDU di ujung tiap baris (sisi pintu).
6. Containment: modul atap 600 mm sepanjang cold aisle di atas rack (Z = tinggi rack), pintu di kedua ujung.
7. Perangkat dinding:
   - panel FM-200 di dinding samping pintu utama, Z 1400;
   - reader di sisi kunci pintu, Z 1100;
   - CCTV di sudut berlawanan menghadap lorong, Z plafon − 300;
   - tabung pemadam di sudut bebas.

**Algoritme ruang listrik/UPS/baterai:**
1. Line-up di dinding terpanjang yang tidak berpintu, menghadap ke dalam dengan ruang kerja depan
   `electrical_front_mm`.
2. Battery rack berbaris dengan lorong `wall_clear_mm`.

**Keluaran:** daftar penempatan, zona clearance (poligon) untuk pratinjau, kapasitas, dan catatan.

### 6.3 Rencana Strata (perluasan skema Perbaiki area)

```
{"type": "fill_room", "room": "R5" | null, "layout": "rows" | "lineup" | null,
 "items": [{"template": "rack-42u-600x1200", "count": 20 | null}, ...],
 "options": {"containment": true, "cooling": "crac" | "inrow" | null, "rows": "auto" | "ns" | "ew"}}
{"type": "place_drawn", "boxes": ["K1", "K2"], "template": "ups-cabinet-generic"}
```

- `count: null` berarti sebanyak yang muat (rack) atau default aturan (perangkat lain).
- `layout` memilih algoritme. Bila `null`, disimpulkan dari kategori template:
  - ada `rack`, `network`, atau in-row cooler → `rows` (algoritme data hall; MDF dengan rack jaringan = satu baris);
  - hanya `power` dan/atau `battery` → `lineup` (algoritme ruang listrik; battery rack tetap berbaris).

  Tipe ruang tidak diubah; R. MEETING Gatsu bisa dipakai sebagai ruang uji tanpa `set_room_type`.
- Template harus ada di daftar library yang dikirim di konteks. Yang tidak dikenal masuk putaran revisi.
- Prompt: untuk "isi ruang" tanpa rincian, Strata **wajib bertanya** dengan usulan §6.1.

### 6.4 Kotak tergambar (ditunjuk user)

- Klik di alat `A` pada kotak gambar: snap kotak yang ada (`core/installation/snap.snap_box`, kotak bergaris dan
  gelap/berarsir). Hasilnya kotak `Kn` dengan pusat, ukuran, dan rotasi 0/90, ditandai di kanvas.
- Kalau snap tidak menemukan kotak, Shift-tarik memakai `fit_box`, sama seperti rack manual di mode Instalasi.
- `place_drawn`: kotak seukuran satu template menjadi satu objek. Kotak yang jauh lebih panjang dari template (≥ 1,5×
  lebar template di sisi panjangnya) dianggap **satu baris**: dipecah menjadi `round(panjang / lebar template)` objek
  berjajar. Untuk jalur ini batas ukuran snap dinaikkan (sisi panjang sampai 20 m); batas 300–3000 mm alat Rack tidak
  berubah.
  - Template diskalakan ke ukuran kotak bila template itu `resizable`; kalau tidak, ukuran asli template dipakai di
    pusat kotak, dengan catatan bila beda > 15%.
  - Arah depan: sisi kotak yang menghadap ruang terbuka terlebar (lorong). Bila ambigu, Strata bertanya atau user
    menyebut ("depannya ke utara").

### 6.5 Validasi objek (aturan baru, khusus usulan interior)

Aturan O001–O003 dijalankan oleh pemeriksaan usulan di `core/interior`, bukan oleh `validate()` global. Proyek lama
dengan objek manual yang tumpang tindih tidak berubah statusnya, dan skor validator tidak berubah.

- **O001 tumpang tindih** (error): footprint objek saling memotong (atap containment di atas rack dikecualikan, karena Z
  berbeda).
- **O002 clearance** (warning): zona depan/belakang template memotong objek lain atau dinding.
- **O003 pintu** (warning): footprint memotong zona pintu.
- V016 (di luar ruang) dan V017 (menabrak dinding/kolom) yang sudah ada tetap berlaku.
- Error baru memicu revisi seperti Perbaiki area. Warning tampil di ringkasan.

### 6.6 Web

- Pratinjau `ProposalLayer`:
  - footprint objek (kuning dari aturan, hijau dari kotak gambar);
  - panah arah depan;
  - zona clearance arsir tipis;
  - label template singkat.
- Objek yang sudah diterima tampil di kanvas review 2D (footprint abu-abu). Sebelumnya objek hanya terlihat di 3D.
- Kotak tergambar `Kn` tampil bernomor selama sesi.

## 7. Ukuran keberhasilan

- Tes mesin tata letak pada ruang sintetis:
  - data hall 10 × 8 m dengan satu pintu menghasilkan baris berpasangan;
  - lorong 1200/1000 mm;
  - tidak ada O001/O003;
  - kapasitas sesuai hitungan tangan.
- Tes pada ruang Gatsu: R. MEETING sebagai "data hall" uji, dan Battery Room via `place_drawn` untuk kotak "PANEL 3"
  dan "UPS".
- Tes Strata langsung:
  - "isi ruang ini" → bertanya dengan usulan;
  - jawaban jumlah → usulan valid;
  - "K1 itu UPS" → `place_drawn`.

## 8. Yang diputuskan user

- v1: ruang kosong otomatis; perangkat tergambar ditunjuk user. Deteksi otomatis ditunda ke v2.
- Default aturan TIA-942/ASHRAE, dikalibrasi kemudian.
- Kotak yang tidak cocok dengan template dilewati.
- Hanya perangkat data center dari library; furnitur non-teknis tidak.
- Aset: low-poly prosedural (16 template), perangkat dinding memakai Z.
- Strata bertanya dulu soal isi sebelum menempatkan (ide awal user).

## 9. Keputusan saya (bisa dikoreksi)

- Fitur ini bagian dari alat `A` (chat yang sama), bukan alat baru. Ini menghemat UI dan memakai ulang revisi/undo.
- Klik di dalam kotak gambar saat alat `A` aktif membuat `Kn`, sedangkan tarik membuat area.
- Ubin raised floor 600 mm sebagai grid walau ruang tanpa raised floor (rapi dan standar).
- In-row cooler menggantikan posisi rack di baris (bukan menambah panjang baris).
- Profil aturan berupa YAML di repo. Kalibrasi per klien nanti cukup dengan file profil lain.
- Perangkat dinding (panel FM-200, CCTV, reader) didaftar di profil (`wall_mounted: [...]`), bukan di kontrak template.
  Footprint-nya diletakkan menempel ke muka dinding tanpa masuk ke dinding, jadi V017 tidak terpicu; O001 membandingkan
  rentang Z.

## 10. Diserahkan ke builder

- Representasi zona clearance dan cara memotong baris di zona pintu/kolom.
- Detail skor pemilihan susunan bila seri.
- Gaya visual pratinjau dalam pola Carbon yang ada.
