# 09 — API

Base path: `/api`. Format JSON (UTF-8). Server: FastAPI. Dokumentasi OpenAPI otomatis tersedia di `/api/docs`.

**Autentikasi**: tidak ada di MVP (LAN internal, NFR-SC-01). Header `X-User` opsional dicatat di provenance spec editor, untuk persiapan autentikasi nanti.

## 1. Konvensi

- ID: `project_id` (slug), `run_id`, versi spec berupa integer.
- Waktu: ISO 8601 dengan zona waktu.
- Format error:
  ```json
  { "error": { "code": "spec_conflict", "message": "base_version 7 is not HEAD (8)", "details": {} } }
  ```
- Kode HTTP: `200`, `201`, `202` (job diterima), `400` (input salah), `404`, `409` (konflik versi / run sedang berjalan), `413` (file terlalu besar), `415` (tipe tidak didukung), `422` (validasi spec gagal), `503` (dependensi tidak tersedia).

## 2. Endpoint

### 2.1 Projects

| Method | Path | Fungsi |
|---|---|---|
| `POST` | `/api/projects` | Buat project + mulai run `full`. `multipart/form-data`: `file`, `name?`, `prompt?`, `params?` (JSON string), `page?`, `start` (default `true`) |
| `GET` | `/api/projects` | Daftar ringkas. Query: `q`, `status`, `limit`, `offset` |
| `GET` | `/api/projects/{id}` | Detail: `project.json` + run terakhir + HEAD + ringkasan output |
| `PATCH` | `/api/projects/{id}` | Ubah `name` / parameter default (tidak memicu run) |
| `DELETE` | `/api/projects/{id}` | Hapus project (P1, butuh `?confirm=true`) |
| `GET` | `/api/projects/{id}/input` | File asli |

Contoh respons `POST /api/projects` (`201`):
```json
{ "project_id": "msc-gatsu-l1-7f3a", "run_id": "20261023T090012-a1", "status": "queued" }
```

### 2.2 Runs

| Method | Path | Fungsi |
|---|---|---|
| `POST` | `/api/projects/{id}/runs` | Mulai run. Body: `{ "kind": "full" \| "from_stage", "from_stage": 3?, "params_override": {}?, "profile_id": "…"? }`. Respons `202`. `409` bila ada run aktif untuk project ini. |
| `GET` | `/api/projects/{id}/runs` | Daftar run |
| `GET` | `/api/projects/{id}/runs/{run_id}` | `run.json`: status per tahap, durasi, versi kode |
| `POST` | `/api/projects/{id}/runs/{run_id}/cancel` | Batalkan: kirim SIGTERM ke subprocess, status `failed (cancelled)` |
| `POST` | `/api/projects/{id}/runs/{run_id}/continue` | Lanjutkan run yang berhenti di `needs_attention` (tahap 5), dengan `{ "accept_low_score": true }` |

### 2.3 Artefak tahap

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/projects/{id}/runs/{run_id}/stages/{nn}` | Ringkasan tahap: status, durasi, metrik, daftar artefak |
| `GET` | `/api/projects/{id}/runs/{run_id}/artifacts/{path}` | File artefak. `path` relatif terhadap `stages/`, dinormalisasi dan dicek tidak keluar folder run (NFR-SC-04). |

### 2.4 Specs

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/projects/{id}/specs` | Daftar versi: `{version, source, created_at, message, run_id, has_outputs}` |
| `GET` | `/api/projects/{id}/specs/HEAD` | Spec terbaru |
| `GET` | `/api/projects/{id}/specs/{v}` | Spec versi tertentu |
| `POST` | `/api/projects/{id}/specs` | Terapkan ops, menghasilkan versi baru. Body: `{ "base_version": 7, "ops": [...], "message": "…" }`. Respons `201 {version, spec, issues}` / `409` / `422 {issues}` |
| `GET` | `/api/projects/{id}/specs/diff?from=6&to=8` | Diff ringkas per tipe + ops |
| `POST` | `/api/projects/{id}/specs/validate` | Dry-run ops tanpa menyimpan: `{base_version, ops}` → `{score, issues}` |
| `POST` | `/api/projects/{id}/specs/import` | Impor spec utuh (`source: manual`), mis. ground truth atau spec hasil perbaikan offline. Divalidasi penuh. Dipakai di M2–M4 sebelum ekstraksi tersedia. Project bisa dibuat tanpa run dengan `POST /api/projects` `start=false`. |

Contoh body ops:
```json
{
  "base_version": 7,
  "message": "Rack baris A + tinggi data hall",
  "ops": [
    { "op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
      "position": [8400, 3000, 0], "rotation": 0, "dims": [600, 1200, 2000], "label": "A-01" },
    { "op": "set_wall_height", "id": "W12", "height": 4500 },
    { "op": "set_room_type", "id": "R5", "type": "battery_room" }
  ]
}
```

### 2.5 Regenerate & Outputs

| Method | Path | Fungsi |
|---|---|---|
| `POST` | `/api/projects/{id}/regenerate` | Body `{ "version": 8 \| "HEAD" }`. Membuat run `regenerate` (tahap 7–10). Respons `202 {run_id}`. Idempoten: bila output lengkap sudah ada, respons `200 {run_id: null, reused: true}`. |
| `GET` | `/api/projects/{id}/outputs` | Daftar versi yang punya output beserta file-nya |
| `GET` | `/api/projects/{id}/outputs/{v}/{file}` | Unduh file (`shell.glb`, `layout.blend`, …). Header `ETag` = sha256 file, `Cache-Control: private, max-age=31536000, immutable` (file per versi tidak pernah berubah) |
| `GET` | `/api/projects/{id}/outputs/{v}/bundle.zip` | Semua output versi itu |

### 2.6 Events (SSE)

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/projects/{id}/events` | Stream `text/event-stream`. Query `since=<seq>` atau header `Last-Event-ID`. Server mengirim event lama dari `events.jsonl` setelah `seq` itu, lalu event baru secara live. Heartbeat komentar `: ping` setiap 15 detik. |
| `GET` | `/api/projects/{id}/events.jsonl?run_id=…` | Unduh log mentah |

### 2.7 Templates

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/templates` | Daftar `template.json` versi terbaru per template. Query `category`. |
| `GET` | `/api/templates/{template_id}/{version}` | `template.json` |
| `GET` | `/api/templates/{template_id}/{version}/asset.glb` | Aset |
| `GET` | `/api/templates/{template_id}/{version}/thumbnail.png` | Thumbnail |

### 2.8 Profiles

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/profiles` | Daftar style profile |
| `POST` | `/api/profiles` | Simpan dari run: `{ "name": "...", "from_run": "<project_id>/<run_id>" }` |

### 2.9 System

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/health` | `{ "server": "ok", "strata": {"ok": bool, "status": "idle"\|"processing"\|null, "latency_ms"}, "blender": {"ok", "version", "busy"}, "queue": {"waiting", "running"} }` |
| `GET` | `/api/config` | Konfigurasi non-rahasia (tugas LLM aktif, ambang, versi skema) |

## 3. Model Run

```jsonc
// run.json
{
  "run_id": "20261023T090012-a1",
  "project_id": "msc-gatsu-l1-7f3a",
  "kind": "full",               // full | from_stage | regenerate
  "from_stage": 0,
  "spec_version_in": null,      // regenerate: versi yang dibangun
  "spec_version_out": 2,        // versi terakhir yang dibuat run ini
  "status": "running",          // queued | running | succeeded | needs_attention | failed
  "stages": [
    { "n": 0, "name": "input", "status": "succeeded", "started_at": "…", "ended_at": "…",
      "duration_ms": 210, "metrics": {}, "warnings": [] },
    { "n": 3, "name": "extract", "status": "running", "progress": 42, "metrics": { "candidates": 12 } }
  ],
  "code_version": "git:abc1234",
  "blender_version": "5.2.2",
  "created_at": "…"
}
```

## 4. Model Event

Satu baris per event di `events.jsonl`, dan satu pesan SSE (`id: <seq>`, `event: <type>`, `data: <json>`):

```jsonc
{ "seq": 1532, "ts": "2026-10-23T09:00:15.221+07:00", "run_id": "…", "stage": 3,
  "type": "stage.log", "level": "info", "msg": "candidate k3: 48 walls, 17 doors", "data": {} }
```

| `type` | Kapan | `data` |
|---|---|---|
| `run.queued` / `run.started` / `run.finished` | Siklus run | `{status}` |
| `stage.started` / `stage.finished` | Siklus tahap | `{status, duration_ms, metrics}` |
| `stage.progress` | Progres | `{percent, msg}` |
| `stage.log` | Baris log | `level`, `msg` |
| `stage.artifact` | Artefak baru tersedia | `{path, kind: "image"\|"json"\|"html"\|"model"}` |
| `llm.decision` | Keputusan per elemen di tahap 6 | `{element, task, verdict, accepted, score_before, score_after}` |
| `spec.created` | Versi spec baru | `{version, source}` |
| `output.ready` | Output versi tersedia | `{version, files[]}` |

`seq` naik monoton per project dan tidak pernah dipakai ulang.

## 5. Batasan & Perilaku

- Satu run aktif per project. Antar-project berbagi antrean global dengan satu worker Blender.
- `POST /specs` diizinkan ketika ada run aktif, **kecuali** run itu sedang di tahap 5–6 dan akan membuat versi baru. Dalam kasus itu respons `409 run_in_progress`.
- Ukuran body JSON maksimal 5 MB. Jumlah ops per request maksimal 2000.
- Semua path file diselesaikan relatif terhadap `DATA_DIR`. Symlink ditolak.
