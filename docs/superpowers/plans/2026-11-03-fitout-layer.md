# One Equipment Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The layout holds architecture only. Every device (racks, CRAC, UPS, panels, cameras, trays) lives in the
installation document, edited in one mode "Instalasi & Interior" (Library drop, 2D move/rotate, tool `A` fill
room). Old layout objects move there once, and the installation follows layout changes by itself.

**Architecture:**
- `core/installation/fitout.py`: the one-time move and the automatic rebase, exposed as `POST /installations/ensure`
  and run before `/build`.
- Installation validation gains I009/I010 for devices.
- The installation build/report learns non-rack equipment.
- Area assist gets `layer`: the layout layer keeps the architecture actions, the installation layer keeps
  `fill_room`/`place_drawn` and reads devices from the installation.
- The web moves Library and tool `A` filling into the install editor and adds 2D device editing.

**Tech Stack:** Python 3.12, FastAPI, pydantic, Shapely; React, Zustand, Carbon, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-03-fitout-layer-design.md`. Branch `fitout-layer`.

## Global Constraints

- Mode name in the UI: "Instalasi & Interior".
- **Move:**
  - layout `objects` become installation `add_object` ops with `evidence: {"moved_from": "<layout id>"}`;
  - the layout is committed without them (`delete_object`, reason "dipindah ke Instalasi & Interior");
  - the installation is then rebased onto that layout version.
- **Skipped on the move:**
  - objects whose `moved_from` already exists in the installation;
  - objects overlapping an installation object of the same category (footprint IoU ≥ 0.8), named in the notes.
- No move while the project's newest layout run is `needs_review`.
- Auto-rebase only when layout HEAD > `meta.layout_version`. The client calls it only with no pending installation
  ops. `/build` always does it first.
- Build: still refused on installation errors (`installation_invalid`). The web "build on the old layout anyway" second
  click is removed.
- **New warnings:**
  - I009 "perangkat di luar ruang atau menabrak dinding/kolom";
  - I010 "perangkat tumpang tindih" (z ranges overlap, footprint area > 1 mm²).

  Both are warnings and leave I001–I008 unchanged.
- Build: non-rack objects go to collection "Equipment" named `obj_<id>`; racks stay `rack_<id>` in "Racks". The
  report gains an equipment schedule (count per template and category).
- **Assist layers:**
  - `layer: "layout"` rejects `fill_room`/`place_drawn` with "isi ruang di mode Instalasi & Interior";
  - `layer: "installation"` rejects every other action with "ubah denah di mode Layout".
- **2D editing:**
  - drop a Library card on the install canvas → `add_object` at the drop point (template dims, rotation 0);
  - click selects an object;
  - drag moves it (`update_object position`);
  - `R` rotates +90°;
  - the Properties panel edits x, y, z, rotation, w, d, h.
- Copy is Indonesian.

## Review Focus

1. **Pending ops while the layout changed:** no auto-rebase. The banner asks to Save first, and nothing is lost.
2. **A project with both layout racks and installation racks at the same spots:** the move keeps one per spot and names
   the skipped ones.
3. **Restoring an older layout version that still lists moved objects:** `ensure` does not duplicate them.
4. **A run paused for review:** opening the mode does not commit a layout version.
5. **Dragging an object onto a wall in 2D:** I009 appears in the Problems panel; Save is still allowed (warning).

---

### Task 1: Move and automatic rebase (`core/installation/fitout.py`, `/ensure`, `/build`)

**Files:**
- Create: `core/installation/fitout.py`
- Modify: `server/routes/installations.py` (`POST /ensure`; `/build` calls `auto_rebase` first)
- Test: `tests/installation/test_fitout.py`, `tests/server/test_installations.py` (or the existing installation route
  test file)

**Interfaces:**
- Produces:
  - `ensure(specs: SpecStore, store: InstallationStore, templates: dict[str, str], params: dict, review_paused: bool)
    -> dict`, returning `{"installation": Installation, "moved": int, "skipped": [str], "rebased_to": int | None,
    "issues": [Issue], "notes": [str]}`. It creates the installation when missing (ceiling = `params["ceiling_height"]`
    or None), moves objects unless `review_paused`, then calls `auto_rebase`.
  - `auto_rebase(specs, store, templates) -> tuple[int | None, list[Issue]]`: rebases when layout HEAD is newer and
    returns `(new layout version or None, issues)`.
- Route: `POST /api/projects/{pid}/installations/ensure` → `{installation, moved, skipped, rebased_to, issues, notes}`.
  `review_paused` comes from the newest run's status (`needs_review`).

- [ ] **Step 1: Write the failing tests** (tmp `SpecStore` + `InstallationStore` on `spec_with_rooms` plus objects):
  - `test_ensure_creates_and_moves`: a layout with 2 objects and no installation →
    - the installation has 2 objects with the same position/rotation/dims and `evidence.moved_from`;
    - layout HEAD has 0 objects;
    - the installation `layout_version` equals layout HEAD.
  - `test_ensure_is_idempotent_after_restore`: commit a layout version that re-adds a moved object (same template and
    position, new id, `moved_from` mapping by position) → `ensure` again does not duplicate it.

    Ruling allowed: match by `moved_from` OR the same template within 10 mm of a moved object.
  - `test_duplicate_racks_are_skipped`: an installation rack and a layout rack at the same spot → one remains and
    `skipped` names the layout id.
  - `test_no_move_while_review_paused`: `review_paused=True` → layout HEAD unchanged, objects not moved.
  - `test_auto_rebase_only_when_newer`: layout HEAD > `layout_version` → rebased; equal → `(None, [])`.
  - Route: `test_ensure_route` returns `moved` and `rebased_to`. `test_build_rebases_first`: after a layout commit,
    `/build` leaves `layout_version` at HEAD (mock the orchestrator `start_run` as the existing build test does).
- [ ] **Step 2:** Run `uv run pytest -q tests/installation/test_fitout.py tests/server -k "ensure or build_rebases"`.
  Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): move layout objects into the installation once; rebase by itself`.

### Task 2: Device checks I009/I010

**Files:**
- Modify: `core/installation/validate.py`
- Test: `tests/installation/test_validate.py`

**Interfaces:** `validate_installation` adds:
- **I009 (warning):** an object (not containment roof: z ≥ 2000 exempt) whose footprint is not covered by any room
  (buffer 1 mm), or intersects a wall footprint or column (area > 1).
- **I010 (warning):** two objects whose footprints intersect (area > 1 mm²) and whose z ranges overlap.

Reuse `core.spec.derive.wall_footprint`/`column_footprint` and `core.interior.layout.Placement.footprint`.

- [ ] **Step 1: Write the failing tests:**
  - an object centred on a wall → I009;
  - two overlapping racks → I010;
  - a roof over a rack → no I010;
  - a clean object → no new issue.
- [ ] **Step 2–4:** Run (FAIL); implement; run `tests/installation` (PASS).
- [ ] **Step 5:** Commit: `feat(installation): warn on devices outside rooms, in walls or overlapping`.

### Task 3: Equipment in the installation build and report

**Files:**
- Modify:
  - `core/installation/build.py:63-66`: racks (category rack/network) → `rack_*` in "Racks"; others → `obj_*` in
    "Equipment";
  - `builder/scene.py:11`: add "Equipment" to `INSTALLATION_CHILDREN`;
  - `core/installation/report.py`: equipment schedule;
  - `web/src/install/layers.ts`: a layer "Perangkat" for the Equipment collection.
- Test: `tests/installation/test_build.py`, `tests/installation/test_report.py` (or the existing report test),
  `web/src/install/layers.test.ts`

- [ ] **Step 1: Write the failing tests:**
  - build input: one rack and one CRAC → names `rack_RK1` (Racks) and `obj_O2` (Equipment);
  - report data holds `equipment: [{template_id, category, count}]` with both;
  - layers: "Perangkat" maps to the Equipment collection.
- [ ] **Step 2–4:** Run (FAIL); implement; run `tests/installation` and the web layers test (PASS).
- [ ] **Step 5:** Commit: `feat(installation): build and report every device, not only racks`.

### Task 4: Assist layers

**Files:**
- Modify:
  - `core/assist/plan.py`: `translate(..., allowed: set[str] | None = None)`. An action whose type is not allowed is
    rejected with the copy in Global Constraints;
  - `core/assist/session.py`: `run_turn(..., layer="layout")` passes `allowed`. The context text states the mode;
  - `core/llm_review/prompts/AF/v1.md`: one line per mode;
  - `server/routes/assist.py`: `AreaBody.layer: Literal["layout", "installation"] = "layout"`. For "installation":
    - `base_version` and `ops` are the installation's;
    - the working spec is the pinned layout with `objects` = the installation objects after applying the ops (via
      `core.installation.ops.apply`);
    - the turn gets `ops=[]`.
- Test: `tests/assist/test_plan.py`, `tests/server/test_assist.py`

- [ ] **Step 1: Write the failing tests:**
  - `test_layout_layer_refuses_fill`: `allowed` = architecture → a `fill_room` plan is rejected with "Instalasi &
    Interior";
  - `test_installation_layer_refuses_walls`: `delete_wall` is rejected with "mode Layout";
  - server: `test_installation_layer_reads_installation_objects`: with an installation holding a CRAC, the fake
    client's text contains the CRAC's template id, and a proposal's `add_object` op passes the installation op
    adapter (`core.installation.ops` validates it).
- [ ] **Step 2–4:** Run (FAIL); implement; run `tests/assist tests/server/test_assist.py` (PASS).
- [ ] **Step 5:** Commit: `feat(assist): layout layer for architecture, installation layer for equipment`.

### Task 5: Web — one equipment mode

**Files:**
- Modify:
  - `web/src/editor/EditorTab.tsx`:
    - the mode toggle shows whenever a layout spec exists, labelled "Layout | Instalasi & Interior";
    - Layout mode has no LibraryPanel;
    - Layout tool `A` sends `layer: "layout"`.
  - `web/src/install/api.ts`: `ensureInstallation(pid)`.
  - `web/src/install/InstallEditor.tsx`:
    - on open (no pending ops) call `ensure` and show its notes/rebase as a notice;
    - Library in the left aside;
    - tool `A` with AssistPanel in the right aside;
    - remove the old-layout second click in `build`.
  - `web/src/editor/assist/store.ts` / `AssistPanel.tsx`: a `layer` and a target store. Installation Terima applies
    to `useInstallStore` ops; the base key uses the install base version + ops.
  - `web/src/install/InstallationBanner.tsx`: "Mulai instalasi" without the outputs requirement; Rebase only when
    pending ops block the auto-rebase.
- Test: `web/src/install/InstallEditor.test.tsx`, `web/src/editor/assist/AssistPanel.test.tsx`,
  `web/src/editor/EditorTab.test.tsx`

- [ ] **Step 1: Write the failing tests:**
  - `InstallEditor` on open calls `ensure` once and shows "2 objek dipindah" from its notes;
  - with pending ops it does not call `ensure`;
  - the Build button no longer asks twice (old test removed or rewritten);
  - AssistPanel with `layer="installation"`: Terima adds the ops to the install store, not the editor store;
  - EditorTab: the Layout mode has no "Library template" aside.
- [ ] **Step 2–4:** Run (FAIL); implement; run the web suite, lint, tsc (PASS).
- [ ] **Step 5:** Commit: `feat(web): Instalasi & Interior holds the Library and filling rooms`.

### Task 6: Web — 2D device editing

**Files:**
- Modify:
  - `web/src/install/InstallWorkspace.tsx`:
    - drop target for Library cards (the same drag payload the layout viewport uses);
    - click-to-select objects;
    - drag-to-move;
    - `R` rotate.
  - `web/src/install/InstallLayer.tsx`: rotated footprints for every object, clickable, selected outline.
  - `web/src/install/InstallPanels.tsx`: Properties for a selected object (x, y, z, rotation, w, d, h →
    `update_object`).
- Test: `web/src/install/InstallWorkspace.test.tsx`, `web/src/install/InstallPanels.test.tsx`

- [ ] **Step 1: Write the failing tests:**
  - a drop of a template payload at (3000, 4000) adds `add_object` with that position and the template dims;
  - click + drag of an object by (500, 0) → `update_object` position +500 x;
  - `R` with one selected object → `rotation + 90`;
  - Properties: changing Z to 1400 → `update_object` z 1400.
- [ ] **Step 2–4:** Run (FAIL); implement; run the web suite, lint, tsc (PASS).
- [ ] **Step 5:** Commit: `feat(web): place, move and rotate devices on the installation canvas`.

### Task 7: Live checks and docs

**Files:**
- Modify:
  - `tests/assist/test_area_strata.py`: the two interior cases run with `layer="installation"` semantics via the
    session's `allowed` set;
  - `README.md` (the editor and installation sections: one equipment mode);
  - `ROADMAP.md` status.

- [ ] **Step 1:** Update the live cases. Run `uv run --env-file .env pytest -q tests/assist/test_area_strata.py -m strata`.
  Expected: PASS.
- [ ] **Step 2:** Docs.
- [ ] **Step 3:** Commit: `docs: one equipment mode; live cases on the installation layer`.
