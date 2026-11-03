# todo.md — current task

Overwritten at the start of every new task phase (AGENTS.md). History lives in CHANGELOG.md and git.

## Phase: PDF input (2026-11-03)

Goal: create a project straight from a multi-page CAD PDF (test case: Ancol p13) and run to review without entering a
scale. Spec: `docs/superpowers/specs/2026-11-03-pdf-input-design.md`.

- [x] Brainstorm: inspect the Ancol/Gatsu PDFs, spikes (door-based scale, photo removal, 600 dpi, tray masking),
  baseline run of p13
- [x] Design doc + builder check
- [ ] User approval of the design doc
- [ ] Branch `feat/pdf-input`, commit the spec
- [ ] Implementation plan (writing-plans)
- [ ] Execute: page picker, photo removal, `drawing_bbox`, door-based scale + `door_leaf_width`, tray mask, web

## Next

Debug phase: rooms do not close on Ancol p13 (wall ends stop short of junctions, V004 ~230).
