# 07 — Web Editor (Room Tour + Layout Editor)

Editor adalah tab **Editor** di aplikasi dashboard (`08-dashboard.md`). Teknologinya React + react-three-fiber + drei, dengan tema Carbon g100.

## 1. Data yang Dimuat

| Sumber | Endpoint | Kegunaan |
|---|---|---|
| Spec versi aktif | `GET /api/projects/{id}/specs/{v}` | Data semantik: dinding, ruang, objek, default |
| Shell | `GET /api/projects/{id}/outputs/{v}/shell.glb` | Geometri bangunan dari Blender |
| Library template | `GET /api/templates` + `asset.glb` per template | Objek drag & drop |

Objek di `spec.objects` dirender dari template `.glb` sesuai transform di spec. Objek **tidak** diambil dari `layout_full.glb`, agar bisa diedit langsung.

Node shell dipetakan ke spec lewat `userData.spec_id` (glTF extras).

Bila `outputs/v<N>` belum ada (spec baru tersimpan tetapi belum di-regenerate), editor memuat shell dari versi terakhir yang punya output dan menampilkan banner "Shell dari v<M>; regenerate untuk memperbarui".

## 2. Tata Letak Layar

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Toolbar: [Orbit][Top][Walk] | [Select][Ukur jarak][Ukur luas][Ukur tinggi]│
│          | Snap 600 ☑ | Undo Redo | v7 (unsaved: 3) [Save] [Regenerate]   │
├──────────────┬──────────────────────────────────────────┬─────────────────┤
│ Library      │                                          │ Properties      │
│ ┌──────────┐ │                                          │ (seleksi aktif) │
│ │ search   │ │            Viewport 3D                   │                 │
│ ├──────────┤ │                                          │ Rooms / Layers  │
│ │ Rack     │ │                                          │ (outline)       │
│ │ Cooling  │ │                                          │                 │
│ │ Power    │ │                                          │                 │
│ │ ...      │ │                                          │                 │
│ └──────────┘ │                                          │                 │
├──────────────┴──────────────────────────────────────────┴─────────────────┤
│ Status: kursor X 12.400 m  Y 6.020 m | Ruang: R. MEETING 57.62 m² | 60 fps│
└───────────────────────────────────────────────────────────────────────────┘
```

Panel kiri dan kanan bisa disembunyikan. Lebar minimal layar 1056 px.

## 3. Mode Tampilan

| Mode | Kontrol | Catatan |
|---|---|---|
| **Orbit** (default) | `OrbitControls`: kiri = putar, kanan = geser, scroll = zoom | Target awal di centroid bangunan |
| **Top** | Kamera ortografik dari atas, putar dikunci | Cocok untuk penempatan presisi dan ukur luas |
| **Walk** (P1) | `PointerLockControls` + WASD, tinggi mata 1.6 m, kecepatan 1.4 m/s (Shift = 3 m/s) | Tabrakan sederhana dengan dinding (raycast horizontal 0.3 m). Teleport ke ruang lewat daftar Rooms. |

**Toggle visibilitas**: dinding, kolom, pintu, objek, label ruang, grid 600 mm, sumbu grid struktur. Ada juga mode **cutaway**: dinding dipotong di ketinggian yang bisa diatur, lewat clipping plane renderer.

## 4. Seleksi & Info

- Klik objek, dinding, pintu, kolom, atau lantai ruang untuk menyeleksi (raycast). Outline biru `#0f62fe`.
- Panel Properties menampilkan info sesuai tipe:
  - **Dinding**: ID, panjang, tebal, tinggi (editable), kind. Koordinat ujung, tebal, dan kind bisa diedit lewat panel koreksi (§6b).
  - **Ruang**: nama, tipe (editable, dengan validasi enum), luas, keliling, pintu.
  - **Pintu**: tipe, lebar, tinggi, engsel, arah, offset. Diedit lewat panel koreksi (§6b).
  - **Tangga**: jumlah flight, tanjakan per flight, lebar, arah naik, `top_z`. Diedit lewat panel koreksi (§6b).
  - **Kolom**: ukuran, kind (read-only).
  - **Objek**: template, label, posisi, rotasi, dimensi (editable), locked.

## 5. Tool Ukur

Semua nilai ditampilkan dalam meter (3 desimal untuk jarak dan tinggi) dan m² (2 desimal). Ukuran disimpan sementara di layer ukur dan bisa dihapus. Ukuran **tidak** disimpan ke spec.

| Tool | Interaksi | Perhitungan |
|---|---|---|
| **Jarak** | Klik titik A lalu titik B. Snap ke vertex (≤ 10 px layar), tengah edge, dan permukaan. Shift mengunci sumbu X/Y/Z. | Jarak Euclid 3D, ditambah komponen ΔX, ΔY, ΔZ |
| **Luas ruang** | Klik lantai ruang | Diambil dari `rooms[].area_m2` di spec (sumber resmi). Poligon ruang di-highlight. |
| **Luas bebas** | Klik titik-titik di lantai, klik dua kali untuk menutup. Snap ke vertex/edge dinding. | Shoelace di bidang XY |
| **Tinggi** | Klik titik di permukaan mana pun | Z titik terhadap lantai (z = 0). Bila mengklik dinding, panel juga menampilkan `height` dinding dari spec. |

Akurasi tool ukur dibatasi presisi geometri `.glb` (float32, tetap di bawah 1 mm untuk skala bangunan).

## 6. Tinggi Dinding

- **Global**: input "Tinggi dinding default" di panel Properties (tanpa seleksi), menghasilkan op `set_default wall_height`. Dinding dengan `height: null` otomatis mengikuti nilai ini. Checkbox "Terapkan juga ke dinding yang tingginya diatur khusus" menambah op `set_wall_height "*" null`, yang mengembalikan semua dinding ke default.
- **Per dinding**: pilih satu atau beberapa dinding (Shift+klik), lalu ubah tinggi. Op yang dihasilkan: `set_wall_height id`.
- **Pratinjau langsung**: mesh dinding diskala di sumbu Z (pivot di z = 0). Banner "Pratinjau: bukaan pintu belum akurat sampai regenerate" ditampilkan, karena potongan pintu ikut terskala.
- **Batas**: 1000–12000 mm.

## 6b. Panel Koreksi Geometri

Jalan keluar ketika ekstraksi meleset pada dinding, pintu, atau tangga. Panel ini berbasis **form numerik**, bukan menggambar bebas atau menyeret vertex. Panel ada di Properties sebagai bagian "Koreksi" yang terlipat secara default.

| Elemen | Aksi | Op |
|---|---|---|
| Dinding terpilih | Ubah `a`/`b` (mm), tebal, kind | `move_wall` |
| | Pisah di offset (mm dari `a`) | `split_wall` |
| | Hapus (alasan wajib, dropdown: "garis anotasi", "duplikat", "bukan dinding", lainnya) | `delete_wall` |
| | Gabung dengan dinding terpilih lain (Shift+klik, harus kolinear) | `merge_walls` |
| Tanpa seleksi | **Tambah dinding**: isi `a`, `b`, tebal, kind; atau klik dua titik di mode Top (snap ke grid struktur, vertex dinding, dan grid 100 mm) lalu koreksi angkanya | `add_wall` |
| Pintu terpilih | Ubah tipe, lebar, tinggi, offset, engsel, arah buka | `set_door` |
| | Hapus | `delete_opening` |
| Dinding terpilih | **Tambah pintu/jendela**: kategori, offset, lebar, tipe | `add_opening` |
| Tangga terpilih | Ubah tanjakan, lebar, `top_z`; tombol "Balik arah naik" (menukar `start`/`end` semua flight) | `set_stair` |
| | Hapus | `delete_stair` |

Perilaku:

- **Pratinjau 2D, bukan 3D.** Shell berasal dari Blender, sehingga perubahan geometri tidak bisa dipratinjau akurat di klien. Perubahan yang belum di-regenerate digambar sebagai garis oranye `#ff832b` (tapak dinding, posisi pintu, garis flight) di atas lantai, ditambah banner "Geometri berubah: Save + Regenerate untuk melihat hasil 3D".
- **Validasi langsung.** Setiap perubahan dikirim ke `POST /specs/validate` (debounce 500 ms). Masalah baru, mis. bukaan keluar dari dinding (V008) atau ruang tidak tertutup (V011), tampil di panel Masalah sebelum Save.
- **Ruang dihitung ulang server.** Op dinding memicu pembentukan ulang ruang di core (`03-layout-spec.md` §11). Nama dan tipe ruang dibawa dengan aturan carry-over (`04-extraction.md` §5.4b).
- Reducer TS klien hanya memperbarui data elemen untuk pratinjau 2D. Reducer tidak menghitung ruang.
- Tambah tangga baru tidak tersedia di editor MVP; gunakan op `add_stair` lewat API atau impor spec.

Target: sisa galat Gatsu setelah ekstraksi bisa dikoreksi lewat panel ini dalam ≤ 15 menit oleh operator yang sudah terbiasa.

## 7. Drag & Drop Objek

### 7.1 Menambah

1. Seret kartu template dari Library ke viewport.
2. Selama drag, raycast ke mesh lantai (`room_*`) menghasilkan ghost semi-transparan pada posisi snap.
3. Lepas mouse untuk membuat op `add_object` dengan dimensi default template, `rotation` 0, dan `room_id` turunan.
4. Bila dilepas di luar lantai ruang, objek ditolak dan muncul toast peringatan.

### 7.2 Memindah, rotasi, resize

| Aksi | Kontrol |
|---|---|
| Pindah | Drag objek di bidang lantai, atau gizmo translate (`TransformControls`, sumbu Z dikunci default) |
| Rotasi | `R` = +90°, `Shift+R` = −90°, atau gizmo rotate Z (snap 15°, Alt = bebas) |
| Resize | Gizmo scale per sumbu, atau input numerik w/d/h. Dibatasi `template.resizable[axis] {min,max,step}`. Sumbu yang tidak boleh di-resize dinonaktifkan. |
| Duplikat | `Ctrl+D` (offset satu langkah snap) |
| Hapus | `Delete` |
| Kunci | Toggle `locked` di Properties |
| Multi-seleksi | Shift+klik atau marquee di mode Top. Operasi pindah/rotasi diterapkan ke grup (pivot di pusat grup). |

### 7.3 Snap

- **Grid 600 mm** (default aktif). Grid beracuan origin spec, dan bisa digeser per ruang lewat "atur origin grid ruang" (P2). Titik snap mengikuti `template.snap.align`: `edge` (tepi objek ke garis grid) atau `center`.
- **Snap ke dinding** (P1): tepi belakang objek menempel ke permukaan dinding bila ≤ 150 mm.
- Tahan `Alt` untuk menonaktifkan snap sementara.

### 7.4 Tabrakan (P1)

- AABB terotasi (OBB) objek dicek terhadap objek lain dan terhadap tapak dinding/kolom dari spec.
- Objek yang bertabrakan diberi outline merah `#fa4d56` dan tercantum di panel "Masalah". Save tetap diizinkan (hanya peringatan, sesuai V017).
- Clearance depan/belakang dari `template.clearance` ditampilkan sebagai area transparan saat objek dipilih.

## 8. Undo/Redo, Save, Regenerate

### 8.1 Model state

- Editor menyimpan `baseVersion` (versi spec yang dimuat) dan **daftar ops lokal** yang belum disimpan.
- State tampilan = spec dasar + ops lokal, diterapkan di klien dengan reducer TypeScript. Reducer ini mencerminkan subset ops editor dan tidak menghitung geometri ruang.
- Undo/redo memanipulasi daftar ops lokal (P1, stack 100 langkah).
- Indikator "unsaved: n". Peringatan `beforeunload` bila ada perubahan yang belum disimpan.

### 8.2 Save

```
POST /api/projects/{id}/specs
{ "base_version": 7, "ops": [ ... ], "message": "Tambah 12 rack baris A" }
```

| Respons | Arti | Perilaku editor |
|---|---|---|
| `201` + `{version: 8, spec}` | Sukses | Kosongkan ops lokal, set `baseVersion = 8`, tawarkan Regenerate |
| `409` | `base_version` bukan HEAD (ada perubahan lain) | Dialog: muat ulang HEAD lalu terapkan ulang ops lokal (rebase sederhana; op yang gagal ditampilkan), atau batal |
| `422` + issues | Validasi gagal (aturan error) | Tampilkan daftar masalah, ops lokal tetap ada |

### 8.3 Regenerate

- Tombol Regenerate memanggil `POST /api/projects/{id}/regenerate {version}`, lalu editor berlangganan SSE run tersebut.
- Progress bar kecil tampil di toolbar. Setelah selesai, `shell.glb` dimuat ulang dengan mempertahankan posisi kamera dan seleksi.
- Opsi "Regenerate otomatis setelah Save" (default mati, disimpan di localStorage).

## 9. Performa

- Template dimuat sekali per (`id`, `version`), lalu dirender dengan **InstancedMesh** bila jumlah instance per template > 20.
- `shell.glb` dimuat dengan cache browser (ETag per versi).
- Target: shell + 500 objek ≥ 45 fps di laptop iGPU (NFR-PF-04).
- Bayangan dimatikan secara default, dengan pencahayaan hemisphere + directional. Ada toggle "kualitas tinggi" untuk SSAO.

## 10. Pintasan Keyboard

| Tombol | Aksi |
|---|---|
| `1` / `2` / `3` | Orbit / Top / Walk |
| `V` | Select |
| `M` | Ukur jarak |
| `A` | Ukur luas bebas |
| `H` | Ukur tinggi |
| `G` | Toggle snap grid |
| `R` / `Shift+R` | Rotasi ±90° |
| `Ctrl+D` | Duplikat |
| `Delete` | Hapus |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / Redo |
| `Ctrl+S` | Save |
| `Esc` | Batal tool / keluar walk |

## 11. Di Luar Cakupan MVP

- Menggambar atau menyeret geometri dinding, pintu, dan tangga langsung di viewport 3D. Koreksi MVP lewat panel numerik (§6b).
- Pratinjau 3D langsung untuk perubahan geometri shell.
- Kolaborasi real-time multi-pengguna. Konflik ditangani dengan 409.
- Anotasi atau komentar di model.
