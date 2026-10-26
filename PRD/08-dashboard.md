# 08 — Dashboard

Dashboard dan editor adalah **satu aplikasi web** (React + Vite + TypeScript) dengan **`@carbon/react` tema `g100`** (dark) sebagai default. Acuan visual: `DESIGN.md` (Carbon).

## 1. Adaptasi `DESIGN.md` ke Dark Mode

`DESIGN.md` mendokumentasikan Carbon versi **marketing light**. Dokumen itu menyebut dark mode (Gray-100) sebagai *known gap*, dan nilai token front-matter-nya tidak disertakan. Dashboard adalah permukaan **produk**, sehingga dipakai tema resmi **Carbon g100**. Prinsip `DESIGN.md` tetap dipertahankan:

| Prinsip `DESIGN.md` | Diterapkan |
|---|---|
| Sudut 0px di semua tombol, kartu, input | Ya (default Carbon) |
| Hairline 1px, tanpa drop shadow; hierarki lewat perubahan surface | Ya: layer 01/02/03 |
| Satu aksen: IBM Blue | Ya: `#0f62fe` untuk tombol primer dan fokus; `#78a9ff` untuk link di atas gelap |
| IBM Plex Sans, body `letter-spacing: 0.16px` | Ya |
| Display weight 300 | Ya, untuk judul halaman (32–42px). Dashboard padat, jadi display 60–76px tidak dipakai. |
| Grid 4px, spacing token Carbon | Ya |
| Semantic green/yellow/red | Ya (varian g100) |
| "No mono" | **Penyimpangan**: log, ID elemen, dan nilai numerik memakai **IBM Plex Mono**. Ini sesuai panduan Carbon untuk permukaan produk. |

### 1.1 Token g100 yang dipakai

| Token | Nilai | Penggunaan |
|---|---|---|
| `background` | `#161616` | Kanvas halaman |
| `layer-01` | `#262626` | Panel, kartu, tabel |
| `layer-02` | `#393939` | Panel di atas panel, baris hover |
| `layer-03` | `#525252` | Elemen di atas layer-02 |
| `border-subtle-01` | `#393939` | Hairline pemisah |
| `border-strong-01` | `#6f6f6f` | Garis bawah input |
| `text-primary` | `#f4f4f4` | Teks utama |
| `text-secondary` | `#c6c6c6` | Meta, label |
| `text-helper` / placeholder | `#a8a8a8` / `#6f6f6f` | Helper text |
| `interactive` / `button-primary` | `#0f62fe` (hover `#0050e6`, active `#002d9c`) | Tombol primer |
| `link-primary` | `#78a9ff` | Link |
| `focus` | `#ffffff` | Ring fokus (g100) |
| `support-success` | `#42be65` | Status sukses |
| `support-warning` | `#f1c21b` | Peringatan, `needs_attention` |
| `support-error` | `#fa4d56` | Gagal |
| `support-info` | `#4589ff` | Info, `running` |

Viewport 3D editor memakai latar `#161616` dengan grid lantai `#393939`.

## 2. Topologi Halaman

```
App Shell (Carbon UI Shell: Header 48px + SideNav)
├─ /projects                      Daftar project
├─ /projects/new                  Project baru
├─ /projects/:id                  Detail project (tab)
│   ├─ ?tab=pipeline   (default)  Timeline tahap + artefak
│   ├─ ?tab=logs                  Log live
│   ├─ ?tab=review                Overlay bernomor, masalah validator, transkrip Strata
│   ├─ ?tab=editor                Web editor (07-web-editor.md)
│   ├─ ?tab=outputs               Unduhan per versi + pratinjau dokumen
│   └─ ?tab=versions              Riwayat spec + diff
├─ /templates                     Library template (read-only di MVP)
└─ /system                        Kesehatan: Strata, worker Blender, antrean, versi
```

### 2.1 Header global

Header berisi logo teks "Floorplan3D", navigasi, dan di kanan **indikator kesehatan** dengan tiga titik status:
- **Strata**: hijau idle / biru processing / merah mati,
- **Blender worker**: idle / busy,
- **Antrean**: jumlah run menunggu.

Klik indikator untuk membuka `/system`.

## 3. Halaman

### 3.1 `/projects`: daftar project

- Carbon `DataTable` dengan sort, search, dan pagination.
- Kolom: Nama · Lantai · Status (Tag berwarna) · Tahap aktif · Skor validator · IoU · Versi · Diperbarui.
- Status: `queued` (abu), `running` (biru + spinner), `succeeded` (hijau), `needs_attention` (kuning), `failed` (merah).
- Aksi baris (overflow menu): Buka, Jalankan ulang, Regenerate, Hapus (konfirmasi, P1).
- Tombol primer kanan atas: **Project baru**.
- *Empty state*: ilustrasi minimal ditambah tombol "Upload denah pertama".

### 3.2 `/projects/new`: project baru

Form satu kolom (max 672px):
1. **File denah**: Carbon `FileUploaderDropContainer` (JPEG/PNG/PDF, ≤ 50 MB), dengan pratinjau thumbnail. Untuk PDF ada pemilih halaman.
2. **Nama project**: default dari nama file.
3. **Prompt**: `TextArea`, contoh placeholder: "Data hall lantai 1, tinggi dinding 4.5 m, pintu 2.4 m".
4. **Parameter lanjutan** (Accordion, tertutup): tinggi dinding, tinggi pintu, tebal dinding default, nama lantai, tipe site, skala manual (mm per px atau "dimensi A–F = 28000 mm"), style profile (Dropdown), dan toggle "Gunakan Strata".
5. Tombol **Mulai pipeline** (primer) dan Batal (ghost).

Setelah submit, pengguna diarahkan ke `/projects/:id?tab=pipeline` dan run langsung berjalan.

### 3.3 `/projects/:id`: detail project

**Header halaman**: nama project (display 32px weight 300), tag status, versi HEAD, dan tombol aksi:
- `Jalankan ulang ▾`: full / dari tahap…,
- `Regenerate`,
- `Batalkan run` (bila running).

#### Tab Pipeline (default)

```
┌ ProgressIndicator vertikal ────┬ Panel tahap terpilih ────────────────────────────┐
│ ● 0 Input           0.2s  ✓    │ 3 · Ekstraksi                    ✓ 24.1s         │
│ ● 1 Preprocess      1.1s  ✓    │ ┌ Kandidat sweep (DataTable) ─────────────────┐  │
│ ● 2 Grid & skala    3.4s  ✓    │ │ k  strategi  t_min  skor  dinding  pintu   │  │
│ ● 3 Ekstraksi      24.1s  ✓    │ │ k3 S2        150    0.91  48       17  ★   │  │
│ ● 4 Ruang           2.0s  ✓    │ │ k1 S1        80     0.74  61       12      │  │
│ ● 5 Validasi        0.6s  ✓    │ └────────────────────────────────────────────┘  │
│ ◐ 6 Review Strata   …     ⟳    │ ┌ Artefak ──────────────────────────────────┐   │
│ ○ 7 Build                      │ │ [overlay.png — zoom/pan, toggle layer]     │   │
│ ○ 8 Verifikasi                 │ └────────────────────────────────────────────┘   │
│ ○ 9 Dokumen                    │ Log tahap ini (20 baris terakhir) → Lihat semua  │
│ ○ 10 Siap                      │                                                  │
└────────────────────────────────┴──────────────────────────────────────────────────┘
```

- `ProgressIndicator` vertikal (Carbon), dengan status per tahap dan durasi. Klik tahap untuk menampilkan panelnya.
- Konten panel per tahap:
  - **0**: prompt, parameter final (tabel: eksplisit / parse / default).
  - **1**: `page.png` sebelum-sesudah, sudut deskew.
  - **2**: overlay grid, tabel sumbu, persamaan skala + residu.
  - **3**: tabel kandidat, overlay kandidat terpilih atau lainnya (Dropdown).
  - **4**: overlay ruang, tabel ruang (nama, tipe, luas).
  - **5**: skor + rincian per aturan (bar), tabel masalah (kode, severity, elemen, pesan). Klik elemen untuk menyorotnya di overlay.
  - **6**: ringkasan (diterima/ditolak/tanpa konsensus), link ke tab Review.
  - **7**: log Blender, daftar file export dengan ukuran.
  - **8**: IoU (angka besar + ambang), gambar `iou_mask.png` dengan legenda, cek dimensi.
  - **9**: pratinjau `report.html` (iframe), unduh PDF.
  - **10**: tombol "Buka editor".
- Saat run berjalan, panel tahap aktif terbuka otomatis dan diperbarui lewat SSE.

#### Tab Logs

- Viewer log virtualized (tahan > 100.000 baris), Plex Mono 12px, latar `layer-01`.
- Filter: run (Dropdown), tahap (MultiSelect), level (debug/info/warn/error), pencarian teks.
- Toggle **Ikuti** (auto-scroll). Tombol unduh `events.jsonl` untuk run terpilih.
- Format baris: `HH:MM:SS.mmm  [S3]  INFO  pesan`. Level warn kuning dan error merah, hanya pada label levelnya, agar tidak mencolok.

#### Tab Review

- Kiri: **overlay bernomor** interaktif (zoom/pan, toggle layer dinding/pintu/kolom/ruang, hover ID untuk tooltip).
- Kanan atas: **tabel masalah validator** tersisa.
- Kanan bawah: **keputusan Strata** (DataTable: elemen, tugas, jawaban per suara, keputusan, skor sebelum→sesudah). Klik baris untuk menampilkan crop yang dikirim ke Strata beserta respons mentahnya.
- Bila tahap 6 `skipped`: banner info berisi alasan (Strata mati / dinonaktifkan).
- (P2) Panel chat eskalasi Tingkat 2.

#### Tab Editor

Web editor penuh (`07-web-editor.md`). Header halaman diringkas agar viewport maksimal.

#### Tab Outputs

- Pemilih versi (Dropdown, default HEAD yang punya output).
- Kartu per file: nama, ukuran, tanggal, tombol Unduh. File: `.blend`, `shell.glb`, `layout_full.glb`, `.fbx`, `.obj`, `report.pdf`, `report.html` (zip dengan renders).
- Pratinjau dokumen (iframe) dan galeri render.
- Tombol "Unduh semua (zip)".

#### Tab Versions

- Daftar versi: nomor, sumber (pipeline/llm/editor/manual), waktu, pesan, run terkait, dan apakah output tersedia.
- **Diff ringkas** antara dua versi: jumlah elemen ditambah/dihapus/diubah per tipe, ditambah daftar ops (`provenance_log`).
- Aksi: "Jadikan basis editor", "Regenerate versi ini". Versi tidak pernah dihapus.

### 3.4 `/templates`

Grid kartu template (thumbnail, nama, kategori, dimensi, versi) dengan filter kategori. Klik untuk membuka pratinjau 3D kecil dan isi `template.json`. Upload template **di luar cakupan** MVP: template ditambahkan oleh alur kerja aset terpisah ke folder `templates/`.

### 3.5 `/system`

- **Strata**: base URL, model, status `/health`, `/status`, latensi ping, tugas LLM aktif (dari konfigurasi), dan tautan laporan benchmark terakhir.
- **Blender**: path, versi, mode render, job aktif.
- **Antrean**: daftar run menunggu atau berjalan.
- **Versi aplikasi**: commit, versi skema spec.

## 4. Pola Real-time

- Satu koneksi SSE per halaman detail: `GET /api/projects/{id}/events?since=<seq>`. Koneksi ulang otomatis dengan `Last-Event-ID`.
- Halaman daftar project: polling `GET /api/projects` setiap 5 detik (cukup untuk MVP).
- Event yang mengubah UI: `run.*`, `stage.*`, `spec.created`, `output.ready` (lihat `09-api.md` §4).

## 5. Status Visual

| Status | Ikon (Carbon) | Warna | Teks |
|---|---|---|---|
| pending | `CircleDash` | `#6f6f6f` | Menunggu |
| running | `InProgress` (animasi) | `#4589ff` | Berjalan |
| succeeded | `CheckmarkFilled` | `#42be65` | Selesai |
| succeeded + warning | `WarningAltFilled` | `#f1c21b` | Selesai dengan peringatan |
| needs_attention | `WarningFilled` | `#f1c21b` | Perlu perhatian |
| failed | `ErrorFilled` | `#fa4d56` | Gagal |
| skipped | `SubtractAlt` | `#8d8d8d` | Dilewati |

Status tidak pernah disampaikan hanya lewat warna: selalu ada ikon dan teks (aksesibilitas).

## 6. Responsif & Aksesibilitas

| Lebar | Perilaku |
|---|---|
| ≥ 1312px | Layout penuh |
| 1056–1311px | Panel tahap menyempit, panel editor bisa dilipat |
| 672–1055px | Dashboard read-only, ProgressIndicator horizontal. Editor menampilkan pesan "butuh layar ≥ 1056px". |
| < 672px | Daftar project dan status saja |

- Kontras teks ≥ 4.5:1 (token g100 sudah memenuhi).
- Semua aksi bisa dicapai dengan keyboard. Fokus terlihat (ring putih g100).
- Target sentuh 48px pada perangkat sentuh.

## 7. Komponen Carbon yang Dipakai

`Header`, `SideNav`, `DataTable`, `ProgressIndicator`, `Tabs`, `Tag`, `Button`, `OverflowMenu`, `FileUploaderDropContainer`, `TextArea`, `TextInput`, `NumberInput`, `Dropdown`, `MultiSelect`, `Accordion`, `Modal`, `InlineNotification`, `ToastNotification`, `Loading`, `InlineLoading`, `Tooltip`, `Toggle`, `CodeSnippet` (untuk JSON). Ikon dari `@carbon/icons-react`.
