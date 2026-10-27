# M6 — Tahap 6: Review Strata (T0–T4), Gerbang Skor, Benchmark LLM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tahap 6 memanggil Strata untuk elemen berkeyakinan rendah atau elemen bermasalah. Perubahan yang lolos gerbang skor disimpan sebagai `spec.vN` (`source: llm`), dan hasilnya tidak pernah lebih buruk dari tahap 5. Setiap tugas hanya aktif bila lolos benchmark Gatsu. Bila Strata mati atau semua tugas nonaktif, tahap 6 `skipped` dan pipeline tetap selesai.

**Architecture:**
- **Paket `core/llm_review/`:**
  - `client.py`: klien Strata di atas SDK `openai`, dengan healthcheck, timeout, retry JSON invalid, serta catatan token dan latensi;
  - `crops.py`: crop zoom 768², thumbnail konteks 384², dan bukti teks;
  - `tasks.py` + `prompts/<task>/v1.md`: schema, prompt berversi, few-shot, voting, dan pemetaan jawaban ke ops;
  - `tools.py`: tool T4 beserta batasnya;
  - `harness.py`: routing, Fase A (T1→T2→T3, gerbang −0.005), Fase B (T4, skor harus naik), batas waktu, `transcript.jsonl`, dan `decisions.json`;
  - `stage.py`: tahap 6 lengkap dengan fallback.
- **Penyimpanan:** semua op yang diterima diputar ulang di atas versi tahap 5 lewat `SpecStore.commit_ops(..., by="llm", run_id=...)`. Dengan begitu edit editor yang masuk selama review tidak tertimpa (`VersionConflict`).
- **Tahap 0:** T0 opsional, hanya mengisi field prompt yang kosong dari parser aturan.
- **Benchmark:**
  - `benchmarks/llm_items.py` membangun item berlabel dari GT Gatsu, memakai tahap 1–4 yang dijalankan ulang secara deterministik;
  - `benchmarks/run_llm_bench.py` membandingkan Strata dengan baseline §7.2;
  - keputusan aktivasi dicatat di `benchmarks/DECISIONS.md`.
- **Dashboard:** tab Review menampilkan tabel keputusan Strata, crop, respons mentah, dan banner `skipped`. Panel tahap 6 menampilkan ringkasan. Halaman `/system` sudah menampilkan status Strata dan tugas aktif sejak M3.

**Tech Stack:** Python 3.12, `openai` SDK (sudah terpasang), `httpx` (sudah terpasang; `MockTransport` untuk test), pydantic 2, OpenCV, Shapely 2, FastAPI, pytest. Dashboard: React + Carbon g100, TanStack Query, Vitest.

**Spec:**
- `PRD/05-llm-review.md` (seluruhnya: §2 tugas dan routing, §3 format input, §4 tool, §5 harness, §6 fallback, §7 benchmark, §8 spike, §9 transkrip);
- `PRD/04-extraction.md` Tahap 0 langkah 4 (parser Strata `PromptParams`);
- `PRD/09-api.md` event `llm.decision`;
- `PRD/08-dashboard.md` (tab Review, panel tahap);
- `PRD/01-requirements.md` FR-IN-04, FR-LLM-01…09;
- `API_DOCUMENTATION.md` (endpoint Strata: `/v1/chat/completions`, `/health`, `/status`);
- `ROADMAP.md` M6 (Tugas dan Kriteria selesai).

Branch: `m6-strata` dari `main` (M0–M5 sudah di-merge).

## Global Constraints

- **Lingkungan kerja:**
  - semua perintah shell diawali `rtk`;
  - jangan membaca atau meng-commit `server-info.txt`;
  - test dijalankan dengan `rtk uv run --env-file .env pytest -q`;
  - test yang memakai Gatsu atau pipeline penuh ditandai `@pytest.mark.slow`.
- **Strata dalam test:**
  - unit test tidak pernah memanggil Strata asli. Semua test memakai `FakeStrata` (`tests/llm_review/conftest.py`) atau `httpx.MockTransport`;
  - test live ditandai `@pytest.mark.strata` dan memakai fixture `strata_live`, yang melakukan `pytest.skip` bila `GET /health` gagal dalam 3 s.
- **Aturan panggilan (PRD/05 §5):**
  - vote 1 memakai `temperature: 0`; vote 2–3 memakai `temperature: 0.4` dengan crop zoom ×1.3;
  - output tidak valid di-retry maksimal 2 kali dengan pesan error parsing, lalu elemen dicatat `invalid_output`;
  - timeout per panggilan `STRATA_TIMEOUT_S`, dan total tahap 6 600 s;
  - batas 60 elemen untuk T1+T2 (keyakinan terendah dulu) dan `LLM_MAX_ITER` iterasi T4;
  - `LLM_VOTES` default 3.
- **Lantai terjamin:**
  - Fase A menerima perubahan bila tidak ada error validator dan `skor_baru >= skor - 0.005`;
  - Fase B menerima perubahan bila tidak ada error dan `skor_baru > skor`;
  - gerbang memakai `ValidationContext` yang sama dengan tahap 5;
  - elemen yang provenance-nya `editor` atau `manual` tidak pernah dikirim ke Strata dan tidak pernah diubah oleh tool.
- **Prompt:**
  - ditulis dalam bahasa Inggris di `core/llm_review/prompts/<task>/v<n>.md`;
  - versinya dicatat di setiap baris transkrip;
  - system prompt T1–T3 memuat kerangka §3.4 secara verbatim.
- **Flag:** `LLM_TASKS_ENABLED` hanya berisi tugas yang lolos §7.2. Keputusannya tercatat di `benchmarks/DECISIONS.md`.
- **Determinisme:**
  - nama file crop berbentuk `crops/<element>_v<vote>.png` dan `crops/<element>_ctx.png`;
  - antrean review diurutkan dengan kunci `(confidence, id)`.
- **Bahasa dan konvensi:**
  - copy UI dalam bahasa Indonesian dengan Carbon g100;
  - dokumen dalam bahasa Indonesia dengan istilah teknis Inggris;
  - commit dalam bahasa Inggris dan diakhiri `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **HEAD berubah selama tahap 6** (pengguna commit di editor saat Strata berjalan). Perubahan Strata tidak boleh menimpa edit itu. Hasil yang diharapkan: `VersionConflict`, v2 tidak disimpan, tahap 6 `succeeded` dengan peringatan. Test di Task 7.
2. **Strata mati di tengah review** (timeout atau koneksi putus per panggilan). Elemen dicatat `invalid_output`, review berlanjut atau berhenti dengan rapi, perubahan yang sudah diterima tetap dipakai, dan pipeline lanjut. Test di Task 6.
3. **Model menjawab dengan ID yang salah atau tidak ada** (jawaban T1 untuk elemen lain, tool T4 dengan ID asing atau elemen hasil edit manusia). Jawaban ditolak dengan alasan tercatat, tanpa crash. Test di Task 5 dan Task 6.
4. **Batas waktu habis di tengah voting.** Review berhenti sebelum panggilan berikutnya, hasil yang sudah diterima disimpan, dan muncul peringatan "batas waktu". Test di Task 6.
5. **Rerun `from_stage=6` tanpa artefak tahap 1–5 di run itu.** Tahap 6 `skipped` dengan alasan `no_artifacts`, bukan crash. Test di Task 7.

---

### Task 1: Probe kemampuan Strata (spike, PRD/05 §8)

**Files:**
- Create: `benchmarks/spike/probe_strata.py`
- Modify: `benchmarks/reports/spike-strata.md`, `.gitignore` (`benchmarks/spike/out/`, `benchmarks/.cache/`)

Throwaway, tanpa unit test. Spike M0 menunda dua hal: kemampuan server dan akurasi. Task ini hanya mengukur **kemampuan server** yang menentukan desain klien di Task 2. Akurasi T1/T2 dalam 4 varian (± bukti teks, ± few-shot) diukur di Task 9 dengan set benchmark ≥ 40 item. Set itu menggantikan 20 crop manual spike M0, jadi pelabelan tidak dikerjakan dua kali.

- [ ] **Step 1: Tulis probe** (pakai `openai.OpenAI(base_url=STRATA_BASE_URL, api_key="none")`). Setiap probe mencatat hasil ke `benchmarks/spike/out/probe.json`:
  - a. `GET /health`, `GET /status`, `GET /v1/models`.
  - b. Teks → JSON `{"answer": "yes"|"no"}` sebanyak 5×, tanpa `response_format`. Hitung respons yang mengandung `<think>` atau code fence, dan respons yang langsung lolos `json.loads`.
  - c. Sama dengan (b), ditambah `response_format={"type": "json_schema", "json_schema": {...}}`. Catat apakah diterima (tidak 4xx) dan apakah ditaati.
  - d. `extra_body={"reasoning_effort": e}` untuk e ∈ {`none`, `low`, `medium`}. Catat apakah diterima dan berapa latensinya.
  - e. **Downscale gambar:** gambar putih 768² berisi 6 kata acak dengan tinggi huruf 6/8/10/12/16/20 px, minta transkripsi. Catat tinggi terkecil yang terbaca. Ulangi untuk gambar 1536² (calon ukuran overlay T4).
  - f. **Tool calling:** tool `finish(summary)` dan `delete_wall(id, reason)`, dengan prompt "delete wall W3 because it is a dimension line". Catat apakah `tool_calls` terisi dan argumennya JSON valid.
  - g. **Latensi:** 5× untuk tiap kombinasi teks saja, 1 gambar 768², serta 768² + 384². Catat median dan p90.

- [ ] **Step 2: Jalankan dan tulis laporan**

Run: `rtk uv run --env-file .env python benchmarks/spike/probe_strata.py`
Expected: `probe.json` terisi untuk a–g.

Tulis ulang `benchmarks/reports/spike-strata.md`: hasil a–g dan **keputusan untuk Task 2–6**:
- `USE_RESPONSE_FORMAT` (true bila (c) diterima dan menaikkan tingkat valid);
- cara mengirim `reasoning_effort`;
- `T4_OVERLAY_MAX_PX` (1536 bila teks 12 px terbaca di 1536², bila tidak 1024);
- latensi median per panggilan bergambar;
- estimasi waktu 60 elemen × ~2.3 suara terhadap batas 600 s.

Bila estimasi > 600 s, catat bahwa batas waktu (Task 6) yang membatasi.

- [ ] **Step 3: Commit**

```bash
rtk git add benchmarks/spike/probe_strata.py benchmarks/reports/spike-strata.md .gitignore
rtk git commit -m "bench(strata): capability probe (JSON, response_format, effort, image size, tools, latency)"
```

---

### Task 2: Klien Strata

**Files:**
- Create: `core/llm_review/__init__.py`, `core/llm_review/client.py`, `tests/llm_review/__init__.py`, `tests/llm_review/conftest.py`, `tests/llm_review/test_client.py`

**Interfaces:**
- Produces:
  - `CallResult` (dataclass): `raw: str`, `parsed: dict | None`, `valid: bool`, `error: str | None`, `latency_ms: int`, `tokens: dict` (`{"prompt": int, "completion": int}`, dijumlah lintas retry), `tool_calls: list[dict]` (`[{"id", "name", "arguments": dict}]`), `attempts: int`.
  - `StrataClient(base_url: str, model: str, timeout_s: float, http_client: httpx.Client | None = None, use_response_format: bool = <hasil Task 1>)`.
  - `StrataClient.health(timeout_s: float = 3.0) -> bool`: `GET <root>/health` dengan root = base_url tanpa `/v1`.
  - `StrataClient.ask_json(messages: list[dict], schema: type[BaseModel], *, effort: str, temperature: float, max_retries: int = 2) -> CallResult`.
  - `StrataClient.ask_tools(messages: list[dict], tools: list[dict], *, effort: str, temperature: float = 0.0) -> CallResult`.
  - `extract_json(text: str) -> dict` (`ValueError` bila gagal).
  - `tests/llm_review/conftest.py`:
    - `FakeStrata(script: Callable[[list[dict], dict], str | dict | Exception])`, dengan antarmuka yang sama (`health`, `ask_json`, `ask_tools`). `ask_json` memvalidasi jawaban dengan schema seperti klien asli. `kwargs` membawa `temperature`, `effort`, `schema`/`tools`;
    - `FakeStrata.calls: list[dict]`;
    - fixture `strata_live`.

- [ ] **Step 1: Tulis test yang gagal** (`tests/llm_review/test_client.py`; server palsu memakai `httpx.MockTransport` yang dipasang lewat `http_client`):

```python
def test_extract_json_strips_think_and_fences():
    assert extract_json('<think>hmm</think>\n```json\n{"id": "W7", "verdict": "wall"}\n```') == {"id": "W7", "verdict": "wall"}

def test_ask_json_retries_invalid_then_succeeds():  # 1st reply "sure!", 2nd valid
    r = client.ask_json(msgs, T1Like, effort="low", temperature=0)
    assert r.valid and r.attempts == 2 and r.parsed["verdict"] == "wall"
    assert "invalid" in sent_bodies[1]["messages"][-1]["content"].lower()  # parse error fed back

def test_ask_json_gives_up_after_two_retries():  # always "no json"
    r = client.ask_json(msgs, T1Like, effort="low", temperature=0)
    assert not r.valid and r.attempts == 3 and r.parsed is None and r.error

def test_schema_violation_counts_as_invalid():  # {"id": "W7", "verdict": "maybe"}
    assert client.ask_json(msgs, T1Like, effort="low", temperature=0, max_retries=0).valid is False

def test_timeout_is_an_invalid_result_not_an_exception():  # transport raises httpx.ReadTimeout
    r = client.ask_json(msgs, T1Like, effort="low", temperature=0)
    assert not r.valid and "timeout" in r.error.lower()

def test_tokens_and_latency_recorded():
    r = client.ask_json(...)
    assert r.tokens == {"prompt": 120, "completion": 9} and r.latency_ms >= 0

def test_ask_tools_parses_tool_calls():
    r = client.ask_tools(msgs, TOOLS, effort="medium")
    assert r.tool_calls == [{"id": "c1", "name": "delete_wall", "arguments": {"id": "W3", "reason": "dim line"}}]

def test_health_false_on_connection_error():
    assert StrataClient("http://x/v1", "m", 1, http_client=failing).health() is False

def test_request_carries_model_temperature_effort():
    assert body["model"] == "m" and body["temperature"] == 0.4 and body["reasoning_effort"] == "low"
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_client.py -q`
Expected: FAIL (`ModuleNotFoundError: core.llm_review`).

- [ ] **Step 3: Implementasi**

Detail implementasi:
- `openai.OpenAI(base_url=..., api_key="none", timeout=timeout_s, max_retries=0, http_client=...)`;
- `reasoning_effort` dikirim lewat cara yang dipilih di Task 1, yaitu `extra_body` atau parameter;
- `extract_json` membuang blok `<think>…</think>` dan code fence, lalu mengambil objek `{…}` terluar;
- pesan retry: `{"role": "assistant", "content": raw}` diikuti `{"role": "user", "content": "Your previous output was invalid: <error>. Answer ONLY with JSON matching the schema."}`;
- error SDK (`APITimeoutError`, `APIConnectionError`, `APIStatusError`) menjadi `CallResult(valid=False, error=...)` dan tidak di-retry;
- yang di-retry hanya parse error dan schema error.

- [ ] **Step 4: Jalankan test, pastikan lolos**

Run: `rtk uv run --env-file .env pytest tests/llm_review -q`
Expected: PASS.

- [ ] **Step 5: Smoke live** (`tests/llm_review/test_client_live.py`, `@pytest.mark.strata`): `ask_json` dengan schema `{"answer": Literal["yes","no"]}` menghasilkan `valid`.

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_client_live.py -q`
Expected: PASS saat Strata hidup, dan skip bila mati.

- [ ] **Step 6: Commit**

```bash
rtk git add core/llm_review tests/llm_review
rtk git commit -m "feat(llm): Strata client with JSON retry, tool calls, timing and token accounting"
```

---

### Task 3: Crop zoom, thumbnail konteks, bukti teks (PRD/05 §3.1–3.2)

**Files:**
- Create: `core/llm_review/crops.py`, `tests/llm_review/test_crops.py`

**Interfaces:**
- Consumes: `px_from_mm(px_to_mm)` (`core/extraction/rooms/overlay.py`), `endpoint_connected`, `wall_footprint` (`core/spec/derive.py`).
- Produces:
  - `crop_box_px(spec: Spec, eid: str, to_px, zoom: float = 1.0) -> tuple[int, int, int, int]`:
    - kotak persegi berpusat di elemen;
    - sisi dalam mm = `clamp(L × 1.6, 2000, 8000) / zoom`, dengan L = panjang dinding atau lebar pintu.
  - `element_crop(page_gray: np.ndarray, spec: Spec, eid: str, to_px, zoom: float = 1.0) -> np.ndarray`:
    - menghasilkan BGR 768×768;
    - elemen target diberi outline magenta `(255, 0, 255)` 3 px dan label ID besar di pojok kiri atas;
    - dinding dan bukaan lain digambar abu-abu tipis (1 px);
    - area di luar halaman diisi putih.
  - `context_thumb(page_gray: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray`: BGR 384×384 dari seluruh halaman (rasio dijaga, sisa diisi putih), dengan kotak merah `(0, 0, 255)` 2 px di posisi crop.
  - `wall_evidence(spec: Spec, wid: str, *, mm_per_px: float, hatch: np.ndarray | None, texts: list[dict], to_px) -> str`, dengan baris persis seperti contoh §3.2:
    - `Element <id>`;
    - `length` / `thickness` (`stroke` = thickness / mm_per_px, 1 desimal) / `orientation` (`horizontal` / `vertical` / `diagonal`, toleransi 1.5°);
    - `connects to walls at ends: start=<id|none>, end=<id|none>`;
    - `passes through dense-hatch area: yes|no (<p>% of length)`, dengan sampel tiap 50 mm di `hatch` > 0 dan "yes" bila ≥ 30%;
    - `nearest text within 600 mm: "<text>" (<cls> class)` atau `none`;
    - `parallel partner line found: yes|no` dari `provenance.evidence.pair_overlap > 0`;
    - `CV confidence: <0.00>`.
  - `door_evidence(spec: Spec, did: str) -> str`: `Element`, host wall, width, `door_type`/`hinge`/`swing` saat ini, `evidence` arc/gap, `CV confidence`.
  - `room_evidence(spec: Spec, rid: str, label_text: str) -> str`: `Element`, `OCR label: "<text>"`, `area: <m² 1 desimal>`, `current type: <type>`.

- [ ] **Step 1: Tulis test yang gagal** (spec sintetis: dinding horizontal W1 4200 mm dan pintu D1; `page` 2000² putih; `to_px` skala 0.25 px/mm):

```python
def test_crop_side_clamped_and_zoomed():
    x0, y0, x1, y1 = crop_box_px(spec, "W1", to_px)
    assert x1 - x0 == y1 - y0 == round(4200 * 1.6 * 0.25)
    assert (crop_box_px(spec, "W1", to_px, zoom=1.3)[2] - crop_box_px(spec, "W1", to_px, zoom=1.3)[0]) == round(4200 * 1.6 / 1.3 * 0.25)
    short = crop_box_px(spec, "D1", to_px); assert short[2] - short[0] == round(2000 * 0.25)  # min 2 m

def test_element_crop_size_and_magenta_target():
    img = element_crop(page, spec, "W1", to_px)
    assert img.shape == (768, 768, 3)
    assert ((img[:, :, 0] == 255) & (img[:, :, 1] == 0) & (img[:, :, 2] == 255)).sum() > 500

def test_crop_near_page_edge_pads_white(): ...  # element at x=0 -> left columns all 255

def test_context_thumb_has_red_box():
    t = context_thumb(page, (100, 100, 600, 600))
    assert t.shape == (384, 384, 3) and ((t[:, :, 2] == 255) & (t[:, :, 0] == 0)).any()

def test_wall_evidence_lines():
    text = wall_evidence(spec, "W1", mm_per_px=29.0, hatch=hatch_half, texts=[{"text": "NYY 4x1C", "cls": "annotation", "at_mm": (2100, 300)}], to_px=to_px)
    assert "length: 4200 mm, thickness: 90 mm (stroke 3.1 px), orientation: horizontal" in text
    assert "connects to walls at ends: start=none, end=none" in text
    assert "passes through dense-hatch area: yes (50% of length)" in text
    assert 'nearest text within 600 mm: "NYY 4x1C" (annotation class)' in text
    assert "CV confidence: 0.41" in text
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_crops.py -q`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implementasi** sesuai Interfaces. `texts` adalah record OCR tahap 2 yang sudah dikonversi pemanggil ke mm (`at_mm` = pusat bbox lewat `px_to_mm`).

- [ ] **Step 4: Jalankan test, pastikan lolos**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_crops.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add core/llm_review/crops.py tests/llm_review/test_crops.py
rtk git commit -m "feat(llm): element crops, context thumbnail and text evidence for Strata"
```

---

### Task 4: Tugas T0–T3: schema, prompt, few-shot, voting, pemetaan ke ops

**Files:**
- Create: `core/llm_review/tasks.py`, `core/llm_review/prompts/T0/v1.md`, `core/llm_review/prompts/T1/v1.md`, `core/llm_review/prompts/T2/v1.md`, `core/llm_review/prompts/T3/v1.md`, `tests/llm_review/test_tasks.py`
- Modify: `core/extraction/params.py`, `core/extraction/stages.py` (`run_params`, `stage_input`), `tests/extraction/test_params.py`

**Interfaces:**
- Consumes: `CallResult`, `StrataClient.ask_json` (Task 2); `DoorType`, `RoomType`.
- Produces:
  - Schema pydantic:
    - `PromptParams` (`wall_height`, `door_height`, `wall_thickness`: `int | None` mm; `floor_name: str | None`; `site_type: Literal["data_hall", "data_center", "office", "mixed", "other"] | None`);
    - `T1Answer` (`id: str`, `verdict: Literal["wall", "annotation", "unsure"]`);
    - `T2Answer` (`id`, `is_door: bool`, `door_type: DoorType | None`, `hinge: Literal["start", "end", "both"] | None`, `swing: Literal["left", "right"] | None`);
    - `T3Answer` (`id`, `type: RoomType`, `name_normalized: str`).
  - `SCHEMAS: dict[str, type[BaseModel]]`, `EFFORT = {"T0": "low", "T1": "low", "T2": "low", "T3": "none", "T4": "medium"}`.
  - `ReviewItem` (dataclass): `task: str`, `element: str`, `evidence: str`, `image: np.ndarray | None`, `context: np.ndarray | None`, `label: str = ""` (T3).
  - `FewShot` (dataclass): `item: ReviewItem`, `answer: dict`.
  - `load_prompt(task: str, version: str = "v1") -> str`.
  - `load_fewshot(task: str, root: Path = FEWSHOT_DIR) -> list[FewShot]`, dengan `FEWSHOT_DIR = <repo>/benchmarks/gatsu/fewshot`. Format foldernya `items.json` (`[{"element", "evidence", "label", "answer", "image": "<file>.png" | null}]`) plus PNG. Folder yang tidak ada menghasilkan `[]`.
  - `messages_for(item: ReviewItem, fewshot: list[FewShot], *, version: str = "v1", evidence: bool = True) -> list[dict]`:
    - system = prompt versi itu;
    - tiap few-shot menjadi pasangan user/assistant (assistant = JSON jawaban);
    - user terakhir berisi teks bukti (bila `evidence`) dan schema JSON, lalu gambar `image` dan `context` sebagai `image_url` data URI PNG base64.
  - `agree_key(task: str, ans: BaseModel) -> tuple`:
    - T1 `(verdict,)`;
    - T2 `(is_door, door_type, hinge, swing)`;
    - T3 `(type, name_normalized.strip().upper())`.
  - `majority(task: str, answers: list[BaseModel | None], min_agree: int = 2) -> BaseModel | None`: jawaban pertama dari kelompok terbesar dengan ≥ `min_agree` anggota; jawaban `None` (invalid) tidak dihitung.
  - `ops_for(task: str, spec: Spec, ans: BaseModel) -> list[dict]`:
    - T1 `annotation` → `[{"op": "delete_wall", "id", "reason": "strata: annotation"}]`, hanya bila confidence dinding < 0.8. `wall` / `unsure` → `[]`;
    - T2 `is_door=False` → `delete_opening` (confidence < 0.8). Bila tidak, `set_door` hanya dengan field yang berbeda dari spec. Tidak ada beda → `[]`;
    - T3 → `set_room_type` bila tipe beda, dan `rename_room` bila `name_normalized` tidak kosong dan beda;
    - `ans.id` tidak sama dengan elemen yang ditanya, atau elemen ber-provenance `editor`/`manual` → `[]`.
  - `parse_prompt_llm(client, prompt: str) -> dict`: field `PromptParams` yang tidak `None`. Invalid → `{}`.
  - `run_params(project_dir, override=None, stages: Path | None = None) -> dict`: bila `stages / "00_input" / "input.json"` punya `params_parsed_llm`, hasil itu mengisi field yang tidak ada di hasil parser aturan. Parameter eksplisit tetap menang.
  - `stage_input(project_dir, work, override=None, llm_parse: Callable[[str], dict] | None = None)`: menulis `params_parsed_llm` (`null` bila T0 tidak dijalankan).

- [ ] **Step 1: Tulis prompt v1.** T1–T3 memakai kerangka §3.4 verbatim, lalu instruksi per tugas:
  - T1: tiga verdict dan arti jebakan jalur kabel;
  - T2: arti `hinge` start/end/both relatif terhadap arah dinding a→b dan `swing` left/right dilihat dari engsel;
  - T3: daftar enum `RoomType` lengkap, dengan `name_normalized` = label OCR yang sudah dikoreksi typo (huruf besar);
  - T0: ekstraksi parameter dari prompt Indonesia, satuan diubah ke mm, field yang tidak disebut bernilai `null`.

- [ ] **Step 2: Tulis test yang gagal** (`tests/llm_review/test_tasks.py`, `tests/extraction/test_params.py`):

```python
def test_majority_needs_two_agreeing():
    a, b = T1Answer(id="W1", verdict="annotation"), T1Answer(id="W1", verdict="wall")
    assert majority("T1", [a, b, None]) is None
    assert majority("T1", [a, b, a]).verdict == "annotation"

def test_t3_agreement_ignores_case_and_spaces():
    x, y = T3Answer(id="R1", type="pantry", name_normalized="Pantry "), T3Answer(id="R1", type="pantry", name_normalized="PANTRY")
    assert majority("T3", [x, y]) is not None

def test_ops_for_t1_respects_confidence_limit():
    assert ops_for("T1", spec_low, T1Answer(id="W1", verdict="annotation")) == [{"op": "delete_wall", "id": "W1", "reason": "strata: annotation"}]
    assert ops_for("T1", spec_conf_085, T1Answer(id="W1", verdict="annotation")) == []

def test_ops_for_t2_only_changed_fields():
    assert ops_for("T2", spec, T2Answer(id="D1", is_door=True, door_type="single_swing", hinge="end", swing="left")) == \
        [{"op": "set_door", "id": "D1", "hinge": "end", "swing": "left"}]  # door_type already single_swing

def test_ops_for_rejects_wrong_id_and_human_edits():
    assert ops_for("T1", spec_low, T1Answer(id="W9", verdict="annotation")) == []
    assert ops_for("T3", spec_editor_room, T3Answer(id="R1", type="toilet", name_normalized="WC")) == []

def test_messages_for_layout():
    m = messages_for(item_with_images, [fs], evidence=True)
    assert m[0]["role"] == "system" and "Answer ONLY with JSON" in m[0]["content"]
    assert [x["role"] for x in m[1:3]] == ["user", "assistant"]
    parts = m[-1]["content"]; assert parts[0]["type"] == "text" and "Element W1" in parts[0]["text"]
    assert sum(p["type"] == "image_url" for p in parts) == 2
    assert "Element W1" not in messages_for(item_with_images, [], evidence=False)[-1]["content"][0]["text"]

def test_llm_params_fill_only_empty_fields(tmp_path):  # upload prompt "tinggi 4.5 m", explicit door_height 2400
    # input.json params_parsed_llm = {"wall_height": 5000, "floor_name": "Lantai 1", "door_height": 2100}
    p = run_params(project_dir, stages=stages)
    assert p["wall_height"] == 4500 and p["floor_name"] == "Lantai 1" and p["door_height"] == 2400
```

- [ ] **Step 3: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_tasks.py tests/extraction/test_params.py -q`
Expected: FAIL.

- [ ] **Step 4: Implementasi** sesuai Interfaces. Semua pemanggil `run_params` di `stages.py` (tahap 2, 3, 4) meneruskan `stages=work.parent`.

- [ ] **Step 5: Jalankan test, pastikan lolos**

Run: `rtk uv run --env-file .env pytest tests/llm_review tests/extraction/test_params.py tests/extraction/test_stages.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add core/llm_review core/extraction/params.py core/extraction/stages.py tests/llm_review tests/extraction/test_params.py
rtk git commit -m "feat(llm): T0-T3 schemas, versioned prompts, few-shot, voting and op mapping"
```

---

### Task 5: Tool T4 dan batasnya (PRD/05 §4)

**Files:**
- Create: `core/llm_review/tools.py`, `core/llm_review/prompts/T4/v1.md`, `tests/llm_review/test_tools.py`

**Interfaces:**
- Produces:
  - `TOOLS: list[dict]`: definisi function OpenAI untuk tepat 7 tool di §4 (`delete_wall`, `merge_walls`, `set_door`, `delete_opening`, `set_room_type`, `rename_room`, `finish`), dengan parameter sesuai tabel. Enum `door_type`/`hinge`/`swing`/`type` diambil dari literal model.
  - `check_call(spec: Spec, name: str, args: dict) -> tuple[list[dict], str | None]`: menghasilkan `(ops, None)` bila boleh, atau `([], reason)` bila ditolak. Alasan penolakan:
    - `unknown_tool`;
    - `unknown_id:<id>`;
    - `human_edit:<id>` (provenance `editor`/`manual`);
    - `confidence>=0.8:<id>` (untuk `delete_wall` dan `delete_opening`);
    - `not_collinear` (`merge_walls`: sudut > 1.5° atau jarak garis > tebal maksimum);
    - `not_adjacent` (`merge_walls`: celah ujung > tebal maksimum);
    - `bad_args:<pesan pydantic>`.
  - `finish` → `([], None)`. Pemanggil yang memutus loop.

- [ ] **Step 1: Tulis prompt T4 v1.** Isinya: peran, overlay bernomor, daftar masalah, aturan "satu tool per giliran, panggil `finish` bila tidak ada perbaikan yang yakin", dan larangan menebak koordinat.

- [ ] **Step 2: Tulis test yang gagal:**

```python
def test_tools_are_exactly_the_whitelist():
    assert sorted(t["function"]["name"] for t in TOOLS) == sorted(["delete_wall", "merge_walls", "set_door", "delete_opening", "set_room_type", "rename_room", "finish"])
    assert not any(t["function"]["name"] in ("add_wall", "move_wall") for t in TOOLS)

def test_delete_wall_limits():
    assert check_call(spec, "delete_wall", {"id": "W1", "reason": "dim"}) == ([{"op": "delete_wall", "id": "W1", "reason": "dim"}], None)  # conf 0.4
    assert check_call(spec, "delete_wall", {"id": "W2", "reason": "dim"})[1] == "confidence>=0.8:W2"
    assert check_call(spec, "delete_wall", {"id": "W99", "reason": "x"})[1] == "unknown_id:W99"
    assert check_call(spec, "delete_wall", {"id": "W3", "reason": "x"})[1] == "human_edit:W3"

def test_merge_walls_needs_collinear_adjacent():
    assert check_call(spec, "merge_walls", {"ids": ["W4", "W5"], "reason": "split"})[1] is None    # collinear, gap 50 mm
    assert check_call(spec, "merge_walls", {"ids": ["W4", "W6"], "reason": "x"})[1] == "not_collinear"
    assert check_call(spec, "merge_walls", {"ids": ["W4", "W7"], "reason": "x"})[1] == "not_adjacent"  # gap 2 m

def test_bad_args_and_unknown_tool():
    assert check_call(spec, "set_room_type", {"id": "R1", "type": "garage"})[1].startswith("bad_args")
    assert check_call(spec, "add_wall", {})[1] == "unknown_tool"
```

- [ ] **Step 3: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_tools.py -q`
Expected: FAIL.

- [ ] **Step 4: Implementasi.** Argumen divalidasi dengan model op yang sudah ada di `core/spec/ops.py` (`DeleteWall`, `MergeWalls`, `SetDoor`, …) lewat `{"op": name, **args}`.

- [ ] **Step 5: Jalankan test, pastikan lolos**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_tools.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add core/llm_review/tools.py core/llm_review/prompts/T4 tests/llm_review/test_tools.py
rtk git commit -m "feat(llm): T4 tool whitelist with confidence, collinearity and human-edit limits"
```

---

### Task 6: Harness: routing, Fase A/B, gerbang, batas waktu, transkrip (PRD/05 §2.1, §5, §9)

**Files:**
- Create: `core/llm_review/harness.py`, `tests/llm_review/test_harness.py`

**Interfaces:**
- Consumes: Task 2–5; `validate`, `ValidationContext`; `apply(spec, ops, "llm", version)`; `render_ids_overlay`.
- Produces:
  - `ReviewInputs` (dataclass): `page: np.ndarray` (gray), `to_px`, `mm_per_px: float`, `hatch: np.ndarray | None`, `texts: list[dict]` (OCR dalam mm), `labels: dict[str, str]` (room id → teks label OCR di dalam ruang), `vctx: ValidationContext`.
  - `select_for_review(spec: Spec, issues: list[Issue], tasks: set[str], limit: int = 60) -> list[tuple[str, str]]`:
    - menghasilkan pasangan `(task, element_id)`, urut T1 lalu T2 (bersama dibatasi `limit`, kunci `(confidence, id)`);
    - T1 = dinding dengan `confidence < 0.6` atau yang dirujuk issue warning/error;
    - T2 = pintu dengan kriteria yang sama;
    - provenance `editor`/`manual` dilewati;
    - T3 tidak dipilih di sini (lihat `run_review`).
  - `run_review(spec: Spec, inputs: ReviewInputs, client, *, tasks: set[str], votes: int, max_iter: int, deadline: float, out: Path, version: int, clock=time.monotonic, emit=None) -> ReviewResult`.
  - `ReviewResult` (dataclass): `spec: Spec`, `ops: list[dict]` (op yang diterima, berurutan), `score_before: float`, `score_after: float`, `decisions: list[dict]`, `timed_out: bool`, `calls: int`, `invalid: int`.
- Perilaku `run_review`:
  - **Fase A.** Elemen dari `select_for_review` (T1/T2) diproses dulu. Sesudah itu T3 untuk ruang di spec **terkini** yang bertipe `other` atau tanpa nama dan punya label OCR (bila `"T3" in tasks`).
  - **Voting:**
    - vote 1: `temperature=0`, zoom 1.0;
    - vote 2–3: `temperature=0.4`, zoom 1.3;
    - bila vote 1 dan 2 valid dan sepakat (`agree_key`), vote 3 dilewati karena tidak bisa mengubah mayoritas;
    - few-shot dari `load_fewshot(task)`.
  - **Gerbang Fase A:** `apply` lalu `validate(candidate, vctx)`. Diterima bila `passed` dan `score_new >= score - 0.005`. `OpError` dicatat sebagai `rejected` (`op_error`).
  - **Fase B (bila `"T4" in tasks`):**
    - paling banyak `max_iter` iterasi; berhenti bila tidak ada issue warning/error;
    - pesan user = overlay bernomor dari spec terkini (sisi panjang ≤ `T4_OVERLAY_MAX_PX` dari Task 1) + daftar issue (`code`, `element_ids`, `message`) + ringkasan penolakan sebelumnya;
    - tool call pertama yang dipakai; berhenti pada `finish` atau tanpa tool call;
    - urutannya `check_call`, lalu `apply`, lalu gerbang ketat `score_new > score`;
    - ditolak → pesan `tool` berisi `"rejected: <reason>"` masuk riwayat untuk iterasi berikutnya; diterima → `"accepted: score <a> -> <b>"`.
  - **Batas waktu:** `clock() >= deadline` dicek sebelum setiap panggilan. Bila lewat, `timed_out=True`, loop berhenti, dan hasil yang sudah diterima tetap dipakai.
  - **Artefak di `out`:**
    - `transcript.jsonl` mengikuti skema §9, satu baris per percobaan panggilan, dengan field `ts`, `task`, `element`, `prompt_version`, `vote`, `request.messages_ref`, `request.effort`, `response.raw`/`parsed`/`valid`, `latency_ms`, `tokens`;
    - `crops/<el>_v<vote>.png` dan `crops/<el>_ctx.png`;
    - `decisions.json` berisi `[{element, task, verdict, decision: accepted|rejected|no_consensus|invalid_output|no_change, reason, score_before, score_after, ops}]`.
  - **Event:** `emit("llm.decision", {element, task, verdict, accepted, score_before, score_after})` untuk setiap keputusan.

- [ ] **Step 1: Tulis test yang gagal** (`FakeStrata` dengan script per elemen; spec sintetis dengan dinding anotasi W2 berkeyakinan 0.4, yang bila dihapus menaikkan skor V018, dan W1 dinding asli 0.5):

```python
def test_select_skips_confident_and_human_edited():
    assert select_for_review(spec, [], {"T1", "T2"}) == [("T1", "W2"), ("T1", "W1"), ("T2", "D1")]  # W3 conf 0.9, W4 editor

def test_phase_a_accepts_majority_delete(tmp_path):
    r = run_review(spec, inputs, fake(W2="annotation", W1="wall"), tasks={"T1"}, votes=3, max_iter=0, deadline=inf, out=tmp_path, version=1)
    assert [o["id"] for o in r.ops] == ["W2"] and r.score_after >= r.score_before - 0.005
    d = {x["element"]: x for x in json.loads((tmp_path / "decisions.json").read_text())}
    assert d["W2"]["decision"] == "accepted" and d["W1"]["decision"] == "no_change"

def test_vote3_skipped_when_first_two_agree(tmp_path):
    f = fake(W2="annotation"); run_review(...)
    assert [c["temperature"] for c in f.calls if c["element"] == "W2"] == [0, 0.4]

def test_no_consensus_changes_nothing(tmp_path):  # answers annotation, wall, unsure
    assert r.ops == [] and decisions["W2"]["decision"] == "no_consensus"

def test_score_drop_rejected(tmp_path):  # deleting real wall W1 drops score > 0.005
    assert decisions["W1"]["decision"] == "rejected" and decisions["W1"]["reason"] == "score_drop"

def test_invalid_output_and_dead_strata_continue(tmp_path):  # W2 -> always invalid; W1 -> raises timeout result
    assert decisions["W2"]["decision"] == "invalid_output" and r.spec == spec

def test_deadline_stops_before_next_call(tmp_path):
    clock = iter([0, 0, 0, 999, 999, 999]).__next__
    r = run_review(..., deadline=10, clock=clock)
    assert r.timed_out and len(fake.calls) <= 3

def test_phase_b_feedback_and_strict_gate(tmp_path):  # 1st tool: delete_wall W3 (conf 0.9) -> rejected; 2nd: delete_wall W2 -> accepted; 3rd: finish
    assert r.ops == [{"op": "delete_wall", "id": "W2", "reason": "dim"}]
    assert "rejected: confidence>=0.8:W3" in json.dumps(fake.calls[1]["messages"])

def test_t3_runs_on_rooms_of_current_spec(tmp_path):  # room R1 type other with label "PANTRI"
    assert {"op": "set_room_type", "id": "R1", "type": "pantry"} in r.ops

def test_transcript_lines_follow_schema(tmp_path):
    line = json.loads((tmp_path / "transcript.jsonl").read_text().splitlines()[0])
    assert {"ts", "task", "element", "prompt_version", "vote", "request", "response", "latency_ms", "tokens"} <= line.keys()
    assert (tmp_path / line["request"]["messages_ref"]).exists()

def test_events_emitted():
    assert events[0][0] == "llm.decision" and {"element", "task", "verdict", "accepted", "score_before", "score_after"} <= events[0][1].keys()
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_harness.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementasi** sesuai Interfaces.

- [ ] **Step 4: Jalankan test, pastikan lolos**

Run: `rtk uv run --env-file .env pytest tests/llm_review -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add core/llm_review/harness.py tests/llm_review/test_harness.py
rtk git commit -m "feat(llm): review harness with voting, score gates, T4 loop, deadline and transcript"
```

---

### Task 7: Tahap 6 dan orchestrator (PRD/05 §6)

**Files:**
- Create: `core/llm_review/stage.py`, `tests/llm_review/test_stage.py`
- Modify: `core/spec/store.py` (`commit_ops(..., run_id=None)`), `core/extraction/stages.py` (`validation_context`), `server/orchestrator.py`, `tests/server/test_orchestrator.py`

**Interfaces:**
- Consumes: Task 2 dan Task 6; `SpecStore`, `VersionConflict`, `ValidationFailed`.
- Produces:
  - `validation_context(stages: Path) -> ValidationContext`: diekstrak dari `stage_validate` (`ocr_dimensions_from(grid)`, `line_len_m` maksimum). `stage_validate` memakainya juga.
  - `SpecStore.commit_ops(base_version, ops, by, message="", run_id: str | None = None)`.
  - `stage_review(project_dir: Path, work: Path, run_id: str, settings: Settings, *, version: int | None, use_strata: bool, client=None, emit=None, progress=None, clock=time.monotonic) -> dict`:
    - skip `disabled`: `{"status": "skipped", "message": <alasan>, "metrics": {"reason": "disabled"}}` bila tidak ada T1–T4 di `settings.llm_tasks_enabled`;
    - skip `disabled_by_user`: `use_strata` false;
    - skip `no_artifacts`: `version` None, atau `01_preprocess/page.png` / `02_grid/grid.json` tidak ada di run ini;
    - skip `strata_unavailable`: `client.health()` gagal;
    - bila jalan: `run_review` dengan `deadline = clock() + 600`, lalu `store.commit_ops(version, ops, "llm", message=f"review Strata: {n} perubahan", run_id=run_id)` bila `ops` tidak kosong;
    - `VersionConflict` → tidak disimpan, peringatan `"HEAD berubah selama review; perubahan Strata tidak disimpan"`;
    - `ValidationFailed` → tidak disimpan, peringatan berisi kode issue;
    - `timed_out` → peringatan `"batas waktu tahap 6 tercapai; hasil sejauh ini dipakai"`;
    - status `succeeded` dengan metrics `{"reviewed", "accepted", "rejected", "calls", "invalid", "score_before", "score_after", "version"?}`.
  - Orchestrator:
    - `StageContext.emit_event: Callable[[str, dict], None]`, di-bind ke `bus.emit(pid, rid, n, type, data=...)`;
    - `_review` memanggil `stage_review` dengan `use_strata = run_params(...).get("use_strata", True)`, `client = StrataClient(settings.strata_base_url, settings.strata_model, settings.strata_timeout_s)`, dan `version = ctx.state.get("version", ctx.version)`. Bila `metrics.version` ada, isi `ctx.state["version"]`;
    - `_run_stage` memperbarui `spec_version_out`/`version` dari metrics tahap 5 **dan tahap 6**;
    - `_input` meneruskan `llm_parse` bila `"T0" in settings.llm_tasks_enabled`, `use_strata` tidak false, dan `health()` true.

- [ ] **Step 1: Tulis test yang gagal** (`tests/llm_review/test_stage.py` membuat folder run sintetis berisi `page.png`, `grid.json`, `ocr.json`, `03_extract/candidates.json`, dan HEAD v1):

```python
def test_skipped_when_no_tasks_enabled(...):
    r = stage_review(..., settings=settings(llm_tasks_enabled=()), version=1, use_strata=True, client=FakeStrata(...))
    assert r["status"] == "skipped" and r["metrics"]["reason"] == "disabled"

def test_skipped_when_user_turned_strata_off(...): assert r["metrics"]["reason"] == "disabled_by_user"
def test_skipped_when_strata_down(...): assert r["metrics"]["reason"] == "strata_unavailable"   # health False
def test_skipped_without_artifacts(...): assert r["metrics"]["reason"] == "no_artifacts"          # from_stage=6 run

def test_accepted_ops_saved_as_llm_version(...):
    r = stage_review(..., settings=settings(llm_tasks_enabled=("T1",)), version=1, use_strata=True, client=fake(W2="annotation"))
    assert r["metrics"]["version"] == 2
    s = SpecStore(specs).load(2); assert s.meta.source == "llm" and s.meta.run_id == "rid" and s.meta.parent_version == 1

def test_head_moved_during_review_keeps_editor_work(...):
    # FakeStrata script commits an editor op to the store on its first call (HEAD -> 2)
    r = stage_review(...)
    assert SpecStore(specs).head() == 2 and "HEAD berubah" in r["warnings"][0]
```

`tests/server/test_orchestrator.py`:

```python
def test_stage6_version_becomes_the_run_output(app_factory, project_id):
    impls = fake_impls([]); impls[5] = lambda ctx: {"status": "succeeded", "metrics": {"version": 1}}
    impls[6] = lambda ctx: {"status": "succeeded", "metrics": {"version": 2}}
    ...; assert run["spec_version_out"] == 2

def test_stage6_emits_llm_decision_events(app_factory, project_id):
    impls[6] = lambda ctx: (ctx.emit_event("llm.decision", {"element": "W1"}), {"status": "succeeded"})[1]
    ...; assert any(e["type"] == "llm.decision" and e["stage"] == 6 for e in client_events(client, project_id))

def test_real_stage6_skips_when_disabled(app_factory, project_with_gt):  # default settings: LLM_TASKS_ENABLED empty
    assert run["stages"][6]["status"] == "skipped" and run["stages"][6]["metrics"]["reason"] == "disabled"
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/llm_review/test_stage.py tests/server/test_orchestrator.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementasi** sesuai Interfaces. `stage_review` memuat input sebagai berikut:
- `page.png` (gray);
- `grid.json["px_to_mm"]`, yang menghasilkan `to_px = px_from_mm(...)` dan `mm_per_px = hypot(a, d)`;
- `03_extract/masks/hatch.png` (opsional);
- `ocr.json`, di mana pusat bbox dikonversi ke mm;
- label ruang dari `labels_from_ocr` yang titiknya ada di dalam ruang.

- [ ] **Step 4: Jalankan test, pastikan lolos, lalu suite penuh**

Run: `rtk uv run --env-file .env pytest -q`
Expected: semua PASS (370 + test baru), xfail tetap 3.

- [ ] **Step 5: Commit**

```bash
rtk git add core/llm_review/stage.py core/spec/store.py core/extraction/stages.py server/orchestrator.py tests
rtk git commit -m "feat(llm): stage 6 review with fallbacks, llm spec versions and decision events"
```

---

### Task 8: Item benchmark, few-shot, dan `run_llm_bench.py` (PRD/05 §7)

**Files:**
- Create: `benchmarks/llm_items.py`, `benchmarks/run_llm_bench.py`, `benchmarks/gatsu/llm_items/T0.json`, `tests/benchmarks/test_llm_bench.py`
- Modify: `.gitignore` (`benchmarks/.cache/`)

**Interfaces:**
- Consumes: tahap 1–4 (`core/extraction/stages.py`), `extraction_metrics` (`wall_metrics`, `door_metrics`, `room_metrics`, `wall_iou`, `gross_area_metrics`), Task 3–6, `match_type` (leksikon).
- Produces:
  - `gatsu_stages(cache: Path = Path("benchmarks/.cache/gatsu")) -> Path`: menjalankan tahap 0–5 untuk `floorplan/plan.jpeg` bila cache belum ada, lalu mengembalikan folder `stages`. Hasilnya deterministik (NFR-RL-06), jadi ID elemen stabil.
  - `build_items(stages: Path, gt: Spec) -> dict[str, list[dict]]`, dengan item `{"id", "task", "candidate": k, "element", "label": {...}, "baseline": {...}, "fewshot": bool}`:
    - **T1** dari semua kandidat sukses `04_rooms/candidates/<k>/spec.json`:
      - dinding dengan IoU tapak ≥ 0.5 terhadap salah satu dinding GT berlabel `wall`;
      - dinding dengan IoU < 0.1 terhadap semua dinding GT berlabel `annotation`;
      - di antaranya dibuang karena ambigu;
      - dedupe per posisi (pusat ≤ 100 mm, panjang ±10%);
      - kelas mayoritas disubsample secara deterministik (urut id) sampai seimbang;
      - baseline `conf >= 0.5 → wall`.
    - **T2:** pintu CV yang pusatnya ≤ 300 mm dari pintu GT, unik per pintu GT. Label `{is_door: true, door_type, hinge, swing}` dari GT, baseline dari field CV.
    - **T3:** label OCR (`labels_from_ocr`) di dalam ruang GT yang tipenya bukan `other`, ditambah varian typo sintetis dari `typo_variants`. Label `{type}` dari GT, baseline `match_type(text)`.
    - **Few-shot:** 4 item per tugas dengan `fewshot: true`, dipilih deterministik (positif pertama, negatif pertama, lalu dua "jebakan": T1 anotasi dengan `pair_overlap > 0`, T2 pintu dengan `hinge` GT `end`, T3 varian typo). Item few-shot tidak masuk evaluasi.
  - `build_items_from_specs(specs: dict[int, Spec], gt: Spec) -> dict[str, list[dict]]`: inti `build_items`, tanpa I/O.
  - `typo_variants(text: str) -> list[str]`, dengan m = `len(text) // 2`:
    - hapus: `text[:m] + text[m+1:]`;
    - tukar: `text[:m-1] + text[m] + text[m-1] + text[m+1:]`;
    - substitusi: O pertama → 0, bila tidak ada maka I pertama → 1, bila tidak ada juga dilewati;
    - urutan dijaga, duplikat dan varian yang sama dengan aslinya dibuang.
  - `evaluation(items: list[dict]) -> list[dict]`: item dengan `fewshot` false.
  - `score_task(task: str, items: list[dict], answers: dict[str, dict | None]) -> dict`: `{n, accuracy, baseline_accuracy, per_field?, confusion, delete_precision? (T1), invalid_rate, passes}`. Jawaban `None` dihitung salah dan invalid.
  - `T0.json` (ditulis tangan, 20 prompt Indonesia + parameter yang diharapkan): variasi satuan (m/cm/mm), urutan kata, typo, dan prompt tanpa parameter. Baseline = `parse_prompt`.
  - `python -m benchmarks.llm_items --out benchmarks/gatsu/llm_items` → `T1.json`, `T2.json`, `T3.json`, `benchmarks/gatsu/fewshot/<task>/items.json` + PNG crop few-shot.
  - `python -m benchmarks.run_llm_bench --task {T0,T1,T2,T3,T4,e2e} --prompt v1 --votes 3 [--no-evidence] [--no-fewshot] [--tasks T1,T3] [--items DIR] [--out-dir DIR] [--fake-oracle]`. Default `--items benchmarks/gatsu/llm_items` dan `--out-dir benchmarks/reports`. Nama varian: `ev`/`noev` + `fs`/`nofs`, misalnya `llm-T1-v1-ev-fs`. Laporannya `benchmarks/reports/llm-<task>-<prompt>-<variant>.md` + `.json`:
    - **T0–T3:** akurasi Strata dan baseline, matriks kebingungan, latensi rata-rata dan p90, tingkat output invalid, n item, dan `passes` sesuai §7.2:
      - T1: `acc >= base + 0.05` dan presisi keputusan "annotation" ≥ 0.90;
      - T2: akurasi `swing` dan `hinge` masing-masing ≥ base + 0.10;
      - T3: `acc >= lex + 0.05`, atau (`lex_fail >= 0.20` dan `acc >= lex`);
      - T0: akurasi per field gabungan (aturan + isian Strata) ≥ aturan + 0.05;
    - **T4 / e2e:** `harness_delta(stages, base_tasks, test_tasks)` menjalankan `run_review` dua kali pada spec tahap 5 (T4: aktif vs aktif+T4; e2e: tanpa Strata vs `--tasks`). Hasilnya Δ semua metrik GT, Δ skor validator, dan waktu tahap 6. `passes` = Δ ≥ 0 untuk semua metrik dan Δ > 0 minimal satu (metrik "max" seperti `gross_area_err` dan posisi dibalik tandanya).

- [ ] **Step 1: Tulis test yang gagal** (`tests/benchmarks/test_llm_bench.py`; spec CV dan GT sintetis kecil):

```python
def test_t1_labels_by_footprint_iou():
    items = build_items_from_specs({0: cv}, gt)["T1"]
    lab = {i["element"]: i["label"]["verdict"] for i in items}
    assert lab["W1"] == "wall" and lab["W2"] == "annotation" and "W3" not in lab  # W3 IoU 0.3: ambiguous

def test_fewshot_items_excluded_from_eval():
    assert not ({i["id"] for i in evaluation(items)} & {i["id"] for i in items if i["fewshot"]})

def test_t3_typo_variants_deterministic():
    assert typo_variants("PANTRY") == ["PANRY", "PATNRY"]          # no O/I/0/1: substitution skipped
    assert typo_variants("BATTERY ROOM")[-1] == "BATTERY R0OM"    # first O -> 0

def test_oracle_passes_and_baseline_fails_gate():
    rep = score_task("T1", items, answers={i["id"]: i["label"] for i in items})  # perfect answers
    assert rep["accuracy"] == 1.0 and rep["passes"] is True
    rep = score_task("T1", items, answers={i["id"]: i["baseline"] for i in items})
    assert rep["passes"] is False  # equal to baseline < baseline + 5 points

def test_t1_delete_precision_gate():  # 10 annotation answers, 2 wrong -> precision 0.8 -> fails even with high accuracy
    assert score_task("T1", items, answers=mixed)["passes"] is False

def test_report_written(tmp_path):
    main(["--task", "T1", "--items", str(items_path), "--out-dir", str(tmp_path), "--fake-oracle"])
    assert (tmp_path / "llm-T1-v1-ev-fs.md").exists() and json.loads((tmp_path / "llm-T1-v1-ev-fs.json").read_text())["n"] > 0
```

(`--fake-oracle` hanya untuk test: jawaban = label, sehingga Strata tidak dipanggil.)

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `rtk uv run --env-file .env pytest tests/benchmarks/test_llm_bench.py -q`
Expected: FAIL.

- [ ] **Step 3: Implementasi** sesuai Interfaces. `build_items_from_specs(specs: dict[int, Spec], gt: Spec)` adalah inti yang dipanggil oleh `build_items`.

- [ ] **Step 4: Jalankan test, pastikan lolos**

Run: `rtk uv run --env-file .env pytest tests/benchmarks/test_llm_bench.py -q`
Expected: PASS.

- [ ] **Step 5: Bangun item Gatsu**

Run: `rtk uv run --env-file .env python -m benchmarks.llm_items --out benchmarks/gatsu/llm_items`
Expected: jumlah item T1 ≥ 40, T2 ≥ 20, T3 ≥ 20 tercetak.

Bila T1 atau T2 kurang dari target karena GT Gatsu terbatas, catat n aktual di laporan. Benchmark tetap berjalan, dan keputusan aktivasi menyebut n yang kecil.

- [ ] **Step 6: Commit**

```bash
rtk git add benchmarks/llm_items.py benchmarks/run_llm_bench.py benchmarks/gatsu/llm_items benchmarks/gatsu/fewshot tests/benchmarks .gitignore
rtk git commit -m "bench(llm): Gatsu item builder, few-shot split and run_llm_bench with section 7.2 gates"
```

---

### Task 9: Jalankan benchmark, putuskan aktivasi, ukur end-to-end (live)

**Files:**
- Create: `benchmarks/DECISIONS.md`, `benchmarks/reports/llm-*.md/json`, `benchmarks/reports/m6-strata.md` + `.json`
- Modify: `.env.example` (`LLM_TASKS_ENABLED`), prompt `v2` bila ada iterasi, `tests/extraction/test_gatsu_pipeline.py`

Butuh Strata hidup. Bila Strata mati saat task ini dikerjakan, tanyakan ke pengguna. Ini satu-satunya titik berhenti di plan ini.

- [ ] **Step 1: Matriks T1/T2 (4 varian, menggantikan bagian akurasi spike §8):** `--evidence/--no-evidence × --fewshot/--no-fewshot`, `--votes 3`. Lalu T3 dan T0 dengan varian terbaik (bukti + few-shot).

Run: `rtk uv run --env-file .env python -m benchmarks.run_llm_bench --task T1 --prompt v1 --votes 3` (dan seterusnya)
Expected: laporan per varian ada di `benchmarks/reports/`.

- [ ] **Step 2: Satu iterasi prompt per tugas** (opsional). Bila tugas gagal §7.2 dan matriks kebingungan menunjukkan pola yang bisa diperbaiki dengan instruksi, tulis `prompts/<task>/v2.md` lalu jalankan ulang sekali. Tidak ada iterasi kedua, dan item evaluasi tidak boleh diubah untuk mengejar angka.

- [ ] **Step 3: T4 dan e2e.**
  - Jalankan `--task T4 --tasks <T1–T3 yang lolos>`.
  - Jalankan `--task e2e --tasks <set aktif>`.
  - Tugas yang membuat metrik GT turun dikeluarkan dari set, lalu e2e diulang sampai Δ ≥ 0 untuk semua metrik (kriteria selesai M6).
  - Catat waktu tahap 6 (≤ 600 s).

- [ ] **Step 4: Tulis keputusan.**
  - `benchmarks/DECISIONS.md` berisi tabel: tanggal, tugas, varian dan prompt, n, metrik dan baseline, syarat §7.2, keputusan (aktif/nonaktif), dan alasan.
  - `.env.example` `LLM_TASKS_ENABLED=<set aktif>` (boleh kosong bila tidak ada yang lolos, karena itu hasil yang sah). Samakan `.env` lokal (tidak di-commit).
  - `m6-strata.md`/`.json` berisi ringkasan dan metrik Gatsu dengan dan tanpa Strata.

- [ ] **Step 5: Test regresi.** Di `test_gatsu_pipeline.py` (`@pytest.mark.slow`), tambahkan `test_stage6_skipped_keeps_stage5_spec`: dengan `LLM_TASKS_ENABLED` kosong, tahap 6 `skipped` dan spec akhir = spec tahap 5.

Run: `rtk uv run --env-file .env pytest -q`
Expected: semua PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add benchmarks/DECISIONS.md benchmarks/reports .env.example core/llm_review/prompts tests/extraction/test_gatsu_pipeline.py
rtk git commit -m "bench(llm): Strata benchmark results, activation decisions and Gatsu end-to-end deltas"
```

---

### Task 10: Dashboard: keputusan Strata di tab Review dan panel tahap 6

**Files:**
- Modify: `web/src/components/ReviewTab.tsx`, `web/src/components/StagePanel.tsx`, `web/src/api/hooks.ts`, `web/src/api/types.ts`, `web/src/index.scss`
- Test: `web/src/components/ReviewTab.test.tsx`, `web/src/components/StagePanel.test.tsx`

**Interfaces:**
- Consumes: artefak lewat route yang sudah ada `GET /api/projects/{pid}/runs/{rid}/artifacts/06_review/{decisions.json|transcript.jsonl|crops/<file>}`; stage 6 `status`, `message`, `metrics`.
- Produces:
  - `types.ts`: `LlmDecision` (`element`, `task`, `verdict: Record<string, unknown> | null`, `decision`, `reason`, `score_before`, `score_after`, `ops`) dan `TranscriptLine`.
  - `hooks.ts`: `useReviewDecisions(pid, rid, enabled)`, `useTranscript(pid, rid, enabled)`. Transkrip di-parse per baris, dan baris rusak dilewati.
  - `ReviewTab`:
    - banner placeholder M6 diganti;
    - tahap 6 `skipped` → `InlineNotification kind="info"` "Review Strata dilewati: <pesan>";
    - selain itu tampil `DataTable` "Keputusan Strata" dengan kolom Elemen, Tugas, Jawaban, Keputusan (`Tag`: accepted hijau, rejected merah, no_consensus/invalid_output abu-abu, no_change biru), dan Skor (`0.812 → 0.825`);
    - klik baris memilih elemen, mengisi `focus` seperti tautan issue, lalu menampilkan crop `<el>_v1.png`, thumbnail `<el>_ctx.png`, dan respons mentah semua suara (`<pre>`).
  - `StagePanel` n === 6: ringkasan "Diperiksa N · diterima A · ditolak R · skor X → Y", atau alasan skip.

- [ ] **Step 1: Tulis test yang gagal** (Vitest + MSW/mock fetch seperti test ReviewTab yang ada):

```tsx
it('shows skip reason when stage 6 skipped', ...)            // "Review Strata dilewati: Strata tidak tersedia"
it('lists decisions with tags and score delta', ...)          // row W2: "accepted", "0.812 → 0.825"
it('row click shows crop, context and raw votes', ...)        // img src .../06_review/crops/W2_v1.png; pre contains raw
it('ignores a broken transcript line', ...)
it('stage 6 panel summarises counts', ...)                    // "Diperiksa 3 · diterima 1 · ditolak 1"
```

- [ ] **Step 2: Jalankan test, pastikan gagal**

Run: `cd web && rtk npx vitest run src/components/ReviewTab.test.tsx src/components/StagePanel.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implementasi** sesuai Interfaces.

- [ ] **Step 4: Jalankan test, lint, dan build**

Run: `cd web && rtk npx vitest run && rtk npm run lint && rtk npm run build`
Expected: semua PASS, tanpa error.

- [ ] **Step 5: Commit**

```bash
rtk git add web/src
rtk git commit -m "feat(web): Strata decisions, crops and raw votes in the Review tab; stage 6 summary"
```

---

### Task 11: End-to-end dashboard dan status M6

**Files:**
- Modify: `ROADMAP.md` (centang tugas M6 + "Status M6")

- [ ] **Step 1: E2E Playwright** (Vite dev + Uvicorn dengan `.env` berisi set aktif dari Task 9):
  1. Upload `plan.jpeg`. Tahap 6 berjalan, event `llm.decision` tampil live, dan tab Review menampilkan keputusan, crop, dan respons mentah.
  2. Bila ada perubahan yang diterima, versi `llm` muncul di tab Versions dan tahap 7–10 membangun dari versi itu.
  3. Jalankan ulang dengan toggle "Gunakan Strata" mati. Tahap 6 `skipped` (`disabled_by_user`) dan pipeline selesai.
  4. Ubah `STRATA_BASE_URL` ke port mati lalu restart server. Tahap 6 `skipped` (`strata_unavailable`), pipeline selesai, dan indikator Strata merah.

- [ ] **Step 2: Suite penuh**

Run: `rtk uv run --env-file .env pytest -q && cd web && rtk npx vitest run && rtk npm run lint && rtk npm run build && cd .. && rtk uv run ruff check .`
Expected: semua hijau.

- [ ] **Step 3: Tulis "Status M6" di ROADMAP.** Isinya:
  - hasil probe;
  - tugas yang aktif beserta angkanya;
  - metrik Gatsu dengan dan tanpa Strata;
  - waktu tahap 6;
  - jumlah test;
  - penyimpangan (misalnya n benchmark di bawah target).

- [ ] **Step 4: Commit**

```bash
rtk git add ROADMAP.md
rtk git commit -m "docs: M6 status"
```
