# M0 — Fondasi & Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repo dan toolchain siap. Blender headless, OCR, WeasyPrint, dan web g100 terbukti jalan di Mac M4. Kemampuan nyata Strata terukur (bila Strata hidup).

**Architecture:** Monorepo sesuai `PRD/11-tech-stack.md` §3, tetapi hanya folder yang dipakai M0 yang dibuat. Kode yang dibawa ke milestone berikutnya: `core/config.py`, `core/extraction/ocr.py`, `builder/build.py` (format `build_input` v0). Spike Strata bersifat throwaway di `benchmarks/spike/`.

**Tech Stack:** Python 3.12 (uv), pytest, ruff, RapidOCR (`rapidocr-onnxruntime`), OpenCV, pygltflib, Jinja2, WeasyPrint, openai SDK; Blender 5.2.2 LTS; Vite + React 18 + TypeScript + `@carbon/react` (g100) + three.js/R3F.

**Spec:** `PRD/` (terutama `02-architecture.md` §7, `05-llm-review.md` §3 dan §8, `06-builder-outputs.md` §2–3, `11-tech-stack.md`) dan `ROADMAP.md` bagian M0.

## Global Constraints

- Python **3.12** via `uv` (bukan 3.14 sistem). Semua perintah Python lewat `uv run`.
- Semua perintah shell diawali `rtk` (aturan global pengguna), mis. `rtk uv run pytest`.
- `server-info.txt` berisi password plaintext: **jangan dibaca, jangan di-commit, jangan dikirim ke subagent.** Harus masuk `.gitignore` sebelum commit pertama.
- Email pengguna tidak boleh dikirim ke layanan mana pun.
- Blender **5.2 LTS** dipanggil lewat binary asli `/Applications/Blender.app/Contents/MacOS/Blender`. Symlink `/opt/homebrew/bin/blender` crash ("Bundled Python not found").
- Pemanggilan builder: `blender -b --factory-startup --python-exit-code 1 -P builder/build.py -- <build_input.json> <out_dir>`. Progres dicetak sebagai `@@PROGRESS <0-100> <pesan>`.
- Builder hanya memakai stdlib + `bpy` + `bmesh`, dan tidak mengimpor `core/`.
- Satuan spec mm (integer). Sumbu +X timur, +Y utara, +Z atas. Blender memakai meter (mm / 1000). glTF di-export `export_yup=True`, sehingga +Y spec menjadi −Z glTF.
- Custom property objek Blender diekspor sebagai glTF extras (`export_extras=True`). Minimal ada `spec_id` dan `spec_type`.
- Konfigurasi dibaca dari environment. File `.env` dimuat dengan `uv run --env-file .env`, tanpa python-dotenv. Nama variabel dan default persis `02-architecture.md` §7.
- Frontend: React **18** (bukan 19), `@carbon/react` tema **g100**, latar body `#161616`.
- Strata: `STRATA_BASE_URL` default `http://192.168.2.142:8081/v1`, model `qwen3.8-flash-next-iq2_xs`, temperature 0.

## Review Focus

1. **`server-info.txt` ter-commit.** Harus selalu diabaikan git. Ditest di Task 1 (`git check-ignore` + `git ls-files`).
2. **`BLENDER_BIN` menunjuk symlink**, sehingga Blender crash dengan pesan menyesatkan. Settings harus me-resolve ke path asli. Ditest di Task 1 (`test_blender_bin_resolves_symlink`).
3. **Salah sumbu/satuan saat export** (mm vs m, Y-utara vs Y-up), sehingga model tidak 1:1 atau terbalik. Ditest di Task 2 lewat translasi dan extent node glb.
4. **Teks dimensi vertikal** (6000/6000/12000 di kiri denah) tidak terbaca, atau bbox-nya salah dipetakan balik dari gambar yang di-upscale/diputar. Ditest di Task 3 (`test_restore_bbox_*` dan smoke test hitungan token).
5. **Strata membalas teks non-JSON** (code fence, blok `<think>`). Spike tidak boleh crash: respons dihitung sebagai invalid lalu tercatat. Dicek di Task 6 langkah 4.

---

### Task 1: Repo, toolchain Python, dan konfigurasi

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `.env.example`, `core/__init__.py`, `core/config.py`
- Test: `tests/test_config.py`, `tests/test_repo_hygiene.py`

**Interfaces:**
- Produces:
  - `core.config.Settings` (frozen dataclass): `data_dir: Path`, `blender_bin: str`, `blender_render_device: str`, `strata_base_url: str`, `strata_model: str`, `strata_timeout_s: int`, `llm_tasks_enabled: tuple[str, ...]`, `llm_max_iter: int`, `llm_votes: int`, `sweep_max_candidates: int`, `max_upload_mb: int`.
  - `core.config.load_settings(env: Mapping[str, str] | None = None) -> Settings` (default `os.environ`).
  - Marker pytest: `blender`, `slow`, `strata`.

- [ ] **Step 1: Init git dan `.gitignore` sebelum file lain**

```bash
rtk git init
```
Isi `.gitignore`: `data/`, `.env`, `server-info.txt`, `.venv/`, `node_modules/`, `web/dist/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `benchmarks/spike/crops/`.

- [ ] **Step 2: `pyproject.toml` + Python 3.12**

`rtk uv python install 3.12`, lalu `uv init --bare` (atau tulis manual) dengan `requires-python = ">=3.12,<3.13"`. Dependencies: `numpy`, `opencv-python-headless`, `rapidocr-onnxruntime`, `pygltflib`, `jinja2`, `weasyprint`, `openai`. Dev group: `pytest`, `ruff`. `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, markers `blender: butuh Blender`, `slow: >10 detik`, `strata: butuh Strata hidup`. `[tool.ruff] line-length = 100`. Jalankan `rtk uv sync`.

- [ ] **Step 3: Tulis test yang gagal**

```python
# tests/test_config.py
from pathlib import Path
from core.config import load_settings

def test_defaults_match_architecture_doc():
    s = load_settings({})
    assert s.data_dir == Path("./data")
    assert s.blender_render_device == "CPU"
    assert s.strata_base_url == "http://192.168.2.142:8081/v1"
    assert s.strata_model == "qwen3.8-flash-next-iq2_xs"
    assert s.strata_timeout_s == 120
    assert s.llm_tasks_enabled == ()
    assert (s.llm_max_iter, s.llm_votes) == (5, 3)
    assert (s.sweep_max_candidates, s.max_upload_mb) == (12, 50)

def test_overrides_are_parsed():
    s = load_settings({"STRATA_TIMEOUT_S": "30", "LLM_TASKS_ENABLED": "T1, T3", "DATA_DIR": "/x"})
    assert s.strata_timeout_s == 30
    assert s.llm_tasks_enabled == ("T1", "T3")
    assert s.data_dir == Path("/x")

def test_blender_bin_resolves_symlink(tmp_path):
    real = tmp_path / "Blender"; real.write_text("#!/bin/sh\n"); real.chmod(0o755)
    link = tmp_path / "blender"; link.symlink_to(real)
    assert load_settings({"BLENDER_BIN": str(link)}).blender_bin == str(real.resolve())
```

```python
# tests/test_repo_hygiene.py
import subprocess

def test_server_info_is_ignored_and_untracked():
    assert subprocess.run(["git", "check-ignore", "-q", "server-info.txt"]).returncode == 0
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    assert "server-info.txt" not in tracked and ".env" not in tracked
```

- [ ] **Step 4: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/test_config.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'core'`

- [ ] **Step 5: Implement `load_settings` di `core/config.py`**

Stdlib saja. `blender_bin`: `shutil.which(value)` lalu `os.path.realpath`. Bila tidak ditemukan, kembalikan nilai mentah (jangan raise; test builder yang akan skip). Default `BLENDER_BIN` = `"blender"`. `LLM_TASKS_ENABLED` di-split koma, di-strip, dan string kosong dibuang.

- [ ] **Step 6: Jalankan test, pastikan lulus**

Run: `rtk uv run pytest -v`
Expected: semua PASS (4 test).

- [ ] **Step 7: `.env.example`**

Semua variabel §7 dengan default, plus:
```
# Wajib path asli; symlink Homebrew crash
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
# WeasyPrint di macOS (pango dari Homebrew)
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```
Salin ke `.env` (gitignored).

- [ ] **Step 8: Cek apa yang akan di-commit, lalu commit**

Run: `rtk git status --short`
Expected: **tidak ada** `server-info.txt` dan `.env`. File yang ada: PRD/, ROADMAP.md, DESIGN.md, API_DOCUMENTATION.md, floorplan/, docs/, dan file Task 1.

```bash
rtk git add -A && rtk git commit -m "chore: init repo, python toolchain, settings"
```

- [ ] **Step 9 (tindakan pengguna, bukan agen):** ingatkan pengguna untuk memindahkan kredensial di `server-info.txt` ke password manager dan mempertimbangkan mengganti password (R-15). Jangan buka file itu.

---

### Task 2: Smoke test Blender headless → `.glb` dengan extras

**Files:**
- Create: `builder/build.py`
- Test: `tests/test_builder_smoke.py`

**Interfaces:**
- Consumes: `core.config.load_settings().blender_bin`
- Produces: format `build_input` **v0** (diperluas di M2, `PRD/03-layout-spec.md` §13):
  ```json
  { "version": 0,
    "boxes": [ { "name": "wall_W1", "min_mm": [0, 0, 0], "size_mm": [1000, 2000, 3000],
                 "props": { "spec_id": "W1", "spec_type": "wall" } } ] }
  ```
  `min_mm` = sudut minimum kotak dalam koordinat spec. Output: `<out_dir>/shell.glb`.

- [ ] **Step 1: Tulis test yang gagal**

```python
# tests/test_builder_smoke.py
import json, os, subprocess
from pathlib import Path
import pytest
from pygltflib import GLTF2
from core.config import load_settings

BLENDER = load_settings().blender_bin
pytestmark = [pytest.mark.blender,
              pytest.mark.skipif(not os.access(BLENDER, os.X_OK), reason="Blender not found")]

def run_build(inp: Path, out: Path):
    return subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1",
                           "-P", "builder/build.py", "--", str(inp), str(out)],
                          capture_output=True, text=True, timeout=300)

def test_box_exports_with_extras_and_axes(tmp_path):
    inp = tmp_path / "build_input.json"
    inp.write_text(json.dumps({"version": 0, "boxes": [{
        "name": "wall_W1", "min_mm": [0, 0, 0], "size_mm": [1000, 2000, 3000],
        "props": {"spec_id": "W1", "spec_type": "wall"}}]}))
    r = run_build(inp, tmp_path / "out")
    assert r.returncode == 0, r.stderr[-2000:]
    assert "@@PROGRESS 100" in r.stdout
    g = GLTF2().load(str(tmp_path / "out" / "shell.glb"))
    node = next(n for n in g.nodes if n.name == "wall_W1")
    assert node.extras["spec_id"] == "W1" and node.extras["spec_type"] == "wall"
    # center spec (0.5, 1.0, 1.5) m -> glTF Y-up (x, z, -y)
    assert node.translation == pytest.approx([0.5, 1.5, -1.0], abs=1e-6)
    acc = g.accessors[g.meshes[node.mesh].primitives[0].attributes.POSITION]
    ext = [hi - lo for hi, lo in zip(acc.max, acc.min)]
    assert ext == pytest.approx([1.0, 3.0, 2.0], abs=1e-6)  # 1:1 dalam meter

def test_missing_input_fails_nonzero(tmp_path):
    assert run_build(tmp_path / "nope.json", tmp_path / "out").returncode != 0
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/test_builder_smoke.py -v`
Expected: FAIL (`builder/build.py` tidak ada → returncode ≠ 0).

- [ ] **Step 3: Implement `builder/build.py`**

`main(argv: list[str]) -> None`, dengan argumen setelah `--`. Urutan:
1. Cek `bpy.app.version[:2] == (5, 2)`. Bila tidak cocok, `raise SystemExit("Blender 5.2 LTS required, got ...")`.
2. `bpy.ops.wm.read_factory_settings(use_empty=True)`.
3. Per box: mesh kubus via bmesh (`bmesh.ops.create_cube(size=1)`), skala = `size_mm/1000`, lokasi objek = pusat kotak (`(min + size/2)/1000`), lalu set `obj[k] = v` untuk tiap `props`. Skala di-apply ke mesh (bukan transform objek) agar extent accessor = ukuran nyata.
4. `bpy.ops.export_scene.gltf(filepath=out/"shell.glb", export_format="GLB", export_extras=True, export_yup=True)`. Buat `out_dir` bila belum ada.
5. Cetak `@@PROGRESS 10 loaded`, `@@PROGRESS 60 built`, `@@PROGRESS 100 exported` (flush).

- [ ] **Step 4: Jalankan test, pastikan lulus**

Run: `rtk uv run --env-file .env pytest tests/test_builder_smoke.py -v`
Expected: 2 PASS (bukan SKIPPED; bila SKIPPED, `BLENDER_BIN` di `.env` salah).

- [ ] **Step 5: Commit**

```bash
rtk git add builder/build.py tests/test_builder_smoke.py && rtk git commit -m "feat(builder): headless blender smoke build with glTF extras"
```

---

### Task 3: Modul OCR + smoke test pada Gatsu

**Files:**
- Create: `core/extraction/__init__.py`, `core/extraction/ocr.py`
- Test: `tests/test_ocr.py` (unit), `tests/test_ocr_smoke.py` (slow)

**Interfaces:**
- Produces (dipakai ulang di M5 tahap 2.1):
  - `OcrItem` (frozen dataclass): `text: str`, `bbox: tuple[float, float, float, float]` (x0, y0, x1, y1, piksel gambar **input**), `angle: int` (0 atau 90), `conf: float`.
  - `restore_bbox(bbox, upscale: float, rotated_w: int | None = None) -> tuple[float, float, float, float]`: memetakan bbox dari gambar kerja (di-upscale, dan bila `rotated_w` diisi, diputar 90° searah jarum jam dengan lebar `rotated_w`) kembali ke koordinat input.
  - `run_ocr(image: np.ndarray, upscale: float = 2.0) -> list[OcrItem]`: dua pass (0° dan `cv2.ROTATE_90_CLOCKWISE`), engine `rapidocr_onnxruntime.RapidOCR` dibuat sekali (cache modul).

- [ ] **Step 1: Tulis test unit yang gagal**

```python
# tests/test_ocr.py
import cv2, numpy as np, pytest
from core.extraction.ocr import restore_bbox

def mask_bbox(m):
    ys, xs = np.nonzero(m)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)

def test_restore_bbox_upscale_only():
    assert restore_bbox((20, 10, 60, 30), upscale=2.0) == pytest.approx((10, 5, 30, 15))

def test_restore_bbox_matches_cv2_rotate_cw():
    img = np.zeros((40, 100), np.uint8); img[5:15, 10:30] = 255
    big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    rot = cv2.rotate(big, cv2.ROTATE_90_CLOCKWISE)
    got = restore_bbox(mask_bbox(rot), upscale=2.0, rotated_w=rot.shape[1])
    assert got == pytest.approx((10, 5, 30, 15))
```

- [ ] **Step 2: Jalankan, pastikan gagal**

Run: `rtk uv run pytest tests/test_ocr.py -v`
Expected: FAIL, `ModuleNotFoundError`

- [ ] **Step 3: Implement `restore_bbox` dan `run_ocr`**

Rotasi CW: titik gambar diputar (xr, yr) berasal dari (x, y) = (yr, rotated_w − xr). Petakan kedua sudut, urutkan min/max, lalu bagi `upscale`. `run_ocr`: grayscale → BGR bila perlu, `cv2.resize(INTER_CUBIC)`, panggil engine per pass. Hasil RapidOCR `[[4 titik], text, score]` diubah ke bbox axis-aligned (min/max titik) lalu `restore_bbox`. Hasil kosong (`None`) = list kosong. Tanpa dedup antar-pass (klasifikasi teks di M5 yang menangani).

- [ ] **Step 4: Jalankan test unit, pastikan lulus**

Run: `rtk uv run pytest tests/test_ocr.py -v`
Expected: 2 PASS

- [ ] **Step 5: Tulis smoke test Gatsu**

```python
# tests/test_ocr_smoke.py
import math, re
from collections import Counter
import cv2, pytest
from core.extraction.ocr import run_ocr

GRID = Counter({c: 1 for c in "ABCDEF123"})
DIMS = Counter({"6000": 6, "4000": 1, "28000": 1, "12000": 1})   # 4+2 kali 6000
ROOMS = ["MEETING", "GUDANG", "PANTRY", "GALERY", "BATTERY", "AHU", "MDF", "CAPASITOR", "MUSHOLA"]

@pytest.mark.slow
def test_gatsu_grid_and_dimensions_readable():
    items = run_ocr(cv2.imread("floorplan/plan.jpeg"))
    found = Counter(re.sub(r"[^A-Z0-9]", "", i.text.upper()) for i in items)
    hits = sum(min(found[k], n) for k, n in (GRID + DIMS).items())
    rooms = [r for r in ROOMS if any(r in i.text.upper() for i in items)]
    print(f"grid+dim hits {hits}/18; rooms {len(rooms)}/{len(ROOMS)}: {rooms}")
    assert hits >= math.ceil(0.9 * 18)
```

- [ ] **Step 6: Jalankan smoke test**

Run: `rtk uv run pytest tests/test_ocr_smoke.py -v -s`
Expected: PASS, dengan cetakan `grid+dim hits ≥17/18`. Bila gagal: coba `upscale=3.0` (satu-satunya knob M0). Bila masih gagal, catat token yang hilang di `benchmarks/reports/m0-smoke.md`, tandai test `xfail(strict=False, reason=...)`, lalu laporkan ke pengguna sebagai temuan risiko untuk M5. Jangan tuning lebih jauh di M0.

- [ ] **Step 7: Commit**

```bash
rtk git add core/extraction tests/test_ocr.py tests/test_ocr_smoke.py && rtk git commit -m "feat(ocr): rapidocr wrapper with rotated pass and bbox restore"
```

---

### Task 4: Smoke test WeasyPrint

**Files:**
- Test: `tests/test_report_smoke.py`

- [ ] **Step 1: Pastikan pango terpasang**

Run: `brew list pango >/dev/null 2>&1 || rtk brew install pango`

- [ ] **Step 2: Tulis test**

```python
# tests/test_report_smoke.py
from jinja2 import Template
from weasyprint import HTML

def test_jinja_html_renders_to_pdf():
    html = Template("<h1>{{ title }}</h1><p>Luas {{ area }} m²</p>").render(title="MSC Gatsu", area=57.62)
    pdf = HTML(string=html).write_pdf()
    assert pdf.startswith(b"%PDF") and len(pdf) > 1000
```

- [ ] **Step 3: Jalankan**

Run: `rtk uv run --env-file .env pytest tests/test_report_smoke.py -v`
Expected: PASS. Bila `OSError: cannot load library 'libgobject-2.0-0'`, pastikan `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` ada di `.env`.

- [ ] **Step 4: Commit**

```bash
rtk git add tests/test_report_smoke.py && rtk git commit -m "test: weasyprint pdf smoke"
```

---

### Task 5: Scaffold `web/` (Vite + React 18 + Carbon g100 + R3F)

**Files:**
- Create: `web/` (scaffold Vite), `web/src/main.tsx`, `web/src/app/App.tsx`, `web/src/index.scss`

**Interfaces:**
- Produces: `App` = app shell kosong (Carbon `Header` "Floorplan3D" + area konten berisi `<Canvas>` R3F). Shell ini dikembangkan di M3.

- [ ] **Step 1: Scaffold dan pin versi**

```bash
rtk npm create vite@latest web -- --template react-ts
cd web && rtk npm i react@18.3.1 react-dom@18.3.1 @carbon/react three @react-three/fiber@^8 @react-three/drei@^9 \
  && rtk npm i -D @types/react@^18 @types/react-dom@^18 @types/three sass
```
Hapus aset demo Vite (`App.css`, logo, `index.css`).

- [ ] **Step 2: Tema dan halaman**

`index.scss`: `@use '@carbon/react';` lalu `html, body, #root { height: 100%; margin: 0; background: #161616; }`. `App.tsx`: bungkus dengan `<Theme theme="g100">`, `Header` + `HeaderName prefix="">Floorplan3D</HeaderName>`, lalu konten `height: calc(100% - 48px)` berisi `<Canvas>` dengan `ambientLight`, `directionalLight`, satu `mesh` box warna `#0f62fe` yang berputar (`useFrame`), dan `OrbitControls` dari drei.

- [ ] **Step 3: Build**

Run: `cd web && rtk npm run build`
Expected: sukses tanpa error TypeScript.

- [ ] **Step 4: Verifikasi visual**

Jalankan `npm run dev` di background, buka `http://localhost:5173` dengan Playwright MCP, ambil screenshot, lalu evaluasi:
- `getComputedStyle(document.body).backgroundColor === "rgb(22, 22, 22)"`
- `document.querySelector("canvas") !== null`
- teks header "Floorplan3D" terlihat.

Simpan screenshot ke scratchpad (tidak di-commit). Matikan dev server.

- [ ] **Step 5: Commit**

```bash
rtk git add web && rtk git commit -m "feat(web): vite react18 carbon g100 shell with r3f cube"
```

---

### Task 6: Spike Strata (bersyarat)

**Files:**
- Create: `benchmarks/spike/items.json`, `benchmarks/spike/make_crops.py`, `benchmarks/spike/run_spike.py`, `benchmarks/reports/spike-strata.md`

Throwaway: tanpa unit test. Kode klien sebenarnya dibuat di M6.

- [ ] **Step 1: Cek Strata**

Run: `rtk curl -s -m 5 http://192.168.2.142:8081/health`
- Gagal/timeout: minta pengguna menyalakan Strata. Bila belum bisa hari ini, tulis `benchmarks/reports/spike-strata.md` berisi "Ditunda ke awal M6: Strata tidak aktif (tanggal)". Tambahkan catatan yang sama di ROADMAP M6, lalu lompat ke Task 7.

- [ ] **Step 2: `items.json`, 20 item berlabel**

Agen mengamati `plan.jpeg` (zoom 2×) dan memilih bbox piksel. Komposisi: 10 dinding asli, 6 non-dinding (jalur kabel, garis dimensi, leader), 4 pintu. Skema per item:
```json
{ "id": "W01", "task": "T1", "element_px": [x0, y0, x1, y1], "label": "wall",
  "evidence": "length: 4200 mm, thickness: 150 mm, ...", "fewshot": false }
```
`label`: T1 `wall`/`annotation`; T2 `{"is_door": true, "door_type": "...", "hinge": "...", "swing": "..."}`. Satu item T1-wall, satu T1-annotation, dan satu T2 diberi `"fewshot": true` (tidak dinilai, sehingga ada 17 item evaluasi). Bukti teks ditulis manual mengikuti format `05-llm-review.md` §3.2.

- [ ] **Step 3: `make_crops.py`**

Sesuai `05-llm-review.md` §3.1: crop persegi berpusat pada elemen, sisi = panjang elemen × 1.6 (min 2 m, maks 8 m, memakai 25.85 mm/px), resize 768×768, outline magenta 3 px + label ID. Thumbnail konteks 384×384 dengan kotak merah. Tulis juga `crops/contact.png` (semua crop + label). **Tunjukkan contact sheet ke pengguna untuk konfirmasi label sebelum lanjut.**

- [ ] **Step 4: `run_spike.py`**

SDK `openai` dengan nilai dari `core.config.load_settings()`: `base_url=strata_base_url`, `api_key="none"`, `timeout=strata_timeout_s`, `model=strata_model`. Per panggilan: `temperature=0`, `max_tokens=300`, `extra_body={"reasoning_effort": "low"}`. Gambar dikirim sebagai `image_url` data URL base64 PNG (crop + konteks). System prompt dari `05-llm-review.md` §3.4. Coba `response_format={"type": "json_object"}` pada panggilan pertama; bila ditolak (HTTP 400), jalan tanpa itu dan catat. Parse: buang blok `<think>…</think>` dan code fence, lalu `json.loads`. Exception parse dihitung sebagai `invalid` (jangan crash). Varian: {bukti teks on/off} × {few-shot on/off} = 4 varian × 17 item. Simpan setiap respons mentah ke `benchmarks/spike/results.jsonl` (id, varian, latensi, raw, parsed, correct).

**Uji downscale:** gambar putih 768×768 berisi lima angka 6 digit berbeda dengan tinggi 8/10/12/16/20 px (`cv2.putText`). Minta model menyalin semuanya. Catat ukuran terkecil yang terbaca benar.

- [ ] **Step 5: Jalankan dan tulis laporan**

Run: `rtk uv run --env-file .env python benchmarks/spike/run_spike.py`

`spike-strata.md` memuat:
- tabel per varian × tugas: akurasi, % JSON invalid, latensi p50/p95;
- dukungan `response_format`;
- ukuran teks terkecil yang terbaca;
- rekomendasi urutan aktivasi tugas dan setelan `reasoning_effort`/bukti teks untuk M6.

Baseline pembanding T1: ambang keyakinan CV belum ada di M0, jadi bandingkan dengan tebakan kelas mayoritas.

- [ ] **Step 6: Commit**

```bash
rtk git add benchmarks/spike/*.py benchmarks/spike/items.json benchmarks/spike/results.jsonl benchmarks/reports/spike-strata.md
rtk git commit -m "spike: strata T1/T2 capability report"
```

---

### Task 7: Verifikasi kriteria selesai M0

- [ ] **Step 1: Seluruh test Python**

Run: `rtk uv run --env-file .env pytest -v -m "not strata"`
Expected: semua PASS, dengan test `blender` dan `slow` ikut jalan (tidak SKIPPED). Kalau OCR di-xfail di Task 3, harus terlihat sebagai XFAIL dan dilaporkan.

- [ ] **Step 2: Lint**

Run: `rtk uv run ruff check .` dan `cd web && rtk npm run lint`
Expected: bersih.

- [ ] **Step 3: Centang ROADMAP M0**

Centang tugas M0 yang selesai di `ROADMAP.md`. Catat penyimpangan (OCR < 90%, spike ditunda, path Blender) di bawah "Kriteria selesai" M0. Tambahkan ke `PRD/11-tech-stack.md` §4 bahwa `BLENDER_BIN` harus memakai path asli `.app`.

- [ ] **Step 4: Commit**

```bash
rtk git add ROADMAP.md PRD/11-tech-stack.md && rtk git commit -m "docs: close M0"
```
