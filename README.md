# Floorplan3D

Mengubah denah 2D (gambar atau PDF) menjadi model 3D berskala 1:1: `.blend`, `.glb`, `.fbx`, `.obj`, render, dan dokumen.

Pipeline otomatis membaca grid, skala, dinding, pintu, kolom, tangga, dan ruang (tahap 0–5). Setelah itu pipeline berhenti untuk **review manusia** di editor web. Setelah disetujui, pipeline membangun 3D di Blender dan memverifikasinya (tahap 6–10).

Dokumen produk ada di `PRD/`, rencana dan status milestone di `ROADMAP.md`, dan keputusan benchmark di `benchmarks/DECISIONS.md`.

## Kebutuhan

| Komponen | Versi | Catatan |
|---|---|---|
| Python | 3.12 | lewat [uv](https://docs.astral.sh/uv/) |
| Node.js | 20+ | untuk web (`web/`) |
| Blender | 5.2 LTS | `BLENDER_BIN` harus path biner asli, bukan symlink Homebrew |
| Pango (macOS) | Homebrew | untuk PDF laporan (WeasyPrint) |
| Strata (opsional) | server OpenAI-compatible | review LLM tahap 0 dan 6; pipeline tetap jalan tanpa Strata |

## Setup

```bash
uv sync
cd web && npm install && cd ..
cp .env.example .env    # lalu isi nilainya (lihat di bawah)
```

Isi `.env`. File ini di-gitignore, jangan di-commit.

| Kunci | Isi |
|---|---|
| `DATA_DIR` | folder data (project, run, spec, output), mis. `./data` |
| `BLENDER_BIN` | mis. `/Applications/Blender.app/Contents/MacOS/Blender` |
| `BLENDER_RENDER_DEVICE` | `CPU` atau `GPU` |
| `STRATA_BASE_URL`, `STRATA_MODEL` | URL `/v1` dan ID model server Strata (untuk server DGX kantor, ambil dari dokumentasi API DGX internal) |
| `STRATA_API_KEY` | bearer key server Strata, bila servernya mewajibkan (DGX: wajib) |
| `LLM_TASKS_ENABLED` | tugas LLM aktif, saat ini `T0,T3` (lihat `benchmarks/DECISIONS.md`) |
| `DYLD_FALLBACK_LIBRARY_PATH` | macOS: `/opt/homebrew/lib` untuk WeasyPrint |

## Menjalankan aplikasi

Dua terminal:

```bash
# 1: API + pipeline (port 8000)
uv run --env-file .env uvicorn server.app:app --port 8000

# 2: web (port 5173, /api diteruskan ke 8000)
cd web && npm run dev
```

Buka <http://localhost:5173>.

## Alur penggunaan (E2E)

1. **Project baru.** Upload denah, isi prompt (opsional, mis. "tinggi dinding 4.5 m, pintu 2.4 m"), lalu "Mulai pipeline". Toggle "Berhenti untuk review sebelum build 3D" menyala secara default.
2. **Tunggu tahap 0–5.** Gatsu butuh sekitar 2 menit. Status menjadi **Perlu review**. Bila skor validator terlalu rendah, statusnya **Perlu perhatian**; "Lanjutkan tetap" di tahap 5 melanjutkan tanpa kanvas review.
3. **Buka review.** Di tab Pipeline, buka tahap 5, lalu klik "Buka review". Kanvas review 2D menampilkan hasil ekstraksi di atas gambar asli. Kerjakan daftar **Tugas review** di panel kiri:
   - **Celah terbuka:** klik tugas, lalu klik kedua titik kuning atau tombol "Tutup celah". Centang "Pasang pintu" bila celah itu pintu.
   - **Ruang bocor dan dinding hilang:** pakai Garis bantu (`L`). Tarik garis kasar di atas dinding yang hilang, dan sistem menempelkannya ke garis di gambar. Bila tidak ada garis yang bisa ditempeli, pakai Dinding baru (`W`): klik, klik, berantai, lalu `Esc` untuk berhenti.
   - **Dinding lepas atau palsu:** tarik kotak (marquee), lalu "Hapus N dinding".
   - **Tipe ruang:** klik ruang, lalu pilih tipe. Untuk banyak ruang sekaligus, pakai Shift-klik, lalu "Tipe semua ruang".
4. **Setujui.** Klik "Setujui & build 3D". Koreksi disimpan sebagai versi spec baru, lalu tahap 6–10 berjalan. Tugas yang belum selesai tercatat di run sebagai `review_open`. Review juga bisa dibatalkan ("Batalkan review"), dan run itu tidak dibangun.
5. **Hasil.** Tab Outputs berisi unduhan model, render, dan dokumen. Tab Versions menyimpan riwayat spec, dan versi mana pun bisa di-regenerate.
6. **Edit lanjutan.** Tab Editor berisi editor 3D (Orbit/Top/Walk) dan editor 2D (Plan 2D). Setelah Save, klik Regenerate untuk membangun ulang.

Panduan sesi koreksi berwaktu (untuk kriteria MVP "koreksi ≤ 15 menit") ada di `docs/calibration-correction.md`.

## CLI (tanpa server)

```bash
uv run --env-file .env python -m core.cli build <spec.json> <out_dir> [--image denah.jpg] [--templates data/templates]
```

Perintah ini menjalankan tahap 7–9 (build, verifikasi, laporan) dari sebuah spec.

## Tes dan benchmark

```bash
uv run --env-file .env pytest -q -m "not strata"        # Python (tes Blender butuh BLENDER_BIN dan GPU/akses layar)
uv run ruff check core server benchmarks tests
cd web && npx vitest run && npm run lint && npm run build

uv run --env-file .env python -m benchmarks.failure_modes --fresh --out benchmarks/reports/<nama>   # Gatsu
uv run --env-file .env python -m benchmarks.run_augment_bench --fresh --out benchmarks/reports/<nama>   # 30 varian
uv run --env-file .env python -m benchmarks.run_synth_bench --out benchmarks/reports/<nama>   # 20 denah sintetis
```

## Data dan backup

Semua state ada di `DATA_DIR`:
- `projects/<id>/`: input, run (artefak tiap tahap), spec bervalidasi per versi, dan output;
- `templates/`: template objek;
- `profiles/`: profil parameter ekstraksi.

Backup cukup dengan menyalin `DATA_DIR` saat server berhenti. Server menolak start bila server lain memakai `DATA_DIR` yang sama.

## Troubleshooting

| Gejala | Penyebab dan solusi |
|---|---|
| Blender keluar dengan "Bundled Python not found" | `BLENDER_BIN` menunjuk symlink Homebrew; pakai path biner di dalam `Blender.app` |
| Render atau build Blender abort (`SIGABRT`, rc 134) | proses tidak punya akses GPU atau sesi layar (mis. dari job background atau SSH tanpa sesi login). Jalankan dari Terminal di sesi login, atau set `BLENDER_RENDER_DEVICE=CPU` |
| Strata "401 Unauthorized" | `STRATA_API_KEY` kosong atau salah |
| Strata mati | tahap 6 dilewati, dan pipeline tetap selesai (status Strata terlihat di header) |
| Status tidak pernah "Perlu review" | project dibuat dengan toggle review dimatikan (`review_pause: false`), atau skor tahap 5 terlalu rendah sehingga run berhenti di "Perlu perhatian" |
| Garis bantu: "Tidak ada garis ganda di dekat garis ini" | tarik garis dalam ±250 mm dari garis di gambar, atau pakai Dinding baru |
| PDF laporan gagal di macOS | `brew install pango` dan set `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` |

## Deploy

Satu image Docker berisi API, pipeline, Blender 5.2 (CPU, headless), dan dashboard yang sudah dibuild. Satu port saja: <http://host:8000>.

```bash
# dari root repo; .env dibaca saat run, tidak masuk image
docker compose -f docker/compose.yaml up -d --build
docker compose -f docker/compose.yaml logs -f

# sekali saja di DATA_DIR baru: buat template objek
docker compose -f docker/compose.yaml run --rm floorplan3d python -m core.templates.make_placeholders --out /data/templates
```

- **Data:** `DATA_DIR` host di-mount ke `/data` (default `./data`; ganti dengan `FLOORPLAN_DATA_DIR=/path`). Port host diganti dengan `FLOORPLAN_PORT`.
- **Path di container** menimpa nilai dev di `.env`: `DATA_DIR=/data`, `BLENDER_BIN=/opt/blender/blender`, `BLENDER_RENDER_DEVICE=CPU`.
- **Strata:** `STRATA_*` diambil dari `.env`. Bila Strata jalan di host yang sama, pakai `STRATA_BASE_URL=http://host.docker.internal:<port>/v1`.
- **Versi Blender:** dikunci lewat build arg `BLENDER_VERSION` (default `5.2.2`). Blender hanya tersedia untuk linux-x64, jadi di Mac Apple Silicon image berjalan teremulasi dan lebih lambat.

Deploy ke gspe-ai2 (milestone M7c) menunggu SSH key di server. Lihat `ROADMAP.md`.
