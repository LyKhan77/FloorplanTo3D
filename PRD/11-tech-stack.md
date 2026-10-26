# 11 — Tech Stack

Disepakati 2026-10-23. Versi di-pin di `pyproject.toml` / `uv.lock` dan `package.json` / lockfile.

## 1. Ringkasan

| Lapisan | Pilihan | Alasan | Alternatif (bila perlu) |
|---|---|---|---|
| Bahasa inti | **Python 3.12** (venv via `uv`) | Satu bahasa untuk CV, server, dan persiapan builder. Python 3.14 di mesin dev terlalu baru: wheel OpenCV/ONNX Runtime sering belum tersedia. | — |
| Input PDF | **PyMuPDF** | Render raster 300 dpi; membaca path dan teks vektor (P2) | pdf2image + poppler |
| CV | **OpenCV** (`opencv-python-headless`), **NumPy**, **scikit-image** | Morfologi, LSD, HoughCircles, skeletonize, contour | — |
| OCR | **RapidOCR** (`rapidocr-onnxruntime`, model PaddleOCR via ONNX) | Akurasi setara PaddleOCR, install `pip` mudah, CPU, jalan di ARM Mac & Linux | PaddleOCR (install berat), Tesseract (lemah untuk teks dimensi kecil) |
| Geometri 2D | **Shapely 2** | Buffer, union, polygonize, luas, snapping | — |
| Skema & validasi | **Pydantic v2** | Model spec, ops, PromptParams, schema output LLM; ekspor JSON Schema | — |
| Tipe frontend | **json-schema-to-typescript** | Membangkitkan `spec.ts` dari JSON Schema | — |
| Klien LLM | **SDK `openai`** (Python) | Strata kompatibel OpenAI, termasuk tool calling dan `reasoning_effort` | `httpx` langsung |
| Builder 3D | **Blender 5.2 LTS** headless, `bpy` + bmesh | Export glTF/FBX/OBJ bawaan, Boolean EXACT, Eevee/Workbench | — |
| Parser glTF (verifikasi) | **pygltflib** | Cek bounding box pasca-export tanpa Blender | trimesh |
| Laporan | **Jinja2** + **WeasyPrint** | Satu template untuk HTML dan PDF | Playwright print-to-PDF |
| Backend | **FastAPI** + **Uvicorn** | Async, SSE via `StreamingResponse`, OpenAPI otomatis | — |
| Antrean/job | asyncio + `multiprocessing` + `asyncio.subprocess` | Satu worker, tanpa infrastruktur tambahan | Celery/RQ + Redis (bila job paralel) |
| Penyimpanan | Filesystem (`DATA_DIR`) | Bisa diaudit, append-only, cukup untuk MVP | SQLite (indeks project) |
| Frontend | **React 18** + **Vite** + **TypeScript** | Ekosistem 3D (R3F) dan Carbon React | — |
| UI kit | **`@carbon/react`** (tema `g100`), `@carbon/icons-react`, font IBM Plex | Implementasi resmi `DESIGN.md`, dark mode bawaan | — |
| 3D web | **three.js** via **@react-three/fiber** + **@react-three/drei** | `TransformControls`, `OrbitControls`, `PointerLockControls`, `useGLTF`, instancing | three.js murni |
| State editor | **Zustand** | Store ringan untuk ops lokal dan seleksi | React context |
| Data fetching | **TanStack Query** | Cache, refetch, status request | fetch + useEffect |
| Viewer log | **react-virtuoso** (atau sejenis) | Daftar virtualized untuk log panjang | — |
| Test Python | **pytest** | Unit + integrasi + benchmark | — |
| Test web | **Vitest** (reducer ops, util ukur) + **Playwright** (1–2 smoke test E2E, P1) | — | — |
| Lint/format | **ruff** (Python), **ESLint** + **Prettier** (TS) | — | — |
| Deploy | **Docker** (image Ubuntu + Blender 5.2 + Python 3.12) di gspe-ai2 | Satu mesin dengan Strata | venv + systemd |
| Blender MCP | Opsional (Tingkat 2 / developer) | Tidak dipakai di jalur utama | — |

Semua dependensi Python dan npm di atas bersifat open-source dengan lisensi permisif (MIT/BSD/Apache). Pengecualian: **PyMuPDF (AGPL)** dan **Blender (GPL, dijalankan sebagai proses terpisah)**. Lisensi PyMuPDF perlu dicek untuk penggunaan internal (lihat `12-risks.md` R-14).

## 2. Batas Lingkungan Python

```
venv inti (Python 3.12, uv)                  Python bawaan Blender 5.2
──────────────────────────────               ──────────────────────────
core/  server/  benchmarks/                  builder/build.py
OpenCV, Shapely, Pydantic, RapidOCR,         stdlib + bpy + bmesh SAJA
FastAPI, Jinja2, WeasyPrint, openai
        │                                            ▲
        └──── build_input.json (sudah matang) ───────┘
```

- Builder **tidak** mengimpor modul dari `core/`, agar tidak bergantung pada versi Python Blender. Satu-satunya kontrak adalah `build_input.json` (`03-layout-spec.md` §13).
- Builder punya test sendiri yang dijalankan dengan `blender -b -P builder/tests/run.py`.

## 3. Struktur Repo (monorepo)

```
floorplan3d_blender/
├─ PRD/                       dokumen ini
├─ ROADMAP.md
├─ DESIGN.md                  acuan visual (Carbon)
├─ pyproject.toml  uv.lock    proyek Python (core + server + benchmarks)
├─ core/
│  ├─ spec/                   model Pydantic, ops, apply, validator, schema export
│  ├─ extraction/             tahap 0–5 (preprocess, grid, walls, doors, columns, rooms, sweep)
│  ├─ llm_review/             klien Strata, tugas T0–T4, harness, prompts/
│  ├─ build_prep/             spec → build_input.json (union dinding, cutter, transform)
│  ├─ verify/                 IoU, cek dimensi, cek glb
│  ├─ report/                 Jinja2 template, renderer HTML/PDF
│  └─ templates/              registry, validate.py, make_placeholders.py
├─ builder/
│  ├─ build.py                entry point Blender
│  ├─ scene/                  walls.py, doors.py, floors.py, columns.py, objects.py, materials.py, cameras.py
│  └─ tests/
├─ server/
│  ├─ app.py                  FastAPI app
│  ├─ routes/                 projects, runs, specs, outputs, events, templates, system
│  ├─ orchestrator.py         state machine + antrean
│  ├─ events.py               event bus, events.jsonl, SSE
│  └─ storage.py              akses DATA_DIR yang aman
├─ web/
│  ├─ package.json  vite.config.ts
│  └─ src/
│     ├─ app/                 shell, routing, tema g100
│     ├─ pages/               projects, new, detail (tabs), templates, system
│     ├─ editor/              viewport, tools (measure, transform), library, properties, ops reducer
│     ├─ components/          StageTimeline, LogViewer, OverlayViewer, IssueTable, …
│     ├─ api/                 klien + hooks TanStack Query + SSE
│     └─ types/spec.ts        (generated)
├─ schema/                    layout-spec.schema.json, template.schema.json (generated)
├─ benchmarks/
│  ├─ gatsu/                  gt_spec.json, fewshot/, items/
│  ├─ run_extraction_bench.py
│  ├─ run_llm_bench.py
│  ├─ reports/
│  └─ DECISIONS.md
├─ floorplan/                 denah contoh (plan.jpeg)
├─ data/                      DATA_DIR dev (gitignored)
├─ docker/                    Dockerfile, compose.yaml
├─ .env.example
└─ .gitignore                 data/, .env, server-info.txt, node_modules, .venv
```

## 4. Prasyarat Lingkungan Dev (Mac M4)

| Kebutuhan | Status saat ini | Tindakan |
|---|---|---|
| Blender 5.2.2 LTS | Terpasang | `BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender`. Symlink `/opt/homebrew/bin/blender` crash ("Bundled Python not found"); `core/config.py` me-resolve symlink otomatis. |
| uv | Terpasang | `uv python install 3.12` |
| Node 24 + npm | Terpasang | — |
| Docker | Terpasang | Untuk uji image deploy |
| WeasyPrint deps (pango, cairo) | Terpasang (M0) | `brew install pango` + `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` di `.env` |
| Akses ke Strata | Server terjangkau (SSH ok); Strata belum dinyalakan | Nyalakan saat spike (M0) / M6 |

## 5. Prasyarat Server (gspe-ai2)

- Docker + docker compose.
- Strata tetap berjalan di host (:8081). Container mengaksesnya via `host.docker.internal` atau IP host.
- Volume persisten untuk `DATA_DIR`.
- Font IBM Plex dan font fallback terpasang di image (untuk WeasyPrint dan label render Blender).
- Blender dijalankan dengan `BLENDER_RENDER_DEVICE=CPU` secara default.
