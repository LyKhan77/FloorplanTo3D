# M3 — Server & Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline bisa dijalankan dan dipantau dari browser. Pengguna membuat project, mengimpor GT Gatsu, menekan Regenerate, melihat log live (≤ 1 s), mengunduh output, dan membaca dokumen di iframe. Run yang terputus karena restart ditandai `interrupted`, lalu antrean berlanjut.

**Architecture:** Server FastAPI satu proses (`server/`):
- penyimpanan filesystem aman di `DATA_DIR`;
- event bus (`events.jsonl` + SSE);
- orchestrator asyncio dengan dua antrean FIFO (analisis 0–6, Blender 7–10), masing-masing satu worker.

Tahap 0–6 berupa stub sampai M5/M6. Tahap 7–10 memakai langkah pipeline M2 yang dipecah ke `core/pipeline.py`. Dashboard React + Carbon g100 (`web/`) berbicara REST + SSE.

**Tech Stack:** FastAPI, Uvicorn, python-multipart, httpx (test); React 18, Vite, TypeScript, `@carbon/react` (g100), `@carbon/icons-react`, react-router-dom, TanStack Query, react-virtuoso, Vitest.

**Spec:** `PRD/09-api.md` (otoritas API), `PRD/02-architecture.md` §3–§5, `PRD/08-dashboard.md`, `PRD/01-requirements.md` (FR-IN-01…03/05, FR-DB-01…09, NFR-SC-01…04, NFR-RL-*, NFR-PF-06), `ROADMAP.md` M3. Branch dasar: `m2-builder`.

## Global Constraints

- Semua perintah shell diawali `rtk`. Test yang menyentuh Blender atau WeasyPrint dijalankan dengan `uv run --env-file .env pytest`.
- Jangan membaca atau meng-commit `server-info.txt`. Tidak ada autentikasi (LAN). Header `X-User` opsional dicatat di provenance (09 §1).
- Kerja di branch baru `m3-server`, dibuat dari `m2-builder`.
- Base path `/api`, JSON UTF-8. Error = `{"error": {"code", "message", "details"}}`. Kode HTTP mengikuti 09 §1.
- Layout disk persis 02 §4: `projects/<id>/{project.json, input/{original.<ext>, input.json}, runs/<run_id>/{run.json, stages/<nn>_<name>/}, specs/, outputs/v<N>/, events.jsonl}`, `templates/<id>/<ver>/`, `profiles/<id>.json`.
- `project_id` = slug + `-` + 4 hex (mis. `msc-gatsu-l1-7f3a`). `run_id` = `YYYYMMDDTHHMMSS-<2 hex>`. `seq` naik monoton per project dan tidak pernah dipakai ulang.
- Status tahap: `pending | running | succeeded | failed | skipped | needs_attention`. Status run: `queued | running | succeeded | needs_attention | failed`. Run `kind`: `full | from_stage | regenerate`.
- Nama tahap: `0 input, 1 preprocess, 2 grid, 3 extract, 4 rooms, 5 validate, 6 review, 7 build, 8 verify, 9 report, 10 publish`.
- Upload: JPEG/PNG/PDF lewat magic bytes, ≤ `MAX_UPLOAD_MB` (50), nama file disanitasi, SHA-256 disimpan. Path artefak dinormalisasi; symlink dan path di luar folder run ditolak (`404`).
- Event SSE: `id: <seq>`, `event: <type>`, `data: <json>`, replay dari `since`/`Last-Event-ID`, heartbeat `: ping` tiap 15 s. Tipe event persis 09 §4.
- Output per versi immutable: `ETag` = sha256 file, `Cache-Control: private, max-age=31536000, immutable`.
- Web: Carbon **g100**, IBM Plex Sans (body) + Plex Mono (log, ID, angka). Status selalu berupa ikon + teks + warna (08 §5). Polling daftar project tiap 5 s, SSE di halaman detail.
- Dev: Vite proxy `/api` → `http://localhost:8000`. Server melayani `web/dist` di `/` bila folder itu ada.

## Review Focus

1. **Path traversal lewat artefak/output/template** (`../`, path absolut, encoded `%2e%2e`, symlink). Harus `404`, tidak pernah membaca di luar folder. Ditest di Task 1 (`test_safe_join_rejects_escape_and_symlink`) dan Task 7 (`test_output_file_traversal_404`).
2. **Klien SSE tersambung ulang di tengah run.** Event yang sudah ada dikirim ulang persis sekali sejak `Last-Event-ID`, lalu event live berlanjut tanpa celah atau duplikat. Ditest di Task 2: `test_sse_replays_since_then_live_without_gap`.
3. **Dua aksi bersamaan pada satu project** (run kedua saat run aktif, `POST /specs` saat tahap 5–6 berjalan, dua tab menyimpan dari base yang sama). `409` dengan kode jelas, tanpa korupsi file. Ditest di Task 6: `test_second_run_409`; Task 4: `test_stale_ops_409`.
4. **Restart server di tengah run.** Run `running` menjadi `failed (interrupted)`, run `queued` dijalankan lagi, tidak ada folder `outputs/v<N>.tmp` yatim yang dianggap output, dan `seq` event tetap naik. Ditest di Task 6: `test_recovery_marks_running_interrupted_and_requeues`.
5. **Upload yang tidak valid** (ekstensi `.jpg` berisi teks, file > 50 MB, nama berisi `../`). Harus `415`/`413`/disanitasi, dan tidak ada project setengah jadi di disk. Ditest di Task 3: `test_upload_rejections_leave_no_project`.

---

### Task 1: Kerangka server, penyimpanan aman, error standar

**Files:**
- Modify: `pyproject.toml` (tambah `fastapi`, `uvicorn[standard]`, `python-multipart`; dev `httpx`)
- Create: `server/__init__.py`, `server/app.py`, `server/errors.py`, `server/storage.py`
- Test: `tests/server/__init__.py`, `tests/server/conftest.py`, `tests/server/test_storage.py`

**Interfaces:**
- Produces:
  - `server.errors.ApiError(Exception)`: `(status: int, code: str, message: str, details: dict | None = None)`. Handler FastAPI → JSON 09 §1. `RequestValidationError` → `400 {"code": "bad_request"}`.
  - `server.storage.Storage(root: Path)`. Method (semua path di bawah `root`):
    - `projects_dir`, `templates_dir`, `profiles_dir` (property);
    - `project_dir(pid) -> Path` (`404 project_not_found` bila tidak ada);
    - `new_project_id(name: str) -> str` (slug ASCII huruf kecil, `[a-z0-9-]`, maks 40 karakter + `-` + `secrets.token_hex(2)`);
    - `new_run_id() -> str`;
    - `safe_join(base: Path, rel: str) -> Path`: tolak path absolut, `..` setelah normalisasi, komponen yang merupakan symlink, dan hasil di luar `base` → `ApiError(404, "not_found")`;
    - `read_json(path) -> dict`;
    - `write_json_atomic(path, data)` (tmp + `os.replace`).
  - `server.app.create_app(settings: Settings | None = None) -> FastAPI` (menyimpan `app.state.settings`, `app.state.storage`; router didaftarkan task berikutnya). Modul punya `app = create_app()` untuk `uvicorn server.app:app`.
  - `tests/server/conftest.py`: fixture `data_dir(tmp_path)` dan `client(data_dir)` (= `TestClient(create_app(load_settings({"DATA_DIR": str(data_dir), ...env saat ini})))`).

- [ ] **Step 1: Branch, dependencies, test yang gagal**

```bash
rtk git checkout -b m3-server m2-builder
rtk uv add fastapi "uvicorn[standard]" python-multipart && rtk uv add --dev httpx
```

```python
def test_safe_join_rejects_escape_and_symlink(tmp_path):
    st = Storage(tmp_path)
    base = tmp_path / "projects" / "p"; base.mkdir(parents=True); (base / "a.txt").write_text("x")
    assert st.safe_join(base, "a.txt") == base / "a.txt"
    for bad in ("../x", "/etc/passwd", "sub/../../x", "%2e%2e/x"):
        with pytest.raises(ApiError) as e:
            st.safe_join(base, bad)
        assert e.value.status == 404
    (base / "link").symlink_to(tmp_path)
    with pytest.raises(ApiError):
        st.safe_join(base, "link/anything")

def test_new_ids_shape(tmp_path):
    st = Storage(tmp_path)
    assert re.fullmatch(r"msc-gatsu-lantai-1-[0-9a-f]{4}", st.new_project_id("MSC Gatsu — Lantai 1!"))
    assert re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{2}", st.new_run_id())

def test_unknown_project_is_standard_404(client):
    r = client.get("/api/projects/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "project_not_found"
```
Test terakhir baru lulus setelah Task 3. Tandai `xfail(strict=True, reason="routes in Task 3")` sekarang, lalu buang tanda itu di Task 3.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/server -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Implement.** `safe_join` men-decode `urllib.parse.unquote` sekali sebelum normalisasi.

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/server -q`
Expected: PASS (+1 xfail)

- [ ] **Step 5: Commit**

```bash
rtk git add pyproject.toml uv.lock server tests/server && rtk git commit -m "feat(server): app skeleton, safe storage, standard errors"
```

---

### Task 2: Event bus + SSE

**Files:**
- Create: `server/events.py`, `server/routes/__init__.py`, `server/routes/events.py`
- Test: `tests/server/test_events.py`

**Interfaces:**
- Produces:
  - `server.events.EventBus(storage)`:
    - `emit(pid, run_id, stage, type, *, level="info", msg="", data=None) -> dict`: membangun event persis 09 §4, dengan `ts` ISO + zona waktu dan `seq` = terakhir + 1 (dibaca dari ekor `events.jsonl` saat pertama kali dipakai, lalu dicache). Event di-append dengan lock per project, lalu dikirim ke setiap subscriber;
    - `history(pid, since: int = 0, run_id: str | None = None) -> list[dict]`;
    - `subscribe(pid) -> asyncio.Queue` dan `unsubscribe(pid, q)`;
    - aman dipanggil dari thread worker: memakai `loop.call_soon_threadsafe` ke loop yang tersimpan saat `bind_loop(loop)`.
  - `server.events.sse_stream(bus, pid, since: int, heartbeat_s: float = 15) -> AsyncIterator[str]`: **subscribe dulu**, lalu kirim history `> since`, lalu event live dengan `seq > last_sent` (dedup untuk celah antara subscribe dan replay). `: ping\n\n` setiap heartbeat.
  - Route `GET /api/projects/{id}/events` (query `since`, header `Last-Event-ID`; `StreamingResponse` `text/event-stream`, `Cache-Control: no-cache`) dan `GET /api/projects/{id}/events.jsonl?run_id=` (unduh, difilter run).

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_emit_seq_monotonic_and_persisted(storage_with_project):
    st, pid = storage_with_project
    bus = EventBus(st)
    e1 = bus.emit(pid, "r1", 3, "stage.log", msg="a"); e2 = bus.emit(pid, "r1", 3, "stage.log", msg="b")
    assert (e1["seq"], e2["seq"]) == (1, 2)
    assert EventBus(st).emit(pid, "r1", 3, "stage.log")["seq"] == 3        # new bus continues from the file
    assert [e["msg"] for e in bus.history(pid, since=1)] == ["b", ""]

async def test_sse_replays_since_then_live_without_gap(storage_with_project):
    st, pid = storage_with_project
    bus = EventBus(st); bus.bind_loop(asyncio.get_running_loop())
    for i in range(3):
        bus.emit(pid, "r1", 7, "stage.log", msg=f"old{i}")
    gen = sse_stream(bus, pid, since=1, heartbeat_s=60)
    first = [await anext(gen), await anext(gen)]
    bus.emit(pid, "r1", 7, "stage.log", msg="live")
    live = await anext(gen)
    ids = [int(re.search(r"^id: (\d+)", c, re.M)[1]) for c in [*first, live]]
    assert ids == [2, 3, 4] and "event: stage.log" in live and '"msg": "live"' in live

async def test_sse_heartbeat(storage_with_project):
    st, pid = storage_with_project
    bus = EventBus(st); bus.bind_loop(asyncio.get_running_loop())
    assert await anext(sse_stream(bus, pid, since=0, heartbeat_s=0.05)) == ": ping\n\n"
```
Fixture `storage_with_project` di `conftest.py` membuat `projects/<pid>/` kosong. Test async memakai `asyncio.run` di dalam fungsi sync biasa (tanpa plugin tambahan).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/server/test_events.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `events.py` dan route events**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/server -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add server tests/server && rtk git commit -m "feat(server): event bus with events.jsonl and SSE replay"
```

---

### Task 3: Projects + upload

**Files:**
- Create: `server/routes/projects.py`, `server/projects.py`
- Test: `tests/server/test_projects.py`

**Interfaces:**
- Consumes: `Storage`, `ApiError`, `EventBus`.
- Produces:
  - `server.projects.sniff_type(head: bytes) -> Literal["jpg","png","pdf"] | None` (`FF D8 FF`, `89 50 4E 47 0D 0A 1A 0A`, `%PDF-`).
  - `server.projects.create_project(storage, file_bytes, filename, name, prompt, params: dict, page: int | None) -> dict`. Isi dan urutan kerja:
    - validasi tipe → `415 unsupported_type` dan ukuran → `413 file_too_large`;
    - tulis ke folder sementara `projects/.tmp-<id>`, lalu rename ke id final (tidak ada project setengah jadi);
    - `project.json` = `{project_id, name, created_at, updated_at, params, status: "new", latest_run: null}`;
    - `input/original.<ext>` dan `input/input.json` = `{filename (sanitasi), sha256, prompt, params, page}`.
  - Route:
    - `POST /api/projects` (multipart: `file`, `name?`, `prompt?`, `params?` JSON string → `400` bila bukan JSON object, `page?`, `start=true`) → `201 {project_id, run_id|null, status}`. Bila `start`, panggil `app.state.orchestrator.start_run(pid, "full")` (Task 6; sampai Task 6 ada, `start` dianggap `false`);
    - `GET /api/projects` (`q`, `status`, `limit=50`, `offset=0`) → `{items: [ringkasan], total}`, dengan ringkasan `{project_id, name, status, active_stage, validator_score, iou, head_version, updated_at}`;
    - `GET /api/projects/{id}` → project.json + `latest_run` (run.json) + `head` (versi) + `outputs` (daftar versi);
    - `PATCH /api/projects/{id}` (`name`, `params`);
    - `DELETE /api/projects/{id}?confirm=true` (tanpa `confirm` → `400`);
    - `GET /api/projects/{id}/input` (`FileResponse` file asli).

- [ ] **Step 1: Tulis test yang gagal** (fixture `plan_bytes` = isi `floorplan/plan.jpeg`)

```python
def test_create_project_stores_original_and_hash(client, data_dir, plan_bytes):
    r = client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")},
                    data={"name": "MSC Gatsu L1", "prompt": "data hall", "start": "false"})
    assert r.status_code == 201
    pid = r.json()["project_id"]
    d = data_dir / "projects" / pid
    assert (d / "input" / "original.jpg").read_bytes() == plan_bytes
    assert json.loads((d / "input" / "input.json").read_text())["sha256"] == hashlib.sha256(plan_bytes).hexdigest()
    assert client.get(f"/api/projects/{pid}").json()["name"] == "MSC Gatsu L1"
    assert [p["project_id"] for p in client.get("/api/projects").json()["items"]] == [pid]

def test_upload_rejections_leave_no_project(client, data_dir, monkeypatch):
    assert client.post("/api/projects", files={"file": ("x.jpg", b"hello", "image/jpeg")}).status_code == 415
    big = b"\xff\xd8\xff" + b"0" * (51 * 1024 * 1024)
    assert client.post("/api/projects", files={"file": ("big.jpg", big, "image/jpeg")}).status_code == 413
    assert not any((data_dir / "projects").iterdir()) if (data_dir / "projects").exists() else True

def test_filename_sanitized(client, data_dir, plan_bytes):
    pid = client.post("/api/projects", files={"file": ("../../evil name.jpeg", plan_bytes, "image/jpeg")},
                      data={"start": "false"}).json()["project_id"]
    meta = json.loads((data_dir / "projects" / pid / "input" / "input.json").read_text())
    assert meta["filename"] == "evil_name.jpeg"

def test_delete_requires_confirm(client, plan_bytes):
    pid = client.post("/api/projects", files={"file": ("p.jpeg", plan_bytes, "image/jpeg")}, data={"start": "false"}).json()["project_id"]
    assert client.delete(f"/api/projects/{pid}").status_code == 400
    assert client.delete(f"/api/projects/{pid}?confirm=true").status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404
```
Hapus tanda xfail di `test_unknown_project_is_standard_404` (Task 1).

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/server/test_projects.py -q`
Expected: FAIL (404 pada route)

- [ ] **Step 3: Implement.** Body upload dibaca bertahap dan dibatasi `MAX_UPLOAD_MB` (stop begitu melewati batas).

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/server -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add server tests/server && rtk git commit -m "feat(server): projects and validated upload"
```

---

### Task 4: Specs (list, ops, validate, diff, import)

**Files:**
- Create: `core/spec/diff.py`, `server/routes/specs.py`
- Test: `tests/spec/test_diff.py`, `tests/server/test_specs.py`

**Interfaces:**
- Consumes: `SpecStore`, `apply`, `validate`, `VersionConflict`, `ValidationFailed`, `OpError` (M1).
- Produces:
  - `core.spec.diff.diff_specs(a: Spec, b: Spec) -> dict` = `{<type>: {"added": [ids], "removed": [ids], "changed": [ids]}}` untuk `walls, columns, openings, rooms, stairs, objects` (tanpa field turunan dan `provenance` saat membandingkan), + `"ops": b.provenance_log`.
  - Route di bawah `/api/projects/{id}/specs` (09 §2.4):
    - `GET ""` → `[{version, source, created_at, message, run_id, has_outputs}]`;
    - `GET /HEAD`, `GET /{v}` (`404 spec_not_found`);
    - `POST ""` `{base_version, ops, message}` → `201 {version, spec, issues}`, `409 spec_conflict` (details `{base, head}`), `422 validation_failed {issues}`, `400 bad_op {index, op, message}`. Selain itu `409 run_in_progress` bila run aktif project sedang di tahap 5 atau 6;
    - `POST /validate` `{base_version, ops}` → `{score, passed, issues}`;
    - `GET /diff?from=&to=`;
    - `POST /import` (body = spec JSON utuh, `source: manual`) → `201 {version}`. Pesan commit diambil dari query `message`.
  - `has_outputs` = folder `outputs/v<N>` ada dan berisi `shell.glb`. `by` untuk ops = `"editor"`. Header `X-User` dicatat ke entri `provenance_log` (`reason` diawali `user=<X-User>; `).

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/spec/test_diff.py
def test_diff_reports_added_removed_changed():
    a = spec_with_rooms()
    b = apply(a, [{"op": "add_wall", "a": (2500, 100), "b": (2500, 5900), "thickness": 100, "kind": "partition"},
                  {"op": "set_wall_height", "id": "W1", "height": 4500},
                  {"op": "delete_opening", "id": "D2", "reason": "x"}], "editor", 2)
    d = diff_specs(a, b)
    assert d["walls"] == {"added": ["W6"], "removed": [], "changed": ["W1"]}
    assert d["openings"]["removed"] == ["D2"] and d["rooms"]["added"] == ["R3"]
    assert [e.op for e in d["ops"]][:2] == ["add_wall", "set_wall_height"]
```

```python
# tests/server/test_specs.py  (fixture project_id: project created with start=false)
def test_import_then_ops_then_diff(client, project_id):
    gt = Path("benchmarks/gatsu/gt_spec.json").read_text()
    assert client.post(f"/api/projects/{project_id}/specs/import", content=gt,
                       headers={"content-type": "application/json"}).json()["version"] == 1
    r = client.post(f"/api/projects/{project_id}/specs",
                    json={"base_version": 1, "ops": [{"op": "set_wall_height", "id": "W1", "height": 4500}],
                          "message": "tinggi"}, headers={"X-User": "lee"})
    assert r.status_code == 201 and r.json()["version"] == 2
    assert client.get(f"/api/projects/{project_id}/specs/diff?from=1&to=2").json()["walls"]["changed"] == ["W1"]
    assert [v["version"] for v in client.get(f"/api/projects/{project_id}/specs").json()] == [1, 2]

def test_stale_ops_409(client, project_with_gt):
    pid = project_with_gt
    ops = {"base_version": 1, "ops": [{"op": "rename_room", "id": "R22", "name": "X"}]}
    assert client.post(f"/api/projects/{pid}/specs", json=ops).status_code == 201
    r = client.post(f"/api/projects/{pid}/specs", json=ops)
    assert r.status_code == 409 and r.json()["error"]["details"] == {"base": 1, "head": 2}

def test_invalid_ops_422_and_bad_op_400(client, project_with_gt):
    pid = project_with_gt
    r = client.post(f"/api/projects/{pid}/specs", json={"base_version": 1, "ops": [{"op": "set_door", "id": "D1", "offset": 99999}]})
    assert r.status_code == 422 and any(i["code"] == "V008" for i in r.json()["error"]["details"]["issues"])
    r = client.post(f"/api/projects/{pid}/specs", json={"base_version": 1, "ops": [{"op": "nope"}]})
    assert r.status_code == 400 and r.json()["error"]["details"]["index"] == 0

def test_validate_dry_run_does_not_write(client, project_with_gt):
    pid = project_with_gt
    r = client.post(f"/api/projects/{pid}/specs/validate", json={"base_version": 1, "ops": []})
    assert r.json()["passed"] and len(client.get(f"/api/projects/{pid}/specs").json()) == 1
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/spec/test_diff.py tests/server/test_specs.py -q`
Expected: FAIL, `ModuleNotFoundError` / 404

- [ ] **Step 3: Implement**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/spec tests/server -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add core/spec/diff.py server tests && rtk git commit -m "feat(server): spec versions, ops, validate, diff, import"
```

---

### Task 5: Langkah pipeline tahap 7–10 sebagai library

**Files:**
- Create: `core/pipeline.py`
- Modify: `core/cli.py` (memakai `core.pipeline`), `core/blender_run.py` (hook `on_start`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `build_input_for`, `run_blender`, `run_verify`, `report_data`, `write_report`, `render_overlay` (M2).
- Produces (`core.pipeline`):
  - `BuildFailed(Exception)` dengan atribut `log: Path`, `exit_code: int`.
  - `stage_build(spec, work: Path, image: Path | None, templates: Path | None, engine: str, on_line=None, on_start=None, timeout_s: int = 300) -> tuple[dict, list[str]]`: tulis `build_input.json`, jalankan Blender (`BuildFailed` bila exit ≠ 0), kembalikan (doc, warnings).
  - `stage_verify(spec, work, doc, image, warnings) -> dict`: membungkus `run_verify` dengan `extra_warnings`.
  - `stage_report(spec, work, doc, verify, image, run_id) -> tuple[Path, Path]`: menyalin denah ke `renders/plan.<ext>`, overlay, `report_data` (dengan `missing_objects`), lalu `write_report`.
  - `OUTPUT_FILES = ("layout.blend", "shell.glb", "layout_full.glb", "layout.fbx", "layout.obj", "layout.mtl", "report.html", "report.pdf", "report.css", "verify.json", "iou_mask.png", "verify_top.png")`, ditambah folder `renders/`.
  - `publish(work: Path, outputs_root: Path, version: int) -> Path`: salin `OUTPUT_FILES` yang ada + `renders/` ke `outputs_root/v<N>.tmp`, lalu `os.rename` ke `v<N>` (folder lama dihapus dulu). Bila ada `v<N>.tmp` yatim, folder itu dihapus.
  - `outputs_complete(path: Path) -> bool` = `shell.glb`, `layout.blend`, dan `report.html` ada.
  - `run_blender(..., on_start: Callable[[subprocess.Popen], None] | None = None)`: dipanggil setelah proses dibuat (untuk pembatalan oleh orchestrator).
  - `core.cli.build` diubah menjadi orkestrasi tipis di atas fungsi-fungsi di atas, dengan perilaku sama (test CLI M2 tetap hijau).

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_publish_atomic_and_replaces(tmp_path):
    work = tmp_path / "work"; (work / "renders").mkdir(parents=True)
    for f in ("shell.glb", "layout.blend", "report.html"):
        (work / f).write_text(f)
    (work / "renders" / "top.png").write_text("png"); (work / "blender.log").write_text("log")
    (tmp_path / "outputs" / "v3.tmp").mkdir(parents=True)          # orphan from a crash
    out = publish(work, tmp_path / "outputs", 3)
    assert out == tmp_path / "outputs" / "v3" and outputs_complete(out)
    assert (out / "renders" / "top.png").exists() and not (out / "blender.log").exists()
    assert not (tmp_path / "outputs" / "v3.tmp").exists()

def test_stage_build_raises_with_log_on_failure(tmp_path, monkeypatch):
    with pytest.raises(BuildFailed) as e:
        stage_build(spec_with_rooms(), tmp_path, None, None, "BLENDER_WORKBENCH", blender_bin="/usr/bin/false")
    assert e.value.exit_code == 1 and e.value.log.exists()

def test_run_blender_reports_process_to_on_start(tmp_path):
    seen = []
    run_blender(tmp_path / "x.json", tmp_path, "/usr/bin/true", on_start=seen.append)
    assert len(seen) == 1 and seen[0].pid > 0
```
`stage_build` menerima kwarg `blender_bin: str | None = None` (default `load_settings().blender_bin`) agar dapat ditest.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/test_pipeline.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement, lalu refactor `core/cli.py`**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/test_pipeline.py tests/test_cli.py tests/test_m2_review_fixes.py -q`
Expected: semua PASS (IoU tetap xfail)

- [ ] **Step 5: Commit**

```bash
rtk git add core tests/test_pipeline.py && rtk git commit -m "refactor(core): pipeline stages 7-10 as a library for CLI and server"
```

---

### Task 6: Orchestrator (dua antrean, state machine, batal, pemulihan) + route runs

**Files:**
- Create: `server/orchestrator.py`, `server/routes/runs.py`
- Test: `tests/server/test_orchestrator.py`

**Interfaces:**
- Consumes: `Storage`, `EventBus`, `SpecStore`, `core.pipeline` (Task 5).
- Produces:
  - `server.orchestrator.STAGES = [(0,"input"),(1,"preprocess"),(2,"grid"),(3,"extract"),(4,"rooms"),(5,"validate"),(6,"review"),(7,"build"),(8,"verify"),(9,"report"),(10,"publish")]`.
  - `Orchestrator(storage, bus, settings, stage_impls: dict[int, Callable] | None = None)`:
    - `async start()`: `bus.bind_loop`, `recover()`, lalu 2 worker task;
    - `async stop()`;
    - `start_run(pid, kind, from_stage=0, version: int | str = "HEAD") -> dict` (run.json; sinkron; `409 run_in_progress` bila project punya run `queued|running`);
    - `cancel(pid, run_id)`;
    - `active_run(pid) -> dict | None`;
    - `queue_info() -> {"waiting": int, "running": [run_id], "blender_busy": bool}`.
  - `run.json` persis 09 §3, plus `version` (spec yang dibangun) dan `error`. Ditulis atomik setiap transisi. `stages[]` berisi 11 entri: `{n, name, status, started_at, ended_at, duration_ms, progress, metrics, warnings}`.
  - Alur: run masuk antrean **analisis** (tahap `from_stage…6`), lalu antrean **Blender** (7–10); `regenerate` langsung ke antrean Blender. Tahap di bawah `from_stage` berstatus `skipped`. Setiap transisi mengirim `run.queued/started/finished` dan `stage.started/finished/progress/log`. Hasil akhir: `succeeded`, `needs_attention` (tahap 2/5 menghentikan run; tahap 6/8 hanya peringatan), atau `failed`.
  - Implementasi tahap default (dapat diganti lewat `stage_impls` untuk test):
    - **0 input**: cek `input/original.*` ada (regenerate: dilewati);
    - **1–4**: `skipped` dengan pesan `"not implemented until M5"`;
    - **5**: bila spec HEAD ada → `skipped` ("using imported spec v<N>"); bila tidak → `needs_attention` ("no spec yet: import a spec (extraction arrives in M5)") dan run berhenti;
    - **6**: `skipped` ("Strata review arrives in M6");
    - **7 build**: `stage_build` di `asyncio.to_thread`. Work dir `runs/<rid>/stages/07_build/work`, gambar = `input/original.jpg|png` (PDF → None), templates = `DATA_DIR/templates`. `@@PROGRESS` → `stage.progress`, baris lain → `stage.log`. `on_start` menyimpan Popen untuk `cancel`;
    - **8 verify**: `stage_verify`. Status `needs_attention` bila verify `needs_attention` (lanjut), `failed` bila `failed`;
    - **9 report**: `stage_report`;
    - **10 publish**: `publish(work, outputs/, version)`, lalu event `output.ready {version, files}`.
  - Batal: run `queued` dikeluarkan dari antrean; run `running` → `proc.terminate()` bila ada Blender aktif, lalu flag dicek di antara tahap. Hasilnya status `failed`, `error: "cancelled"`.
  - `recover()`: run `running` → `failed`, `error: "interrupted"`, tahap yang sedang berjalan `failed`; run `queued` dimasukkan lagi ke antrean (sesuai urutan `created_at`); folder `outputs/v*.tmp` dihapus. Event `run.finished` untuk run yang terputus.
  - Route (09 §2.2, §2.3, §2.5):
    - `POST /api/projects/{id}/runs` → `202`;
    - `GET /runs`, `GET /runs/{rid}`;
    - `POST /runs/{rid}/cancel`;
    - `POST /runs/{rid}/continue` (`accept_low_score`: lanjut dari tahap 6 bila tahap 5 `needs_attention` dan sekarang ada spec);
    - `GET /runs/{rid}/stages/{nn}`;
    - `GET /runs/{rid}/artifacts/{path:path}` (`safe_join` terhadap folder `stages/`);
    - `POST /api/projects/{id}/regenerate` `{version}` → `202 {run_id}`, atau `200 {run_id: null, reused: true}` bila `outputs_complete(outputs/v<N>)`.
  - Lifespan app: `create_app` membuat Orchestrator dan menjalankan `start()`/`stop()` di lifespan; `app.state.orchestrator`. `POST /api/projects start=true` kini memanggil `start_run`.

- [ ] **Step 1: Tulis test yang gagal**

Test memakai `stage_impls` palsu yang cepat (tanpa Blender). Untuk sinkronisasi, gunakan helper `wait_status(client, pid, rid, {"succeeded", ...}, timeout=10)` di conftest.

```python
def fake_impls(calls, block: threading.Event | None = None):
    def ok(ctx): calls.append(ctx.stage); return {"status": "succeeded"}
    def slow(ctx):
        calls.append(ctx.stage)
        if block: block.wait(5)
        return {"status": "succeeded"}
    return {n: ok for n in range(11)} | ({7: slow} if block else {})

def test_regenerate_runs_7_to_10_in_blender_queue(app_factory, project_with_gt):
    calls = []
    with app_factory(stage_impls=fake_impls(calls)) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        run = wait_status(client, project_with_gt, rid, {"succeeded"})
        assert calls == [7, 8, 9, 10] and [s["status"] for s in run["stages"][:7]] == ["skipped"] * 7
        types = [e["type"] for e in client_events(client, project_with_gt)]
        assert types[0] == "run.queued" and "run.finished" in types and types.count("stage.started") == 4

def test_second_run_409(app_factory, project_with_gt):
    block = threading.Event()
    with app_factory(stage_impls=fake_impls([], block)) as client:
        client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"})
        r = client.post(f"/api/projects/{project_with_gt}/runs", json={"kind": "full"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "run_in_progress"
        block.set()

def test_full_run_without_spec_stops_needs_attention(app_factory, project_id):
    with app_factory() as client:                                  # default stage impls; stage 5 has no spec
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        run = wait_status(client, project_id, rid, {"needs_attention"})
        assert run["stages"][5]["status"] == "needs_attention" and run["stages"][7]["status"] == "pending"

def test_cancel_running(app_factory, project_with_gt):
    block = threading.Event()
    with app_factory(stage_impls=fake_impls([], block)) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        wait_stage_running(client, project_with_gt, rid, 7)
        assert client.post(f"/api/projects/{project_with_gt}/runs/{rid}/cancel").status_code == 200
        block.set()
        run = wait_status(client, project_with_gt, rid, {"failed"})
        assert run["error"] == "cancelled"

def test_recovery_marks_running_interrupted_and_requeues(app_factory, project_with_gt, data_dir):
    run_dir = data_dir / "projects" / project_with_gt / "runs"
    write_fake_run(run_dir, "20261026T000000-aa", status="running", stage_running=7)
    write_fake_run(run_dir, "20261026T000001-bb", status="queued", kind="regenerate")
    (data_dir / "projects" / project_with_gt / "outputs" / "v1.tmp").mkdir(parents=True)
    calls = []
    with app_factory(stage_impls=fake_impls(calls)) as client:
        a = client.get(f"/api/projects/{project_with_gt}/runs/20261026T000000-aa").json()
        assert (a["status"], a["error"]) == ("failed", "interrupted")
        wait_status(client, project_with_gt, "20261026T000001-bb", {"succeeded"})
        assert not (data_dir / "projects" / project_with_gt / "outputs" / "v1.tmp").exists()

def test_regenerate_reuses_complete_outputs(app_factory, project_with_gt, data_dir):
    out = data_dir / "projects" / project_with_gt / "outputs" / "v1"; out.mkdir(parents=True)
    for f in ("shell.glb", "layout.blend", "report.html"):
        (out / f).write_text("x")
    with app_factory(stage_impls=fake_impls([])) as client:
        r = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": 1})
        assert r.status_code == 200 and r.json() == {"run_id": None, "reused": True}

def test_artifact_traversal_404(app_factory, project_with_gt):
    with app_factory(stage_impls=fake_impls([])) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        wait_status(client, project_with_gt, rid, {"succeeded"})
        assert client.get(f"/api/projects/{project_with_gt}/runs/{rid}/artifacts/..%2F..%2Fproject.json").status_code == 404
```
Helper di `tests/server/conftest.py`:
- `app_factory(stage_impls=None)` = context manager `TestClient(create_app(settings, stage_impls=...))`, yang menjalankan lifespan;
- `project_with_gt` = project + GT diimpor sebagai v1;
- `client_events`, `wait_status`, `wait_stage_running`, `write_fake_run` (run.json minimal dengan 11 tahap).

`ctx` yang diterima stage impl = `StageContext(pid, run_id, stage, version, work_dir, emit_log, emit_progress, cancelled: threading.Event)`. Impl mengembalikan `{"status", "metrics"?, "warnings"?, "message"?}`.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/server/test_orchestrator.py -q`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement orchestrator, route runs/regenerate, lifespan**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest tests/server -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add server tests/server && rtk git commit -m "feat(server): orchestrator with two queues, cancel, recovery, run routes"
```

---

### Task 7: Outputs, templates, profiles, health/config, web statis

**Files:**
- Create: `server/routes/outputs.py`, `server/routes/templates.py`, `server/routes/system.py`
- Modify: `server/app.py` (mount `web/dist` bila ada)
- Test: `tests/server/test_outputs_system.py`

**Interfaces:**
- Produces:
  - `GET /api/projects/{id}/outputs` → `[{version, files: [{name, bytes}], renders: [names]}]` (urut versi turun).
  - `GET /api/projects/{id}/outputs/{v}/{file:path}`: `safe_join`, `ETag` = sha256 (dicache per path+mtime), `Cache-Control` immutable, `304` bila `If-None-Match` cocok.
  - `GET /api/projects/{id}/outputs/{v}/bundle.zip` (zip seluruh isi versi, dibangun on-the-fly ke `SpooledTemporaryFile`).
  - Templates:
    - `GET /api/templates?category=` → template.json versi tertinggi (semver) per id, + field `thumbnail_url`/`asset_url`. Template yang `validate_template` gagal disembunyikan dan dicatat di log server;
    - `GET /api/templates/{id}/{ver}`, `.../asset.glb`, `.../thumbnail.png`.
  - Profiles: `GET /api/profiles` → isi `profiles/*.json`; `POST /api/profiles` → `501 not_implemented` ("style profiles arrive in M5").
  - `GET /api/health` → persis 09 §2.9. Strata: `httpx.get(<base tanpa /v1>/health, timeout=2)`; `ok`, `status` dari `/status` bila ada, `latency_ms`. Blender: `{ok, version, busy}` (versi dari `blender --version` sekali, dicache). Queue dari `orchestrator.queue_info()`.
  - `GET /api/config` → `{llm_tasks_enabled, llm_max_iter, llm_votes, sweep_max_candidates, max_upload_mb, schema_version: "1.0", code_version}` (tanpa base URL Strata? URL boleh tampil karena bukan rahasia: sertakan `strata_base_url`, `strata_model`, `blender_bin`).
  - `server/app.py`: bila `web/dist/index.html` ada, `StaticFiles` di `/` dengan fallback SPA ke `index.html` untuk path non-`/api`.

- [ ] **Step 1: Tulis test yang gagal**

```python
def test_output_file_etag_and_304(client_with_outputs):
    client, pid = client_with_outputs                      # fixture writes outputs/v1/{shell.glb,report.html,renders/top.png}
    r = client.get(f"/api/projects/{pid}/outputs/1/shell.glb")
    assert r.status_code == 200 and r.headers["etag"].strip('"') == hashlib.sha256(r.content).hexdigest()
    assert "immutable" in r.headers["cache-control"]
    assert client.get(f"/api/projects/{pid}/outputs/1/shell.glb", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    assert client.get(f"/api/projects/{pid}/outputs").json()[0]["version"] == 1

def test_output_file_traversal_404(client_with_outputs):
    client, pid = client_with_outputs
    for bad in ("..%2F..%2Fproject.json", "%2Fetc%2Fpasswd", "renders/..%2F..%2F..%2Fproject.json"):
        assert client.get(f"/api/projects/{pid}/outputs/1/{bad}").status_code == 404

def test_bundle_zip_contains_files(client_with_outputs):
    client, pid = client_with_outputs
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{pid}/outputs/1/bundle.zip").content))
    assert {"shell.glb", "report.html", "renders/top.png"} <= set(z.namelist())

@pytest.mark.blender
def test_templates_listing_hides_invalid(app_factory, data_dir, placeholder_root):
    shutil.copytree(placeholder_root, data_dir / "templates")
    (data_dir / "templates" / "pdu-floor-generic" / "1.0.0" / "asset.glb").write_bytes(b"broken")
    with app_factory() as client:
        ids = {t["id"] for t in client.get("/api/templates").json()}
        assert "rack-42u-600x1200" in ids and "pdu-floor-generic" not in ids
        assert client.get("/api/templates/rack-42u-600x1200/1.0.0/thumbnail.png").status_code == 200

def test_health_reports_strata_down(app_factory, monkeypatch):
    with app_factory(env={"STRATA_BASE_URL": "http://127.0.0.1:9/v1"}) as client:
        h = client.get("/api/health").json()
        assert h["server"] == "ok" and h["strata"]["ok"] is False and set(h["queue"]) >= {"waiting", "running"}

def test_profiles_post_not_implemented(client):
    assert client.post("/api/profiles", json={"name": "x", "from_run": "a/b"}).status_code == 501
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/server/test_outputs_system.py -q`
Expected: FAIL (404 pada route)

- [ ] **Step 3: Implement**

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/server -q`
Expected: semua PASS

- [ ] **Step 5: Commit**

```bash
rtk git add server tests/server && rtk git commit -m "feat(server): outputs with etag and zip, templates, profiles stub, health and config"
```

---

### Task 8: Integrasi API nyata (import → regenerate → output)

**Files:**
- Test: `tests/server/test_integration.py`

- [ ] **Step 1: Tulis test**

```python
@pytest.mark.blender
@pytest.mark.slow
def test_import_regenerate_download(app_factory, plan_bytes):
    with app_factory() as client:                                    # real stage impls, real Blender
        pid = client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")},
                          data={"name": "Gatsu", "start": "false"}).json()["project_id"]
        client.post(f"/api/projects/{pid}/specs/import", content=Path("benchmarks/gatsu/gt_spec.json").read_bytes(),
                    headers={"content-type": "application/json"})
        rid = client.post(f"/api/projects/{pid}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        run = wait_status(client, pid, rid, {"succeeded", "needs_attention"}, timeout=120)
        assert [s["status"] for s in run["stages"][7:]] == ["succeeded", "needs_attention", "succeeded", "succeeded"]
        outs = client.get(f"/api/projects/{pid}/outputs").json()
        assert outs[0]["version"] == 1 and {"shell.glb", "report.pdf"} <= {f["name"] for f in outs[0]["files"]}
        assert client.get(f"/api/projects/{pid}/outputs/1/report.html").status_code == 200
        events = client_events(client, pid)
        assert any(e["type"] == "stage.progress" for e in events) and events[-1]["type"] in ("run.finished", "output.ready")
        again = client.post(f"/api/projects/{pid}/regenerate", json={"version": 1}).json()
        assert again == {"run_id": None, "reused": True}
```
Tahap 8 bernilai `needs_attention` karena IoU Gatsu 0.45 < 0.70 (sudah dicatat di M2), dan itu tidak menghentikan run.

- [ ] **Step 2: Jalankan**

Run: `rtk uv run --env-file .env pytest tests/server/test_integration.py -q -s`
Expected: PASS dalam < 60 s. Bila gagal, debug dengan systematic-debugging; test tidak boleh dilemahkan.

- [ ] **Step 3: Commit**

```bash
rtk git add tests/server/test_integration.py && rtk git commit -m "test(server): import, regenerate and download end to end"
```

---

### Task 9: Fondasi web (shell, routing, klien API, SSE, status)

**Files:**
- Modify: `web/package.json` (deps: `react-router-dom`, `@tanstack/react-query`, `@carbon/icons-react`, `react-virtuoso`; dev: `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`; script `"test": "vitest run"`), `web/vite.config.ts` (proxy + test env jsdom), `web/src/main.tsx`, `web/src/index.scss` (font Plex Mono via `@ibm/plex` yang sudah dibundel Carbon; util `.mono`)
- Create: `web/src/app/App.tsx` (ganti demo), `web/src/app/Shell.tsx`, `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/hooks.ts`, `web/src/api/sse.ts`, `web/src/components/StatusTag.tsx`, `web/src/components/HealthIndicator.tsx`, `web/src/lib/runState.ts`
- Test: `web/src/lib/runState.test.ts`, `web/src/components/StatusTag.test.tsx`

**Interfaces:**
- Produces:
  - `api/types.ts`: `ProjectSummary`, `ProjectDetail`, `Run`, `Stage`, `StageStatus`, `RunStatus`, `ApiEvent` (09 §3–§4), `SpecVersion`, `OutputVersion`, `Template`, `Health`. Field persis respons server Task 3–7.
  - `api/client.ts`: `api.get<T>(path)`, `api.post<T>(path, body?)`, `api.upload(form: FormData)`. Error → `ApiError {status, code, message, details}`.
  - `api/hooks.ts` (TanStack Query):
    - `useProjects()` (refetch 5 s), `useProject(id)`, `useRuns(id)`, `useSpecs(id)`, `useOutputs(id)`, `useTemplates()`;
    - `useHealth()` (refetch 10 s);
    - mutasi `useCreateProject`, `useImportSpec`, `useStartRun`, `useRegenerate`, `useCancelRun`.
  - `api/sse.ts useProjectEvents(id, onEvent)`: `EventSource('/api/projects/{id}/events?since=<lastSeq>')` dengan reconnect otomatis. Menyimpan `lastSeq`. Setiap event `run.*`/`stage.*`/`spec.created`/`output.ready` meng-invalidate query terkait.
  - `lib/runState.ts`:
    - `applyEvent(run: Run, e: ApiEvent): Run` (reducer murni: `stage.started` → running, `stage.progress` → progress, `stage.finished` → status + durasi, `run.finished` → status);
    - `stageLabel(n)` = nama Indonesia (`Input`, `Preprocess`, `Grid & skala`, `Ekstraksi`, `Ruang`, `Validasi`, `Review Strata`, `Build`, `Verifikasi`, `Dokumen`, `Publikasi`).
  - `components/StatusTag.tsx`: `<StatusTag status warning? />` menampilkan ikon + teks + warna persis tabel 08 §5 (`Menunggu`, `Berjalan`, `Selesai`, `Selesai dengan peringatan`, `Perlu perhatian`, `Gagal`, `Dilewati`; `queued` = `Menunggu`).
  - `app/Shell.tsx`: Carbon `Theme g100` + `Header` ("Floorplan3D") + `SideNav` (Projects, Templates, System) + `HealthIndicator` di kanan (tiga titik: Strata hijau/biru/merah, Blender idle/busy, angka antrean; klik → `/system`; setiap titik punya teks untuk screen reader).
  - `app/App.tsx`: router `/projects`, `/projects/new`, `/projects/:id`, `/templates`, `/system`, redirect `/` → `/projects`. Halaman berupa placeholder sampai Task 10–12.

- [ ] **Step 1: Install + tulis test yang gagal**

```bash
cd web && rtk npm i react-router-dom @tanstack/react-query @carbon/icons-react react-virtuoso \
  && rtk npm i -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

```ts
// runState.test.ts
it("applies stage events in order", () => {
  let run = emptyRun("r1", "regenerate");
  run = applyEvent(run, ev("stage.started", 7));
  run = applyEvent(run, ev("stage.progress", 7, { percent: 60, msg: "built" }));
  expect(run.stages[7]).toMatchObject({ status: "running", progress: 60 });
  run = applyEvent(run, ev("stage.finished", 7, { status: "succeeded", duration_ms: 4100 }));
  run = applyEvent(run, ev("run.finished", null, { status: "succeeded" }));
  expect([run.stages[7].status, run.stages[7].duration_ms, run.status]).toEqual(["succeeded", 4100, "succeeded"]);
});
it("ignores events of another run", () => {
  expect(applyEvent(emptyRun("r1", "full"), { ...ev("stage.started", 3), run_id: "r2" }).stages[3].status).toBe("pending");
});
```

```tsx
// StatusTag.test.tsx
it.each([["running", "Berjalan"], ["needs_attention", "Perlu perhatian"], ["skipped", "Dilewati"], ["queued", "Menunggu"]])(
  "%s shows icon and text", (status, text) => {
    render(<StatusTag status={status as StageStatus} />);
    expect(screen.getByText(text)).toBeInTheDocument();
    expect(document.querySelector("svg")).not.toBeNull();
  });
```
`emptyRun` dan `ev` adalah helper di file test.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test`
Expected: FAIL (modul belum ada)

- [ ] **Step 3: Implement fondasi**

- [ ] **Step 4: Jalankan test, build, lint**

Run: `cd web && rtk npm test && rtk npm run build && rtk npm run lint`
Expected: semua PASS / sukses

- [ ] **Step 5: Commit**

```bash
rtk git add web && rtk git commit -m "feat(web): app shell, routing, api client, SSE hook, status tag"
```

---

### Task 10: Halaman projects + project baru

**Files:**
- Create: `web/src/pages/ProjectsPage.tsx`, `web/src/pages/NewProjectPage.tsx`, `web/src/lib/params.ts`
- Test: `web/src/lib/params.test.ts`

**Interfaces:**
- Produces:
  - `ProjectsPage`: Carbon `DataTable` (sort, `TableToolbarSearch`, `Pagination` 10/25/50). Kolom: Nama · Lantai · Status (`StatusTag`) · Tahap aktif · Skor validator · IoU · Versi · Diperbarui (angka Plex Mono). Aksi baris `OverflowMenu`: Buka, Jalankan ulang, Regenerate, Hapus (dengan `Modal` konfirmasi). Tombol primer "Project baru". Empty state dengan tombol "Upload denah pertama".
  - `NewProjectPage`: form maks 672px:
    - `FileUploaderDropContainer` (accept `.jpg,.jpeg,.png,.pdf`, ≤ 50 MB, pratinjau thumbnail untuk gambar);
    - `TextInput` nama (default nama file tanpa ekstensi);
    - `TextArea` prompt (placeholder dari 08 §3.2);
    - `Accordion` "Parameter lanjutan": tinggi dinding, tinggi pintu, tebal dinding default (`NumberInput` mm), nama lantai, tipe site (`Dropdown` dari enum spec), skala manual (`TextInput` mm/px), `Toggle` "Gunakan Strata";
    - tombol "Mulai pipeline" dan "Buat tanpa menjalankan" (`start=false`, untuk impor spec); sukses → `/projects/:id?tab=pipeline`;
    - error API tampil di `InlineNotification`.
  - `lib/params.ts buildProjectForm(file, fields) -> FormData` (hanya parameter yang diisi; angka divalidasi > 0).

- [ ] **Step 1: Tulis test yang gagal**

```ts
it("only sends filled advanced params", () => {
  const fd = buildProjectForm(new File(["x"], "plan.jpeg"), { name: "", prompt: "data hall", wallHeight: 4500, start: true });
  expect(fd.get("name")).toBe("plan");
  expect(JSON.parse(fd.get("params") as string)).toEqual({ wall_height: 4500 });
  expect(fd.get("start")).toBe("true");
});
it("rejects non-positive numbers", () => {
  expect(() => buildProjectForm(new File(["x"], "a.png"), { wallHeight: -1, start: false })).toThrow(/wall_height/);
});
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test`
Expected: FAIL

- [ ] **Step 3: Implement halaman**

- [ ] **Step 4: Jalankan test, build, lint**

Run: `cd web && rtk npm test && rtk npm run build && rtk npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add web && rtk git commit -m "feat(web): projects list and new project form"
```

---

### Task 11: Detail project — header, tab Pipeline, tab Logs

**Files:**
- Create: `web/src/pages/ProjectDetailPage.tsx`, `web/src/components/StageTimeline.tsx`, `web/src/components/StagePanel.tsx`, `web/src/components/LogViewer.tsx`, `web/src/lib/logs.ts`
- Test: `web/src/lib/logs.test.ts`

**Interfaces:**
- Produces:
  - `ProjectDetailPage`: header (nama display 32px weight 300, `StatusTag`, versi HEAD, tombol `Jalankan ulang ▾` (`OverflowMenu`: full / dari tahap…), `Regenerate`, `Batalkan run` saat running, "Impor spec" (`Modal` + file JSON → `useImportSpec`)). `Tabs` sinkron dengan `?tab=`: pipeline, logs, outputs, versions (review/editor menampilkan "tersedia di M5/M4"). Satu `useProjectEvents` di level halaman.
  - `StageTimeline`: Carbon `ProgressIndicator vertical` dengan 11 tahap, ikon/teks status, dan durasi. Klik → pilih tahap. Tahap aktif terpilih otomatis saat run berjalan.
  - `StagePanel`:
    - tahap 0–6: kerangka ("tersedia di M5/M6" + pesan tahap dari run);
    - **7**: progres + 20 baris log terakhir + daftar file output (nama, ukuran);
    - **8**: IoU besar + ambang + `iou_mask.png` dengan legenda (hijau/merah/biru) + status cek glb dan grid;
    - **9**: iframe `report.html` (dari output versi run) + tombol unduh PDF;
    - **10**: tombol "Buka editor" (ke `?tab=editor`).
  - `LogViewer`:
    - `Virtuoso` dengan data `useProjectEvents` + history awal `GET events.jsonl`;
    - filter run (`Dropdown`), tahap (`MultiSelect`), level (`MultiSelect`), pencarian teks;
    - `Toggle` "Ikuti" (auto-scroll);
    - tombol unduh `events.jsonl?run_id=`;
    - baris memakai `formatLogLine`, Plex Mono 12px, label level warn kuning dan error merah.
  - `lib/logs.ts`: `formatLogLine(e) -> {time: "HH:MM:SS.mmm", stage: "[S3]"|"[--]", level: "INFO", msg}` dan `filterEvents(events, {runId, stages, levels, q}) -> ApiEvent[]` (q tidak peka huruf besar, mencari di `msg`).

- [ ] **Step 1: Tulis test yang gagal**

```ts
it("formats a log line", () => {
  expect(formatLogLine({ seq: 1, ts: "2026-10-23T09:00:15.221+07:00", run_id: "r", stage: 3, type: "stage.log", level: "warn", msg: "hi", data: {} }))
    .toEqual({ time: "09:00:15.221", stage: "[S3]", level: "WARN", msg: "hi" });
});
it("filters by run, stage, level and text", () => {
  const evs = [log("r1", 3, "info", "Candidate k3"), log("r1", 7, "error", "boom"), log("r2", 3, "info", "other")];
  expect(filterEvents(evs, { runId: "r1", stages: [3], levels: ["info"], q: "cand" }).map(e => e.msg)).toEqual(["Candidate k3"]);
});
```
Waktu ditampilkan memakai jam lokal dari string `ts` (bagian jam setelah `T`), tanpa konversi zona waktu, agar konsisten dengan server.

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test`
Expected: FAIL

- [ ] **Step 3: Implement**

- [ ] **Step 4: Jalankan test, build, lint**

Run: `cd web && rtk npm test && rtk npm run build && rtk npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add web && rtk git commit -m "feat(web): project detail with pipeline timeline, stage panels and live logs"
```

---

### Task 12: Outputs, Versions, Templates, System, OverlayViewer

**Files:**
- Create: `web/src/components/OutputsTab.tsx`, `web/src/components/VersionsTab.tsx`, `web/src/pages/TemplatesPage.tsx`, `web/src/pages/SystemPage.tsx`, `web/src/components/OverlayViewer.tsx`, `web/src/lib/viewport.ts`, `web/src/lib/diff.ts`
- Test: `web/src/lib/viewport.test.ts`, `web/src/lib/diff.test.ts`

**Interfaces:**
- Produces:
  - `OutputsTab`: `Dropdown` versi (default terbaru yang punya output); kartu per file (nama, ukuran terformat, tombol Unduh); "Unduh semua (zip)"; iframe dokumen; galeri render (`renders/*.png`).
  - `VersionsTab`: tabel versi (nomor, sumber `Tag`, waktu, pesan, run, output tersedia) + pemilih dua versi → diff ringkas (`summarizeDiff`) + daftar ops. Aksi baris "Regenerate versi ini". "Jadikan basis editor" ditunda ke M4 (tombol disabled + tooltip).
  - `TemplatesPage`: grid kartu (thumbnail, nama, kategori, dimensi `w × d × h`, versi), filter kategori (`Dropdown`), klik → `Modal` berisi `CodeSnippet` JSON template. Pratinjau 3D ditunda ke M4.
  - `SystemPage`: Strata (URL, model, ok/status/latensi), Blender (path, versi, busy), antrean (waiting + daftar running), versi aplikasi (commit, schema).
  - `OverlayViewer` props `{src, layers?: {id, label, src, visible}[]}`: gambar dasar + layer gambar transparan bertumpuk, zoom (wheel, tombol +/−/reset), pan (drag), toggle layer (`Checkbox`). Matematika ada di `lib/viewport.ts`.
  - `lib/viewport.ts`:
    - `zoomAt(view: {scale, x, y}, factor, cx, cy) -> view`: titik di bawah kursor tetap di tempat; skala dibatasi `[0.1, 20]`;
    - `fit(imgW, imgH, boxW, boxH) -> view`.
  - `lib/diff.ts summarizeDiff(d) -> string[]`, mis. `["Dinding: +1 −0 ~1", "Pintu: −1"]`. Tipe tanpa perubahan tidak ditampilkan.

- [ ] **Step 1: Tulis test yang gagal**

```ts
it("zooms around the cursor", () => {
  const v = zoomAt({ scale: 1, x: 0, y: 0 }, 2, 100, 50);
  expect(v).toEqual({ scale: 2, x: -100, y: -50 });              // image point (100,50) stays under the cursor
  expect(zoomAt({ scale: 19, x: 0, y: 0 }, 2, 0, 0).scale).toBe(20);
});
it("fits the image in the box", () => {
  expect(fit(1600, 945, 800, 800)).toEqual({ scale: 0.5, x: 0, y: (800 - 472.5) / 2 });
});
it("summarizes a diff", () => {
  expect(summarizeDiff({ walls: { added: ["W6"], removed: [], changed: ["W1"] }, openings: { added: [], removed: ["D2"], changed: [] },
                         rooms: { added: [], removed: [], changed: [] } })).toEqual(["Dinding: +1 −0 ~1", "Bukaan: +0 −1 ~0"]);
});
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `cd web && rtk npm test`
Expected: FAIL

- [ ] **Step 3: Implement**

- [ ] **Step 4: Jalankan test, build, lint**

Run: `cd web && rtk npm test && rtk npm run build && rtk npm run lint`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
rtk git add web && rtk git commit -m "feat(web): outputs, versions with diff, templates, system, overlay viewer"
```

---

### Task 13: Verifikasi end-to-end di browser + kriteria M3

- [ ] **Step 1: Siapkan data dan jalankan server + web**

```bash
rtk uv run --env-file .env python -m core.templates.make_placeholders --out data/templates
rtk uv run --env-file .env uvicorn server.app:app --port 8000        # background
cd web && rtk npm run dev                                            # background, port 5173
```

- [ ] **Step 2: Alur kriteria selesai lewat Playwright MCP**

1. `/projects/new`: upload `floorplan/plan.jpeg`, nama "MSC Gatsu L1", klik "Buat tanpa menjalankan".
2. Detail project: "Impor spec" → `benchmarks/gatsu/gt_spec.json` → versi 1 muncul di tab Versions.
3. Klik Regenerate. Di tab Pipeline, tahap 7–10 bergerak live. Di tab Logs, baris muncul tanpa reload. Ukur latensi: selisih `ts` event dan waktu muncul di DOM (`performance.now()` lewat `browser_evaluate` pada event `stage.progress`) ≤ 1 s.
4. Tab Outputs: unduh `shell.glb` (status 200), iframe dokumen tampil.
5. Header: indikator kesehatan tampil (Strata merah, karena server Strata mati).

Simpan screenshot tiap langkah ke scratchpad.

- [ ] **Step 3: Restart di tengah run**

Mulai Regenerate pada versi baru (ops tinggi dinding lewat API), matikan Uvicorn saat tahap 7 berjalan, lalu jalankan lagi. `GET runs/{rid}` harus `failed` + `interrupted`; run berikutnya yang `queued` (bila ada) berjalan, dan regenerate baru bisa dimulai.

- [ ] **Step 4: Lighthouse a11y**

Run: `npx lighthouse http://localhost:5173/projects --only-categories=accessibility --quiet --chrome-flags="--headless" --output=json --output-path=<scratchpad>/lh-projects.json` (dan halaman detail).
Expected: skor ≥ 0.90. Perbaiki temuan (label, kontras, landmark) hingga lulus. Bila Chrome untuk Lighthouse tidak tersedia, jalankan axe-core lewat Playwright (`browser_evaluate` dengan axe dari `node_modules/axe-core` yang di-inject), catat hasilnya, dan tandai kriteria sebagai "diverifikasi dengan axe".

- [ ] **Step 5: Suite + lint**

Run: `rtk uv run --env-file .env pytest -q` dan `cd web && rtk npm test && rtk npm run lint && rtk npm run build`
Expected: semua hijau.

- [ ] **Step 6: Tutup M3 di ROADMAP, lalu commit**

Centang hanya tugas yang benar-benar selesai. Tulis blok "Status M3": hasil alur, latensi log terukur, skor a11y, dan penyimpangan (profiles POST 501, tab Review/Editor placeholder, pratinjau 3D template ditunda).

```bash
rtk git add ROADMAP.md && rtk git commit -m "docs: close M3"
```
