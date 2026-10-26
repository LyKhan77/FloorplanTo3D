# 03 — Layout Spec

Layout spec adalah kontrak utama antar-komponen. Skema didefinisikan dengan **Pydantic v2** di `core/spec/`. Dari situ diekspor:
- **JSON Schema** (`schema/layout-spec.schema.json`), dipakai untuk validasi output LLM;
- **tipe TypeScript** (`web/src/types/spec.ts`), dibuat otomatis.

Versi skema: `schema_version: "1.0"`. Perubahan yang tidak kompatibel menaikkan versi mayor dan wajib disertai migrasi.

## 1. Konvensi

| Hal | Konvensi |
|---|---|
| Satuan panjang | **milimeter (integer)**. Pembulatan ke 1 mm. |
| Satuan sudut | derajat (float), berlawanan arah jarum jam, 0° = arah +X |
| Sistem koordinat | Tangan kanan. **+X = timur** (ke kanan di denah), **+Y = utara** (ke atas di denah), **+Z = atas** |
| Origin | Perpotongan **sumbu grid vertikal pertama** dan **sumbu grid horizontal terakhir**, yaitu sudut kiri-bawah grid. Pada Gatsu: grid **A × 3**. Bila grid tidak terdeteksi: sudut kiri-bawah bounding box dinding. |
| Lantai | z = 0 adalah permukaan lantai jadi |
| Konversi ke Blender | 1 unit Blender = 1 m. `X_bl = x/1000`, `Y_bl = y/1000`, `Z_bl = z/1000` |
| Konversi ke glTF | Y-up. `X_gl = x/1000`, `Y_gl = z/1000`, `Z_gl = -y/1000` (dilakukan otomatis oleh exporter Blender) |
| ID | Prefiks tipe + nomor urut: `W` dinding, `C` kolom, `D` pintu, `N` jendela, `R` ruang, `S` tangga, `O` objek, `G` grid. ID **stabil antar-versi**: elemen yang tidak berubah mempertahankan ID-nya. ID yang dihapus tidak dipakai ulang. |
| Poligon | Daftar titik `[x, y]` berlawanan arah jarum jam, tanpa titik penutup duplikat |

## 2. Struktur Tingkat Atas

```jsonc
{
  "schema_version": "1.0",
  "meta":     { ... },     // identitas, versi, skala, default
  "grid":     { ... },     // sumbu struktur
  "walls":    [ ... ],
  "columns":  [ ... ],
  "openings": [ ... ],     // pintu dan jendela
  "rooms":    [ ... ],
  "stairs":   [ ... ],     // tangga (geometri, bukan hanya tipe ruang)
  "objects":  [ ... ],     // instance template (dari editor)
  "provenance_log": [ ... ] // ringkasan asal perubahan versi ini
}
```

## 3. `meta`

| Field | Tipe | Keterangan |
|---|---|---|
| `project_id` | string | |
| `version` | int | Nomor versi spec ini (≥ 1) |
| `parent_version` | int \| null | Versi asal |
| `created_at` | ISO datetime | |
| `source` | enum | `pipeline` \| `llm` \| `editor` \| `manual` \| `migration` |
| `run_id` | string \| null | Run yang menghasilkan versi ini |
| `floor_name` | string | mis. "Lantai 1" |
| `site_type` | enum | `data_hall` \| `data_center` \| `office` \| `mixed` \| `other` |
| `condition` | enum | `existing` (satu-satunya nilai di MVP). Elemen bertanda PROPOSED/NEW/RENCANA tidak dimodelkan. Dinding bertanda "dismantle"/"bongkar" **tetap** dimodelkan karena masih ada di kondisi existing. |
| `image` | object | `{ "sha256", "width_px", "height_px", "dpi" }` |
| `px_to_mm` | number[6] | Matriks affine 2×3 dari piksel gambar (setelah preprocess) ke mm spec. Sumbu Y dibalik di sini. |
| `mm_per_px` | number | Skala rata-rata (informasi) |
| `scale_source` | enum | `grid_dimensions` \| `dimension_text` \| `manual` \| `total_length` |
| `defaults` | object | `{ "wall_height": 3000, "wall_thickness": 150, "door_height": 2100, "window_sill": 900, "window_height": 1200, "floor_to_floor": 4000 }`. `floor_to_floor` = tinggi lantai ke lantai di atasnya, dipakai sebagai tinggi total tangga. |
| `building_outline` | polygon[] | Kontur **terluar** bangunan, termasuk pita luar, blok sirip/pilaster, dan bangunan terpisah (mis. Capasitor Room). Satu poligon per massa bangunan. Dipakai untuk slab dan luas kotor. |
| `gross_area_m2` | number | **Turunan**: luas total `building_outline`. Sesuai keputusan Gatsu, pita luar ikut dihitung. |
| `id_seq` | object | Nomor terakhir yang pernah dipakai per prefiks ID (`{"W": 41, ...}`), agar ID yang dihapus tidak dipakai ulang. Dikelola core. |

## 4. `grid`

```jsonc
"grid": {
  "axes": [
    { "id": "GA", "label": "A", "orientation": "vertical",   "offset": 0 },
    { "id": "GB", "label": "B", "orientation": "vertical",   "offset": 6000 },
    { "id": "G1", "label": "1", "orientation": "horizontal", "offset": 12000 },
    { "id": "G3", "label": "3", "orientation": "horizontal", "offset": 0 }
  ]
}
```

- `orientation: vertical` artinya garis sejajar sumbu Y, dengan `offset` = nilai x.
- `orientation: horizontal` artinya garis sejajar sumbu X, dengan `offset` = nilai y.

## 5. `walls`

| Field | Tipe | Keterangan |
|---|---|---|
| `id` | string | `W1`… |
| `a`, `b` | [x, y] | Titik ujung **garis tengah** |
| `thickness` | int | mm |
| `height` | int \| null | null berarti memakai `meta.defaults.wall_height` |
| `base_z` | int | default 0 |
| `kind` | enum | `exterior` \| `interior` \| `partition` \| `glass` \| `low` |
| `grid_ref` | string[] | Sumbu grid tempat dinding di-snap (opsional) |
| `free_ends` | bool | default `false`. `true` = ujung dinding boleh tidak terhubung (V004 dilewati), mis. dinding pendek berdiri bebas. |
| `allow_skew` | bool | default `false`. `true` = dinding sengaja tidak ortogonal (V006 dilewati). |
| `provenance` | object | Lihat §10 |

Dinding lurus saja (segmen). Dinding lengkung didekati dengan beberapa segmen (non-goal untuk akurasi).

## 6. `columns`

| Field | Tipe | Keterangan |
|---|---|---|
| `id` | string | `C1`… |
| `center` | [x, y] | |
| `shape` | enum | `rect` \| `circle` \| `h_section` |
| `size` | [w, d] | mm. Untuk `circle`, w = diameter. |
| `rotation` | number | derajat |
| `kind` | enum | `structural` (kolom di titik grid) \| `pilaster` (blok kecil menempel/di luar dinding, mis. sirip di pita luar Gatsu). Default `structural`. |
| `height` | int \| null | null berarti sama dengan tinggi dinding default |
| `grid_ref` | [string, string] \| null | mis. `["GA", "G1"]` |
| `provenance` | object | |

## 7. `openings`

| Field | Tipe | Keterangan |
|---|---|---|
| `id` | string | `D1`… untuk pintu, `N1`… untuk jendela |
| `category` | enum | `door` \| `window` |
| `wall_id` | string | Dinding induk |
| `offset` | int | Jarak dari titik `a` dinding ke **tepi awal** bukaan, sepanjang dinding (mm) |
| `width` | int | Lebar bersih bukaan |
| `height` | int \| null | null berarti default pintu/jendela |
| `sill` | int | 0 untuk pintu; default `window_sill` untuk jendela |
| `door_type` | enum \| null | `single_swing` \| `double_swing` \| `sliding` \| `opening` (tanpa daun) \| `rolling` |
| `hinge` | enum \| null | `start` \| `end` \| `both` (double). Relatif terhadap arah a→b. |
| `swing` | enum \| null | `left` \| `right`. Sisi dinding tempat daun membuka, dilihat dari a menghadap b. |
| `leaf_split` | number \| null | Untuk double tak simetris, rasio daun pertama (default 0.5) |
| `provenance` | object | |

## 8. `rooms`

| Field | Tipe | Keterangan |
|---|---|---|
| `id` | string | `R1`… |
| `polygon` | polygon | Batas **bersih** (sisi dalam dinding) |
| `holes` | polygon[] | Lubang di dalam ruang, mis. tapak kolom yang berdiri di dalam ruang. Default `[]`. Poligon searah jarum jam. |
| `name` | string | Label dari OCR / LLM / editor, mis. "BATTERY ROOM" |
| `type` | enum | `data_hall` \| `ups_room` \| `battery_room` \| `electrical_room` \| `mdf` \| `ahu_room` \| `capacitor_room` \| `meeting` \| `office` \| `storage` \| `pantry` \| `toilet` \| `corridor` \| `lobby` \| `stair` \| `lift` \| `prayer_room` \| `outdoor` \| `other` |
| `area_m2` | number | **Turunan**: luas bersih = luas `polygon` − luas `holes`, dibulatkan 0.01. Nilai dari luar diabaikan. GT dan benchmark memakai definisi yang sama. |
| `perimeter_m` | number | Turunan |
| `bounding_walls` | string[] | ID dinding yang membatasi |
| `doors` | string[] | ID pintu yang terhubung ke ruang ini |
| `label_pos` | [x, y] | Posisi label teks |
| `provenance` | object | |

## 8b. `stairs`

Tangga adalah geometri shell (dari denah), bukan objek template. Satu tangga terdiri dari satu atau beberapa *flight* (lari tangga) dan bordes di antaranya.

| Field | Tipe | Keterangan |
|---|---|---|
| `id` | string | `S1`… |
| `flights` | object[] | `{ "start": [x,y], "end": [x,y], "width": int, "risers": int }`. `start`→`end` = garis tengah flight searah **naik**. `risers` = jumlah tanjakan. |
| `landings` | polygon[] | Bordes antar-flight. Ketinggiannya turunan (lihat bawah). |
| `base_z` | int | default 0 |
| `top_z` | int \| null | null berarti `meta.defaults.floor_to_floor` |
| `room_id` | string \| null | Turunan: ruang `stair` tempat tangga berada |
| `provenance` | object | |

Turunan untuk builder: tinggi tanjakan = (`top_z` − `base_z`) / Σ`risers`. Flight ke-i dimulai di ketinggian kumulatif flight sebelumnya. Bordes berada di ketinggian akhir flight sebelumnya. Kedalaman injakan = panjang flight / `risers`.

## 9. `objects`

| Field | Tipe | Keterangan |
|---|---|---|
| `id` | string | `O1`… |
| `template_id` | string | Lihat `10-template-contract.md` |
| `template_version` | string | Semver template |
| `position` | [x, y, z] | Posisi **pivot** template (tengah-bawah) dalam mm |
| `rotation` | number | Derajat terhadap sumbu Z |
| `dims` | [w, d, h] | Dimensi akhir (mm). Harus berada di batas `resizable` template. |
| `room_id` | string \| null | Turunan: ruang tempat pivot berada |
| `label` | string \| null | mis. "RACK A-01" |
| `locked` | bool | Tidak bisa dipindah di editor |
| `provenance` | object | |

## 10. `provenance` (per elemen)

```jsonc
"provenance": {
  "source": "cv",            // cv | llm | editor | manual
  "confidence": 0.92,        // 0–1; editor/manual = 1.0
  "candidate": "k3",         // kandidat sweep asal (untuk cv)
  "evidence": { "thickness_px": 6.1, "pair_gap_mm": 148 },  // fitur pendukung (bebas)
  "changed_in": 4            // versi terakhir elemen ini berubah
}
```

`provenance_log` di tingkat atas berisi daftar ringkas operasi yang membentuk versi ini, mis. `{"op": "delete_wall", "id": "W7", "by": "llm", "reason": "garis kabel"}`.

## 11. Operasi Spec (Ops)

Editor dan Strata **tidak** mengirim spec utuh. Keduanya mengirim daftar operasi. Server menerapkannya ke `base_version`, memvalidasi hasilnya, lalu membuat versi baru.

| Op | Parameter | Dipakai oleh |
|---|---|---|
| `add_object` | `template_id, template_version, position, rotation, dims, label?` | editor |
| `update_object` | `id, position?, rotation?, dims?, label?, locked?` | editor |
| `delete_object` | `id` | editor |
| `set_wall_height` | `id \| "*"`, `height` (int, atau `null` = ikuti default) | editor |
| `set_default` | `key, value` | editor |
| `rename_room` | `id, name` | editor, llm |
| `set_room_type` | `id, type` | editor, llm |
| `delete_wall` | `id, reason` | llm, editor, manual |
| `merge_walls` | `ids[], reason` | llm, manual |
| `split_wall` | `id, at_offset` | editor, manual |
| `move_wall` | `id, a?, b?, thickness?, kind?` | editor, manual |
| `add_wall` | `a, b, thickness, kind` | editor, manual |
| `set_door` | `id, door_type?, hinge?, swing?, width?, offset?, height?` | llm, editor, manual |
| `delete_opening` | `id, reason` | llm, editor, manual |
| `add_opening` | `wall_id, category, offset, width, ...` | editor, manual |
| `set_stair` | `id, flights?, landings?, top_z?` | editor, manual |
| `delete_stair` | `id, reason` | llm, editor, manual |
| `add_stair` | `flights, landings?, top_z?` | manual |

Setelah ops diterapkan, core selalu menghitung ulang field turunan (`area_m2`, `perimeter_m`, `gross_area_m2`, `room_id` objek dan tangga, `bounding_walls`, `doors`). Untuk ops yang mengubah dinding, core menjalankan ulang pembentukan ruang. Hasilnya lalu divalidasi. Spec yang gagal aturan berseverity `error` ditolak dengan HTTP 422 dan daftar masalahnya.

## 12. Aturan Validasi

Validator dipakai di tahap 5, di gerbang LLM tahap 6, dan setiap kali ops diterapkan.

| Kode | Aturan | Severity | Bobot skor |
|---|---|---|---|
| V001 | Skala tersedia dan `px_to_mm` valid | error | — |
| V002 | Semua ID unik dan referensi valid (`wall_id`, `room_id`, dst.) | error | — |
| V003 | Tidak ada dinding dengan panjang < 100 mm | warning | 0.02 |
| V004 | Ujung dinding terhubung (jarak ke dinding lain ≤ tebal/2), kecuali `free_ends: true` | warning | 0.15 |
| V005 | Tebal dinding dalam rentang [50, 600] mm, dan konsisten per `kind` (deviasi ≤ 30% dari median) | warning | 0.08 |
| V006 | Dinding ortogonal (±1.5°) terhadap grid, kecuali `allow_skew: true` | warning | 0.08 |
| V007 | Dinding tidak saling tumpang tindih lebih dari 50% panjangnya | warning | 0.08 |
| V008 | Setiap bukaan berada di dalam panjang dinding induknya, dengan margin ≥ 50 mm dari ujung | error | — |
| V009 | Bukaan pada dinding yang sama tidak tumpang tindih | error | — |
| V010 | Lebar pintu dalam rentang [600, 3000] mm (rolling ≤ 6000) | warning | 0.05 |
| V011 | Setiap ruang tertutup (poligon valid, tidak self-intersect) dan luas ≥ 1 m² | error | — |
| V012 | Setiap ruang dengan luas ≥ 4 m² punya minimal satu pintu atau bukaan | warning | 0.12 |
| V013 | Jarak antar-sumbu grid di spec cocok dengan angka dimensi hasil OCR (≤ 0.5%) | warning | 0.12 |
| V014 | Kolom yang bertanda grid berada ≤ 150 mm dari perpotongan grid | warning | 0.05 |
| V015 | Rasio label: ≥ 70% ruang ber-luas ≥ 4 m² punya nama (bukan "") | warning | 0.05 |
| V016 | Objek berada di dalam suatu ruang dan dimensinya dalam batas template | warning | 0.05 |
| V017 | Objek tidak bertabrakan dengan dinding/kolom (AABB terotasi) | info | 0.05 |
| V018 | Cakupan: panjang dinding hasil ≥ 60% dari estimasi panjang garis tebal di gambar | warning | 0.10 |
| V019 | Tangga: tinggi tanjakan 150–200 mm, kedalaman injakan ≥ 250 mm, flight berada di dalam satu ruang | warning | — (tidak masuk skor) |

**Skor validator** = `1 − Σ(bobot × rasio_pelanggaran)`, dibatasi ke [0, 1]. `rasio_pelanggaran` adalah proporsi elemen yang melanggar aturan itu (0–1). Bila ada `error`, kandidat tidak lolos, apa pun skornya.

## 13. `build_input.json` (turunan, untuk builder)

Builder tidak membaca spec mentah. Core menyiapkan `build_input.json` yang sudah "matang", agar builder cukup memakai stdlib + `bpy`:

- `wall_solids`: satu poligon tapak per dinding (sambungan dibagi di garis bagi sudut, tanpa overlap), plus tinggi dan base.
- `wall_union`: union tapak per tinggi, hanya untuk render top-down verifikasi.
- `cutters`: kotak 3D per bukaan (posisi, ukuran, rotasi), untuk boolean.
- `doors`: transform kusen, daftar daun (pivot engsel, lebar, tebal, sudut default 0° = tertutup), dan tipe.
- `windows`: transform dan dimensi.
- `floors`: poligon per ruang dengan nama `room_<id>` + metadata, dan `slabs`: poligon per massa `building_outline`.
- `columns`: tipe, kind, transform, dimensi.
- `stairs`: per flight daftar kotak anak tangga siap ekstrusi (posisi, ukuran, rotasi), plus poligon bordes dengan tinggi masing-masing.
- `objects`: path absolut `asset.glb`, transform final, dan skala per sumbu.
- `materials`: palet per jenis.
- `renders`: daftar kamera yang diminta (top, iso ×4, per ruang).
- `exports`: daftar format yang diminta.

## 14. Contoh (ilustrasi Gatsu, bukan ground truth)

```jsonc
{
  "schema_version": "1.0",
  "meta": {
    "project_id": "msc-gatsu-l1-7f3a", "version": 1, "parent_version": null,
    "created_at": "2026-10-23T09:00:00+07:00", "source": "pipeline", "run_id": "20261023T0900-a1",
    "floor_name": "Lantai 1", "site_type": "data_center", "condition": "existing",
    "image": { "sha256": "…", "width_px": 1600, "height_px": 945, "dpi": null },
    "px_to_mm": [25.85, 0, -5170, 0, -25.85, 15460], "mm_per_px": 25.85,
    "scale_source": "grid_dimensions",
    "defaults": { "wall_height": 3000, "wall_thickness": 150, "door_height": 2100,
                  "window_sill": 900, "window_height": 1200, "floor_to_floor": 4000 }
  },
  "grid": { "axes": [
    { "id": "GA", "label": "A", "orientation": "vertical", "offset": 0 },
    { "id": "GB", "label": "B", "orientation": "vertical", "offset": 6000 },
    { "id": "GC", "label": "C", "orientation": "vertical", "offset": 12000 },
    { "id": "GD", "label": "D", "orientation": "vertical", "offset": 16000 },
    { "id": "GE", "label": "E", "orientation": "vertical", "offset": 22000 },
    { "id": "GF", "label": "F", "orientation": "vertical", "offset": 28000 },
    { "id": "G1", "label": "1", "orientation": "horizontal", "offset": 12000 },
    { "id": "G2", "label": "2", "orientation": "horizontal", "offset": 6000 },
    { "id": "G3", "label": "3", "orientation": "horizontal", "offset": 0 }
  ]},
  "walls": [
    { "id": "W12", "a": [6000, 6000], "b": [16000, 6000], "thickness": 150, "height": null,
      "base_z": 0, "kind": "interior", "grid_ref": ["G2"],
      "provenance": { "source": "cv", "confidence": 0.94, "candidate": "k3", "changed_in": 1 } }
  ],
  "columns": [
    { "id": "C1", "center": [0, 12000], "shape": "h_section", "size": [400, 400], "rotation": 0,
      "kind": "structural", "height": null, "grid_ref": ["GA", "G1"],
      "provenance": { "source": "cv", "confidence": 0.97, "changed_in": 1 } }
  ],
  "openings": [
    { "id": "D3", "category": "door", "wall_id": "W12", "offset": 2200, "width": 1600,
      "height": null, "sill": 0, "door_type": "double_swing", "hinge": "both", "swing": "right",
      "provenance": { "source": "cv", "confidence": 0.81, "changed_in": 1 } }
  ],
  "rooms": [
    { "id": "R2", "name": "R. MEETING", "type": "meeting",
      "polygon": [[6075, 6075], [15925, 6075], [15925, 11925], [6075, 11925]],
      "area_m2": 57.62, "perimeter_m": 31.4, "bounding_walls": ["W12", "W4", "W5", "W6"],
      "doors": ["D3"], "label_pos": [11000, 9000],
      "provenance": { "source": "cv", "confidence": 0.9, "changed_in": 1 } }
  ],
  "stairs": [
    { "id": "S1", "base_z": 0, "top_z": null,
      "flights": [ { "start": [1100, 3800], "end": [1100, 8200], "width": 1100, "risers": 12 },
                   { "start": [4900, 8200], "end": [4900, 3800], "width": 1100, "risers": 12 } ],
      "landings": [ [[550, 8200], [5450, 8200], [5450, 9600], [550, 9600]] ],
      "provenance": { "source": "cv", "confidence": 0.7, "changed_in": 1 } }
  ],
  "objects": [],
  "provenance_log": []
}
```
