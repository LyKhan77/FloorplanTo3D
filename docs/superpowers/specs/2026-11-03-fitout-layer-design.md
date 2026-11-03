# Desain: satu lapisan perangkat (Layout = arsitektur, Instalasi & Interior = semua perangkat)

Tanggal: 2026-11-03 · Status: draf untuk disetujui user · Branch: `fitout-layer`

## 1. Maksud dan alasan

Sekarang perangkat tersimpan di dua dokumen yang tidak saling tahu:

| | Disimpan di | Ikut build 3D |
|---|---|---|
| Objek dari generate interior / Library (mode Layout) | spec layout (`objects`) | build layout saja |
| Rack dari alat Rack `K` (mode Instalasi) | dokumen instalasi (`objects`) | build instalasi saja (`core/installation/build.py:63` mengganti objek layout dengan objek instalasi) |

Akibatnya (dilaporkan user 2026-11-03):

- rack bisa dobel di ruang yang sama;
- drop tray hanya mengenal rack instalasi;
- editor layout tidak melihat tray;
- setiap Save layout, termasuk yang hanya menambah objek, membuat instalasi tertinggal dan perlu Rebase manual;
- build instalasi tidak menampilkan perangkat hasil generate interior.

User menilai alurnya ribet dan memilih **pendekatan A**: dua lapisan dengan tugas yang jelas.

## 2. Tujuan, non-tujuan, anti-tujuan

**Tujuan**

- **Layout = arsitektur saja:** dinding, bukaan, ruang, tangga, kolom. Mode Layout tidak lagi menempatkan perangkat.
- **Instalasi & Interior = semua perangkat:** rack, CRAC, UPS, panel, CCTV, tabung, meja, juga tray dan drop. Semuanya
  dalam dokumen instalasi yang sudah ada (berversi, terikat ke satu versi layout).
- **Satu editor perangkat** (mode "Instalasi & Interior"):
  - Library;
  - alat Rack `K` dan Tray `T`;
  - Perbaiki area `A` dengan generate interior (`fill_room`, `place_drawn`, kotak `K1…`).

  Semuanya menulis ke dokumen instalasi, dan drop tray langsung mengenal semua rack.
- **Perbaiki area di mode Layout** hanya untuk aksi arsitektur (dinding, bukaan, tangga, ruang).
- **Rebase otomatis:**
  - saat mode Instalasi dibuka tanpa perubahan tertunda, dan sebelum Build 3D, instalasi otomatis pindah ke layout
    terbaru;
  - masalah baru (misalnya tray menembus dinding baru) tampil sebagai pemberitahuan dan di panel Masalah;
  - tombol Rebase manual hanya tersisa untuk kasus ada perubahan tertunda.
- **Pemindahan sekali jalan:**
  - objek di spec layout lama dipindah otomatis ke dokumen instalasi (posisi, rotasi, dimensi, template sama; ID baru);
  - spec layout menjadi versi baru tanpa objek;
  - project tanpa dokumen instalasi mendapat dokumen baru dengan default (plafon = parameter project atau tinggi
    dinding).
- **Build:**
  - build 3D layout = arsitektur (tanpa perangkat);
  - Build 3D instalasi = arsitektur + semua perangkat + tray, satu tampilan lengkap.

**Non-tujuan**

- Menampilkan perangkat sebagai bayangan read-only di editor Layout (bisa menyusul).
- Mengubah skema dokumen instalasi atau aturan I001–I008.
- Mengubah mesin tata letak interior.

**Anti-tujuan**

- Ada dua sumber perangkat lagi.
- Pemindahan kehilangan objek atau mengubah posisinya.
- Rebase otomatis menimpa perubahan yang belum disimpan.

## 3. Batasan

- Dokumen instalasi sudah menyimpan objek generik:
  - op `add_object` / `update_object` / `delete_object` di `core/installation/ops.py` (template apa pun, ada
    `evidence`);
  - hapus wajib alasan.
- Rebase (`InstallationStore.rebase`) selalu menyimpan versi baru dan hanya memindahkan `layout_version`. Masalahnya
  diperbaiki di instalasi.
- Usulan asisten tetap berupa op yang masuk ke perubahan tertunda editor yang aktif (Terima = satu langkah undo, lalu
  Save).
- Spec layout tetap boleh memuat objek (skema tidak berubah). Setelah pemindahan, objek tidak lagi ditambahkan lewat UI
  Layout.

## 4. Pendekatan

| | Pendekatan | Keputusan |
|---|---|---|
| **A** | Layout arsitektur saja; semua perangkat di dokumen instalasi dengan satu editor; rebase otomatis | **dipilih user** |
| B | Perangkat tetap di layout, instalasi hanya tray yang merujuk rack layout | ditolak: tetap dua editor; alat Rack harus menulis lintas dokumen |
| C | Gabung instalasi ke spec layout | ditolak: perubahan terbesar, menghapus pemisahan berversi M12a |

## 5. Alur

1. User membuka mode "Instalasi & Interior".
   - Belum ada dokumen instalasi → dibuat otomatis dengan default (dialog "Mulai instalasi" tetap bisa dipakai untuk
     mengisi tinggi plafon/raised floor).
   - Ada objek di spec layout → dipindah sekali (§6.2).
   - Layout lebih baru dan tidak ada perubahan tertunda → rebase otomatis (§6.3).
2. Di mode ini user:
   - mengisi ruang (Perbaiki area `A`: "isi ruang ini", klik kotak `K1`);
   - menaruh dari Library;
   - menelusur rack `K` dan tray `T`.
3. Save → versi instalasi baru.
4. Build 3D → rebase otomatis bila perlu, lalu build lengkap.
5. Mode Layout: koreksi denah dan Perbaiki area untuk arsitektur. Save layout tidak lagi memaksa Rebase manual; mode
   Instalasi menyusul sendiri.

## 6. Detail

### 6.1 Asisten di dua mode

- **API:**
  - body `POST /assist/area` mendapat `layer: "layout" | "installation"`;
  - `layer = "installation"`:
    - `base_version` dan `ops` adalah milik dokumen instalasi;
    - spec kerja untuk konteks = layout versi terikat;
    - objek yang sudah ada = objek instalasi (+ op tertunda);
    - validasi usulan memakai dry-run instalasi (aturan I001–I007 + O001–O003).
- **Pembagian aksi:**
  - `layer = "layout"`: prompt dan penerjemah menolak `fill_room` / `place_drawn` ("isi ruang di mode Instalasi &
    Interior");
  - `layer = "installation"`: menolak aksi arsitektur ("ubah denah di mode Layout").
- **Web:** panel chat Perbaiki area dan alat `A` (termasuk kotak `K1…`) tersedia di editor instalasi. Terima menambah op
  ke store instalasi.

### 6.2 Pemindahan objek layout (sekali jalan)

- **Pemicu:** `POST /installations/start` atau pembukaan mode Instalasi pada project yang spec layout HEAD-nya memuat
  objek.
- **Server, dalam satu operasi:**
  1. dokumen instalasi mendapat `add_object` untuk tiap objek (template, versi, posisi, rotasi, dimensi, label;
     `evidence: {"moved_from": "<id layout>"}`);
  2. spec layout di-commit tanpa objek (`delete_object` dengan alasan "dipindah ke Instalasi & Interior");
  3. instalasi di-rebase ke versi layout baru itu.
- **Idempoten:** spec tanpa objek tidak memicu apa pun.
- Chat/notifikasi: "N objek dipindah ke Instalasi & Interior".

### 6.3 Rebase otomatis

- **Kapan:** saat editor instalasi memuat HEAD dan `layout_changed`, tanpa op tertunda; juga di `POST
  /installations/build`. Rebase dijalankan dulu, lalu validasi.
- **Bila ada op tertunda:** banner Rebase manual yang sekarang (Save dulu).
- **Hasil:** masalah baru tampil di panel Masalah dan sebagai notifikasi singkat ("instalasi dipindah ke layout vN: 2
  masalah").

### 6.4 Build

- **Build layout:** objek spec tidak lagi ikut, karena setelah pemindahan memang kosong. Kode tidak perlu berubah selain
  memastikan tidak ada yang menambahkannya.
- **Build instalasi:** sudah memakai objek instalasi. Kini itu semua perangkat.

### 6.5 Web

- **Mode Layout:**
  - panel Library dipindah ke mode Instalasi & Interior;
  - Perbaiki area hanya arsitektur;
  - editor 3D layout tetap ada untuk melihat arsitektur.
- **Mode Instalasi & Interior:**
  - toggle berganti nama;
  - Library di panel kiri;
  - alat `A` dan chat di panel kanan saat aktif.
- **Edit perangkat di kanvas 2D (keputusan user: opsi 1):**
  - kartu Library di-drop ke kanvas instalasi;
  - pilih perangkat dengan klik, geser dengan seret, putar 90° dengan `R`;
  - posisi (x, y, z), rotasi, dan ukuran diisi angka di panel Properti;
  - viewer 3D tetap untuk melihat hasil build. Editor 3D interaktif ditunda.
- `InstallationBanner` di halaman project memakai rebase otomatis yang sama.

## 7. Ukuran keberhasilan

- Project lama dengan objek layout dan instalasi: setelah membuka mode Instalasi, semua objek ada di instalasi dengan
  posisi sama, spec layout kosong objek, dan satu build menampilkan semuanya.
- Save layout (ubah dinding) lalu buka mode Instalasi: tanpa tombol Rebase; masalah baru tampil.
- "Isi ruang ini" di mode Instalasi: usulan masuk ke op instalasi, dan drop tray ke rack baru muncul.
- Perbaiki area di mode Layout: menolak "isi ruang" dengan pesan yang mengarahkan.

## 8. Yang diputuskan user

- Pendekatan A (2026-11-03).
- `generate-interior` di-merge dulu (`db681ed`), A dikerjakan di branch baru.
- Edit perangkat di kanvas 2D (drop, seret, putar, angka di Properti), bukan editor 3D (opsi 1).

## 9. Keputusan saya (bisa dikoreksi)

- Pemindahan objek layout otomatis dan sekali jalan, bukan tombol. Bisa di-undo lewat riwayat versi kedua dokumen.
- Dokumen instalasi dibuat otomatis dengan default bila belum ada. Dialog tinggi plafon tetap bisa diisi kemudian lewat
  meta instalasi.
- Rebase otomatis hanya tanpa op tertunda.
- Nama mode: "Instalasi & Interior".
- Bayangan perangkat di editor Layout ditunda.

- **Build dan rebase:**
  - Build 3D instalasi tetap tidak bisa diklik selama ada perubahan tertunda (seperti sekarang);
  - rebase otomatis sebelum build tidak pernah memblokir;
  - build ditolak hanya bila instalasi punya error (perilaku `installation_invalid` yang ada);
  - jalan pintas "tetap build di layout lama" dihapus, karena rebase otomatis membuatnya tidak perlu.
- **Laporan dan build instalasi:**
  - laporan instalasi mendapat jadwal perangkat (jumlah per template dan kategori), menggantikan daftar perangkat di
    laporan layout yang kini kosong;
  - di build, objek non-rack masuk collection "Equipment" dengan nama `obj_<id>`;
  - rack tetap di "Racks".
- **Rack dobel saat pemindahan:**
  - objek layout yang tumpang tindih dengan objek instalasi sekategori (IoU footprint ≥ 0,8) tidak dipindah dan
    disebut di notifikasi ("RK3 sudah ada di instalasi");
  - sisanya dipindah.

  Tidak ada objek yang hilang tanpa disebut.
- **Kapan mode tersedia:**
  - mode Instalasi & Interior bisa dibuka begitu ada spec layout, tanpa menunggu output 3D;
  - pemindahan objek layout tidak dijalankan selama run menunggu review (`needs_review`), karena ia meng-commit spec
    layout. Pemindahan dijalankan setelah review disetujui atau dibatalkan.
- **Riwayat versi:** pemindahan melewati objek yang `evidence.moved_from`-nya sudah ada di instalasi. Memulihkan versi
  layout lama tidak menggandakan perangkat.
- **Pemeriksaan perangkat di instalasi:** dua warning baru, tanpa mengubah I001–I008, ikut di dry-run, Save, dan rebase:
  - I009: perangkat di luar ruang atau menabrak dinding/kolom (setara V016/V017);
  - I010: perangkat tumpang tindih (setara O001).

## 10. Diserahkan ke builder

- Letak tombol, urutan panel, dan teks notifikasi dalam pola Carbon yang ada.
- Cara berbagi kode chat Perbaiki area antara dua editor (komponen sama dengan prop `layer`).
