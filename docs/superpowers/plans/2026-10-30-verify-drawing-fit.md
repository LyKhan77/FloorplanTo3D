# Verify: drawing fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stage 8 judges the model against the drawing itself, not against the extractor's wall mask, so human review corrections no longer lower the score.

**Architecture:** A new `core/verify/fit.py` samples every wall along its length (every 50 mm) and asks whether a drawn line lies under the wall (either face or the centre line, ±50 mm) on the Otsu ink of the original image. Wall junctions and opening spans are skipped. The length-weighted share of hits is the *drawing fit*; walls with under half their samples on ink are listed. Fit drives the stage status (with glb 1:1); the top-down IoU stays as information only.

**Tech Stack:** Python 3.12, OpenCV, Shapely, pydantic Spec; React (StagePanel), Jinja report.

**Spec:** user decision in conversation (2026-10-30): "IoU dinilai berdasarkan apa? ... pemilihan penilaian yang tepat" → approved the proposal: fit to the drawing is the main measure, walls off the drawing are warnings with IDs, IoU to the extractor mask is information only. Deviation from the proposal: no 1.2 m section render. The fit is computed from the spec and the image, not from the render, because the drawing shows walls as face lines while the render fills them solid, and a per-wall list needs the spec anyway.

## Global Constraints

- Tolerance 50 mm, sampling step 50 mm, a wall is off when it has ≥ 5 samples and < 0.5 of them on ink.
- `FIT_OK = 0.90`: below it the stage is `needs_attention` (outputs still published).
- Calibration (spike, 2026-10-30): Gatsu GT 0.929 (2 off: W30, W64); GT shifted 300 mm 0.71; GT scaled +1% 0.84; plan-37a2 v20 0.980.
- glb 1:1 failure still fails the stage. IoU never changes the status.
- UI and report copy in Indonesian.

## Review Focus

- A spec with no `px_to_mm` or an unreadable image: fit is `None`, a warning says why, status falls back to glb only.
- A wall entirely inside other walls or entirely spanned by openings: no samples, not listed as off, not counted.
- Old `verify.json` files (no `drawing_fit`): StagePanel, ProjectsPage, and the report still render.
- A PDF project: the image is `input/raster.png`, the same pixels `px_to_mm` refers to.
- Single-line walls (Gatsu draws some walls as one line): the centre sample must count them as on the drawing.

---

### Task 1: `drawing_fit`

**Files:**
- Create: `core/verify/fit.py`
- Test: `tests/verify/test_fit.py`

**Interfaces:**
- Produces: `drawing_fit(spec: Spec, gray: np.ndarray) -> dict` with keys `fit: float | None`, `walls_off: list[str]`, `checked: int`, `tolerance_mm: int`.

- [ ] **Step 1: Write the failing tests:**
  - `test_gt_fits_the_drawing`: GT on `floorplan/plan.jpeg` has fit ≥ 0.90 and `walls_off` ⊆ {W30, W64}.
  - `test_shifted_model_does_not_fit`: GT shifted +300 mm in x has fit < 0.90.
  - `test_one_misplaced_wall_is_listed`: GT with W1 moved 1500 mm off the drawing lists `W1`.
  - `test_walls_without_samples_are_skipped`: a wall fully covered by one opening is not counted and not listed.
  - `test_no_transform_gives_none`: no `px_to_mm` gives fit `None`.
- [ ] **Step 2:** Run `uv run pytest -q tests/verify/test_fit.py`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement as in the spike: Otsu ink, elliptical dilation of radius ceil(50 / mm_per_px), samples at the faces ±t/2 and the centre, other walls' footprints (flat-cap buffers, shrunk 1 mm) and opening spans skipped.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit.

### Task 2: Stage 8 status from fit

**Files:**
- Modify: `core/verify/run.py`, `server/orchestrator.py` (stage 8 metrics), `server/projects.py` (list: `fit`)
- Test: `tests/verify/test_verify.py`

**Interfaces:**
- Consumes: `drawing_fit` (Task 1).
- Produces: `verify_status(glb_pass: bool, fit: float | None) -> tuple[str, list[str]]`; `verify.json` gains `drawing_fit` (the Task 1 dict) and `fit_threshold`; stage 8 metrics gain `fit`; the project list gains `fit`.

- [ ] **Step 1:** Write the failing tests:
  - `verify_status` returns `failed` on glb failure, `needs_attention` below 0.90, and `succeeded` otherwise.
  - A low IoU alone no longer gives `needs_attention`.
  - `run_verify` writes `drawing_fit` and adds a warning naming the off walls ("N dinding tidak di atas garis gambar: W1, …").
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Keep `iou` and `iou_mask.png`.
- [ ] **Step 4:** Run `tests/verify` and `tests/server`. Expected: PASS.
- [ ] **Step 5:** Commit.

### Task 3: UI and report

**Files:**
- Modify: `web/src/components/StagePanel.tsx`, `web/src/pages/ProjectsPage.tsx`, `web/src/api/types.ts` (if the project type lives there), `core/report/templates/report.html.j2`
- Test: the StagePanel test and the report test

- [ ] **Step 1:** Write the failing tests:
  - StagePanel stage 8 shows "Kecocokan gambar", the fit value, threshold 0.90, and the off wall IDs; IoU is shown as secondary info.
  - An old `verify.json` without `drawing_fit` still renders.
  - The report shows the fit row.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. The ProjectsPage column shows fit, falling back to IoU for old outputs.
- [ ] **Step 4:** Run `npx vitest run`, `npm run lint`, and `tsc -b`, plus the report tests. Expected: PASS.
- [ ] **Step 5:** Commit, including the README Troubleshooting row and the ROADMAP status.
