# Desain: lapisan Instalasi — cable tray (tahap 1)

Tanggal: 2026-10-30 · Status: draf untuk disetujui user

## 1. Maksud dan alasan

Perusahaan user menjual dan memasang produk data center. Client memberi denah 2D (PDF atau gambar) dan detail umum.
Pipeline sekarang sudah menghasilkan layout 3D gedung (dinding, pintu, ruang, kolom, tangga) dengan review manusia.
Langkah berikutnya: **simulasi instalasi produk** di atas layout itu, supaya engineer bisa membayangkan penempatan
produk dan mengestimasi kebutuhannya, lalu menunjukkannya ke client.

Produk pertama: **cable tray**. Tray menjadi jalur untuk menarik kabel ke rack. Hasil yang dicari:
- **visual 3D yang realistis:** tray perforated, hanger, dan drop ke rack;
- **estimasi panjang tray** per kelas (data, power), termasuk drop.

Ini bukan BOM katalog: tray dimodelkan generik dan parametrik.

## 2. Tujuan, non-tujuan, anti-tujuan

**Tujuan (tahap 1)**
- Lapisan **Instalasi** yang terpisah dari layout dan **opsional**. Project tanpa instalasi bekerja persis seperti sekarang.
- Engineer menelusuri jalur tray yang **sudah tergambar di denah client**, dengan snap ke gambar.
- **Rack juga ditelusuri dari denah** dan masuk ke lapisan instalasi. Klik pada kotak rack di gambar, lalu ukuran dan
  orientasinya di-snap dan template yang cocok dipilih (§6.3b).
- Kelas tray: **data** (kecil, LAN/fiber) dan **power** (besar). Keduanya dibedakan oleh lebar dan warna di editor.
- Cara pasang per jalur: **overhead** (digantung dari plafon) atau **underfloor** (di bawah raised floor). Satu proyek bisa memakai keduanya.
- **Drop otomatis** ke rack terdekat dalam radius; panjang drop ikut dihitung.
- Hanger/penyangga, sleeve di dinding yang ditembus, dan material perforated yang realistis di Blender.
- Editor: layer tray bisa show/hide (data dan power terpisah). Tray **kosong secara default**.
- Laporan: panjang tray per kelas, daftar drop, rack yang belum terhubung.

**Non-tujuan (tahap 1)**
- Deteksi tray otomatis dari gambar. Data model dan alurnya disiapkan (`source: auto`, I1), tapi detektornya belum dibuat.
  Alasannya, baru satu denah (Gatsu) yang punya contoh tray, dan tiap konsultan menggambar tray berbeda.
- Kabel di dalam tray dan **animasi aliran kabel**. Ini tahap 2, opsional, hanya di editor; di GLB dan render kabel statis.
- Produk selain rack dan tray (UPS, PDU, CRAC) di lapisan instalasi. Mekanismenya sama dengan rack (objek template),
  jadi tinggal menambah template dan kategori.
- BOM katalog, SKU, dan harga. Juga perhitungan fill ratio kabel.
- Beberapa skenario instalasi per layout. Desain tidak menghalanginya (§5.1), tapi tidak dibuat sekarang.

**Anti-tujuan** (hal yang membuatnya gagal walau "jalan")
- Instalasi mengubah atau memperlambat alur layout: ekstraksi, review dinding, build layout.
- Tray terlihat melayang, menembus dinding tanpa sleeve, atau menembus rack.
- Jalur tray bergeser dari gambar client tanpa jejak alasan.

## 3. Batasan

- Mengikuti pola yang ada: dokumen berversi, op dengan alasan untuk perubahan geometri, validasi dry run, Regenerate ke Blender, publish ke `outputs/`.
- Satuan mm. Koordinat dan transform `px_to_mm` sama dengan spec layout.
- Blender 5.2 CLI headless (`builder/`). Builder hanya stdlib + bpy; data disiapkan oleh `core/build_prep`.
- Editor: React + three.js. Kanvas review 2D (SVG) dipakai ulang untuk anotasi.
- Copy UI dan dokumen berbahasa Indonesia; kode dan commit berbahasa Inggris.

## 4. Pendekatan yang dipertimbangkan

| | Pendekatan | Trade-off | Keputusan |
|---|---|---|---|
| A | Tray sebagai elemen baru di spec layout | Memakai ulang semua mekanisme spec, tapi instalasi tercampur dengan gedung. Proses otomatis nanti harus menulis ke spec layout. | ditolak |
| B | Tray sebagai rangkaian template objek (potongan lurus, elbow) | Memakai ulang sistem template, tapi jalur berbelok, panjang, dan drop jadi manual dan rapuh | ditolak |
| **C** | **Lapisan instalasi terpisah**, dokumen sendiri yang merujuk ke versi layout | Terpisah dan opsional; proses otomatis hanya menulis instalasi; siap untuk produk lain dan skenario. Biayanya: versi, op, dan validasi sendiri, serta sinkronisasi dengan layout. | **dipilih user** |

Alasan user memilih C: produk lain (rack, UPS, PDU, CRAC) kemungkinan akan masuk ke instalasi juga. Pemrosesan otomatis
nanti harus bisa bekerja hanya pada bagian instalasi, berdampingan dengan anotasi manual. Pemisahan ini mengikuti
praktik BIM: model arsitektur dan model peralatan disimpan terpisah, lalu disatukan saat ditampilkan.

Pertanyaan user "apakah opsi A akan overlap dengan garis dinding?": A atau C tidak mengubah hal ini. Dua jenis overlap
ditangani di §6.6.

## 5. Model data

### 5.1 Dokumen instalasi

`data/projects/<id>/installations/installation.v<N>.json` + `HEAD`. Strukturnya sama dengan `specs/` (SpecStore); setiap Save
menghasilkan versi baru.

```
Installation
  schema_version: "1.0"
  meta:
    version: int
    layout_version: int             # versi spec layout yang menjadi dasar
    ceiling_height: Mm | null       # null → defaults.wall_height (lihat §6.2)
    raised_floor_height: Mm | null  # null → tidak ada raised floor
    created_at, message, source     # source: editor | auto | migration
  cable_trays: [CableTray]
  objects: [PlacedObject]         # rack (dan produk lain nanti): bentuk sama dengan objects di spec layout
  provenance_log: [{op, id, by, reason}]
```

Field `scenario` sengaja tidak ada sekarang. Kalau dibutuhkan beberapa skenario, cukup ditambah satu field atau satu folder per skenario.

### 5.2 CableTray (yang disimpan hanya yang ditentukan manusia)

```
CableTray
  id: "T1", "T2", ...
  path: [Point, ...]            # polyline sumbu tray di denah, ≥ 2 titik, mm
  tray_class: "data" | "power"
  width: Mm                     # default data 200, power 400 (pilihan: 100/150/200/300/400/500/600)
  side_height: Mm               # default 100 (pilihan: 50/100/150)
  tray_type: "perforated"       # tahap 1 hanya perforated; ladder/wire_mesh/solid menyusul
  mounting: "overhead" | "underfloor"
  elevation: Mm | null          # sisi bawah tray dari lantai jadi; null → default dari mounting (§6.2)
  flow: "forward" | "reverse"   # arah aliran (tahap 2); default forward = dari path[0]
  provenance: {source: editor | auto, confidence, changed_in}
```

**Yang diturunkan, tidak disimpan** (dihitung ulang setiap validasi dan build): drop ke rack, hanger/penyangga, fitting di
belokan, sleeve di dinding, dan panjang. Dengan begitu, rack atau tray yang digeser tidak pernah meninggalkan drop basi.

### 5.3 Op (perubahan berversi)

`add_tray`, `set_tray` (kelas, lebar, tinggi sisi, mounting, elevasi, flow), `move_tray_path` (ganti path), `delete_tray`
(reason wajib), `set_installation_meta` (tinggi plafon, raised floor). Untuk objek: `add_object`, `update_object`, dan
`delete_object` dengan bentuk yang sama seperti op layout. Menggeser objek hasil telusur (`update_object` posisi/rotasi)
dan menghapusnya wajib alasan.

Tahap 1 sifatnya telusur dulu, koreksi opsional. Tetapi semua op geometri (`move_tray_path`, `delete_tray`) **wajib alasan**,
dan `add_tray` serta `move_tray_path` hanya bisa disimpan kalau lolos validasi error (§6.5).

## 6. Perilaku

### 6.1 Alur kerja

```
LAYOUT (tetap)  0 input → … → 5 validasi → [review] → 6 → 7 build → 8 verifikasi → 9 laporan → 10 publish
                                                                      │ layout vN punya output
INSTALASI (opsional, run kind "installation")                         ▼
  I0 dasar     gambar + px_to_mm dari layout vN, dinding/pintu/rack dari layout vN
  I1 deteksi   (belum dibuat) kandidat tray dari gambar → source: auto
  I2 anotasi   editor mode Instalasi: telusuri, atur, validasi, Save → installation vM
  I3 build     Blender: layout vN + instalasi vM → installation.glb + render gabungan
  I4 laporan   panjang per kelas, drop, rack terhubung/belum
  I5 publish   installation_outputs/v<M>/ (di luar outputs/v<N>, yang dihapus saat layout di-regenerate)
```

- **Pemicu:** tombol **"Mulai instalasi"** di halaman project, aktif setelah layout HEAD punya output. Tombol ini membuat
  installation v1 kosong dengan `layout_version = HEAD`, lalu membuka editor dalam mode Instalasi.
- **Editor:** toggle mode **Layout | Instalasi** di toolbar. Di mode Instalasi, layout terkunci (hanya tampil), dan Save
  menyimpan dokumen instalasi.
- **Build instalasi:** tombol Regenerate di mode Instalasi menjalankan run `installation` (I3–I5). Layout tidak dibangun ulang.
- **Layout berubah** (HEAD baru setelah instalasi dibuat): instalasi tetap merujuk ke versi lamanya. Halaman project
  menampilkan "Layout berubah (v20 → v22): cek instalasi". Tombol **"Rebase ke v22"** menjalankan validasi terhadap layout
  baru, lalu menyimpan versi instalasi baru dengan `layout_version` yang baru. Masalah yang muncul (tray menembus dinding
  baru, rack hilang) tampil di panel Masalah.
  **Rebase selalu menyimpan** (versi baru mencatat perubahan dasar layout), walaupun ada error. Error yang muncul dari
  rebase ditampilkan di panel Masalah dan **menahan Regenerate instalasi** sampai diperbaiki. Error bisa diperbaiki cukup
  dari sisi instalasi, misalnya elevasi, `ceiling_height`, atau path. Save biasa tetap ditolak kalau ada error.

### 6.2 Elevasi (sisi bawah tray, dari lantai jadi)

| Mounting | Default | Batas |
|---|---|---|
| overhead | `ceiling_height − 300 − side_height` (ruang akses 300 mm di atas tray) | ≥ tinggi rack tertinggi di radius + 300 mm; ≤ plafon − side_height |
| underfloor | `−raised_floor_height + 100` (100 mm di atas pelat, di bawah panel lantai) | sisi atas tray ≤ −50 (di bawah panel); butuh raised floor |

- **Lantai jadi** adalah z = 0 layout. Dengan raised floor, permukaan lantai yang diinjak berada di z = 0, dan pelat ada di z = −raised_floor_height.
- **Default `ceiling_height` = `defaults.wall_height`.** Dinding model naik sampai plafon. Dengan default 3000, sisi bawah
  tray overhead ada di 2600, cukup di atas rack 42U (±2200) + 300. Pada ketinggian itu tray **memotong** dinding, sehingga
  sleeve (§6.6) memang terjadi. Kalau plafon diisi lebih tinggi dari dinding (dinding partisi tidak sampai plafon), tray di atas
  dinding tidak memotongnya. I003 menguji tumpang tindih z dengan rentang tinggi dinding.
  Nilainya diisi lewat dialog "Mulai instalasi" atau panel properti instalasi. Prompt project baru juga dibaca: "tinggi plafon
  3.2 m", "raised floor 600 mm" (dua pola baru di parser tahap 0, ikut ke input instalasi).
- **Plafon dan raised floor digambar di output gabungan supaya tidak ada yang melayang:**
  - **Plafon:** pelat tipis di `ceiling_height`, tempat hanger berakhir. Di editor menjadi layer "Plafon" (default tersembunyi
    supaya isi ruang terlihat). Di render isometrik disembunyikan, di render potongan ditampilkan.
  - **Raised floor:** pelat struktur layout dipindah ke `−raised_floor_height` di output gabungan (`shell.glb` layout tidak
    berubah). Panel lantai 600×600 setebal 30 mm di z = 0 dengan material semi-transparan, plus pedestal di setiap sudut
    panel. Di editor menjadi layer "Raised floor" (bisa disembunyikan). Ada satu render tambahan "underfloor" dengan panel
    lantai disembunyikan.

### 6.3 Snap dan anotasi (I2)

- **Alat "Tray" (`T`)** di kanvas 2D mode Instalasi.
  - **Gambar:** klik berantai titik-titik jalur, Enter untuk selesai, Esc untuk batal.
  - **Atur jalur sebelum disimpan:** kelas, lebar, dan mounting diambil dari pilihan terakhir di panel. Saat menggambar, lebar sementara di-snap
    ke pita gambar.
- **Snap ke pita tray** (`POST /snap-tray`, mirip `/snap` Garis bantu). Untuk setiap segmen kasar, profil melintang mencari
  pasangan garis tepi yang sejajar, dan voting dari banyak sampel menentukan sumbu dan lebarnya. Arsir atau warna di dalam
  pita boleh ada (Gatsu: pita cokelat berarsir). Hasilnya sumbu yang lurus, dan lebar dibulatkan ke ukuran standar terdekat
  (§5.2). Kalau tidak ada pita, segmen dipakai seperti digambar, dengan pesan "tidak ada pita tray di dekat garis ini".
- **Alat "Rack" (`K`, §6.3b):** klik di dalam kotak rack yang tergambar di denah.
- **Tampilan 2D:** tray digambar sebagai layer sendiri: data biru, power oranye, semi-transparan, dengan lebar sebenarnya.
  Tidak tercampur dengan dinding.
- **Koreksi (opsional):** seret titik jalur, tambah atau hapus titik, ubah properti, atau hapus tray. Op geometri wajib alasan.

### 6.3b Telusur rack dari denah

- **Klik di dalam kotak rack** yang tergambar. `POST /snap-box` mencari persegi panjang tinta tertutup terkecil yang memuat
  titik klik (kontur pada `bin`), lalu mengembalikan pusat, ukuran (mm), dan rotasi (kelipatan 90° dari sumbu kotak).
- **Template dipilih otomatis** dari kategori `rack` dengan tapak paling cocok (selisih lebar dan dalam ≤ 100 mm, misalnya
  600×1200 → `rack-42u-600x1200`, 800×1200 → `rack-48u-800x1200`). Kalau tidak ada yang cocok, engineer memilih dari daftar;
  ukuran tapak tetap mengikuti gambar.
- **Hasil:** `add_object` dengan `provenance.source = editor`, `evidence.box` = kotak gambar. Deretan rack ditelusuri dengan
  klik berurutan; Shift-klik menyeret kotak seleksi untuk menelusuri semua kotak seukuran rack di dalamnya sekaligus.
- **Kalau tidak ada kotak** di titik klik: pesan "tidak ada kotak rack di sini". Rack masih bisa ditaruh manual dari library
  (ukuran template).
- **Objek di layout** (dari editor lama) tetap dibaca sebagai rack untuk drop, supaya project lama tidak rusak. Tombol
  "Pindahkan objek ke instalasi" memindahkannya sekali jalan (op `delete_object` di layout + `add_object` di instalasi,
  alasan "pindah ke instalasi").

### 6.4 Drop ke rack

- **Rack** adalah `objects` berkategori `rack` di dokumen instalasi, ditambah objek berkategori `rack` di layout vN (§6.3b).
- Sebuah rack **terhubung** kalau atap rack (overhead) atau dasarnya (underfloor) berada dalam **radius 1500 mm** dari sumbu tray (jarak
  horizontal ke segmen terdekat). Rack dalam radius beberapa tray terhubung ke tray **terdekat** untuk setiap kelas: satu drop
  data dan satu drop power per rack, kalau ada.
- **Bentuk drop:**
  - overhead: segmen horizontal pendek dari tray ke atas pusat rack (kalau rack tidak tepat di bawah tray), lalu waterfall
    vertikal sampai atap rack;
  - underfloor: segmen naik ke dasar rack (melalui cutout panel lantai).
- **Lebar drop:** sama dengan tray induknya, maksimal 300 mm.
- **Panjang drop:** horizontal + vertikal, ikut panjang kelasnya.
- **Rack tanpa sambungan:** muncul sebagai `info` di panel Masalah ("R12 tidak terhubung ke tray data/power").

### 6.5 Validasi instalasi (dry run, seperti layout)

| Kode | Tingkat | Aturan |
|---|---|---|
| I001 | error | path < 2 titik, segmen < 100 mm, atau titik berulang |
| I002 | error | elevasi di luar batas mounting (§6.2), atau underfloor tanpa raised floor |
| I003 | warning | tray menembus dinding → builder membuat sleeve (§6.6) |
| I004 | warning | jarak tray power–data < 300 mm (jarak terdekat 3D antar badan tray) |
| I005 | warning | tray overhead menabrak rack, kolom, atau tangga (kotak batas) |
| I006 | info | rack tidak terhubung ke tray kelas tertentu |
| I007 | warning | instalasi merujuk layout lama (layout HEAD lebih baru) |

Save ditolak kalau ada error. Warning dan info tidak menahan Save.

### 6.6 Overlap dengan dinding

1. **Di ekstraksi layout:** pita tray (dua garis sejajar) bisa terbaca sebagai dinding palsu. Tahap 1 tidak mengubah
   ekstraksi: dinding palsu dihapus saat review seperti sekarang. Nanti mask pita dari I1 bisa dipakai untuk menyaring
   deteksi dinding.
2. **Di 3D:** tray overhead yang melewati dinding dibuatkan **sleeve**: lubang di dinding seukuran tray + 50 mm di setiap
   sisi, di elevasi tray. Lubang dibuat dengan Boolean cutter yang sama dengan bukaan pintu, tapi dibatasi ke koleksi instalasi:
   `shell.glb` layout tidak berubah. Builder mengekspor dinding layout yang berlubang ini ke render gabungan dan `installation.glb`.
   Tray underfloor tidak menembus dinding (ada di bawah lantai).

### 6.7 Build (I3) dan realisme

- **`core/build_prep/installation.py`** menyiapkan mesh tray dari path:
  - penampang U (dasar + dua sisi, tebal pelat 1.5 mm) diekstrusi sepanjang segmen;
  - fitting siku 90°/45° di belokan (miter sederhana di tahap 1; elbow melengkung boleh menyusul);
  - drop, hanger, penyangga, dan cutter sleeve.
- **Hanger overhead:** setiap ≤ 1500 mm dan di setiap belokan. Terdiri dari dua batang ulir M10 dari plafon ke trapeze
  (profil C 41×41 selebar tray + 100 mm) di bawah tray.
- **Penyangga underfloor:** pedestal pendek ke pelat pada jarak yang sama.
- **Material:** logam galvanis (abu-abu terang, metallic 0.8, roughness 0.4). Dasar tray memakai **tekstur alpha perforasi**
  (slot 7×20 mm, jarak 25 mm) supaya terlihat tembus di render Workbench/EEVEE tanpa ribuan lubang mesh. Sisi tray juga
  berperforasi. Warna aksen tipis di tepi tray: data biru, power oranye, bisa dimatikan.
- **Output:**
  - `installation.glb`: hanya instalasi, dalam koordinat yang sama dengan `shell.glb`;
  - `layout_installation.glb`: gabungan;
  - render isometrik dan atas gabungan;
  - `installation_report.html/pdf`.
- **Verifikasi (I4):** cek glb 1:1 untuk tray (panjang tiap segmen ±1 mm terhadap path) dan ringkasan validasi.

### 6.8 Editor 3D

- **Layer baru di panel Layers:** "Tray data", "Tray power", "Hanger", "Drop". Semua show/hide; default tampil.
- Tray digambar di three.js dari mesh yang sama (dibuat di klien dari path, mengikuti logika `build_prep` yang disederhanakan,
  atau dari `installation.glb` terakhir plus pratinjau untuk ubahan yang belum disimpan, seperti dinding sekarang).
- **Tahap 2:** layer "Kabel" (bundel di dalam tray) dan tombol "Animasi aliran" (tekstur pulsa bergerak di sepanjang jalur
  dan drop, searah `flow`). Mati secara default.

### 6.9 Laporan (I4)

Ringkasan:
- panjang tray **data** dan **power**, masing-masing horizontal + drop + total;
- jumlah belokan, hanger, dan sleeve;
- tabel per tray (ID, kelas, lebar, mounting, elevasi, panjang);
- tabel per rack (drop data/power, panjang);
- daftar rack yang belum terhubung;
- render gabungan.

## 7. Yang diputuskan user (dari percakapan)

- Visualisasi 3D + estimasi panjang tray; bukan BOM katalog.
- Kelas data (kecil) dan power (besar), dibedakan oleh lebar.
- Jalur mengikuti gambar denah client. Koreksi engineer opsional, tapi harus lewat validasi dan disertai alasan.
- Mounting overhead atau underfloor, tergantung client; keduanya didukung.
- Drop otomatis ke rack terdekat kalau rack ada di sekitarnya.
- Tampil di editor (show/hide) dan di output Blender. Tray kosong secara default; kabel dan animasi aliran opsional.
- Lapisan instalasi terpisah (C), dan instalasi opsional. Produk lain kemungkinan akan masuk ke instalasi juga.
- Rack ditempatkan sesuai denah, sehingga rack masuk lapisan instalasi sejak tahap 1 (opsi b).

## 8. Keputusan saya (bisa dikoreksi)

- Default ukuran: data 200 mm, power 400 mm, tinggi sisi 100 mm. Radius drop 1500 mm. Jarak power–data ≥ 300 mm.
  Ruang akses 300 mm di atas tray overhead. Hanger setiap ≤ 1500 mm.
- `ceiling_height` default = `wall_height`. Output gabungan menambah pelat plafon (tempat hanger) dan, kalau ada raised floor, panel lantai + pedestal dengan pelat struktur dipindah ke bawah.
- Rebase selalu menyimpan; error hasil rebase menahan Regenerate instalasi, bukan Save.
- Output instalasi di `installation_outputs/v<M>/`, tidak di dalam `outputs/v<N>/`.
- Rack ditelusuri dari denah ke lapisan instalasi (keputusan user: penempatan rack sesuai denah). Objek layout lama tetap dibaca, dan bisa dipindah sekali klik.
- Sleeve hanya memengaruhi output gabungan; `shell.glb` layout tidak berubah.
- Tidak ada deteksi otomatis di tahap 1; slot datanya disiapkan.

## 9. Diserahkan ke builder

- Algoritma snap pita tray (pola profil, voting, ambang) mengikuti `core/extraction/snap.py`; algoritma snap kotak rack (kontur, toleransi).
- Bentuk persis fitting siku, profil trapeze, dan tekstur perforasi, dalam batas §6.7.
- Mesh tray di editor: dihitung di klien atau diambil dari glb, asalkan pratinjau ubahan yang belum disimpan tetap tampil.
- Penamaan endpoint, struktur folder output, dan pembagian milestone/task.
