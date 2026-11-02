# Area fix with a prompt (layout, v1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the 2D review canvas, the user marks an area and writes an instruction. Strata either asks back or
proposes a fix. The fix is translated into ops by deterministic tools, validated (one revision round), and streamed to a
chat panel. The user accepts it (the ops become pending edits) or rejects it.

**Architecture:**
- `core/assist/` holds four modules:
  - `context.py`: the area context;
  - `plan.py`: the plan schema and its translation into spec ops;
  - `session.py`: one conversation turn, a generator of events, with the revision round, the question limit and the log;
  - `prompts/AF/v1.md`.
- `server/routes/assist.py` streams a turn as Server-Sent Events.
- Room type and name ride on two new point-based ops that `core/spec/ops.apply` runs after the room rebuild (the user's
  option b).
- The web gets the `A` tool, a chat panel, and a proposal preview over the review canvas.

**Tech Stack:** Python 3.12, pydantic, Shapely, OpenCV, FastAPI (StreamingResponse), Strata client; React, Zustand, Carbon, Vitest.

**Spec:** `docs/superpowers/specs/2026-11-02-area-fix-prompt-design.md` (§ numbers below refer to it). Branch `area-assist`.

## Global Constraints

- **Scope:** layout only (walls, openings, rooms) in the review canvas. No installation actions and no door add in this
  version (§2, §9).
- **Plan actions:** `delete_wall`, `merge_walls`, `add_wall`, `delete_opening`, `set_room_type`, `rename_room`. ID
  references are allowed only to elements listed in the area context.
- **Limits:**
  - at most 3 questions per session;
  - at most 1 revision round per proposal;
  - Strata call timeout 120 s, `effort="medium"`, `temperature=0`.
- **Merge rule:** collinear and touching → existing op `merge_walls`. Parallel (≤ 3°) and apart ≤ max thickness +
  100 mm → delete them all and add one wall on the midline over the union span, at the max thickness, snapped. Anything
  else → rejected.
- **New walls** go through `core/extraction/snap.snap_wall` on the newest run's `bin.png` (frame of `grid.json`
  `px_to_mm`). Unsnapped → kept as drawn at HEAD's default thickness and flagged `snapped: false`.
- **Op order:** deletes → merges → adds → room point ops.
- **Delete reasons:** `"asisten: " + instruction[:60]`.
- **Accept** adds the ops to the editor's pending ops as one undo step. It never saves.
- **Text:** LLM-visible system prompt in English; `explanation` and `question` in Indonesian; UI copy in Indonesian.
- **Strata down or timeout:** an event `error` with "Strata tidak tersedia, coba lagi atau perbaiki manual"; nothing
  else changes.
- **Session log:** every turn is logged to `data/projects/<id>/assist/<session_id>.json`.

## Review Focus

1. **"Ini" with a selection:** "hapus dinding ini" with one wall selected goes straight to a `delete_wall` of that wall;
   with nothing selected and several walls in the area, the LLM asks.
2. **Stale proposal:** the user edits the plan by hand after a proposal arrives. Accept then refuses with "usulan usang,
   kirim ulang" instead of applying ops against a changed base.
3. **ID outside the area:** a plan naming an ID that is not in the area is not applied; it goes to the revision round,
   and if still wrong, the proposal shows as invalid with Terima disabled.
4. **No extraction run** (imported spec): no image and no snapping. The chat says so; added walls are flagged unsnapped.
5. **Question limit:** a fourth question in one session is turned into an error message asking the user to be more
   specific; no loop.

---

### Task 1: Point-based room ops

**Files:**
- Modify:
  - `core/spec/ops.py`: ops `SetRoomTypeAt {op: "set_room_type_at", at: Point, type: RoomType}` and
    `RenameRoomAt {op: "rename_room_at", at: Point, name: str}`. `apply()` defers them until after
    `rebuild_rooms`/`derive`, then applies each to the room whose polygon covers `at` (holes excluded).
    Unmatched → `OpError(index, op, "tidak ada ruang di titik ini")`.
  - `web/src/editor/ops/reducer.ts`: same ops, applied to the room covering `at` in the current rooms (the client does
    not rebuild rooms; the server dry run returns rebuilt rooms).
  - `web/src/editor/ops/compose.ts`: `targetIds` returns none for them.
  - Regenerate the schemas (`uv run python -m core.spec.export_schema`, `cd web && npm run gen:types`).
  - Add one case of each to `tests/test_editor_parity.py` and regenerate the fixture with `UPDATE_PARITY=1`.
- Test: `tests/spec/test_ops.py`, `web/src/editor/ops/reducer.test.ts` (or the existing reducer test file)

**Interfaces:**
- Produces: op dicts `{"op": "set_room_type_at", "at": [x, y], "type": "stair"}` and
  `{"op": "rename_room_at", "at": [x, y], "name": "Tangga"}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_room_type_at_applies_after_rebuild`: on `spec_with_rooms()`, `[delete_wall W5, set_room_type_at at=(2500, 3000)
    type="stair"]` gives the merged room type `stair`. Without the delete, it sets R1.
  - `test_room_op_at_outside_every_room_fails`: `at=(-5000, -5000)` raises `OpError` with index 0.
  - The reducer test: `set_room_type_at` sets the covering room; the parity test passes after regeneration.
- [ ] **Step 2:** Run `uv run pytest -q tests/spec/test_ops.py` and `cd web && npx vitest run src/editor/ops`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/spec`, `tests/test_editor_parity.py`, and the web `src/editor`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(spec): set room type and name at a point, after the room rebuild`.

### Task 2: Area context

**Files:**
- Create: `core/assist/__init__.py`, `core/assist/context.py`
- Test: `tests/assist/__init__.py`, `tests/assist/test_context.py`

**Interfaces:**
- Produces:
  - `AreaContext` dataclass:
    - `box: tuple[float, float, float, float]` (mm);
    - `wall_ids`, `opening_ids`, `room_ids: list[str]`;
    - `selection: list[str]`;
    - `text: str` (the element list for the prompt);
    - `image: np.ndarray | None`.
  - `area_context(spec: Spec, box, selection: list[str], page: np.ndarray | None, px_to_mm: list[float] | None) -> AreaContext`:
    - walls intersecting the box (`id, a, b, thickness, length, kind`, plus their openings `id, category, offset, width`);
    - rooms whose polygon intersects the box (`id, name, type, area_m2, rep_point`);
    - stairs and columns inside (id and position only);
    - the selected IDs called out ("elemen yang dimaksud user (terpilih): W12"). Selected walls count as in the area
      even if outside the box.
  - **Image:** crop of `page` at box + 15% margin, longest side 900 px. Walls are drawn 2 px in alternating colours
    with an ID label at the midpoint; selected walls 4 px. `None` without a page.

- [ ] **Step 1: Write the failing tests** on `spec_with_rooms()`:
  - `test_walls_and_rooms_in_box`: box `(4000, 1000, 6000, 5000)` lists W5 and rooms R1 and R2; it excludes W2.
  - `test_selection_is_called_out_and_included`: selecting W2 with the same box puts W2 in `wall_ids` and "terpilih: W2" in `text`.
  - `test_image_has_the_box_and_labels`: a white 600 × 1000 page with `px_to_mm=[10, 0, 0, 0, -10, 6000]` gives an
    image whose longest side is ≤ 900 and which holds red-or-blue pixels (walls drawn). `page=None` gives `image is None`.
- [ ] **Step 2:** Run `uv run pytest -q tests/assist/test_context.py`. Expected: FAIL.
- [ ] **Step 3:** Implement. Reuse `core/extraction/rooms/overlay.px_from_mm`.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(assist): area context — elements, selection, labelled crop`.

### Task 3: Plan schema and translation into ops

**Files:**
- Create: `core/assist/plan.py`
- Test: `tests/assist/test_plan.py`

**Interfaces:**
- Consumes: `AreaContext` (Task 2); `snap_wall` (`core/extraction/snap.py`); the Task 1 ops.
- Produces:
  - `AreaPlan` (pydantic): `question: str | None`, `actions: list[Action]`, `explanation: str`. `Action` is
    discriminated on `type` with the six action shapes of §6.2.
  - `Translation` dataclass:
    - `ops: list[dict]`;
    - `deleted: list[str]`;
    - `added: list[dict]` (`{a, b, thickness, snapped}`);
    - `notes: list[str]` (Indonesian, shown in chat);
    - `rejected: list[str]` (problems for the revision round).
  - `translate(plan: AreaPlan, spec: Spec, ctx: AreaContext, instruction: str, binary: np.ndarray | None, px_to_mm: list | None) -> Translation`.
    It applies the rules in Global Constraints. A room action uses that room's representative point. When a room is
    deleted by the change, it uses the area centre and adds a note.

- [ ] **Step 1: Write the failing tests:**
  - `test_delete_and_reason`: `delete_wall W5` → op with reason `"asisten: <instruction[:60]>"`.
  - `test_unknown_id_is_rejected`: `delete_wall W99` → no op; `rejected` names W99 (Review Focus 3).
  - `test_parallel_merge_becomes_one_midline_wall`: two parallel walls 120 mm apart, 2000 and 1500 mm long and
    overlapping, merge into deletes of both plus one `add_wall` on the midline over the union span at the max
    thickness; `added[0]["snapped"]` is False with `binary=None`.
  - `test_far_or_skewed_merge_is_rejected`: 600 mm apart or 20° apart → rejected.
  - `test_collinear_merge_uses_merge_walls`: two touching collinear walls → one `merge_walls` op.
  - `test_add_wall_snaps_to_the_drawing`: on the Gatsu page fixture (`preprocess(plan.jpeg)` and the GT `px_to_mm`
    halved), a rough line near a GT wall snaps within 60 mm of it (`snapped: True`). The same line on a blank image →
    `snapped: False` at HEAD's default thickness.
  - `test_order_and_room_ops`: the ops come out ordered deletes, merges, adds, `set_room_type_at`; the room op's `at`
    lies inside the named room.
- [ ] **Step 2:** Run `uv run pytest -q tests/assist/test_plan.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(assist): plan schema and its deterministic translation into ops`.

### Task 4: Session turn (LLM, validation, revision, log)

**Files:**
- Create:
  - `core/assist/session.py`;
  - `core/llm_review/prompts/AF/v1.md`: the system prompt of §6.7, with the JSON schema of §6.2 and the rule "if
    instruction is ambiguous or 'ini/this' has no selection and several candidates, set question".
- Test: `tests/assist/test_session.py`

**Interfaces:**
- Consumes: Tasks 1–3; `StrataClient.ask_json`; `core.spec.ops.apply`; `core.spec.validate.validate`.
- Produces:
  - `Session` dataclass: `id`, `project_id`, `box`, `selection`, `messages: list[dict]`, `questions: int`,
    `proposals: list[dict]`, `decisions: list[dict]`.
  - `run_turn(client, session: Session, message: str, base: Spec, ops: list[dict], page, binary, px_to_mm, log_dir: Path) -> Iterator[dict]`.
    It yields event dicts `{"event": "step" | "question" | "proposal" | "error" | "done", ...}`:
    - **`step`:** at least "membaca N dinding dan M ruang di area…" and "menunggu Strata…".
    - **`question`:** when the plan has a question and `questions < 3`. A fourth question becomes `error`.
    - **`proposal`:** `{ops, deleted, added, explanation, notes, issues, valid}`.
      - Validation applies `ops` + the translated ops on `base` and compares error issues with `base` + `ops` alone.
      - New errors, an `OpError`, or `rejected` trigger ONE revision. The LLM gets its plan and the problems.
      - `valid` = no new errors after the revision.
    - **`error`:** Strata unavailable, an invalid answer, or the question limit.
  - The session JSON is written to `log_dir/<id>.json` after every turn.

- [ ] **Step 1: Write the failing tests** with a fake client (an object with `ask_json` returning queued
  `JsonAnswer`-like results):
  - `test_question_then_proposal`: the first answer is a question, so a `question` event; then the user replies and a
    plan answer gives a `proposal` with `valid: True`; the log has both turns.
  - `test_invalid_plan_gets_one_revision`: the first plan names W99 and the second is valid. The fake client sees 2
    calls; the second user message lists "W99".
  - `test_still_invalid_after_revision`: both plans are bad → `proposal` with `valid: False`.
  - `test_fourth_question_is_an_error` (Review Focus 5).
  - `test_strata_down_is_an_error_event`: the fake raises or returns invalid → `error` with the Indonesian text.
  - `test_selection_resolves_this` (Review Focus 1, fake client): the messages sent contain "terpilih: W5".
- [ ] **Step 2:** Run `uv run pytest -q tests/assist/test_session.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/assist`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(assist): conversation turns with validation, one revision and a session log`.

### Task 5: Streaming API

**Files:**
- Create: `server/routes/assist.py`
- Modify: `server/app.py` (router)
- Test: `tests/server/test_assist.py`

**Interfaces:**
- Consumes: Task 4.
- Produces:
  - `POST /api/projects/{pid}/assist/area` with body `{session_id?, base_version, ops, box, selection, message}` →
    `text/event-stream`, a sequence of `event: <name>\ndata: <json>\n\n`.
    - A new session sends `session` first.
    - The page and binary come from `latest_stage_file` (`01_preprocess/page.png`, `bin.png`, `02_grid/grid.json`);
      when they are missing, they are `None` (Review Focus 4).
    - The client comes from `request.app.state.assist_client_factory()`. The default is
      `StrataClient.from_settings(settings)`; tests set a fake.
    - Sessions are kept in `app.state.assist_sessions` (dict), and an unknown `session_id` → 404 `no_session`.
  - `POST /api/projects/{pid}/assist/area/{session_id}/decision {accepted: bool}` → 204. It is recorded in the session log.

- [ ] **Step 1: Write the failing tests** with `setup_client` + `project_with_gt` and a fake factory:
  - `test_stream_sends_session_steps_and_proposal`: the parsed SSE events, in order, start with `session`, end with
    `done`, and hold a `proposal` with `ops`.
  - `test_followup_uses_the_session`: a second POST with the `session_id` continues; an unknown id → 404.
  - `test_without_run_no_image`: an imported spec → the fake client received no image part; a `step` mentions "tanpa gambar".
  - `test_decision_is_logged`: the log file holds `accepted: true`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement with `StreamingResponse`. The Strata call is synchronous, so iterate the generator in a
  threadpool (`starlette.concurrency.iterate_in_threadpool`).
- [ ] **Step 4:** Run `tests/server/test_assist.py tests/assist`. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(assist): streaming area-fix endpoint and decision log`.

### Task 6: Web — tool A, chat panel, preview, accept/reject

**Files:**
- Create:
  - `web/src/editor/assist/stream.ts`: `streamAssist(pid, body, onEvent): Promise<void>`, a fetch + ReadableStream
    SSE parser.
  - `web/src/editor/assist/store.ts`: Zustand, holding the session id, box, messages
    `[{role: 'user' | 'step' | 'question' | 'proposal' | 'error', ...}]`, `pending: boolean`, the current proposal and
    `baseKey`.
  - `web/src/editor/assist/AssistPanel.tsx`: the chat, the input, and the Terima/Tolak buttons on the latest proposal.
  - `web/src/editor/assist/ProposalLayer.tsx`: deleted walls red dashed, added walls green (yellow when `snapped: false`).
- Modify:
  - `web/src/editor/store.ts`: Tool gains `'assist'`;
  - `web/src/editor/review/ReviewWorkspace.tsx`: the tool `A` "Perbaiki area" drags a box (purple dashed) and opens the
    panel; it renders `ProposalLayer`;
  - `web/src/editor/EditorTab.tsx`: the right aside shows `AssistPanel` while tool `assist` is active.
- Test: `web/src/editor/assist/stream.test.ts`, `web/src/editor/assist/AssistPanel.test.tsx`

**Interfaces:**
- Consumes: Task 5 endpoints; `useEditorStore` (`baseVersion`, `ops`, `selection`, `applyMany`).
- Behaviour:
  - Send posts `{session_id, base_version, ops, box, selection, message}` and records
    `baseKey = JSON.stringify([baseVersion, ops])`.
  - Accept runs `applyMany(proposal.ops)` only when `baseKey` still matches; otherwise it shows "usulan usang, kirim
    ulang" (Review Focus 2). Then it posts the decision.
  - Reject clears the proposal and posts the decision.
  - Esc closes the session (`setTool('select')`).
  - Terima is disabled when `valid` is false.

- [ ] **Step 1: Write the failing tests:**
  - `stream`: a body of three SSE chunks split mid-event parses into the events in order.
  - `AssistPanel`:
    - sending shows the user message, then the `step` texts as they stream (mock `streamAssist`), then the question text;
    - a proposal enables Terima, and Terima adds its ops to the editor pending ops;
    - Tolak leaves the ops unchanged;
    - after a manual op, Terima shows "usulan usang, kirim ulang" and adds nothing;
    - `valid: false` keeps Terima disabled.
  - `ReviewWorkspace`: `a` selects the tool, and a drag opens the panel with the box.
- [ ] **Step 2:** Run `cd web && npx vitest run src/editor/assist src/editor/review`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the web suite, `npm run lint`, and `npx tsc -b`. Expected: PASS, exit 0.
- [ ] **Step 5:** Commit: `feat(web): fix an area with a prompt — tool A, streamed chat, preview, accept/reject`.

### Task 7: Strata regression cases and docs

**Files:**
- Create: `tests/assist/test_area_strata.py` (`@pytest.mark.strata`)
- Modify: `README.md` (a "Perbaiki area dengan prompt" item in the review steps), `ROADMAP.md` (status)

- [ ] **Step 1: Write the tests** (they run only with Strata up), on the GT Gatsu spec + the `preprocess(plan.jpeg)` page:
  - **duplicate:** a parallel copy of a GT wall moved 120 mm, with "dua dinding dobel, satukan" → a proposal whose ops
    delete both and add one wall within 80 mm of the original line;
  - **"hapus ini":** a stray wall added inside a room and selected, with "hapus dinding ini" → a proposal deleting
    exactly it;
  - **ambiguous:** the same without a selection and with several walls in the box → a `question`;
  - **stair area:** the GT stair S1 box with a small extra square of walls inside it, with "rapikan, jadikan ruang
    tangga" → no exterior wall deleted, and the extra square gone.
- [ ] **Step 2:** Run `uv run --env-file .env pytest -q tests/assist/test_area_strata.py -m strata` (DGX reachable).
  Expected: pass. A failure is a finding to report, not a reason to loosen the assertion.
- [ ] **Step 3:** Update the README and ROADMAP.
- [ ] **Step 4:** Run the full non-Strata suites (Python and web). Expected: green.
- [ ] **Step 5:** Commit: `test(assist): Strata regression cases; docs`.
