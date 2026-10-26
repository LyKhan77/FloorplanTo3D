# 02 — Architecture

## 1. Prinsip Arsitektur: Spec-Centric

```
                ┌──────────────────────────────┐
                │   spec.vN.json (append-only) │  ← satu-satunya sumber kebenaran
                └──────────────┬───────────────┘
        ditulis oleh           │            dibaca oleh
  ┌───────────────┬────────────┼──────────────┬──────────────────┐
  │ Ekstraksi CV  │ Strata     │ Web editor   │ Builder Blender  │
  │ (tahap 1–5)   │ (tahap 6)  │ (ops → v+1)  │ (tahap 7–9)      │
  └───────────────┴────────────┴──────────────┴──────────────────┘
```

Aturan:
1. **Hanya spec yang diedit.** `.blend`, `.glb`, dan dokumen adalah turunan, tidak pernah diedit langsung.
2. **Setiap perubahan menghasilkan versi baru**, berlaku untuk perubahan dari pipeline, Strata, maupun editor. Versi lama tidak ditimpa.
3. **Output terikat pada versi.** Output untuk `spec.v7` disimpan di `outputs/v7/`.

## 2. Komponen

```
┌────────────────────────── Browser ──────────────────────────┐
│  Web App (React + Carbon g100)                              │
│   ├─ Dashboard (projects, timeline, logs, artefak, versi)   │
│   └─ Editor 3D (react-three-fiber)                          │
└───────────────▲───────────────────────────┬─────────────────┘
                │ REST + SSE                │ GET glb/png/pdf
┌───────────────┴───────────────────────────▼─────────────────┐
│  API Server (FastAPI)                                       │
│   ├─ Project & spec service (versioning, ops apply)         │
│   ├─ Run orchestrator (state machine tahap 0–10)            │
│   ├─ Job queue (single worker, subprocess)                  │
│   ├─ Event bus → events.jsonl → SSE                         │
│   └─ Template registry                                      │
└──────┬──────────────────┬───────────────────┬───────────────┘
       │ import (in-proc) │ subprocess        │ HTTP (OpenAI API)
┌──────▼──────────┐ ┌─────▼──────────────┐ ┌──▼─────────────────┐
│ core (Python)   │ │ builder            │ │ Strata (LLM lokal) │
│  extraction     │ │ blender -b -P      │ │ gspe-ai2:8081      │
│  validator      │ │ build.py spec.json │ │ qwen3.8-flash-next │
│  llm_review     │ │ (Python Blender)   │ │ iq2_xs             │
│  spec (Pydantic)│ └────────────────────┘ └────────────────────┘
│  report (Jinja) │
└─────────────────┘
       │ baca/tulis
┌──────▼──────────────────────────────────────────────────────┐
│ Filesystem: projects/<id>/ · templates/ · profiles/         │
└─────────────────────────────────────────────────────────────┘
```

| Komponen | Tanggung jawab | Tidak boleh |
|---|---|---|
| **core** | Library Python murni. Berisi algoritma tahap 1–6, model spec (Pydantic), validator, apply ops, dan generator laporan. | Import `bpy`; I/O jaringan selain ke Strata |
| **builder** | Script yang dijalankan di dalam Blender. Membaca `build_input.json`, membangun scene, mengekspor, dan merender. | Import library di luar stdlib + `bpy`; memvalidasi semantik (diasumsikan sudah divalidasi core) |
| **server** | Lapisan HTTP, orchestrator, antrean, event, dan penyimpanan. | Logika geometri (didelegasikan ke core) |
| **web** | UI dashboard + editor. Mengirim *operasi* ke server. | Memodifikasi mesh sebagai sumber kebenaran |
| **Strata** | Layanan eksternal (OpenAI-compatible). | Dipanggil oleh siapa pun selain modul `core.llm_review` / parser prompt |

## 3. Aliran Data Pipeline

```
upload ─► [0 Input] ─► [1 Preprocess] ─► [2 Grid & Skala] ─► [3 Ekstraksi ×K kandidat]
      ─► [4 Ruang ×K] ─► [5 Validasi + pilih kandidat] ─► spec.v1 (source=pipeline)
      ─► [6 Review Strata] ─► spec.v2 (source=llm)  (dilewati jika nonaktif/mati)
      ─► [7 Build Blender] ─► [8 Verifikasi IoU] ─► [9 Dokumen] ─► [10 Siap di editor]

editor save ─► ops ─► spec.v(N+1) (source=editor) ─► Regenerate ─► [7] ─► [8] ─► [9] ─► [10 publish]
```

### 3.1 State machine run

Status per tahap: `pending → running → succeeded | failed | skipped | needs_attention`.

| Transisi | Kondisi |
|---|---|
| `running → failed` | Exception tak tertangani atau timeout tahap |
| `running → needs_attention` | Hasil valid tetapi di bawah ambang batas (mis. skala tidak bisa dihitung, skor validator < 0.6, IoU < 0.7) |
| `running → skipped` | Tahap dinonaktifkan konfigurasi, atau dependensi opsional (Strata) tidak tersedia |
| Run berlanjut setelah `needs_attention` | Hanya untuk tahap 6 dan 8 (peringatan). Tahap 2 dan 5 menghentikan run. |

Run bisa dimulai dari tahap mana pun (`from_stage`), asalkan artefak tahap sebelumnya ada.

### 3.2 Jenis run

| Jenis | Tahap | Pemicu |
|---|---|---|
| `full` | 0–10 | Project baru atau re-ekstraksi |
| `from_stage` | n–10 | Ulang dari tahap tertentu (mis. setelah ganti profile) |
| `regenerate` | 7–10 | Save dari editor atau tombol Regenerate |

**Re-ekstraksi pada project yang sudah diedit.** Run `full`/`from_stage` (n ≤ 5) pada project yang HEAD-nya sudah berisi edit dari editor tidak membuang edit tersebut. Spec baru dari tahap 5 menjalani **carry-over** terhadap HEAD sebelum disimpan (lihat `04-extraction.md` §5.4b). Hasilnya disimpan sebagai versi berikutnya, bukan sebagai v1.

**Istilah HEAD** hanya berarti versi spec terbaru (`specs/HEAD`). Versi output yang dimuat editor disebut "versi output terbaru".

## 4. Struktur Penyimpanan

```
projects/<project_id>/
  project.json                 # nama, dibuat, parameter, status ringkas, versi terbaru
  input/
    original.<ext>             # file asli, tidak diubah
    input.json                 # prompt, parameter eksplisit, hasil parse prompt, sha256
  runs/<run_id>/
    run.json                   # jenis, from_stage, status per tahap, durasi, versi kode
    stages/
      01_preprocess/  page.png, meta.json
      02_grid/        grid.json, overlay.png
      03_extract/     candidates/<k>/{params.json, elements.json, overlay.png}
      04_rooms/       candidates/<k>/{rooms.json, overlay.png}
      05_validate/    scores.json, issues.json, chosen.json, overlay_ids.png
      06_review/      transcript.jsonl, decisions.json, crops/*.png
      07_build/       build_input.json, blender.log
      08_verify/      top.png, iou_mask.png, verify.json
      09_report/      report.html, report.pdf, renders/*.png
  specs/
    spec.v1.json  spec.v2.json  ...   # append-only
    HEAD                              # berisi nomor versi terbaru
  outputs/v<N>/
    layout.blend  shell.glb  layout_full.glb  layout.fbx  layout.obj
    report.html  report.pdf  renders/
  events.jsonl                 # semua event, semua run (append-only)

templates/<template_id>/<version>/  asset.glb  template.json  thumbnail.png
profiles/<profile_id>.json          # style profile hasil sweep
benchmarks/<plan_id>/               # ground truth + crop berlabel untuk benchmark LLM
```

`project_id` berbentuk slug + sufiks acak pendek (mis. `msc-gatsu-l1-7f3a`). `run_id` berbentuk timestamp ISO + sufiks.

## 5. Model Proses

- **Server** adalah satu proses Uvicorn. Orchestrator berjalan sebagai task asyncio di proses yang sama.
- **Tahap 1–6** dijalankan dalam *worker process* terpisah (`multiprocessing`), agar CV yang berat tidak memblokir event loop dan crash tidak menjatuhkan server.
- **Tahap 7–9** memanggil `blender -b --factory-startup -P builder/build.py -- <build_input.json> <out_dir>` sebagai subprocess. Stdout Blender diteruskan ke event log.
- **Antrean**: dua antrean FIFO global, masing-masing dengan satu worker:
  - **antrean analisis** untuk tahap 0–6 (CV + Strata),
  - **antrean Blender** untuk tahap 7–10 (NFR-RL-04).

  Akibatnya, Regenerate dari editor tidak menunggu review Strata milik project lain. Satu run berpindah dari antrean analisis ke antrean Blender setelah tahap 6. Antrean disimpan di memori dan dipulihkan dari `run.json` saat server restart. Run berstatus `running` ditandai `failed (interrupted)`.
- **Event**: tiap tahap memanggil `emit(event)`. Event ditulis ke `events.jsonl`, lalu dipublikasikan ke subscriber SSE.

## 6. Topologi Deploy

### 6.1 Development (Mac M4)

```
Mac M4: web (vite dev :5173) ─► server (uvicorn :8000) ─► core, builder (Blender 5.2 lokal)
                                         └──────────► Strata @ 192.168.2.142:8081 (LAN/VPN)
```

### 6.2 Production MVP (gspe-ai2 · 192.168.2.142)

```
gspe-ai2
 ├─ Strata (sudah ada, :8081, memakai GPU)
 └─ Docker: floorplan3d
      ├─ server (uvicorn :8000) + web build statis (disajikan server)
      ├─ Blender 5.2 headless (CPU / Workbench + Eevee)
      └─ volume: /data/projects, /data/templates, /data/profiles
```

- Blender di server dijalankan dalam **mode CPU**, atau dengan render ringan (Workbench) untuk verifikasi, agar tidak berebut VRAM dengan Strata. Render dokumen memakai Eevee bila GPU bebas. Ini dikonfigurasi lewat `BLENDER_RENDER_DEVICE`.
- Path project di server: `/home/gspe-ai2/project_AI/floorplan3d/`.

## 7. Konfigurasi

Semua konfigurasi dibaca dari environment / `.env`:

| Variabel | Default | Arti |
|---|---|---|
| `DATA_DIR` | `./data` | Root `projects/`, `templates/`, `profiles/` |
| `BLENDER_BIN` | `blender` | Path binary Blender |
| `BLENDER_RENDER_DEVICE` | `CPU` | `CPU` atau `GPU` |
| `STRATA_BASE_URL` | `http://192.168.2.142:8081/v1` | Endpoint Strata |
| `STRATA_MODEL` | `qwen3.8-flash-next-iq2_xs` | Model ID |
| `STRATA_TIMEOUT_S` | `120` | Timeout per panggilan |
| `LLM_TASKS_ENABLED` | `` (kosong) | Daftar tugas LLM aktif, mis. `T1,T3` |
| `LLM_MAX_ITER` | `5` | Iterasi maksimal loop review |
| `LLM_VOTES` | `3` | Jumlah suara self-consistency |
| `SWEEP_MAX_CANDIDATES` | `12` | Batas kandidat sweep |
| `MAX_UPLOAD_MB` | `50` | Batas upload |

## 8. Keputusan Arsitektur (ADR ringkas)

| # | Keputusan | Alasan | Alternatif ditolak |
|---|---|---|---|
| ADR-1 | Spec JSON berversi sebagai sumber kebenaran | Sinkronisasi semua output; edit tidak hilang | Edit langsung `.blend` / `.glb` |
| ADR-2 | Builder Blender headless deterministik, bukan agen + Blender MCP | Bisa diulang dan diaudit; model 2-bit tidak menulis kode | Agen penuh via MCP |
| ADR-3 | Web memuat shell dari Blender (`shell.glb`) dan menempatkan objek dari spec | Satu builder geometri, jadi 1:1 konsisten | Builder geometri kedua di JS |
| ADR-4 | Filesystem, bukan database | Sederhana, bisa diaudit, cukup untuk MVP | PostgreSQL/SQLite sejak awal |
| ADR-5 | Dua antrean di memori (analisis, Blender), masing-masing satu worker | Cukup untuk volume MVP; menghindari kontensi Blender; regenerate tidak terblokir Strata | Celery + Redis |
| ADR-6 | Strata hanya di tahap 6 dan parse prompt, dengan gerbang skor | Model lemah tidak boleh memperburuk hasil | LLM di semua tahap |
| ADR-7 | Builder hanya bergantung pada stdlib + `bpy` | Python bawaan Blender tidak berbagi venv dengan core | Memasang Pydantic/Shapely ke Python Blender |
| ADR-8 | Ekstraksi CV klasik khusus (grid-first, S1/S2, mask simbol), **tanpa** model segmentasi terlatih di MVP | Uji 2026-10-26 pada `plan.jpeg`: UNet CubiCasa5K (Yytsi/floorplan-to-3d) hanya menandai 0.5–3% piksel sebagai dinding, terfragmentasi, dan salah menandai blok sirip sebagai pintu. Filter dinding FloorplanToBlender3d hanya menangkap blob panel MEP. Domain residensial Nordik ≠ denah komersial garis ganda + anotasi MEP. Bobot CubiCasa juga berisiko lisensi (dataset CC BY-NC 4.0), dan kode FloorplanToBlender3d GPL-3. | Memakai salah satu repo itu langsung; fine-tune UNet (ditunda sampai ada ≥ 20 denah nyata/sintetis berlabel, backlog) |
