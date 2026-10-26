# 10 — Kontrak Paket Template

Template adalah aset 3D (rack, CRAC, UPS, panel, battery cabinet, furnitur, dsb.) yang ditempatkan di web editor. Template **dibuat oleh alur kerja terpisah**: dari gambar referensi atau prompt menjadi aset 3D. Alur kerja itu di luar cakupan PRD ini. Dokumen ini hanya mendefinisikan **kontrak** yang harus dipenuhi paket template agar bisa dipakai pipeline dan editor.

## 1. Struktur Paket

```
templates/
  <template_id>/
    <version>/            # semver, mis. 1.0.0
      asset.glb           # wajib
      template.json       # wajib
      thumbnail.png       # wajib, 512×512, latar transparan
      preview.png         # opsional, render besar
```

- `template_id`: kebab-case ASCII, unik, stabil. Contoh: `rack-42u-600x1200`, `crac-downflow-25kw`, `ups-modular-200kva`.
- Versi baru dibuat untuk setiap perubahan aset atau metadata. Versi lama **tidak dihapus**, karena spec merujuk ke (`template_id`, `template_version`).

## 2. `template.json`

```jsonc
{
  "id": "rack-42u-600x1200",
  "version": "1.0.0",
  "name": "Server Rack 42U 600×1200",
  "category": "rack",                 // rack | cooling | power | battery | network | fire | security | furniture | structure | other
  "tags": ["42U", "server", "cabinet"],
  "dims": { "w": 600, "d": 1200, "h": 2000 },   // mm, dimensi bounding box aset pada skala 1
  "pivot": "bottom_center",           // wajib bottom_center
  "front": "+y",                      // arah depan objek dalam koordinat spec saat rotation = 0
  "resizable": {
    "w": false,
    "d": { "min": 1000, "max": 1200, "step": 100 },
    "h": { "min": 1800, "max": 2400, "step": 100 }
  },
  "scale_mode": "stretch",            // stretch (skala non-uniform) | fixed
  "snap": { "grid_mm": 600, "align": "edge" },  // edge | center
  "clearance": { "front": 1200, "back": 1000, "left": 0, "right": 0 },  // mm, untuk visualisasi aisle
  "stackable": false,
  "allowed_room_types": ["data_hall", "mdf"],   // opsional; kosong = semua
  "metadata": { "power_kw": 8, "weight_kg": 120, "vendor": null },       // bebas, ditampilkan di Properties
  "source": { "workflow": "asset-gen", "reference": "…", "created_at": "2026-10-20" },
  "stats": { "triangles": 18200, "materials": 3, "file_bytes": 1840000 }
}
```

| Field | Wajib | Aturan |
|---|---|---|
| `id`, `version` | ya | Harus cocok dengan path folder |
| `name`, `category` | ya | `category` dari enum |
| `dims` | ya | Integer mm > 0. Harus cocok dengan bounding box `asset.glb` dengan galat ≤ 2%. |
| `pivot` | ya | Hanya `bottom_center` |
| `front` | ya | Hanya `+y` di versi kontrak ini (lihat §3) |
| `resizable` | ya | Per sumbu: `false` atau `{min, max, step}` dengan `min ≤ dims ≤ max` |
| `scale_mode` | ya | `fixed` berarti `resizable` semua `false` |
| `snap` | ya | `grid_mm` > 0 |
| `clearance` | tidak | Default 0 |
| `allowed_room_types` | tidak | Editor menampilkan peringatan bila dilanggar, tidak memblokir |
| `metadata`, `source`, `stats` | tidak | Informasi |

## 3. Aturan Geometri `asset.glb`

| Aturan | Nilai |
|---|---|
| Format | glTF 2.0 binary (`.glb`), satu scene, satu root node |
| Satuan | meter (1 unit = 1 m), skala sebenarnya (1:1) |
| Sumbu | glTF standar Y-up |
| Pivot | Origin root node = **tengah-bawah** bounding box (x dan z di tengah, y = 0 di dasar) |
| Arah depan | Sisi depan objek (pintu rack, panel kontrol) menghadap **−Z glTF**, setara **+Y spec** saat `rotation = 0` |
| Transform | Semua transform node sudah di-apply. Root tanpa rotasi/skala. |
| Material | PBR metallic-roughness. Tekstur ≤ 2048 px, PNG/JPEG/KTX2. |
| Anggaran | ≤ 50.000 segitiga, ≤ 8 material, ≤ 10 MB per file |
| Animasi, kamera, lampu | Tidak boleh ada |
| Nama node | Bebas. Root diberi nama `template_root`. |

**Catatan orientasi.** Konversi glTF ke spec adalah `X_gl = x`, `Z_gl = −y` (`03-layout-spec.md` §1). Jadi −Z glTF sama dengan +Y spec (utara di denah), sesuai field `front: "+y"`. Validator template (§5) memeriksa arah ini lewat node opsional `front_marker` (Empty di sisi depan). Bila node itu tidak ada, pemeriksaan diganti dengan cek visual di thumbnail.

## 4. Perilaku di Editor & Builder

- **Penempatan**: `objects[].position` = posisi pivot dalam mm spec. `rotation` = derajat terhadap Z spec.
- **Resize**: `dims` objek yang berbeda dari `template.dims` menghasilkan skala per sumbu = `dims / template.dims`. Skala ini dipakai identik di editor (three.js) dan builder (Blender).
  - `w` → sumbu X lokal, `d` → sumbu Y spec (Z glTF), `h` → sumbu Z spec (Y glTF).
- **Snap**:
  - `align: edge` artinya tepi bounding box objek (setelah rotasi kelipatan 90°) menempel ke garis grid.
  - `align: center` artinya pivot berada di titik grid.
  - Rotasi non-kelipatan 90° menonaktifkan snap edge, dan snap center dipakai sebagai gantinya.
- **Clearance**: kotak transparan di depan/belakang objek, hanya saat objek dipilih atau saat toggle "tampilkan aisle" aktif.
- **Versi**: editor selalu menambahkan objek dengan versi terbaru template. Objek lama tetap memakai versinya. Opsi "perbarui ke versi terbaru" (P2) menghasilkan op `update_object` dengan template_version baru.

## 5. Validasi Template

Script `core/templates/validate.py <path>` dijalankan oleh alur kerja aset sebelum publish, dan oleh server saat memuat registry (template tidak valid disembunyikan dan dicatat di log). Pemeriksaannya:

1. `template.json` lolos JSON Schema (`schema/template.schema.json`).
2. `id`/`version` cocok dengan path.
3. `asset.glb` valid (parse `pygltflib`), satu scene, tanpa animasi/kamera/lampu.
4. Bounding box `asset.glb` cocok dengan `dims` (≤ 2%).
5. Pivot: min Y ≈ 0 (±5 mm), pusat X/Z ≈ 0 (±1% dimensi).
6. Anggaran segitiga, material, ukuran file, dan tekstur.
7. `thumbnail.png` ada, 512×512.
8. Bila ada `front_marker`: posisinya berada di sisi −Z.

Keluaran: `OK`, atau daftar pelanggaran (exit code ≠ 0).

## 6. Template Awal untuk MVP

Untuk pengujian M4 sebelum alur kerja aset siap, disediakan **template placeholder** yang dibangkitkan script (kotak berwarna dengan sisi depan ditandai):

| id | dims (mm) | kategori | resizable |
|---|---|---|---|
| `rack-42u-600x1200` | 600 × 1200 × 2000 | rack | d, h |
| `rack-48u-800x1200` | 800 × 1200 × 2250 | rack | d, h |
| `crac-unit-generic` | 2500 × 900 × 1950 | cooling | w |
| `ups-cabinet-generic` | 1200 × 800 × 2000 | power | w |
| `battery-rack-generic` | 1500 × 750 × 1800 | battery | w |
| `pdu-floor-generic` | 600 × 600 × 1800 | power | — |
| `fire-cylinder-generic` | 400 × 400 × 1800 | fire | — |

Script: `core/templates/make_placeholders.py`, yang membangkitkan `asset.glb` lewat Blender headless beserta `template.json` dan thumbnail.
