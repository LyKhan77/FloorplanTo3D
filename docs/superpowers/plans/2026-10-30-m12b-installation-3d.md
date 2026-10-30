# M12b Installation 3D: build, report, viewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** turn a saved installation (traced trays and racks, M12a) into a realistic 3D model:
- perforated trays, hangers or pedestals, and drops to racks;
- ceiling, raised floor, and wall sleeves;
- a GLB, renders, and a report of tray lengths;
- a 3D view in the editor with show/hide layers.

**Architecture:**
- A run of the new kind `installation` reuses stages 7–10 of the orchestrator with installation implementations:
  - 7: build;
  - 8: verify;
  - 9: report;
  - 10: publish to `installation_outputs/v<M>`.
- `core/installation/geometry.py` turns trays, drops, hangers, ceiling, raised floor, and sleeves into the existing
  build_input items (meshes, cutters, instances).
- `core/installation/build.py` assembles one build_input: the layout plus the installation, with installation exports
  and cameras. The Blender builder stays generic; it gains two small features:
  - an image-texture material with alpha clip, for the perforation;
  - box-mapped UVs on meshes that ask for them.
- The web gets a Build button in mode Instalasi, a 3D viewer of the combined GLB with layer toggles, and the
  installation outputs.

**Tech Stack:** Python 3.12, Shapely, Blender 5.2 bpy (builder), Jinja/WeasyPrint, React + @react-three/fiber/drei.

**Spec:** `docs/superpowers/specs/2026-10-30-installation-cable-tray-design.md` (§6.6–§6.9; § numbers below refer to it).
M12a (merged) built §5, §6.1–§6.5.

## Global Constraints

- **Layout outputs** (`outputs/v<N>`, `shell.glb`) never change. The installation writes only `installation_outputs/v<M>/`.
- **Geometry** (mm, same frame as the layout; z = 0 is the finished floor):
  - **Tray:** sheet 1.5 mm. U section = a bottom plate of the tray width + two side plates of `side_height`, mitred at
    corners. Underside at `tray_elevation()` (M12a `core/installation/derive.py`).
  - **Overhead hangers:** every ≤ 1500 mm along each tray, plus one at every corner. Each hanger is two M10 rods
    (10 × 10 mm boxes) from the tray underside up to `ceiling(meta, layout)`, and a trapeze channel 41 × 41 mm,
    `width + 100` long, under the tray.
  - **Underfloor pedestals:** 41 × 41 mm, from the slab (`−raised_floor_height`) up to the tray underside, at the same spacing.
  - **Drop:** a horizontal tray piece from `at` to above the rack centre (when `horizontal > 0`), then a vertical U piece
    (width = `min(tray width, 300)`) down to the rack top (overhead) or up from the tray to the rack base (underfloor).
  - **Ceiling:** a 100 mm slab over the floor outline, underside at `ceiling(meta, layout)`.
  - **Raised floor** (only when `raised_floor_height` is set): panels 30 mm thick at z −30..0 over the floor outline;
    pedestals 41 × 41 mm at a 600 mm grid inside the outline. The layout floor slab moves down by `raised_floor_height`
    in this build only.
  - **Sleeve:** for every tray footprint × wall footprint crossing (I003) of an overhead tray, a cutter on that wall,
    `width + 100` wide across the wall's full thickness + 20 mm, z from `elevation − 50` to `elevation + side_height + 50`.
- **Materials:**
  - `tray_galv` `#B8BCC2`, roughness 0.4, metallic 0.8, perforation texture (slot 7 × 20 mm, pitch 25 mm, alpha clip
    0.5), box-mapped UV at 25 mm per tile;
  - `tray_edge_data` `#33B1FF`, `tray_edge_power` `#FF832B`: a 1.5 mm lip on top of each side plate, so the class reads
    from afar;
  - `hanger` `#7A7F85`, roughness 0.5, metallic 0.6;
  - `ceiling` `#F2F2F2` alpha 0.25;
  - `raised_floor` `#C6C6C6` alpha 0.35.
- **Collections** (builder):
  - `Installation/{TrayData, TrayPower, Hangers, Drops, Racks}`;
  - `Ceiling`;
  - `RaisedFloor`.
- **Object name prefixes** (the viewer toggles layers by them): `tray_data_`, `tray_power_`, `hanger_`, `drop_`,
  `rack_`, `ceiling`, `raised_floor`.
- **Exports:**
  - `installation.glb`: Installation collection only, layout frame;
  - `layout_installation.glb`: everything except Ceiling;
  - `installation.blend`.
- **Renders:**
  - layout top and iso cameras, with the Ceiling collection hidden;
  - an extra `renders/underfloor.png` iso with `RaisedFloor` panels hidden, when a raised floor exists.
  - Engine: setting `BLENDER_INSTALL_ENGINE`, default `BLENDER_EEVEE` (the alpha-clipped perforation shows);
    `BLENDER_WORKBENCH` in the Docker image.
- **Build refusal:** a build is refused (stage 7 fails with the I-codes) while `validate_installation` reports any `error`.
- Copy in Indonesian; code, tests, and commits in English. Blender tests are `@pytest.mark.blender` and run in the user's
  Terminal.

## Review Focus

1. **Tray corners:** a path with a 90° turn gives side plates that meet without gaps or spikes (mitre), and a 30° turn too.
2. **Racks:** a rack of the installation and a rack object of the layout both get drops in 3D; a rack with no drop has
   no drop mesh.
3. **No raised floor:** an installation without one builds no panels, and the layout floor stays at z −150..0.
4. **Re-running a build:** the build for the same installation version replaces `installation_outputs/v<M>` atomically;
   the layout's `outputs/` is untouched.
5. **Errors left:** an installation that still has I001/I002 errors (e.g. rebased onto a layout that broke a tray) is
   refused by POST /build with 409 `installation_invalid`, and the Build button says why.

---

### Task 1: Installation geometry

**Files:**
- Create: `core/installation/geometry.py`
- Test: `tests/installation/test_geometry.py`

**Interfaces:**
- Consumes: `tray_elevation`, `ceiling`, `mounting`, `drops`, `racks` (`core/installation/derive.py`);
  `core/build_prep/mesh.py` (`prism`, `box`, `merge`); `core/build_prep/shell.mesh_item`.
- Produces: `installation_items(inst, layout, templates) -> tuple[list[MeshItem], list[CutterItem]]`.
  - Meshes are named `tray_<class>_<id>`, `drop_<rack>_<tray>`, `hanger_<tray>_<k>`, `ceiling`,
    `raised_floor_panels`, `raised_floor_pedestals`.
  - Each mesh carries `props: {spec_id, spec_type: "tray" | "drop" | "hanger" | "ceiling" | "raised_floor", tray_class?}`,
    the collection from Global Constraints, and `uv_box_mm: 25` for tray and drop plates.
  - Also produces `floor_drop(layout, inst) -> int`: the z shift for layout floor meshes (`−raised_floor_height` or 0).

- [ ] **Step 1: Write the failing tests:**
  - `test_tray_u_section_dimensions`: a 3000 mm straight data tray (width 200, side height 100) at elevation 2600 gives
    one mesh whose bounding box is x 0..3000, y −100..100, z 2600..2700 (plus the 1.5 mm lip), material `tray_galv`.
  - `test_corner_is_mitred` (Review Focus 1): an L path `[(0,0),(3000,0),(3000,3000)]` has a side-plate outline with
    no point farther than `width/2 + 2` from the path.
  - `test_hangers_every_1500_and_at_corners`: a 4000 mm straight tray gets hangers at 0, 1500, 3000, and 4000 (4); the
    L path gets one at the corner. Rods reach z = ceiling.
  - `test_drops_follow_derive` (Review Focus 2): one installation rack and one layout rack, each in range, give two
    `drop_` meshes. The vertical part runs from the rack top (2000) to the tray underside.
  - `test_sleeve_cutter_on_crossed_wall`: a tray crossing W5 of the `spec_with_rooms` fixture gives a cutter with
    target `wall_W5`, spanning z 2550..2750.
  - `test_raised_floor_only_when_set` (Review Focus 3): without a raised floor, no `raised_floor_*` meshes, and
    `floor_drop` is 0. With 600: panels at z −30..0, and `floor_drop` −600.
- [ ] **Step 2:** Run `uv run pytest -q tests/installation/test_geometry.py`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement.
  - Tray: bottom plate = `prism(LineString(path).buffer(w/2, cap_style="flat", join_style="mitre"), z, z+1.5)`.
  - Side plates: the same buffer of each `offset_curve(±(w/2 − 0.75))` at 0.75, from z to z + side_height.
  - Lip: a 1.5 mm cap of the side plates, in the class material.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): 3D geometry of trays, drops, hangers, ceiling, raised floor, sleeves`.

### Task 2: Builder — perforated material and box UVs

**Files:**
- Modify: `core/build_prep/schema.py` (Material gains `metallic?: float`, `texture?: str`; MeshItem gains
  `uv_box_mm?: int`), `builder/scene.py` (`make_materials`, `make_mesh`)
- Create: `core/build_prep/perforation.py` (`write_perforation_png(path) -> Path`: a 50 × 125 px RGBA tile, one 7 × 20
  mm slot per 25 × 25 mm cell at 2 px/mm, transparent slot, opaque metal)
- Test: `tests/build_prep/test_perforation.py`, `tests/builder/test_installation_material.py` (`@pytest.mark.blender`)

**Interfaces:**
- Produces:
  - A material whose dict has `texture: "<abs path>"` gets:
    - an Image Texture node (Closest), colour into Base Color × `color`;
    - its alpha through a Math GREATER_THAN 0.5 into Alpha (glTF exports alphaMode MASK);
    - `surface_render_method = "DITHERED"`.
  - A mesh with `uv_box_mm` gets UVs per face from its dominant normal axis: z → (x, y), x → (y, z), y → (x, z),
    divided by that size in mm.

- [ ] **Step 1: Write the failing tests:**
  - `test_perforation_tile_has_one_transparent_slot`: alpha 0 over 7 × 20 mm × (2 px/mm)², alpha 255 elsewhere.
  - `test_material_texture_exports_mask` (blender): a build of one tray mesh with `tray_galv` exports a GLB whose
    material has `alphaMode == "MASK"` and one image; the mesh has a UV layer (TEXCOORD_0).
- [ ] **Step 2:** Run the non-Blender test. Expected: FAIL. The Blender test is run by the user.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q tests/build_prep`. Expected: PASS. Ask the user to run
  `uv run --env-file .env pytest -q tests/builder -m blender` in their Terminal.
- [ ] **Step 5:** Commit: `feat(builder): image-textured alpha-clip materials and box UVs`.

### Task 3: Installation build input and stage functions

**Files:**
- Create: `core/installation/build.py`
- Test: `tests/installation/test_build.py`

**Interfaces:**
- Consumes: Task 1, Task 2; `core/build_prep/assemble.build_input_for`, `cameras`; `core/pipeline` helpers
  (`run_blender`, `BuildFailed`, `image_size`).
- Produces:
  - `installation_build_input(inst, layout, templates_root, templates, work: Path, engine: str) -> tuple[dict, list[str]]`:
    - the layout doc;
    - floors shifted by `floor_drop`;
    - the installation meshes and cutters;
    - installation racks as instances (from `inst.objects`, like `assemble._instances`, collection `Racks`);
    - the perforation material and PNG written into `work`;
    - exports and cameras per Global Constraints.
  - `install_build(inst, layout, work, image, templates_root, engine, ...) -> tuple[dict, list[str]]`: writes
    `build_input.json` and runs Blender; refuses with `InstallInvalid(issues)` when `validate_installation` has errors.
  - `install_publish(work, root: Path, version: int) -> Path` → `installation_outputs/v<M>`, atomic like `core.pipeline.publish`.
    Files: `installation.glb`, `layout_installation.glb`, `installation.blend`, `installation_report.html`,
    `installation_report.pdf`, `installation.json` (the lengths and drops summary), `renders/`.

- [ ] **Step 1: Write the failing tests** (no Blender: inspect the doc):
  - `test_doc_has_layout_and_installation`: the walls of the layout are present; `tray_data_T1`, a `drop_`, and
    `hanger_` items are present; the exports name `installation.glb` with `["Installation"]`.
  - `test_floor_moves_down_with_raised_floor`: floor meshes' z are shifted by −600.
  - `test_errors_refuse_the_build` (Review Focus 5): an underfloor tray without a raised floor raises `InstallInvalid` naming I002.
  - `test_publish_replaces_atomically` (Review Focus 4): publishing v1 twice leaves one `installation_outputs/v1`, with
    `outputs/` untouched.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/installation`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): build input, build and publish of the installation`.

### Task 4: Run kind `installation`, report, and API

**Files:**
- Modify: `server/orchestrator.py`
  - run kind `installation`: `start_run` takes it, begins at stage 7, and stores `installation_version`;
  - stages 7–10 dispatch to the installation implementations when `run["kind"] == "installation"`;
- Modify: `server/routes/installations.py` (`POST /build`, `GET /outputs`, `GET /outputs/{v}/{path:path}`)
- Create: `core/installation/report.py` and `core/report/templates/installation_report.html.j2`. The report holds:
  - a summary of lengths per class;
  - a tray table (id, class, width, mounting, elevation, length);
  - a rack table (drops data/power, length);
  - racks with no drop;
  - warnings;
  - renders.
- Test: `tests/server/test_installation_build.py`, `tests/installation/test_report.py`

**Interfaces:**
- Produces:
  - `POST /api/projects/{pid}/installations/build {version?: "HEAD" | int}` → 202 `{run_id}`. Errors:
    - 409 `installation_invalid` with the issues (Review Focus 5);
    - 409 `run_in_progress`.
  - `GET /installations/outputs` → `[{version, files}]`. `GET /installations/outputs/{v}/{path}` serves a file (safe join).
  - Stage 8 verify: `verify.json` `{trays: n, glb_ok: bool, lengths, drops}`. `glb_ok` = `installation.glb` exists and
    has one node per tray.

- [ ] **Step 1: Write the failing tests** (fake Blender: `stage_impls` stubs like the existing orchestrator tests):
  - `test_build_runs_stages_7_to_10_and_publishes`: after a fake build, `installation_outputs/v2` has `installation.json`
    with lengths; the run has kind `installation`.
  - `test_build_refused_with_errors`: 409 `installation_invalid`.
  - `test_report_lists_lengths_and_unconnected_racks`: the HTML holds the lengths in metres (1 decimal), and the I006
    rack ids.
  - `test_outputs_listing_and_safe_path`: listing shows v2; `../` is refused.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/server tests/installation -m "not blender"`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(installation): build runs, report and outputs API`.

### Task 5: Web — build, 3D viewer, outputs

**Files:**
- Create: `web/src/install/InstallViewer.tsx` (Canvas + `useGLTF(url)` + OrbitControls; layer checkboxes
  `Tray data, Tray power, Hanger, Drop, Rack, Plafon, Raised floor`, toggling `object.visible` by name prefix;
  Plafon off by default), `web/src/install/InstallOutputs.tsx` (download links of the latest installation output)
- Modify:
  - `web/src/install/InstallEditor.tsx`:
    - a `2D | 3D` switch; 3D shows `InstallViewer` with the latest output's `layout_installation.glb`, or "Belum ada
      build" when there is none;
    - a **Build 3D** button (disabled with unsaved ops, or while a run is active), with the 409 issues shown in the
      Masalah panel;
    - a progress bar from the project run events.
  - `web/src/components/RunPicker.tsx` (kind label "Instalasi");
  - `web/src/components/OutputsTab.tsx`, or the outputs page component: an "Instalasi" section;
  - `README.md`, `ROADMAP.md`.
- Test: `web/src/install/InstallViewer.test.tsx`, `web/src/install/InstallEditor.test.tsx` (build button), `web/src/components/RunPicker.test.tsx`

**Interfaces:**
- Consumes: Task 4 endpoints; `useProjectEvents`/`useRegenerateFlow` patterns for progress.
- Produces: `layerOf(name: string) -> Layer | null` (exported pure helper, tested).

- [ ] **Step 1: Write the failing tests:**
  - `layerOf('tray_power_T6') === 'Tray power'`, `layerOf('raised_floor_panels') === 'Raised floor'`, `layerOf('wall_W1') === null`.
  - The Build button is disabled while ops are pending, and posts `/installations/build` otherwise.
  - A 409 `installation_invalid` lists its issues.
  - The 3D tab says "Belum ada build" without outputs.
  - RunPicker shows "Instalasi" for kind `installation`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the web suite, lint, and `tsc -b`. Expected: PASS, exit 0.
- [ ] **Step 5:** Commit: `feat(web): build the installation in 3D and view it with layers`.

---

After Task 5: the final review, then the user tests in a browser and runs the Blender tests in their Terminal. No merge
until the user says the feature works.
