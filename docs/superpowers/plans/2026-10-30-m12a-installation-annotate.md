# M12a Installation layer: annotate trays and racks — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An optional, versioned installation document per project, in which an operator traces cable trays and racks
from the client's plan, with snapping, validation, reasons, automatic drops to racks, and tray lengths per class.

**Architecture:** A new `core/installation/` package holds the document model, an ops reducer, a version store (same
pattern as `core/spec/store.py`), derived geometry (elevations, drops, lengths), validation (I001–I007), and the tray/box
snap. `server/routes/installations.py` exposes start, commit, dry-run validate, rebase, and snap. On the web, a separate
`web/src/install/` store and workspace reuse the review canvas (layout read-only) and add the tray tool (`T`) and the rack
tool (`K`). The editor gets a Layout | Instalasi mode toggle. M12b (Blender build, report, 3D layers) is planned after this lands.

**Tech Stack:** Python 3.12, pydantic, Shapely, OpenCV, FastAPI; React, Zustand, Carbon, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-30-installation-cable-tray-design.md` (§ numbers below refer to it).

## Global Constraints

- Installation is optional. A project without one behaves exactly as today. No layout code path changes behaviour.
- Files: `data/projects/<id>/installations/installation.v<N>.json` + `HEAD`.
- Tray defaults (§5.2):
  - width: data 200, power 400; allowed widths 100/150/200/300/400/500/600;
  - side_height 100; allowed 50/100/150;
  - tray_type `"perforated"` only;
  - flow `"forward"`.
- Elevation (§6.2): sisi bawah tray, from finished floor z = 0.
  - overhead default = `ceiling_height − 300 − side_height`;
  - underfloor default = `−raised_floor_height + 100`;
  - `ceiling_height` default = layout `defaults.wall_height`.
- Drops (§6.4): drop radius 1500 mm, horizontal distance from a rack's centre to the nearest tray segment. One drop per rack
  per class, to the nearest tray of that class. Drop width = min(tray width, 300).
- Racks: objects whose template category is `rack`, from the installation and from layout `objects`.
- Power–data separation ≥ 300 mm; access clearance 300 mm above overhead trays.
- Reasons are required for `move_tray_path`, `delete_tray`, `delete_object`, and `update_object` that changes position
  or rotation. Save is refused on any `error` issue. Rebase always saves.
- UI copy is in Indonesian; code, tests, and commits are in English.
- Run Python with `uv run --env-file .env`, and web from `web/` (`npx vitest run`, `npm run lint`, `npx tsc -b`).

## Review Focus

1. **No extraction run** (imported spec): the snap endpoints return 404 `no_run`. The tray tool then keeps the clicked path
   as drawn, and the rack tool says "tidak ada kotak rack di sini". Nothing crashes.
2. **Double clicks:** a double click while tracing adds repeated or near-identical points. The client drops points closer
   than 100 mm to the previous one before saving, and the server rejects what remains with I001.
3. **Underfloor tray without a raised floor:** an I002 error names the tray. Save is refused, and the message tells the
   operator to set `raised_floor_height`.
4. **Rack near several trays:** a rack in range of two data trays and one power tray gets exactly one data drop (nearest)
   and one power drop.
5. **Rebase onto a layout version where a tray now crosses a new wall or a rack's layout object is gone:** rebase saves,
   and the issues list it.

---

### Task 1: Installation model and schema

**Files:**
- Create: `core/installation/__init__.py`, `core/installation/models.py`
- Modify: `core/spec/export_schema.py` (add `installation.schema.json`), `web/package.json` (`gen:types` adds `src/types/installation.ts`)
- Test: `tests/installation/__init__.py`, `tests/installation/test_models.py`

**Interfaces:**
- Produces:
  - `CableTray`, `InstallMeta`, `Installation` (pydantic), with fields exactly as §5.1/§5.2.
    - `Installation.objects: list[PlacedObject]` (import from `core.spec.models`).
    - `InstallMeta`: `version`, `parent_version`, `layout_version`, `ceiling_height: int | None`,
      `raised_floor_height: int | None`, `default_mounting: "overhead" | "underfloor" = "overhead"`, `created_at`,
      `source: "editor" | "auto" | "migration"`, `message`.
    - Ids: trays `T<n>`, objects `O<n>`; next id from the highest existing number.
- [ ] **Step 1: Write the failing tests:**
  - `test_tray_defaults`: `CableTray(id="T1", path=[(0, 0), (1000, 0)], tray_class="data")` has width 200, side height 100,
    mounting None (meaning: take `meta.default_mounting`), elevation None, and flow "forward".
  - `test_unknown_fields_rejected`: an extra key raises a validation error.
  - `test_committed_schemas_match_models` (existing, `tests/spec/test_schema_export.py`) after regenerating.
- [ ] **Step 2:** Run `uv run pytest -q tests/installation/test_models.py`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement. Run `uv run python -m core.spec.export_schema` and `cd web && npm run gen:types`.
- [ ] **Step 4:** Run the tests above. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): document model and schema`.

### Task 2: Installation ops

**Files:**
- Create: `core/installation/ops.py`
- Test: `tests/installation/test_ops.py`

**Interfaces:**
- Produces: `apply(inst: Installation, ops: list[dict], by: str, version: int) -> Installation`, raising `OpError(index, op, message)`.
  - Ops (pydantic, `extra="forbid"`, discriminated on `op`):
    - `add_tray` (`path`, `tray_class`, optional `width`, `side_height`, `mounting`, `elevation`, `flow`; width defaults by class);
    - `set_tray` (`id` + any of `tray_class`, `width`, `side_height`, `mounting`, `elevation` (nullable), `flow`);
    - `move_tray_path` (`id`, `path`, `reason`);
    - `delete_tray` (`id`, `reason`);
    - `set_installation_meta` (`ceiling_height`, `raised_floor_height`, `default_mounting`; nullable heights);
    - `add_object` / `update_object` / `delete_object`, same fields as `core/spec/ops.py` plus `reason` on `delete_object`.
      `update_object` requires `reason` when `position` or `rotation` is given.
  - Every op logs `{op, id, by, reason}` to `provenance_log`.
  - A width or side height outside the allowed lists is an `OpError`.

- [ ] **Step 1: Write the failing tests:**
  - `test_add_tray_defaults_width_by_class`: data → 200, power → 400, ids `T1` and `T2`.
  - `test_move_and_delete_need_a_reason`: without `reason` → `OpError`; with it → the log has the reason.
  - `test_update_object_position_needs_a_reason_label_does_not`.
  - `test_width_outside_standard_sizes_is_rejected`: 250 → `OpError`.
- [ ] **Step 2:** Run `uv run pytest -q tests/installation/test_ops.py`. Expected: FAIL.
- [ ] **Step 3:** Implement following `core/spec/ops.py` (`_Op`, `HANDLERS`, `Ctx.prov`).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): ops with reasons`.

### Task 3: Derived geometry, validation, and store

**Files:**
- Create: `core/installation/derive.py`, `core/installation/validate.py`, `core/installation/store.py`
- Test: `tests/installation/test_derive.py`, `tests/installation/test_validate.py`, `tests/installation/test_store.py`

**Interfaces:**
- Produces:
  - `rack_categories(templates_dir: Path) -> dict[str, str]`: `{template_id: category}` read from `*/*/template.json`.
  - `tray_elevation(tray, meta: InstallMeta, layout: Spec) -> int`: §6.2 defaults when `tray.elevation is None`.
  - `racks(inst, layout, templates) -> list[PlacedObject]`: installation objects plus layout objects with category `rack`.
  - `drops(inst, layout, templates) -> list[Drop]`. `Drop` is a TypedDict:
    `{rack_id, tray_id, tray_class, at: Point (on the tray axis), to: Point (rack centre), horizontal: int, vertical: int}`.
    Vertical: overhead = tray elevation − rack height; underfloor = −tray elevation − side_height.
  - `lengths(inst, layout, templates) -> dict` with keys `{"data": {"horizontal", "drops", "total"}, "power": {...}}` (mm, ints).
  - `validate_installation(inst, layout, templates) -> list[Issue]` (reuse `core.spec.validate.Issue`):
    - I001 error: path < 2 points, a segment < 100 mm, or a repeated point;
    - I002 error: elevation outside the limits in §6.2, or underfloor with `raised_floor_height` None;
    - I003 warning: the tray's footprint crosses a wall's footprint and the z ranges overlap (wall 0..height);
    - I004 warning: power–data body distance < 300 (plan distance between footprints when the z ranges overlap, else the vertical gap);
    - I005 warning: an overhead tray footprint overlaps a rack, column, or stair footprint, and the tray underside is below that element's top;
    - I006 info: a rack with no data or no power drop, worded "R… tidak terhubung ke tray data" (or "power");
    - I007 warning: `meta.layout_version` < the layout HEAD (the caller passes `layout_head`).
  - `InstallationStore(dir: Path)`:
    - `head() -> int | None`, `versions() -> list[int]`, `load(version | "HEAD") -> Installation`
    - `start(layout_version: int, ceiling_height, raised_floor_height, default_mounting) -> Installation` (v1, empty;
      `FileExistsError` if any version exists)
    - `commit_ops(base_version, ops, by, message, layout: Spec, templates: dict[str, str]) -> tuple[Installation, list[Issue]]`
      (raises `VersionConflict`, `ValidationFailed`, `OpError`, the same classes as `core/spec/store.py`)
    - `rebase(layout_version: int, layout: Spec, templates) -> tuple[Installation, list[Issue]]` (always saves).
  - `templates` is `{template_id: category}`. Task 3 gives `rack_categories(templates_dir) -> dict[str, str]`.


- [ ] **Step 1: Write the failing tests.** Fixture: `tests.spec.fixtures.spec_with_rooms()` as the layout, plus one rack template `{"rack-42u-600x1200": "rack"}`.
  - `test_default_elevations`: with `ceiling_height` None and the layout `wall_height` 3000, overhead → 2600. With a raised floor of 600, underfloor → −500.
  - `test_drop_to_nearest_rack_per_class`: one rack 1000 mm from a data tray and 1200 mm from a power tray gives two
    drops. A second data tray 500 mm away takes the data drop instead. A rack 1600 mm from every tray gets no drop, and
    I006 is raised.
  - `test_lengths_sum_horizontal_and_drops`: a 5000 mm data tray with one overhead drop to a 2000 mm rack
    (horizontal 300 mm) gives `{"horizontal": 5000, "drops": 300 + 600, "total": 5900}`.
  - `test_underfloor_without_raised_floor_is_I002` (Review Focus 3).
  - `test_repeated_point_is_I001` (Review Focus 2).
  - `test_tray_crossing_a_wall_is_I003` and `test_power_data_too_close_is_I004`.
  - `test_layout_objects_count_as_racks`: a rack-category object in the layout is reached.
  - `test_start_creates_empty_v1_with_layout_version`: `start(20, None, None, "overhead")` gives `head() == 1`,
    `meta.layout_version == 20`, and no trays; a second `start` raises `FileExistsError`.
  - `test_commit_conflict_and_versions`: a base other than HEAD raises `VersionConflict`; a valid commit makes v2 with
    `parent_version == 1`; an `error` issue raises `ValidationFailed`.
  - `test_rebase_saves_even_with_errors` (Review Focus 5): an underfloor tray, rebased onto a layout version with no
    raised floor, saves v2 with the new `layout_version`, and the issues contain I002.
- [ ] **Step 2:** Run `uv run pytest -q tests/installation`. Expected: FAIL.
- [ ] **Step 3:** Implement. The store mirrors `SpecStore` (lock, atomic write, HEAD last). Derived geometry uses Shapely: tray footprint = `LineString(path).buffer(width / 2, cap_style="flat", join_style="mitre")`; wall footprints as in `core/verify/fit.py`.
- [ ] **Step 4:** Run `tests/installation` (Tasks 1–3). Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): drops, lengths and validation`.

### Task 4: Tray and box snap

**Files:**
- Create: `core/installation/snap.py`
- Test: `tests/installation/test_snap.py`

**Interfaces:**
- Produces:
  - `snap_tray(binary, px_to_mm, points: list[Point]) -> dict | None`: `{"path": [...], "width": int}`.
    - Each segment is snapped like `core/extraction/snap.snap_wall`, but with face spacing 80–700 mm.
    - The width is the median face spacing over all segments, rounded to the nearest allowed width.
    - The new vertices are the intersections of consecutive snapped lines.
    - A segment with no band keeps its drawn position.
    - Returns `None` only when no segment snaps.
  - `snap_box(binary, px_to_mm, at: Point) -> dict | None`: `{"center": Point, "size": [w, d], "rotation": 0 | 90}`.
    - Finds the smallest closed region (4-connected background component of the binary image) that contains `at`.
    - The region must be ≥ 300 × 300 mm and ≤ 3000 × 3000 mm.
    - `rotation` is 90 when the box is taller than wide in plan.

- [ ] **Step 1: Write the failing tests:**
  - `test_snap_tray_on_gatsu_band`. Use `floorplan/plan.jpeg` (Otsu binary) and the GT `px_to_mm`. The rough points
    `[(24500, 600), (30000, 250)]` give a path whose y values are 395 ± 60 at both ends and a width of 200. Measured:
    band edges at about y = 500 and 290 mm, x 23800–32000.
  - `test_snap_tray_without_band_returns_none`: a blank 800 × 800 image gives `None`.
  - `test_snap_box_finds_drawn_rack`. On a white synthetic image with `px_to_mm = [10, 0, 0, 0, -10, 8000]`, draw a
    60 × 120 px rectangle outline (600 × 1200 mm). A click inside gives size `[600, 1200]` ± 20, rotation 90, and the
    centre ± 20 mm.
  - `test_snap_box_ignores_huge_regions`: a click in a 4000 mm room gives `None`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Move `snap_wall`'s profile and vote into parameters (face min/max), so both functions share
  them. `snap_wall`'s behaviour stays the same: its existing tests in `tests/extraction` must stay green.
- [ ] **Step 4:** Run `tests/installation/test_snap.py` and `tests/extraction`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): snap traced trays and racks to the drawing`.

### Task 5: API and prompt parameters

**Files:**
- Create: `server/routes/installations.py`
- Modify: `server/app.py` (router), `server/projects.py` (`summary` and project detail gain `installation: {head, layout_version, layout_changed} | None`), `core/extraction/params.py` (`ceiling_height` "tinggi plafon 3.2 m", `raised_floor_height` "raised floor 600 mm" in `KNOWN` and `parse_prompt`)
- Test: `tests/server/test_installations.py`, `tests/extraction/test_params.py` (or its existing file)

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces (prefix `/api/projects/{pid}/installations`):
  - `POST /start {ceiling_height?, raised_floor_height?, default_mounting}` → 201 `Installation`.
    - Missing heights come from the project's `params_final` (prompt), else `None`.
    - 409 `no_layout` without a layout HEAD; 409 `exists` when already started.
  - `GET /HEAD` → `Installation` (404 `no_installation`). `GET ""` → `[{version, created_at, message, layout_version}]`.
  - `POST "" {base_version, ops, message}` → `{version, installation, issues, lengths}`; 409 / 422 / 400 as in `server/routes/specs.py`.
  - `POST /validate {base_version, ops}` → `{issues, drops, lengths}` (dry run against the layout version the installation names).
  - `POST /rebase` → `{version, issues}` onto the layout HEAD.
  - `POST /snap-tray {points}` → `snap_tray` result (404 `no_run`, 422 `no_band`).
  - `POST /snap-box {at}` → `snap_box` result plus `template_id`: the rack template whose (w, d) matches the size within
    100 mm in either orientation, else `null` (404 `no_run`, 422 `no_box`).

- [ ] **Step 1: Write the failing tests** using the `client` / `project_with_gt` fixtures:
  - `test_start_commit_validate_flow`: start → commit `add_tray` → HEAD has `T1`; `/validate` returns `lengths.data.horizontal`.
  - `test_save_refused_on_error`: an underfloor tray without a raised floor gives 422 `validation_failed` with I002.
  - `test_layout_changed_flag_and_rebase`: after a new layout version, `summary.installation.layout_changed` is True;
    `/rebase` makes it False.
  - `test_snap_without_run_is_404` (Review Focus 1).
  - `test_prompt_sets_ceiling_and_raised_floor`: "tinggi plafon 3.2 m, raised floor 600 mm" gives 3200 and 600.
  - `test_project_without_installation_is_unchanged`: `summary.installation is None`, and the layout endpoints behave as before.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/server`, `tests/installation`, and `tests/extraction -k params`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): API to start, edit, validate, rebase and snap`.

### Task 6: Web data layer

**Files:**
- Create: `web/src/install/store.ts`, `web/src/install/reducer.ts`, `web/src/install/api.ts`
- Modify: `web/src/api/types.ts` (`ProjectDetail.installation`, `ProjectSummary.installation`)
- Test: `web/src/install/reducer.test.ts`, `web/src/install/store.test.ts`

**Interfaces:**
- Consumes: Task 1 types (`web/src/types/installation.ts`); Task 5 endpoints.
- Produces:
  - `applyInstallOps(base: Installation, ops: InstallOp[]) -> { inst, failed }`, a pure TS mirror of Task 2 used for the
    instant preview.
  - `useInstallStore` (Zustand): `{ base, ops, view, selection, tool: 'select' | 'tray' | 'rack', trayDraft: Point[],
    trayClass, load(inst), apply(op), applyMany(ops), undo(), redo(), select(ids), setTool, setTrayClass, clear() }`.
  - Hooks in `api.ts`: `useInstallation(pid)`, `useStartInstallation(pid)`, `useInstallValidate(pid, base, ops)`
    (debounced 300 ms, like `useValidate`), `saveInstallation(pid, base, ops, message)`, `snapTray(pid, points)`,
    `snapBox(pid, at)`, `rebaseInstallation(pid)`.

- [ ] **Step 1: Write the failing tests:**
  - `reducer`: `add_tray` defaults widths by class; `delete_tray` removes the tray; an unknown id goes to `failed`.
  - `store`: `apply` then `undo` restores the view.
  - Points closer than 100 mm to the previous one are dropped when a tray draft is committed (Review Focus 2).
- [ ] **Step 2:** Run `npx vitest run src/install`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(web): installation store and API hooks`.

### Task 7: Installation workspace (canvas and tools)

**Files:**
- Create: `web/src/install/InstallWorkspace.tsx`, `web/src/install/InstallLayer.tsx`
- Modify: `web/src/editor/review/ReviewCanvas.tsx` (a `readOnly` prop: no wall, room, or opening picking; marquee off), `web/src/index.scss`
- Test: `web/src/install/InstallWorkspace.test.tsx`

**Interfaces:**
- Consumes: Task 6 store and hooks; `ReviewCanvas` (`children`, `onCanvasPointer`, `backdrop`).
- Produces: `<InstallWorkspace projectId layout={Spec} backdrop />`.
  - **Tray tool `T`:** click to add points, Enter to finish, Esc to cancel. On finish, call `snapTray`; on 404/422 keep
    the drawn points. Then `add_tray` with the current class.
  - **Rack tool `K`:** a click calls `snapBox`, then `add_object`. The template comes from the response, or the first
    template of category `rack` with dims from the box. Shift-drag a box to call `snapBox` at the centre of each enclosed
    region of rack size inside it; the server endpoint takes `at` only, so the client samples a 600 mm grid inside the
    box and dedupes the boxes it gets back by centre.
  - **`InstallLayer`** draws:
    - trays: data `#33b1ff`, power `#ff832b`, opacity 0.45, real width;
    - racks as outlined boxes with their id;
    - drops from the `/validate` response as dashed lines from `at` to `to`;
    - the draft path while tracing.

    Trays and racks are selectable by click.
  - Toolbar: `Pilih V`, `Tray T`, `Rack K`, and a class toggle `Data / Power`.

- [ ] **Step 1: Write the failing tests:**
  - `T` then three clicks then Enter calls `snapTray` with three points and adds `T1`.
  - When `snapTray` rejects with 404, `T1` uses the drawn points (Review Focus 1).
  - `K` then a click adds an object with the template from `snapBox`.
  - On a read-only layout, clicking a wall does not select it.
- [ ] **Step 2:** Run `npx vitest run src/install`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the whole web suite. Expected: PASS, exit 0.
- [ ] **Step 5:** Commit: `feat(web): trace trays and racks on the plan`.

### Task 8: Panels, save, mode toggle, start and rebase

**Files:**
- Create: `web/src/install/InstallPanels.tsx` (properties, issues, lengths), `web/src/install/StartInstallationDialog.tsx`
- Modify: `web/src/editor/EditorTab.tsx` (Layout | Instalasi toggle, shown when the project has an installation;
  Instalasi renders `InstallWorkspace` and `InstallPanels`), `web/src/pages/ProjectDetailPage.tsx` ("Mulai instalasi"
  button when layout outputs exist and no installation; "Layout berubah (vA → vB): cek instalasi" notice with a
  "Rebase" button), `README.md` (an Instalasi section in the E2E flow), `ROADMAP.md` (M12a status)
- Test: `web/src/install/InstallPanels.test.tsx`, `web/src/install/StartInstallationDialog.test.tsx`

**Interfaces:**
- Consumes: Tasks 6–7.
- Produces:
  - **Properties for a selected tray:** class, width (allowed list), side height, mounting, elevation (empty = default,
    with the default shown), flow. Delete and path changes ask for a reason with the existing `DeleteWithReason` component.
  - **Properties for a selected rack:** template, label. Delete asks for a reason.
  - **Masalah list:** issues from `/validate`. Ids are clickable and select the element.
  - **"Panjang tray" table:** data/power × horizontal/drop/total in metres, 1 decimal.
  - **Save:** posts the ops. On 422 it shows the issues and keeps the ops, as the layout Save does.
  - **Start dialog:** ceiling height (prefilled from the prompt or wall height), raised floor (checkbox + height), and
    default mounting. Submit posts `/start` and opens the editor in Instalasi mode.

- [ ] **Step 1: Write the failing tests:**
  - The lengths table shows "5.9" for data total 5900.
  - Deleting a tray without a reason keeps the button disabled.
  - Save on 422 keeps the ops and lists I002.
  - The start dialog posts `{ceiling_height: 3200, raised_floor_height: 600, default_mounting: "underfloor"}`.
  - The project page shows "Mulai instalasi" only when outputs exist and there is no installation.
  - The rebase notice appears when `installation.layout_changed`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Update README and ROADMAP.
- [ ] **Step 4:** Run the web suite, `npm run lint`, `npx tsc -b`, and `uv run --env-file .env pytest -q tests/installation tests/server -m "not blender"`. Expected: all pass, exit 0.
- [ ] **Step 5:** Commit: `feat(web): installation panels, save, start and rebase`.

---

**After M12a (planned separately as M12b):**
- §6.6 sleeves;
- §6.7 Blender build (tray mesh, perforated material, hangers, ceiling and raised floor);
- I3–I5 run kind `installation` and `installation_outputs/`;
- §6.8 editor 3D layers;
- §6.9 report.
