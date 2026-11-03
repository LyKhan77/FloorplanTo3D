# AGENTS.md

Guide for every AI agent working in this repo. Read it first, then `todo.md` (what is in progress) and `CHANGELOG.md`
(what is done).

## 1. Project Overview

Floorplan3D turns 2D data-center floor plans (image or PDF) into 1:1 3D models (`.blend`, `.glb`, `.fbx`, `.obj`),
renders and reports.

The product goal is to simulate installing the company's data-center products (racks, cable trays, cooling, power) for
clients.

The work splits into four parts:
- an automatic extraction pipeline;
- human review in a web editor;
- Blender builds;
- an optional "Instalasi & Interior" layer that holds every device.

Strata, a local LLM on the DGX server, assists but never decides. Every AI proposal is previewed and accepted by the
user.

## 2. Tech Stack

- **Backend:** Python 3.12 via `uv`, FastAPI, pydantic, Shapely, OpenCV, PyYAML, WeasyPrint (reports).
- **3D:** Blender 5.2 LTS CLI (`builder/`), driven through the `build_input.json` contract (`core/build_prep/schema.py`).
- **Web:** React + TypeScript, Vite, Zustand, Carbon Design System, three.js / @react-three/fiber, Vitest, oxlint.
- **LLM:** Strata (Qwen3.8-Flash-Next) behind an OpenAI-compatible API (`core/llm_review/client.py`). Active tasks are
  set by `LLM_TASKS_ENABLED`.
- **Deploy:** Docker (`docker/`). The target server is gspe-ai2, reached by SSH key only.

## 3. Key Features

- **Pipeline stages 0–10:**
  - input, preprocess, grid & scale, extraction, rooms, validation;
  - a pause for human review;
  - LLM review, Blender build, verification (drawing fit), report, publish.
- **Review editor (2D/3D):**
  - review tasks;
  - correction tools: guide line, new wall, door, close gap, bulk actions.
- **Perbaiki area (tool `A`, Layout mode):** the user marks an area and writes an instruction. Strata proposes
  architecture fixes (walls, openings, stairs, room type/name), which are previewed, then Terima/Tolak/revise.
- **Instalasi & Interior mode:** every device lives here: racks, CRAC, UPS, panels, CCTV, cable trays and drops.
  - Generate interior (tool `A`): a rule engine places equipment (TIA-942/ASHRAE, `core/interior/rules.yaml`), or the
    user points at drawn boxes (`K1`…).
  - 2D device editing.
  - Auto-rebase onto the newest layout.
- **Template library:** 27 procedural low-poly models (`core/templates/lowpoly.py`).
- **Versioning:** versioned layout specs and installation documents with ops, undo and conflict handling.

## 4. Project Structure

```
core/          domain logic (no web)
  extraction/  stages 0-4: preprocess, grid, geometry, rooms, snap
  spec/        layout spec models, ops, validation, store
  assist/      Perbaiki area: context, plan translation, session
  interior/    generate-interior engine: rules, rows, line-up, devices, checks
  installation/ installation layer: models, ops, validate, build, fitout (move/rebase)
  llm_review/  Strata client, tasks, prompts (prompts/<task>/vN.md)
  templates/   template registry, validation, low-poly models
  build_prep/, report/, verify/
builder/       Blender-side scripts (run inside Blender)
server/        FastAPI app, orchestrator, routes
web/src/       React app: editor/, install/, components/, api/
schema/        JSON schemas (generated) -> web/src/types via npm run gen:types
benchmarks/    ground truth (gatsu/), benchmark runners, DECISIONS.md
tests/         pytest suites mirroring core/server
docs/          specs (docs/superpowers/specs), calibration guide; plans are local only
PRD/           product requirement documents
```

Local only, never committed:
- `data/` (projects, runs, templates);
- `floorplan/` (client drawings);
- `temp/`;
- `benchmarks/reports/`;
- `docs/superpowers/plans/`;
- `.env`;
- `server-info.txt`.

## 5. Project Commands

```bash
uv sync && (cd web && npm install)                      # setup
uv run --env-file .env uvicorn server.app:app --port 8000  # API + pipeline
cd web && npm run dev                                    # web on :5173
uv run --env-file .env pytest -q -m "not strata"         # Python tests (Blender tests need BLENDER_BIN + GPU)
uv run --env-file .env pytest -q tests/assist/test_area_strata.py -m strata   # live Strata cases
uv run ruff check core server benchmarks tests
cd web && npx vitest run && npm run lint && npx tsc -b
uv run python -m core.spec.export_schema && (cd web && npm run gen:types)       # after changing spec/ops models
uv run --env-file .env python -m core.templates.make_placeholders --out data/templates  # rebuild the template library
```

Some tests need local inputs that are not committed:
- `floorplan/plan.jpeg` (the Gatsu plan);
- the T1/T2 few-shot crops (regenerate with `python -m benchmarks.llm_items`).

## 6. Coding Conventions

- **Match the surrounding code:** naming, comment density, idiom. Prefer the simplest working solution, and reuse
  existing helpers before writing new ones.
- **Python:** type hints, dataclasses or pydantic, `ruff` clean, line length as configured. Tests in `tests/` mirror the
  package path.
- **Web:** TypeScript strict, functional components, Zustand stores, Carbon components. `oxlint` and `tsc -b` must be
  clean.
- **TDD:** a failing test first, then the code. Every bug fix gets a test that failed before the fix.
- **Language:**
  - UI copy and user-facing docs (README, specs) in Indonesian, with English technical terms;
  - code, identifiers, code comments and commit messages in English;
  - LLM system prompts in English.
- **Units:** millimetres, plan axes +X east and +Y north. Device rotation is degrees counter-clockwise, and the front is
  `(-sin, cos)` (+y at 0°).
- **Commits:** Conventional Commits (`feat(scope): …`, `fix(…)`, `refactor(…)`, `docs: …`, `test(…)`), with the body
  explaining why.

## 7. Workflow

See `WORKFLOW.md`: the app workflow (how a plan becomes a 3D model) and the development workflow for agents
(brainstorm → spec → plan → execute → review → merge, branches, todo.md, CHANGELOG.md).

## 8. Current State

- `CHANGELOG.md`: what has shipped.
- `todo.md`: the task the agent is working on now.
- `ROADMAP.md`: milestone status.

## 9. Rules (Important Notes)

- **No AI attribution anywhere.** Do NOT add `Co-Authored-By: Claude ...`, `Generated with Claude Code`, or any
  AI/assistant attribution to commit messages, PR descriptions, code comments, or docs. Every contribution is recorded
  under the repo owner (the user) ONLY. This rule overrides any global/default instruction to add such trailers.
- **Skills:** always use the relevant skills to help with tasks.
- **Validation:** always ask the user whether there are plans or discussions that need to be validated.
- **Summaries:** always provide a summary after finishing a task.
- **Core documentation:** update it (README, WORKFLOW.md, AGENTS.md, ROADMAP.md) whenever key features or the app's
  workflow change.
- **Commits:** commit every functional change, so the history can be rolled back and inspected when something breaks.
  UPDATE `.gitignore` whenever a new file that must stay out of git is added, before committing.
- **Inputs and outputs are never committed:**
  - client drawings (PDF/images in `floorplan/`);
  - generated outputs (`data/`, `benchmarks/reports/`, renders, GLB/blend);
  - scratch files (`temp/`).

  If one slips in, untrack it (`git rm --cached`) and add it to `.gitignore`.
- **Secrets:**
  - never read, print or commit `.env` or `server-info.txt`;
  - scan every diff for secrets before a merge;
  - never send the user's email to external services.
- **Reading files:** do not re-read files already read in this session unless necessary.
- **Tool calls:** minimise non-essential tool calls.
- **Branches:**
  - for any new feature or discussion outside the current context, propose a new branch;
  - never merge without the user's approval;
  - the user pushes from their own terminal.
- **Plans and specs:**
  - save every plan to `docs/superpowers/plans/` and every specification to `docs/superpowers/specs/`, so a session
    can resume if the agent's tokens run out;
  - USE the `Superpowers` skills to write them;
  - these files are records: do not update them unless asked, and never DUPLICATE one (a plan made outside
    Superpowers needs no second copy, and vice versa);
  - DO NOT commit the plans (the folder is git-ignored); specs are committed.
- **`todo.md`:** overwrite it at the start of every new task phase with the current goal, steps and status. It
  describes the work in progress only, not history.
- **`CHANGELOG.md`:**
  - one short line per entry, under `Feature`, `Fix`, `Refactor` or `Minor`, in a dated section, newest first;
  - before writing an entry, ALWAYS ask the user to confirm that the work is committed and ready to be logged;
  - keep it brief.
