# todo.md — current task

Overwritten at the start of every new task phase (AGENTS.md). History lives in CHANGELOG.md and git.

## Phase: PDF input (2026-11-03)

Goal: create a project straight from a multi-page CAD PDF (test case: Ancol p13) and run to review without entering a
scale. Spec: `docs/superpowers/specs/2026-11-03-pdf-input-design.md`. Branch: `feat/pdf-input`.

- [x] Brainstorm, design doc, builder check, plan
- [x] Photos removed from vector PDF pages
- [x] `drawing_bbox` skips the sheet frame, spans every building block
- [x] Scale from door swings; `door_leaf_width` (default 800 mm) always wins when set
- [x] Cable-tray ladders masked in stage 3
- [x] PDF resolution: stays 300 dpi (`benchmarks/DECISIONS.md`)
- [x] `POST /api/pdf/pages` + page picker; "Lebar pintu standar (mm)" replaces mm/px in the UI
- [x] End-to-end on the API: Ancol p13 reaches review (door estimate 31.7 mm/px); Gatsu keeps grid dimensions
- [ ] Final branch review
- [ ] User approval to merge; CHANGELOG entry after the user confirms

## Next

Debug phase: rooms do not close on Ancol p13 (wall ends stop short of junctions, V004 ~230; 1 room at review).
Equipment boxes (racks) still read as columns on p13 (~115 in the chosen candidate at 300 dpi).
