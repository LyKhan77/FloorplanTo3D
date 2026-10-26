# 00 — Overview

> Status: Draft v1 · Tanggal: 2026-10-23 · Kasus acuan: MSC Gatsu Lantai 1 (`floorplan/plan.jpeg`)

## 1. Latar Belakang

Tim perlu mengubah denah 2D site **data hall / data center** menjadi model 3D berskala **1:1**. Model ini dipakai untuk tiga hal: dokumentasi, room tour interaktif, dan perencanaan penempatan perangkat (rack, CRAC, UPS, panel).

Denah yang masuk hampir selalu berupa **gambar (JPEG / PDF raster)**. File CAD asli (DWG/DXF) dianggap tidak tersedia.

Seluruh proses harus memakai **model LLM lokal** (Strata, `qwen3.8-flash-next-iq2_xs`, kuantisasi ±2-bit) di server internal. Model ini tidak sekuat frontier model. Karena itu desain sistem tidak boleh bergantung pada kecerdasan LLM untuk akurasi geometri.

## 2. Visi

> Upload sebuah denah, tulis satu prompt, lalu dapatkan model 3D 1:1 yang bisa diukur, diedit, dan diekspor. Seluruh progres terpantau dari satu dashboard.

## 3. Masalah yang Diselesaikan

| Masalah | Dampak saat ini | Solusi di sistem ini |
|---|---|---|
| Membangun model 3D dari denah dikerjakan manual di Blender | Lama, tidak konsisten antar operator | Pipeline otomatis berbasis spec |
| LLM lokal lemah membaca denah dan menulis kode 3D | Hasil tidak stabil, tidak bisa diulang | Geometri dikerjakan kode deterministik; LLM hanya untuk semantik dan koreksi terbatas |
| Denah komersial penuh anotasi MEP (kabel, panel, label) | Model vision salah mengira anotasi sebagai dinding | Filter CV + validasi aturan + verifikasi LLM berbasis ID |
| Hasil edit 3D sering tidak sinkron dengan dokumen | Versi `.blend`, `.glb`, dan dokumen berbeda-beda | Satu sumber kebenaran: **layout spec** berversi |

## 4. Pengguna

| Persona | Kebutuhan utama |
|---|---|
| **Engineer / planner data center** | Mengukur luas lantai dan tinggi dinding, mencoba layout rack, mengekspor model |
| **Project manager / presales** | Room tour untuk presentasi, dokumen map 3D |
| **Operator pipeline** | Memantau progres dan log, menangani denah yang gagal |
| **Developer pipeline** | Menambah dukungan gaya denah baru, men-tuning ekstraktor |

## 5. Tujuan (Goals)

1. **G1 — Layout 1:1.** Dinding, kolom (termasuk blok sirip/pilaster), pintu, jendela, tangga, lantai, dan ruang direkonstruksi sesuai skala denah, dalam **kondisi existing**. Seluruh denah umum dimodelkan, termasuk pita luar di luar grid. Furnitur dan perangkat tidak. Target galat dimensi ada di `01-requirements.md`.
2. **G2 — Pipeline untuk banyak denah.** Pipeline bisa dipakai untuk denah baru tanpa menulis kode, melalui grid-first, parameter sweep, dan style profile.
3. **G3 — Campur tangan manusia minimal.** Input cukup upload dan prompt. Koreksi manual bersifat opsional dan dilakukan lewat web editor.
4. **G4 — Empat output dari satu spec:**
   - dokumen map 3D (HTML + PDF),
   - file Blender (`.blend`),
   - export 3D (`.glb` utama, `.fbx` dan `.obj` sekunder),
   - web interaktif untuk room tour dan editor.
5. **G5 — Web editor.** Editor bisa mengukur jarak, luas, dan tinggi. Tinggi dinding bisa diubah. Template aset bisa di-drag & drop dan di-resize. Hasil edit tersimpan di server dan bisa di-regenerate ke Blender.
6. **G6 — Dashboard.** Seluruh tahap terpantau dari input sampai output: status, log live, artefak, dan versi.
7. **G7 — LLM lokal yang aman.** Strata hanya boleh memperbaiki hasil. Kontribusinya terukur lewat benchmark.

## 6. Non-Goals (di luar cakupan MVP)

- Ekstraksi **objek interior** dari denah. Rack, panel, dan furnitur berasal dari **library template** yang dibuat di alur kerja terpisah (lihat `10-template-contract.md`).
- Pemodelan **MEP** (jalur kabel, ducting, pipa), walaupun anotasinya ada di denah.
- **Plafon**, **raised floor**, dan detail struktur (balok, pondasi).
- **Multi-lantai** atau penumpukan beberapa denah. Satu denah sama dengan satu lantai.
- Denah **scan miring, foto kamera, atau sketsa tangan**.
- Dinding **lengkung** atau **non-ortogonal** (didukung sebagian, tanpa jaminan akurasi).
- Menggambar atau menyeret geometri dinding/pintu/tangga langsung di viewport. Koreksi geometri di MVP lewat **panel koreksi numerik** (`07-web-editor.md` §6b).
- Kondisi **rencana/proposed**. Model selalu kondisi existing; elemen bertanda PROPOSED/NEW tidak dimodelkan.
- **Railing** tangga dan detail tangga lain di luar anak tangga dan bordes.
- Autentikasi dan multi-tenant. MVP hanya berjalan di LAN internal.
- Rendering fotorealistik.

## 7. Anti-Goals (gagal walaupun "jalan")

- **LLM menulis kode `bpy` bebas di jalur utama.** Hasilnya tidak bisa diulang dan tidak bisa diaudit.
- **Edit yang hilang saat regenerate.** Semua perubahan harus masuk ke spec, bukan langsung ke mesh atau `.blend`.
- **Model terlihat bagus tetapi ukurannya salah.** Akurasi 1:1 lebih penting daripada estetika.
- **Pipeline berhenti total ketika Strata mati.** Pipeline harus tetap menghasilkan output dari CV murni.
- **LLM memperburuk hasil CV.** Setiap perubahan LLM melewati gerbang "terima hanya jika skor naik".

## 8. Prinsip Desain

1. **Spec-centric.** `spec.vN.json` adalah satu-satunya sumber kebenaran. Semua output dibangkitkan darinya.
2. **Deterministik dulu, LLM belakangan.** Kode menangani geometri. LLM hanya menangani keputusan semantik yang sempit.
3. **Terukur.** Setiap tahap menghasilkan artefak dan skor. Setiap fitur LLM diaktifkan hanya jika lolos benchmark.
4. **Degradasi anggun.** Kegagalan satu komponen (Strata, OCR, render) menurunkan kualitas, tetapi tidak menghentikan pipeline.
5. **Grid-first.** Grid struktur dan angka dimensi adalah jangkar skala dan orientasi.

## 9. Glosarium

| Istilah | Arti |
|---|---|
| **Layout spec / spec** | JSON berversi yang mendeskripsikan grid, dinding, kolom, bukaan, ruang, dan objek dalam milimeter |
| **Shell** | Geometri bangunan dari spec: dinding, lantai, kolom, pintu, jendela. Tidak termasuk objek template. |
| **Template** | Paket aset 3D (`asset.glb` + `template.json`) yang bisa ditempatkan di editor |
| **Tahap (stage)** | Langkah pipeline bernomor 0–10 |
| **Kandidat** | Satu hasil ekstraksi dari satu kombinasi parameter dalam parameter sweep |
| **Parameter sweep** | Menjalankan ekstraksi dengan beberapa setelan, lalu memilih kandidat dengan skor validator terbaik |
| **Style profile** | Setelan parameter pemenang yang disimpan per sumber atau gaya gambar, dipakai sebagai titik awal sweep berikutnya |
| **Overlay bernomor (Set-of-Mark)** | Gambar denah yang ditimpa garis berwarna dan label ID (W12, D3, R2) agar LLM bisa menjawab per ID |
| **Validator** | Kumpulan aturan yang memeriksa konsistensi spec dan menghasilkan skor serta daftar masalah |
| **IoU** | Intersection over Union antara mask dinding hasil render top-down dan mask dinding denah asli |
| **Tingkat 1/2/3** | Peran LLM: otomatis di harness / eskalasi chat / developer (lihat `05-llm-review.md`) |
| **Ground truth (GT)** | Spec Gatsu yang dibuat manual dan diverifikasi, dipakai sebagai patokan benchmark |
| **Regenerate** | Menjalankan ulang tahap 7–10 dari spec versi tertentu (default terbaru) |

## 10. Peta Dokumen

| File | Isi |
|---|---|
| `01-requirements.md` | Kebutuhan fungsional dan non-fungsional, kriteria sukses |
| `02-architecture.md` | Komponen, aliran data, topologi deploy |
| `03-layout-spec.md` | Skema spec dan aturan validasi |
| `04-extraction.md` | Tahap 1–5: preprocess sampai validasi |
| `05-llm-review.md` | Tahap 6: peran Strata, tool, gerbang, benchmark |
| `06-builder-outputs.md` | Tahap 7–9: Blender, export, verifikasi, dokumen map |
| `07-web-editor.md` | Editor 3D interaktif |
| `08-dashboard.md` | Topologi UI dashboard, dark mode Carbon g100 |
| `09-api.md` | REST + SSE |
| `10-template-contract.md` | Kontrak paket aset template |
| `11-tech-stack.md` | Tech stack dan struktur repo |
| `12-risks.md` | Risiko, mitigasi, pertanyaan terbuka |
| `../ROADMAP.md` | Milestone, tugas, dependensi, estimasi |
