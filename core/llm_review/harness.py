"""Stage-6 harness (PRD/05 §2.1, §5, §9): route low-confidence or flagged elements to Strata, vote, and keep a
change only when the validator score allows it, so the result is never worse than stage 5.

Phase A (classification, T1 -> T2 -> T3): accept when there is no validator error and score >= score - 0.005.
Phase B (repair, T4 tool calls): accept only when the score strictly rises; rejections are told back to the model.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from shapely.geometry import Point
from shapely.geometry import Polygon as SPolygon

from core.extraction.rooms.overlay_ids import render_ids_overlay
from core.llm_review.crops import (
    context_thumb,
    crop_box_px,
    door_evidence,
    element_crop,
    room_evidence,
    wall_evidence,
)
from core.llm_review.tasks import (
    EFFORT,
    FEWSHOT_DIR,
    HUMAN_SOURCES,
    SCHEMAS,
    ReviewItem,
    agree_key,
    load_fewshot,
    load_prompt,
    majority,
    messages_for,
    ops_for,
    png_part,
)
from core.llm_review.tools import TOOLS, check_call
from core.spec.models import Spec
from core.spec.ops import OpError, apply
from core.spec.validate import Issue, ValidationContext, validate

REVIEW_CONF = 0.6
PHASE_A_TOL = 0.005
VOTE_ZOOM = 1.3
VOTE_TEMPERATURE = 0.4
T4_OVERLAY_MAX_PX = 1536  # spike-strata.md: 6 px text still readable at 1536^2


@dataclass
class ReviewInputs:
    page: np.ndarray  # stage-1 page.png, grey, working px
    to_px: Callable[[float, float], tuple[float, float]]
    mm_per_px: float
    hatch: np.ndarray | None
    texts: list[dict]  # stage-2 OCR records with "at_mm"
    labels: list[tuple[str, tuple[float, float]]]  # room-label OCR text and its point (mm)
    vctx: ValidationContext


@dataclass
class ReviewResult:
    spec: Spec
    ops: list[dict]
    score_before: float
    score_after: float
    decisions: list[dict] = field(default_factory=list)
    timed_out: bool = False
    calls: int = 0
    invalid: int = 0


def _flagged(issues: list[Issue]) -> set[str]:
    return {e for i in issues if i.severity in ("warning", "error") for e in i.element_ids}


def select_for_review(spec: Spec, issues: list[Issue], tasks: set[str], limit: int = 60) -> list[tuple[str, str]]:
    """T1 walls and T2 doors below REVIEW_CONF or named by a warning/error, lowest confidence first, at most
    `limit` together; elements a person edited are never sent."""
    flagged = _flagged(issues)

    def pick(task: str, items) -> list[tuple[float, str, str]]:
        if task not in tasks:
            return []
        return [(x.provenance.confidence, x.id, task) for x in items if x.provenance.source not in HUMAN_SOURCES
                and (x.provenance.confidence < REVIEW_CONF or x.id in flagged)]

    chosen = sorted(pick("T1", spec.walls) + pick("T2", [o for o in spec.openings if o.category == "door"]))[:limit]
    return [(t, eid) for _, eid, t in sorted(chosen, key=lambda c: (c[2], c[0], c[1]))]


class _Run:
    def __init__(self, spec, inputs, client, *, out, version, clock, deadline, emit, prompt_version, evidence,
                 fewshot_root):
        self.spec, self.inputs, self.client, self.out = spec, inputs, client, out
        self.version, self.clock, self.deadline, self.emit = version, clock, deadline, emit
        self.prompt_version, self.evidence, self.fewshot_root = prompt_version, evidence, fewshot_root
        self.score = validate(spec, inputs.vctx).score
        self.ops: list[dict] = []
        self.decisions: list[dict] = []
        self.timed_out, self.calls, self.invalid = False, 0, 0
        self._fewshot: dict[str, list] = {}
        self._log = (out / "transcript.jsonl").open("a")
        (out / "crops").mkdir(parents=True, exist_ok=True)

    def expired(self) -> bool:
        if self.clock() >= self.deadline:
            self.timed_out = True
        return self.timed_out

    def transcript(self, task, element, vote, ref, effort, r) -> None:
        self.calls += r.attempts
        self._log.write(json.dumps({
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"), "task": task, "element": element,
            "prompt_version": self.prompt_version, "vote": vote, "attempts": r.attempts,
            "request": {"messages_ref": ref, "effort": effort},
            "response": {"raw": r.raw, "parsed": r.parsed, "valid": r.valid, "error": r.error,
                         **({"tool_calls": r.tool_calls} if r.tool_calls else {})},
            "latency_ms": r.latency_ms, "tokens": r.tokens}) + "\n")
        self._log.flush()

    def gate(self, ops: list[dict], strict: bool) -> tuple[Spec | None, float, str | None]:
        try:
            cand = apply(self.spec, ops, "llm", self.version + 1)
        except OpError as e:
            return None, self.score, f"op_error: {e}"
        res = validate(cand, self.inputs.vctx)
        if not res.passed:
            return None, res.score, "validator_error"
        ok = res.score > self.score if strict else res.score >= self.score - PHASE_A_TOL
        return (cand, res.score, None) if ok else (None, res.score, "score_drop")

    def decide(self, task, element, verdict, decision, reason=None, ops=(), after=None, before=None) -> None:
        before = self.score if before is None else before
        d = {"element": element, "task": task, "verdict": verdict, "decision": decision, "reason": reason,
             "score_before": round(before, 4), "score_after": round(before if after is None else after, 4),
             "ops": list(ops)}
        self.decisions.append(d)
        if self.emit:
            self.emit("llm.decision", {"element": element, "task": task, "verdict": verdict,
                                       "accepted": decision == "accepted", "score_before": d["score_before"],
                                       "score_after": d["score_after"]})

    def try_ops(self, task, element, verdict, ops, strict) -> None:
        cand, new, reason = self.gate(ops, strict)
        if cand is None:
            self.decide(task, element, verdict, "rejected", reason, ops, new)
            return
        before, self.spec, self.score = self.score, cand, new
        self.ops += ops
        self.decide(task, element, verdict, "accepted", None, ops, new, before)

    # --- phase A ------------------------------------------------------------------------------------------------

    def item(self, task: str, eid: str, vote: int, label: str = "") -> tuple[ReviewItem, str | None]:
        inp = self.inputs
        if task == "T3":
            return ReviewItem(task, eid, room_evidence(self.spec, eid, label), None, None, label), None
        zoom = 1.0 if vote == 1 else VOTE_ZOOM
        ref = f"crops/{eid}_v{vote}.png"
        img = element_crop(inp.page, self.spec, eid, inp.to_px, zoom)
        cv2.imwrite(str(self.out / ref), img)
        ctx = context_thumb(inp.page, crop_box_px(self.spec, eid, inp.to_px, zoom))
        if vote == 1:
            cv2.imwrite(str(self.out / "crops" / f"{eid}_ctx.png"), ctx)
        ev = (wall_evidence(self.spec, eid, mm_per_px=inp.mm_per_px, hatch=inp.hatch, texts=inp.texts,
                            to_px=inp.to_px) if task == "T1" else door_evidence(self.spec, eid))
        return ReviewItem(task, eid, ev, img, ctx), ref

    def classify(self, task: str, eid: str, votes: int, label: str = "") -> bool:
        """Ask, vote, gate; False when the deadline stopped it before a decision."""
        if task not in self._fewshot:
            self._fewshot[task] = load_fewshot(task, self.fewshot_root) if self.fewshot_root else []
        answers = []
        for vote in range(1, votes + 1):
            if vote == 3 and None not in answers[:2] and agree_key(task, answers[0]) == agree_key(task, answers[1]):
                break  # a third vote cannot change a 2-of-3 majority
            if self.expired():
                return False
            item, ref = self.item(task, eid, vote, label)
            msgs = messages_for(item, self._fewshot[task], version=self.prompt_version, evidence=self.evidence)
            r = self.client.ask_json(msgs, SCHEMAS[task], effort=EFFORT[task],
                                     temperature=0 if vote == 1 else VOTE_TEMPERATURE)
            self.transcript(task, eid, vote, ref, EFFORT[task], r)
            answers.append(SCHEMAS[task].model_validate(r.parsed) if r.valid else None)
        if all(a is None for a in answers):
            self.invalid += 1
            self.decide(task, eid, None, "invalid_output", "invalid JSON/schema or Strata unreachable")
            return True
        verdict = majority(task, answers, min_agree=1 if votes == 1 else 2)
        if verdict is None:
            self.decide(task, eid, None, "no_consensus")
            return True
        ops = ops_for(task, self.spec, eid, verdict)
        if not ops:
            self.decide(task, eid, verdict.model_dump(), "no_change")
            return True
        self.try_ops(task, eid, verdict.model_dump(), ops, strict=False)
        return True

    def rooms_for_t3(self) -> list[tuple[str, str]]:
        out = []
        for r in self.spec.rooms:
            if r.provenance.source in HUMAN_SOURCES or (r.type != "other" and r.name):
                continue
            shape = SPolygon(r.polygon, r.holes)
            texts = list(dict.fromkeys(t for t, at in self.inputs.labels if shape.covers(Point(at))))
            if texts:
                out.append((r.id, " / ".join(texts)))
        return out

    # --- phase B ------------------------------------------------------------------------------------------------

    def repair(self, max_iter: int) -> None:
        history: list[str] = []
        for i in range(max_iter):
            problems = [x for x in validate(self.spec, self.inputs.vctx).issues if x.severity in ("warning", "error")]
            if not problems or self.expired():
                return
            overlay, _ = render_ids_overlay(self.inputs.page, self.spec, self.inputs.to_px)
            k = min(1.0, T4_OVERLAY_MAX_PX / max(overlay.shape[:2]))
            overlay = cv2.resize(overlay, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else overlay
            ref = f"crops/T4_{i + 1}.png"
            cv2.imwrite(str(self.out / ref), overlay)
            lines = ["Validator problems:"] + [f"- {p.code} ({p.severity}) {', '.join(p.element_ids)}: {p.message}"
                                               for p in problems[:40]]
            if history:
                lines += ["", "Your previous tool calls in this review:", *history]
            msgs = [{"role": "system", "content": load_prompt("T4", self.prompt_version)},
                    {"role": "user", "content": [{"type": "text", "text": "\n".join(lines)}, png_part(overlay)]}]
            r = self.client.ask_tools(msgs, TOOLS, effort=EFFORT["T4"], temperature=0)
            self.transcript("T4", None, i + 1, ref, EFFORT["T4"], r)
            if not r.valid:
                self.invalid += 1
                self.decide("T4", "-", None, "invalid_output", r.error)
                return
            if not r.tool_calls or r.tool_calls[0]["name"] == "finish":
                return
            call = r.tool_calls[0]
            args = call["arguments"]
            target = (",".join(args.get("ids", [])) or args.get("id")) if isinstance(args, dict) else None
            target = target or "-"
            ops, reason = check_call(self.spec, call["name"], args)
            verdict = {"tool": call["name"], "arguments": args}
            n_before = len(self.decisions)
            if reason:
                self.decide("T4", target, verdict, "rejected", reason)
            else:
                self.try_ops("T4", target, verdict, ops, strict=True)
            d = self.decisions[n_before]
            outcome = (f"accepted: score {d['score_before']:.4f} -> {d['score_after']:.4f}" if d["decision"] == "accepted"
                       else f"rejected: {d['reason']}")
            history.append(f"- {call['name']} {json.dumps(args)}: {outcome}")


def run_review(spec: Spec, inputs: ReviewInputs, client, *, tasks: set[str], votes: int, max_iter: int,
               deadline: float, out: Path, version: int, clock: Callable[[], float] = time.monotonic,
               emit: Callable[[str, dict], None] | None = None, limit: int = 60, prompt_version: str = "v1",
               evidence: bool = True, fewshot_root: Path | None = FEWSHOT_DIR) -> ReviewResult:
    out.mkdir(parents=True, exist_ok=True)
    run = _Run(spec, inputs, client, out=out, version=version, clock=clock, deadline=deadline, emit=emit,
               prompt_version=prompt_version, evidence=evidence, fewshot_root=fewshot_root)
    before = run.score
    try:
        issues = validate(spec, inputs.vctx).issues
        for task, eid in select_for_review(spec, issues, tasks, limit):
            if not any(x.id == eid for x in [*run.spec.walls, *run.spec.openings]):
                continue  # gone with an accepted change (a door on a deleted wall)
            if not run.classify(task, eid, votes):
                break
        if "T3" in tasks and not run.timed_out:
            for rid, label in run.rooms_for_t3():
                if not run.classify("T3", rid, votes, label):
                    break
        if "T4" in tasks and not run.timed_out:
            run.repair(max_iter)
    finally:
        run._log.close()
        (out / "decisions.json").write_text(json.dumps(run.decisions, indent=1))
    return ReviewResult(run.spec, run.ops, before, run.score, run.decisions, run.timed_out, run.calls, run.invalid)
