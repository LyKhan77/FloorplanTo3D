# todo.md — current task

Overwritten at the start of every new task phase (AGENTS.md). History lives in CHANGELOG.md and git.

## Phase: room-by-room extraction from PDF vectors (2026-11-04)

Branch `feat/room-tracing`, based on `feat/pdf-input` (not merged yet). Merge only after the user approves the
improvement.

Goal: the reviewer fixes about 20% of a plan, not most of it.

- [x] Measure the review of Ancol Lt. 2 (v1 vs v8) and the vector spike
- [x] Design, plan, vector walls, door source, room tracer, `room_open`, vector switch in Project baru
- [x] Outside-in structure selection (spec 6.5b)
- [ ] Gates not reached (Ancol recall 0.79, precision 0.80, rooms 2/12, duplicates 0): the path is opt-in
- [ ] User tries the vector path in the editor, final review, merge decision
- [ ] Later: Strata `T5` for ambiguous gaps (own design)

## Queued

- Page picker in a modal (bigger thumbnails, page names)
- Guide line (L) slowness: measure in the browser
- Merge decision for `feat/pdf-input`
