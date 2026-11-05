# Gabung ruangan di editor review

Tanggal: 2026-11-05. Branch: `feat/room-tracing`. Status: disetujui.

## Tujuan

Sekat toilet membuat banyak ruangan kecil yang terpisah, padahal semuanya satu ruangan. Reviewer perlu memilih
ruangan-ruangan itu dan menjadikannya satu ruangan: satu nama, satu luas, satu baris di report. Sekat tetap ada di 3D.

Bukan tujuan: menghapus dinding, mengubah deteksi sekat di pipeline, atau menggabungkan ruangan yang tidak bersebelahan.

## Pendekatan

Pilihan user: B, merge sungguhan.

- A. Nama massal. Kecil, tetapi tetap N ruangan dan N baris di report. Tidak dipilih.
- B. Merge lewat dinding. Dinding di antara ruangan ditandai tidak membagi ruangan. Dipilih.
- Grup di level ruangan dibuang, karena ruangan dibentuk ulang setiap kali dinding diedit.

## Cara kerja

Ruangan dibentuk dari dinding oleh `form_rooms`. Dinding `low` sudah tidak membagi ruangan, tetapi nama itu berarti
dinding rendah, jadi penanda baru dipakai.

1. Field baru `Wall.divides_room: bool = True`. `form_rooms` melewati dinding bernilai `false` saat membentuk `dividers`.
   Dinding tetap ada di outline, build 3D, dan report.
2. Op baru `set_wall_divides {id, divides}`, masuk `GEOMETRY_OPS`, sehingga ruangan dibentuk ulang.
3. Route baru `merge-plan` menerima versi dasar, ops yang belum disimpan, dan id ruangan, seperti dry run validate.
   Route mengembalikan daftar ops, lalu editor menerapkannya lewat `applyMany`. Satu undo membatalkan semuanya.

### Dinding yang hanya sebagian dipakai bersama

Satu dinding panjang bisa membatasi ruangan yang dipilih sekaligus ruangan lain. Menandai seluruh dinding akan ikut
membuka ruangan lain. Karena itu plan memotong dinding dengan `split_wall` di kedua ujung bagian bersama, lalu hanya
menandai potongan itu. `split_wall` menolak potongan yang mengenai bukaan, dan plan melaporkan hal itu.

### Pemeriksaan sebelum plan dikembalikan

Plan dijalankan pada salinan spec. Plan ditolak dengan pesan yang jelas jika:

- ruangan terpilih tidak menjadi satu ruangan, misalnya tidak berbagi dinding atau terhalang kolom;
- ruangan lain ikut berubah;
- potongan dinding mengenai bukaan.

### Nama dan tipe

Plan menambahkan `rename_room_at` dan `set_room_type_at` di titik label ruangan pertama. Nama hasil merge adalah nama
pertama yang terisi menurut urutan seleksi, tipe mengikuti ruangan yang sama. Keduanya bisa diedit setelah merge.

## UI

- Shift+Click ruangan sudah berjalan. `RoomsBulk` di Properties mendapat tombol "Gabung ruangan".
- Blok V kini juga mengambil ruangan yang seluruhnya berada di dalam blok. Properties menampilkan aksi dinding dan aksi
  ruangan berdampingan bila keduanya terpilih, agar aksi massal dinding yang ada tidak hilang.
- Ruangan yang punya dinding `divides_room: false` di dalamnya mendapat tombol "Pisahkan ruangan". Tombol ini mengembalikan
  semua dinding itu ke `true`.
- Penolakan plan tampil sebagai notice editor.
- Sekat dalam ruangan hasil merge digambar lebih redup di kanvas 2D, agar terlihat tidak membagi ruangan.

## Keputusan builder

- Potongan dinding hasil `split_wall` tidak disambung lagi saat "Pisahkan ruangan". Dinding tetap benar, hanya idnya lebih
  banyak.
- Spec lama tetap terbaca karena default field `true`. Schema dan tipe web dibuat ulang (`core.spec.export_schema`,
  `npm run gen:types`).
- Hasil ekstraksi ulang lewat `carry_over` belum wajib membawa penanda ini. Merge diulang bila dinding diekstraksi ulang.

## Pengujian

- `form_rooms`: dinding `divides_room: false` menyatukan dua ruangan, dan dinding tetap ada.
- Plan: dua ruangan berbagi dinding penuh; dinding panjang yang juga membatasi ruangan ketiga; ruangan tidak bersebelahan
  ditolak; potongan mengenai pintu ditolak.
- Web: tombol Gabung muncul untuk dua ruangan atau lebih, Pisahkan untuk ruangan hasil merge, blok V mengambil ruangan.
- Reducer web dan server sama untuk `set_wall_divides`.
