# Generate Interior (v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In tool `A` the user marks a room (or clicks drawn boxes); Strata asks what equipment and how much, then a
deterministic engine places library templates by TIA-942/ASHRAE rules (or on the pointed drawn boxes), previewed and
accepted as `add_object` ops.

**Architecture:**
- New package `core/interior/`:
  - `rules.yaml` + `rules.py`: the calibration profile;
  - `library.py`: template facts from the registry;
  - `space.py`: the room's free space, doors and walls;
  - `rows.py` / `lineup.py`: the two layout algorithms;
  - `devices.py`: wall devices, fire cylinders, containment;
  - `drawn.py`: objects from pointed boxes;
  - `check.py`: O001–O003.
- Area assist gains two plan actions (`fill_room`, `place_drawn`) that translate into `add_object` ops through this
  package.
- The web adds drawn-box clicks (`Kn`) and object previews to tool `A`.

**Tech Stack:** Python 3.12, Shapely, PyYAML, FastAPI; React, Zustand, Vitest. Strata via `core/llm_review/client.py`.

**Spec:** `docs/superpowers/specs/2026-11-03-generate-interior-design.md` (§ numbers below refer to it). Branch
`generate-interior` (on top of `lowpoly-assets`: 16 templates at version 1.1.0).

## Global Constraints

- **Strata picks templates and counts, never coordinates.** All positions come from the engine or from the drawing.
- **Object convention:** pivot bottom-centre; rotation θ in degrees, counter-clockwise about +Z. The front is
  `(-sin θ, cos θ)`, so θ = 0 faces +y and θ = −90 faces +x. Floor objects have z = 0.
- **Rules defaults (`core/interior/rules.yaml`):**
  - aisles and grid: `cold_aisle_mm` 1200, `hot_aisle_mm` 1000, `grid_mm` 600;
  - clearances: `row_end_clear_mm` 1200, `wall_clear_mm` 1000, `door_clear_mm` 1200, `electrical_front_mm` 1000;
  - rows: `max_row_len` 12, `inrow_per_racks` 4, `pdu_per_row` 1;
  - wall devices: `fm200_z_mm` 1400, `reader_z_mm` 1100, `cctv_below_ceiling_mm` 300,
    `wall_mounted: [fire-control-panel, cctv-camera-bullet, access-reader-generic]`;
  - fire: `fire_cylinder_per_m2` 50.
- **Template clearance** from `template.json` wins when larger than the rule value (racks: front 1200, back 1000).
- **Layout choice:** `fill_room.layout`, else inferred:
  - any `rack`/`network` category or an in-row cooler → `rows`;
  - only `power`/`battery` → `lineup`.

  Room types are never changed.
- **Over target:** place the capacity and add a note. This is not an error and starts no revision.
- **Validation:** O001 overlap (error), O002 clearance (warning), O003 door zone (warning). These run on the proposal
  only; `core/spec/validate.validate` stays unchanged.
- **Drawn boxes:**
  - a box ≥ 1.5 × the template width along its long side is a row of `round(long / width)` objects;
  - the drawn-box snap allows a long side up to 20 000 mm;
  - the Rack tool keeps 300–3000 mm.
- **Unknown or unmatched:** a box that matches no template is skipped. An unknown template id is a revision problem.
- **Copy:** UI and chat in Indonesian; the system prompt in English.

## Review Focus

1. **Door inside a row path:** a hall whose door opens onto where a row would run. No rack, PDU or containment may stand
   in the door zone (O003 none), and rows are cut around it.
2. **Columns in a data hall:** racks never overlap a column. The row is split, never moved through it.
3. **Odd-shaped room (L shape):** every placed footprint lies inside the room polygon (V016 none, O001 none).
4. **Target larger than capacity:** a valid proposal with the capacity and a note "muat N dari M rack".
5. **Existing objects in the room:** new placements avoid objects already in the spec, and their clearance.

---

### Task 1: Rules profile and template library facts

**Files:**
- Create:
  - `core/interior/__init__.py`;
  - `core/interior/rules.yaml` (the defaults above);
  - `core/interior/rules.py`;
  - `core/interior/library.py`.
- Test: `tests/interior/__init__.py`, `tests/interior/test_rules_library.py`

**Interfaces:**
- Produces:
  - `Rules` (frozen dataclass): one field per key above, plus `wall_mounted: tuple[str, ...]`.
    `load_rules(path: Path | None = None) -> Rules`; `None` means the packaged `rules.yaml`. Unknown keys raise
    `ValueError`.
  - `Tpl` (frozen dataclass): `id`, `version`, `category`, `w`, `d`, `h`, `front_clear`, `back_clear`,
    `resizable: dict[str, tuple[int, int] | None]`.
  - `load_library(templates_dir: Path) -> dict[str, Tpl]`: the newest valid version per id, as `/api/templates` lists
    them; reuse `server/routes/templates._semver` logic by moving it to `core/templates/registry.newest_versions`.
  - `layout_kind(items: list[str], lib) -> Literal["rows", "lineup"]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_defaults_load`: `load_rules().cold_aisle_mm == 1200` and `"cctv-camera-bullet" in load_rules().wall_mounted`.
  - `test_unknown_key_rejected`: a yaml with `colde_aisle_mm` raises `ValueError`.
  - `test_library_newest_version`: a tmp registry with `rack-x` at 1.0.0 and 1.1.0 gives version `1.1.0` with
    `front_clear` 1200.
  - `test_layout_kind`:
    - `["rack-42u-600x1200", "pdu-floor-generic"]` → `rows`;
    - `["ups-cabinet-generic", "battery-rack-generic"]` → `lineup`;
    - `["network-rack-2post"]` → `rows`.
- [ ] **Step 2:** Run `uv run pytest -q tests/interior/test_rules_library.py`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it again, plus `tests/server/test_templates*.py` if `_semver` moved. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(interior): rules profile and template library facts`.

### Task 2: Room space and the rows engine (data hall)

**Files:**
- Create: `core/interior/space.py`, `core/interior/rows.py`, `core/interior/layout.py`
- Test: `tests/interior/test_rows.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `Placement` (dataclass) in `layout.py`:
    - `template_id`, `version`;
    - `x`, `y`, `z`, `rotation`;
    - `dims: tuple[float, float, float]`;
    - `source: Literal["rules", "drawing"]`.

    Plus `footprint() -> Polygon` and `zones(lib, rules) -> list[Polygon]` (front/back clearance rectangles).
  - `Layout` (dataclass): `placements`, `capacity: dict[str, int]` (template → max that fits), `notes: list[str]`.
  - `Space` (dataclass): `room: Polygon`, `blocked: list[Polygon]` (columns, existing objects with their zones, door
    zones), `doors: list[Door]`, `walls: list[LineString]` (room boundary edges), `ceiling: float`.
    `room_space(spec, room_id, box_polygon | None, ceiling) -> Space`.
    - The area is room ∩ box when a box is given.
    - A door zone is a rectangle `width × (width + door_clear_mm)` on both sides of the wall at the opening (doors
      only).
  - `layout_rows(space, lib, items: dict[str, int | None], options: dict, rules) -> Layout`. `options` holds
    `containment: bool`, `cooling: "crac" | "inrow" | None`, `rows: "auto" | "ns" | "ew"`.

- [ ] **Step 1: Write the failing tests** on synthetic rooms (a `Spec` with 4 walls, one 900 mm door, rooms rebuilt):
  - `test_hall_rows_face_the_cold_aisle`: hall 10 × 8 m, door on the south wall, items `{rack-42u: None}`.
    - Racks come in row pairs.
    - The fronts of a pair point at each other (front vectors opposite, centres 1200 + 1200 mm apart across the aisle,
      i.e. cold aisle 1200).
    - Back-to-back rows are 1000 mm apart (hot aisle).
  - `test_capacity_hand_count`: the same hall gives `capacity["rack-42u-600x1200"]` equal to the hand count in the test
    docstring (compute it in the test from the rules: rows per module and racks per row).
  - `test_target_smaller_fills_from_the_door`: target 6 → 6 racks; the mean distance to the door is less than for the
    unused capacity slots.
  - `test_target_larger_notes_capacity` (Review Focus 4): target 999 → `placements` = capacity and a note containing
    `"muat"`.
  - `test_door_zone_kept_clear` (Review Focus 1): no footprint intersects any door zone.
  - `test_column_splits_a_row` (Review Focus 2): a 600 × 600 column in a row line → no footprint intersects it.
  - `test_l_shaped_room` (Review Focus 3): every footprint is within the room polygon.
  - `test_existing_objects_avoided` (Review Focus 5): an existing CRAC in the room → no footprint intersects it or its
    front zone.
  - `test_inrow_and_pdu`: `cooling: inrow` → one `inrow-cooler-300x1200` after every 4 racks in a row. `pdu-floor-generic`
    in items → one per row at the end nearest the door.
- [ ] **Step 2:** Run `uv run pytest -q tests/interior/test_rows.py`. Expected: FAIL.
- [ ] **Step 3: Implement `layout_rows`.** The algorithm is fixed here; the code is the implementer's:
  1. For each orientation (rows along x, rows along y; `options.rows` may fix one): the cross axis is the other one.
  2. Walk the cross axis from the room's min edge:
     - back clearance (template back, ≥ `wall_clear_mm`);
     - row A (rack depth), then the cold aisle, then row B, then the hot aisle;
     - repeat while a pair plus back clearance fits;
     - a last single row fits with front clearance + back clearance.
  3. Try cross offsets in 100 mm steps over one module; keep the best.
  4. Along each row line:
     - slots on `grid_mm` from the room min corner;
     - a slot is valid when the footprint is inside the room, outside `blocked`, and its front/back zones are inside the
       room and outside `blocked`;
     - consecutive valid slots form row runs;
     - cut runs longer than `max_row_len` with a gap of `row_end_clear_mm`;
     - keep `row_end_clear_mm` from the room edge at both run ends.
  5. The run sequence is `[PDU] + racks`, with an in-row cooler after every `inrow_per_racks` racks when
     `cooling == "inrow"`. The sequence uses each template's own width.
  6. Score is the rack count (capped by the target), then fewer runs. Fill the target from runs ordered by distance to
     the nearest door.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(interior): room space and the hot/cold-aisle rows engine`.

### Task 3: Line-up engine, wall devices, CRAC and containment

**Files:**
- Create: `core/interior/lineup.py`, `core/interior/devices.py`
- Modify: `core/interior/layout.py` (`fill(space, lib, items, options, layout_kind, rules) -> Layout` dispatching rows or
  line-up, then devices)
- Test: `tests/interior/test_lineup_devices.py`

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - `layout_lineup(space, lib, items, rules) -> Layout`;
  - `add_devices(layout, space, lib, items, options, rules, rows_meta) -> Layout`;
  - `fill(...)` as above, the only entry point the assist uses.

- [ ] **Step 1: Write the failing tests:**
  - `test_lineup_on_the_longest_free_wall`: a UPS room 6 × 4 m with the door on the short wall, items `{ups: 1, ats: 1,
    mdb: 1}`.
    - All three backs touch the longest door-free wall.
    - Each front zone is `electrical_front_mm` deep and free.
    - The order follows the items order.
  - `test_battery_rows_with_aisles`: battery racks fill rows parallel to the line-up wall with 1000 mm aisles; no O001.
  - `test_crac_on_end_walls`: `cooling: crac`, CRAC count 2.
    - Both stand against walls perpendicular to the rows, facing into the room.
    - `row_end_clear_mm` lies between each CRAC front and the row ends.
  - `test_containment_over_cold_aisles`: `containment: true` →
    - roof modules (`containment-roof-600`) cover each cold aisle span at z = rack height;
    - one `containment-door-1200` at each aisle end, rotated across the aisle.
  - `test_wall_devices`:
    - the FM-200 panel is within 600 mm of the main door jamb at z 1400;
    - the reader is on the other side at z 1100;
    - the CCTV is at z = ceiling − 300 − h in a corner, facing the room centroid (±45°);
    - wall devices touch a wall face and do not intersect a wall footprint (V017 none).
  - `test_fire_cylinders_by_area`: 50 m² → 1, 120 m² → 3, placed against walls clear of door zones.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. CRAC reserves `crac_d + row_end_clear_mm` at the chosen end(s) before Task 2's row walk
  (pass the reduced band into `layout_rows`).
- [ ] **Step 4:** Run `tests/interior`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(interior): line-up rooms, CRAC, containment and wall devices`.

### Task 4: Drawn boxes pointed by the user

**Files:**
- Modify:
  - `core/installation/snap.py`: `snap_box(..., max_mm=BOX_MAX_MM)`, `fit_box(..., max_mm=BOX_MAX_MM)`, threaded into
    `_box`/`_dark_box`;
  - `server/routes/assist.py`: `POST /api/projects/{pid}/assist/drawn-box {at} | {a, b}` →
    `{center, size: [short, long], rotation}` with `max_mm=20000`, 404 `no_run` without a run, 422 `no_box`.
- Create: `core/interior/drawn.py`
- Test: `tests/interior/test_drawn.py`, `tests/server/test_assist.py` (one case)

**Interfaces:**
- Produces:
  - `DrawnBox` (TypedDict): `id: "K1"`, `center`, `size: [short, long]`, `rotation: 0 | 90`.
  - `place_drawn(boxes: list[DrawnBox], tpl: Tpl, space: Space | None, rules) -> tuple[list[Placement], list[str]]`
    returns placements and notes.
    - A box that is not row-like and not within ±15% of the template footprint keeps the template size at the box
      centre, with a note.
    - Resizable axes take the box size.
    - Front: the long side faces the side with more free room inside the space (sampled 1500 mm out). A tie keeps
      θ = 0 and adds a note "arah depan K1 belum pasti".

- [ ] **Step 1: Write the failing tests:**
  - `test_one_box_one_object`: a 620 × 1160 box with `rack-42u` → 1 placement at the box centre, `source="drawing"`.
  - `test_row_box_splits`: a 600 × 4800 box → 8 racks along the long side, centres 600 apart.
  - `test_front_faces_the_open_side`: a box against the west wall → front points east (θ = −90).
  - `test_snap_box_allows_a_row_when_asked`: synthetic image with a 600 × 4800 mm outlined box →
    - `snap_box(..., max_mm=20000)` finds it;
    - the default `snap_box` returns None.
  - server: `test_drawn_box_endpoint` without a run → 404 `no_run`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/interior tests/installation tests/server/test_assist.py`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(interior): place templates on boxes the user points at in the drawing`.

### Task 5: Proposal checks O001–O003

**Files:**
- Create: `core/interior/check.py`
- Test: `tests/interior/test_check.py`

**Interfaces:**
- Produces: `check(placements: list[Placement], space: Space, lib, rules) -> list[dict]`, each
  `{code, severity, message, index}`.
  - **O001 (error):** two footprints intersect (area > 1 mm²) and their z ranges overlap. Containment roofs sit at rack
    height, so they pass.
  - **O002 (warning):** a placement's front/back zone intersects another footprint or leaves the room polygon (wall
    devices exempt).
  - **O003 (warning):** a footprint intersects a door zone.

- [ ] **Step 1: Write the failing tests:**
  - two overlapping racks → O001;
  - a roof over two racks → no O001;
  - a rack facing a wall 500 mm away → O002;
  - a rack in a door zone → O003;
  - a clean `fill` result from Task 2's hall → `[]`.
- [ ] **Step 2–4:** Run → FAIL; implement; run → PASS.
- [ ] **Step 5:** Commit: `feat(interior): overlap, clearance and door checks for proposals`.

### Task 6: Assist integration (plan actions, context, session, prompt, API)

**Files:**
- Modify:
  - `core/assist/plan.py`:
    - actions `FillRoom {type, room, layout, items: [{template, count}], options}` and
      `PlaceDrawn {type, boxes: [str], template}`;
    - `translate(..., library=None, drawn=None, rules=None)`;
    - `Translation.objects: list[dict]` (preview).
  - `core/assist/context.py`:
    - the library list (`id, category, w×d×h`) in the text;
    - drawn boxes `Kn` (centre, size) in the text;
    - the room type in the rooms list.
  - `core/assist/session.py`:
    - `run_turn(..., templates_dir=None, drawn=None, ceiling=None)`;
    - O001 joins the problems (revision);
    - O002/O003 go to issues;
    - the summary lists objects.
  - `core/llm_review/prompts/AF/v1.md`:
    - the two actions;
    - the §6.1 default table;
    - the rule "for 'isi ruang' without a list, ASK with the default proposal first";
    - templates only from the list.
  - `server/routes/assist.py`:
    - body `drawn: [DrawnBox]`;
    - pass `storage.templates_dir` and the ceiling (installation `ceiling_height`, else `defaults.wall_height`).
- Test: `tests/assist/test_plan.py`, `tests/assist/test_session.py`, `tests/server/test_assist.py`

**Interfaces:**
- Consumes: Tasks 1–5 (`fill`, `place_drawn`, `check`, `load_library`, `load_rules`, `room_space`).
- Produces:
  - op `{"op": "add_object", "template_id", "template_version", "position": [x, y, z], "rotation", "dims": [w, d, h]}`;
  - proposal field `objects: [{template_id, corners: [[x, y] × 4], front: [[x, y], [x, y]], zones: [[[x, y], ...]],
    snapped: bool}]`.

- [ ] **Step 1: Write the failing tests:**
  - plan:
    - `test_fill_room_emits_add_objects`: R1 of `spec_with_rooms` with `{rack-42u: 4}` → 4 `add_object` ops with
      version `1.1.0` (tmp library fixture) and `objects[i].snapped is False`;
    - `test_unknown_template_rejected`;
    - `test_place_drawn_uses_the_box`.
  - session:
    - `test_fill_question_first` (fake client returns a question for "isi ruang ini") → `question` event;
    - `test_o001_triggers_revision`: a fake plan whose two `place_drawn` overlap → 2 calls.
  - server: `test_drawn_boxes_reach_the_context`: the body with `drawn` → the fake client's text holds `K1`.
- [ ] **Step 2:** Run `tests/assist tests/server/test_assist.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS (and the existing assist tests still pass).
- [ ] **Step 5:** Commit: `feat(assist): fill a room and place pointed boxes through the interior engine`.

### Task 7: Web — drawn boxes, object preview, objects on the 2D canvas

**Files:**
- Modify:
  - `web/src/editor/assist/store.ts`: `drawn: DrawnBox[]`, `addDrawn`, cleared by `close()`, sent in the body;
  - `web/src/editor/assist/stream.ts`: the `Proposal.objects` type, the `drawn` body field, `drawnBox(pid, at | a,b)`;
  - `web/src/editor/review/ReviewWorkspace.tsx`: in tool `A`,
    - a click (drag < 300 mm) calls `drawnBox` and adds `K{n}`;
    - Shift-drag calls `drawnBox` with `a, b`;
    - a plain drag stays the area box;
  - `web/src/editor/assist/ProposalLayer.tsx`:
    - `Kn` outlines with labels;
    - object footprints (yellow rules / green drawing) with a front arrow and thin hatched zones;
  - `web/src/editor/review/ReviewCanvas.tsx`: existing `view.objects` footprints in grey (rotated rectangles).
- Test: `web/src/editor/assist/AssistPanel.test.tsx`, `web/src/editor/review/ReviewWorkspace.test.tsx`

- [ ] **Step 1: Write the failing tests:**
  - `ReviewWorkspace`: with tool A, a click → mocked `drawnBox` resolves → store `drawn` = `[{id: 'K1', ...}]` and the
    canvas shows text `K1`.
  - `AssistPanel`: Terima on a proposal with two `add_object` ops adds both to the editor ops.
  - `ReviewCanvas`: an object in `view.objects` renders one polygon with `data-object` id.
- [ ] **Step 2:** Run `cd web && npx vitest run src/editor`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the web suite, `npm run lint`, `npx tsc -b`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(web): drawn boxes and equipment previews in Perbaiki area`.

### Task 8: Live Strata cases and docs

**Files:**
- Modify: `tests/assist/test_area_strata.py`, `README.md` (the "Isi ruang" item), `ROADMAP.md` (status)

- [ ] **Step 1:** Add `@pytest.mark.strata` cases on Gatsu:
  - "isi ruang ini dengan rack" on the R. MEETING box → a `question`. Answer "16 rack 42U, containment, in-row
    cooler" → a valid proposal with racks + in-row coolers + containment, no O001.
  - Battery Room with `drawn` K1 = the "PANEL 3" box (from `snap_box` at its centre) and "K1 itu panel MDB" → one
    `panel-mdb-generic` at the box centre.
- [ ] **Step 2:** Run `uv run --env-file .env pytest -q tests/assist/test_area_strata.py -m strata` twice. Expected:
  PASS.
- [ ] **Step 3:** Update the README and ROADMAP.
- [ ] **Step 4:** Commit: `test(interior): live Strata cases; docs for filling a room`.
