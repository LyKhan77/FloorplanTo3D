# WORKFLOW.md

## 1. App workflow (plan → 3D)

1. **New project:** upload the plan (image/PDF) and an optional prompt (heights). "Berhenti untuk review" is on by
   default.
   - A multi-page PDF shows page thumbnails (`POST /api/pdf/pages`); the user picks the plan page. One page = one
     project. Pasted site photos, the sheet frame and the title block are dropped.
   - No dimensions on the plan → stage 2 estimates the scale from door swings (`door_leaf_width`, default 800 mm).
     A door width the user sets always wins; it is the only scale correction in the UI.
   - Experimental switch for PDFs: `extract_source: vector` adds a stage-3 candidate that reads walls from the PDF
     paths and traces rooms one by one; rooms that stay open become `room_open` tasks. Raster stays the default.
2. **Pipeline stages 0–5** (about 2 min on Gatsu):
   - input → preprocess → grid & scale → extraction → rooms → validation;
   - the run pauses at **Perlu review**.
3. **Review (Layout mode, 2D canvas):**
   - work through the review task list;
   - correct with the tools: guide line `L`, new wall `W`, door `D`, close gap, bulk delete/room types;
   - **Perbaiki area `A`**: an instruction to Strata for architecture fixes (walls, openings, stairs, rooms);
   - then **Setujui & build 3D**.
4. **Stages 6–10:** LLM review → Blender build → verification (drawing fit ≥ 0.90) → report → publish. Outputs are
   versioned. Any spec version can be regenerated.
5. **Instalasi & Interior mode** (all equipment, optional):
   - **Opening the mode:**
     - the installation is created on first open;
     - old layout objects move there once;
     - it auto-rebases onto the newest layout.
   - **Placing equipment:**
     - Library drag-and-drop, then drag, `R` or numbers in Properties;
     - rack `K` and tray `T` tracing on the drawing;
     - **Isi ruang `A`**: Strata asks first, then the rule engine places equipment, or the user points at drawn boxes
       `K1…`.
   - **Save → Build 3D:** the installation run (stages 7–10) builds trays, hangers, drops, equipment, ceiling and raised
     floor, plus a report with tray lengths and the equipment schedule.

Layout = architecture only; Instalasi & Interior = every device. The assistant in each mode only does that mode's work.

## 2. Development workflow (agents)

1. **Start:**
   - read `AGENTS.md`, `todo.md`, `CHANGELOG.md`;
   - check `git status` and the branch.
2. **New feature or discussion:**
   - propose a new branch (`feature-name`);
   - no worktrees unless asked.
3. **Brainstorm** (superpowers:brainstorming):
   - clarify intent;
   - lay out approaches;
   - get a decision.
4. **Spec:**
   - `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (committed);
   - a builder-check subagent reads it; open questions go to the user once;
   - the user approves.
5. **Plan:**
   - superpowers:writing-plans → `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` (local only, never committed);
   - the user confirms the execution method.
6. **Execute** (superpowers:executing-plans or subagent-driven-development):
   - TDD per task: failing test → code → green;
   - one commit per task;
   - a ledger in `.superpowers/sdd/<plan>/progress.md` (local);
   - overwrite `todo.md` at the start of each phase.
7. **Final review:**
   - a fresh reviewer subagent on the most capable model;
   - one fix pass: each Critical/Important finding gets a RED→GREEN test;
   - minors are listed for the user.
8. **User test:**
   - the user tests in the browser;
   - **no merge until the user says it works**.
9. **Merge:**
   - scan the diff for secrets and for inputs/outputs;
   - run the full suites;
   - fast-forward `main`;
   - delete the branch;
   - the user pushes from their own terminal (this environment may have no network).
10. **Log:**
    - ask the user to confirm the work is committed and ready;
    - add short lines to `CHANGELOG.md`.
11. **Summary:** report what changed, the tests, the decisions taken, the deferred items and the next step.
