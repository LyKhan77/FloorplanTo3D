# CHANGELOG

One line per change, newest first. Kinds: Feature · Fix · Refactor · Minor. Log only work the user confirmed as
committed (see AGENTS.md).

## 2026-11-05
- **Feature:** PDF input: page picker, site photos and sheet frame dropped, door-width scale, cable-tray mask.
- **Feature:** vector path, opt-in (`extract_source: vector`): walls from PDF paths, rooms traced one by one; gates not reached.
- **Feature:** `room_open` review tasks for rooms that do not close.
- **Feature:** merge rooms: "Gabung ruangan" / "Pisahkan ruangan"; partitions stay in 3D. The V box takes whole rooms.
- **Feature:** manual stair (`S`) as a walking line; flight width and risers in Properties.
- **Feature:** 19 more room types for data centres and general buildings.
- **Feature:** wall id tags on the canvas for a selection and a Perbaiki area box.
- **Feature:** Masalah list hides and shows; an element id centres the canvas on it.
- **Fix:** a hairline gap between walls no longer opens a room.
- **Fix:** rooms closed in the editor take the label inside them.
- **Fix:** Masalah lists only walls joined to nothing, not every loose end.
- **Fix:** review tools stay on screen on a tall plan.
- **Fix:** one dry run at a time in the editor, so Garis Bantu no longer waits behind them.
- **Fix:** grid axes the OCR misread no longer stop a run.

## 2026-11-03
- **Feature:** front mark (yellow edge + arrow) on every device in the installation canvas; ⟲/⟳ 90° buttons.
- **Feature:** one equipment layer.
  - Layout holds architecture only; every device lives in "Instalasi & Interior".
  - `/installations/ensure` moves layout objects once and auto-rebases.
  - New checks I009/I010.
  - The report gains an equipment schedule.
- **Feature:** 2D device editing in Instalasi & Interior (Library drop, drag-move, `R`, numeric Properties).
- **Feature:** generate interior.
  - Rule engine `core/interior` (hot/cold aisle rows, line-up, CRAC, containment, wall devices, TIA-942/ASHRAE rules).
  - `fill_room` / `place_drawn` with user-pointed boxes `K1…`.
- **Feature:** template library of 27 procedural low-poly models (data-center + technical-room units).
- **Fix:**
  - clicking a room selects it instead of making a drawn box;
  - units that do not fit stand on walls or are swapped for a fitting alternative;
  - empty errors always explain themselves.

## 2026-11-02
- **Feature:** Perbaiki area (tool `A`).
  - Strata proposes wall/opening/stair/room fixes from an instruction, previewed with Terima/Tolak/revise.
  - Streamed chat; one revision round.
- **Feature:** add/delete stairs (read from the drawing, or designed to fit, with a fit-to-box fallback).
- **Feature:** Rebase notice in the installation mode; Build 3D on an old layout asked first (superseded by auto-rebase).

## 2026-10-30 – 2026-11-02
- **Feature:** M12a/M12b installation layer.
  - Cable trays and racks traced from the plan; validation I001–I008.
  - Blender build (perforated trays, hangers, drops, ceiling, raised floor, sleeves); report; 3D viewer with layers.
- **Feature:** drawing-fit verification at stage 8 (replaces IoU); editor fixes from the user's E2E session.
- **Feature:** Docker image (M7c part 1).

## 2026-10-26 – 2026-10-29
- **Feature:** M0–M6 foundation.
  - Spec + ground truth; Blender builder and outputs; server + orchestrator.
  - Web editor; CV extraction; Strata review (T0/T3 active).
- **Feature:** M7–M8 hardening, correction-effort metric, bulk editor actions, synthetic benchmark; human-in-the-loop
  review pause with review tasks.
