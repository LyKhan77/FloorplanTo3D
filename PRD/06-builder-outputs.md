# 06 — Builder & Outputs (Tahap 7–9)

## 1. Ringkasan

| Tahap | Proses | Output |
|---|---|---|
| 7 Build | Core menyiapkan `build_input.json`. Blender headless membangun scene, lalu mengekspor. | `layout.blend`, `shell.glb`, `layout_full.glb`, `layout.fbx`, `layout.obj` |
| 8 Verifikasi | Render top-down ortografik dibandingkan dengan mask dinding denah; cek dimensi | `verify.json`, `top.png`, `iou_mask.png` |
| 9 Dokumen | Blender merender view dokumen; Jinja2 menghasilkan HTML; WeasyPrint menghasilkan PDF | `report.html`, `report.pdf`, `renders/*.png` |
| 10 Publish | Output dipublikasikan ke `outputs/v<N>/` secara atomik (tulis ke folder sementara, lalu rename), lalu event `output.ready` dikirim. Editor memuat versi output terbaru. | — |

Tahap 7–9 dijalankan dalam **satu** proses Blender per run. Tujuannya menghindari biaya start Blender berulang. Urutannya: build, export, render verifikasi, render dokumen. Pembuatan HTML/PDF dan perhitungan IoU dilakukan di core setelah Blender selesai.

## 2. Pemanggilan Blender

```
blender -b --factory-startup --python-exit-code 1 \
        -P builder/build.py -- <build_input.json> <out_dir>
```

- `--factory-startup` mengabaikan preferensi dan addon pengguna, agar hasilnya deterministik.
- `--python-exit-code 1` membuat exception Python menghasilkan exit code ≠ 0, sehingga tahap ditandai `failed`.
- Stdout/stderr dialirkan baris per baris ke event `stage.log`. `build.py` mencetak progres dalam format `@@PROGRESS <0-100> <pesan>`, lalu server mengubahnya menjadi `stage.progress`.
- Timeout: 300 detik (konfigurasi).
- Versi Blender di-pin ke **5.2 LTS**. `build.py` memeriksa `bpy.app.version` di awal dan gagal dengan pesan jelas bila tidak cocok.

## 3. Struktur Scene

```
Scene "Layout"
├─ Collection "Shell"
│   ├─ "Walls"     wall_W1 … (satu mesh per tapak dinding hasil union, atau per dinding; lihat §4.1)
│   ├─ "Columns"   column_C1 …
│   ├─ "Doors"     door_D1 (Empty, pivot di engsel) ─ frame_D1, leaf_D1_a, leaf_D1_b
│   ├─ "Windows"   window_N1 …
│   ├─ "Stairs"    stair_S1 (Empty) ─ stair_S1_f1, stair_S1_f2, stair_S1_l1 …
│   └─ "Floors"    room_R1 … (satu mesh datar per ruang), slab_1 … (per massa bangunan)
├─ Collection "Objects"   obj_O1 … (instance template)
├─ Collection "Annotations" (hanya untuk render dokumen: label ruang, grid; tidak diekspor)
└─ Collection "Cameras"   cam_top, cam_iso_ne, cam_iso_nw, cam_iso_se, cam_iso_sw, cam_room_R1 …
```

**Custom properties** pada setiap objek: `spec_id`, `spec_type` (`wall`/`column`/`door`/`window`/`room`/`stair`/`object`), `spec_version`. Ditambah per tipe: `area_m2` (room), `height_mm` (wall), dan `template_id` (object). Properti ini diekspor sebagai **glTF extras** (`export_extras=True`) dan dibaca web sebagai `object.userData`.

## 4. Aturan Geometri

### 4.1 Dinding

1. Core sudah menyiapkan `wall_solids`: **satu poligon tapak per dinding**. Sambungan sudut dibagi di garis bagi sudut, sehingga tapak antar-dinding tidak tumpang tindih dan tetap bisa dipilih per ID di web.
2. Builder mengekstrusi tiap poligon dengan bmesh (tutup atas dan bawah) setinggi `height`, sebagai mesh `wall_<id>`.
3. Union tapak (per tinggi) disertakan terpisah di `wall_union` dan **hanya** dipakai untuk render top-down verifikasi.
4. **Bukaan**: untuk setiap opening, buat kotak cutter (lebar × (tebal + 20 mm) × tinggi, dimulai dari `sill`), lalu terapkan modifier Boolean `DIFFERENCE` (solver `EXACT`) dan apply. Cutter dihapus setelahnya.
5. Normal dirapikan (`recalc_face_normals`) dan vertex digabung (jarak 0.1 mm).

### 4.2 Pintu (parametrik, dari spec, bukan template)

- **Kusen**: profil U 50×(tebal dinding) mm mengelilingi bukaan (dua tiang + ambang atas).
- **Daun**: kotak tebal 40 mm. Lebar = lebar bersih (single) atau lebar × `leaf_split` (double), tinggi = `height − 10` mm.
- **Pivot** setiap daun berada di garis engsel (Empty parent `door_D<n>`). Rotasi default 0° = tertutup. Web bisa memutar daun untuk animasi buka (P2).
- `sliding`: daun digeser sejajar dinding di sisi `swing`. `opening`: tanpa daun, hanya kusen. `rolling`: panel tipis di sisi atas bukaan.
- Simbol busur buka (garis lengkung di lantai) **hanya** digambar di collection Annotations untuk render dokumen.

### 4.3 Jendela

Kusen tipis ditambah satu panel kaca (material transparan), di tengah tebal dinding.

### 4.4 Lantai

- Satu mesh datar per ruang dari `rooms[].polygon` di z = 0. Mesh ditriangulasi dengan poligon berlubang bila ruang mengelilingi kolom.
- Nama mesh `room_<id>`. Mesh ini menjadi target raycast tool ukur luas dan drop objek di web.
- **Slab** bangunan: satu mesh tipis (z −150 sampai 0 mm) per poligon `meta.building_outline`, termasuk pita luar dan blok sirip. Slab dikecualikan dari picking ruang. Area slab di luar semua ruang tetap terlihat sebagai lantai.

### 4.5 Kolom

Ekstrusi sesuai `shape`: rect (kotak), circle (silinder 24 segmen), h_section (profil H dengan flens dan web 1/10 ukuran). Tinggi = tinggi dinding default bila null. `kind: pilaster` dibangun sama dengan `rect`, dengan material dinding.

### 4.5b Tangga

- Per flight: `risers` balok anak tangga **pejal** (bukan pelat melayang), agar tampilan dan tool ukur tinggi benar. Anak tangga ke-k: kotak lebar `width` × kedalaman injakan × tinggi (k × tinggi tanjakan), diukur dari `base_z` flight. Semua balok digabung menjadi satu mesh `stair_S<n>_f<i>`.
- Bordes: ekstrusi poligon `landings[j]` dari `base_z` sampai ketinggian akhir flight sebelumnya, mesh `stair_S<n>_l<j>`.
- Tanpa railing di MVP.
- Tinggi tanjakan dan kedalaman injakan dihitung core di `build_input.json` (lihat `03-layout-spec.md` §8b). Builder tidak menghitung ulang.

### 4.6 Objek template

- Impor `asset.glb` sekali per (`template_id`, `version`) ke collection tersembunyi `_templates`, lalu buat **linked duplicate** per instance, agar file ringan.
- Transform: posisi pivot, rotasi Z, dan skala per sumbu = `dims / template.dims`.
- `shell.glb` **tidak** memuat objek. `layout_full.glb`, `.blend`, `.fbx`, dan `.obj` memuat objek.

### 4.7 Material

Material PBR sederhana yang netral. Tujuannya keterbacaan, bukan fotorealisme.

| Elemen | Base color | Roughness |
|---|---|---|
| Dinding exterior | #D9D9D9 | 0.9 |
| Dinding interior/partition | #E8E8E8 | 0.9 |
| Kolom | #A8A8A8 | 0.8 |
| Lantai (default) | #6F6F6F | 0.7 |
| Lantai `data_hall` | #8D8D8D + tekstur grid 600 mm (opsional) | 0.6 |
| Kusen pintu | #4D4D4D | 0.5 |
| Daun pintu | #8A6A4F (kayu) / #9AA0A6 (besi, untuk ruang teknis) | 0.6 |
| Kaca | #BFD7EA, alpha 0.3 | 0.1 |

Warna lantai per tipe ruang, sebagai *tint* tipis, hanya diterapkan di render dokumen, bukan di `.glb`.

## 5. Export

| File | Isi | Pengaturan |
|---|---|---|
| `shell.glb` | Shell saja | glTF binary, `export_extras=True`, `export_apply=True`, Y-up, tanpa kamera/lampu, tanpa collection Annotations |
| `layout_full.glb` | Shell + objek | sama |
| `layout.blend` | Seluruh scene termasuk kamera dan anotasi | `save_as_mainfile`, relative paths, pack resources |
| `layout.fbx` | Shell + objek | skala 1.0, unit meter, `apply_unit_scale` |
| `layout.obj` | Shell + objek | dengan `.mtl` |

**Verifikasi 1:1 pasca-export** (NFR-AC-09): core membuka `shell.glb` dengan parser glTF ringan (`pygltflib`), membaca bounding box per node `wall_*`, lalu membandingkannya dengan spec. Galat yang diizinkan ≤ 1 mm.

## 6. Tahap 8 — Verifikasi

1. **Render top-down**: kamera ortografik tepat di atas, dengan `ortho_scale` disesuaikan agar 1 px render = 1 px gambar kerja (memakai `px_to_mm`). Engine Workbench, warna flat: dinding dan kolom hitam, sisanya putih, tanpa anti-alias.
2. **Mask denah**: dari kandidat terpilih, gunakan mask garis tebal / area dinding (S1) atau isi antara pasangan garis (S2). Bagian di luar area gambar dibuang.
3. **IoU** = |render ∩ mask| / |render ∪ mask|, setelah keduanya didilasi 1 px untuk toleransi rasterisasi.
4. **Cek dimensi**: jarak antar-sumbu grid di spec dibandingkan dengan dimensi OCR, dan bounding box bangunan di `.glb` dibandingkan dengan spec.
5. **Visual diff** `iou_mask.png`: hijau = cocok, merah = ada di denah tapi tidak di model, biru = ada di model tapi tidak di denah.
6. **Ambang**: IoU ≥ 0.85 `succeeded`; 0.70–0.85 `succeeded` dengan peringatan; < 0.70 `needs_attention`. Output tetap dibuat, tetapi diberi label peringatan di dashboard dan dokumen.

`verify.json`:
```jsonc
{ "iou": 0.88, "iou_threshold": 0.85, "grid_check": { "max_err_mm": 12, "pass": true },
  "glb_check": { "max_err_mm": 0.4, "pass": true }, "status": "succeeded", "warnings": [] }
```

## 7. Tahap 9 — Dokumen Map 3D

### 7.1 Render

| Kamera | Spesifikasi |
|---|---|
| `cam_top` | Ortografik dari atas, dengan label ruang dan grid (collection Annotations) |
| `cam_iso_*` (4) | Ortografik isometrik dari 4 sudut, elevasi 35°, dinding dipotong pada 1.2 m (cutaway) agar interior terlihat. Pemotongan memakai boolean sementara atau clipping kamera. |
| `cam_room_<id>` | Perspektif di centroid ruang, tinggi mata 1.6 m, menghadap dinding terpanjang, FOV 75°. Hanya ruang ≥ 4 m². |

Engine: Eevee, 1600×1000 px untuk iso/top dan 1280×800 px untuk ruang. Engine bisa diturunkan ke Workbench lewat konfigurasi agar cepat di server tanpa GPU.

### 7.2 Isi dokumen (urutan)

1. **Sampul**: nama project, lantai, versi spec, tanggal, status verifikasi.
2. **Ringkasan**: luas kotor bangunan, luas bersih total, jumlah ruang/pintu/kolom, tinggi dinding default, skala, sumber skala, IoU.
3. **Denah asli** berdampingan dengan **overlay deteksi** (dinding/pintu/kolom berwarna dengan ID).
4. **Top view 3D** dengan label ruang dan grid.
5. **Isometrik ×4**.
6. **Tabel ruang**: ID, nama, tipe, luas (m²), keliling (m), jumlah pintu, tinggi dinding. Diurut berdasarkan ID.
7. **Jadwal pintu**: ID, ruang A ↔ ruang B, tipe, lebar × tinggi, engsel, arah.
7b. **Tangga**: ID, ruang, jumlah flight, jumlah tanjakan, tinggi tanjakan, kedalaman injakan, arah naik.
8. **Ringkasan dinding**: total panjang per `kind` dan per tebal.
9. **Objek** (bila ada): daftar per template (jumlah, dimensi) dan per ruang.
10. **Render per ruang** (galeri).
11. **Peringatan & provenance**: masalah validator tersisa, keputusan LLM yang diterima, elemen yang diedit manual.
12. **Metadata**: hash input, run id, versi kode, versi Blender, versi prompt LLM.

### 7.3 Format

- Template Jinja2 `core/report/templates/report.html.j2`. CSS cetak memakai Carbon light (dokumen cetak tetap terang agar mudah dicetak).
- HTML: gambar disematkan sebagai file relatif di `renders/`, sehingga bisa dibuka offline.
- PDF: WeasyPrint dari HTML yang sama, ukuran A4 landscape, dengan nomor halaman.

## 8. Regenerate

- Pemicu: Save di editor (opsional otomatis) atau tombol Regenerate, untuk versi spec tertentu (default `HEAD`).
- Menjalankan tahap 7–10 saja. Hasilnya di `outputs/v<N>/`. Output versi lain tidak disentuh.
- Bila `outputs/v<N>/` sudah lengkap dan spec tidak berubah, hasil yang ada dipakai ulang (idempoten).
- Tahap 8 tetap dijalankan agar IoU terhadap denah asli tetap terpantau. Editor tidak mengubah dinding (kecuali tinggi), jadi IoU seharusnya stabil.
