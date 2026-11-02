"""One conversation turn of area assist (design §5, §6.4): context, Strata, translation, validation, one revision."""

import json
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from core.assist.context import area_context
from core.assist.plan import AreaPlan, translate
from core.llm_review.tasks import load_prompt, png_part
from core.spec.models import Spec
from core.spec.ops import OpError, apply
from core.spec.validate import validate

MAX_QUESTIONS = 3
CALL_TIMEOUT_S = 120
DOWN = "Strata tidak tersedia, coba lagi atau perbaiki manual"


@dataclass
class Session:
    id: str
    project_id: str
    box: tuple[float, float, float, float]
    selection: list[str] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)  # chat history sent to the LLM, text only
    questions: int = 0
    proposals: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)


def _errors(spec: Spec) -> set[tuple[str, str]]:
    return {(i.code, i.message) for i in validate(spec).issues if i.severity == "error"}


def _check(base: Spec, ops: list[dict], tr, before: set) -> tuple[list[str], list[dict]]:
    """Problems for the revision round, and the issues the proposal adds."""
    problems = list(tr.rejected)
    try:
        after = apply(base, ops + tr.ops, "editor", base.meta.version + 1)
    except OpError as e:
        return [*problems, f"op {e.op}: {e.message}"], []
    new = [i for i in validate(after).issues if (i.code, i.message) not in before and i.severity != "info"]
    problems += [f"{i.code}: {i.message}" for i in new if i.severity == "error"]
    return problems, [{"code": i.code, "severity": i.severity, "message": i.message} for i in new]


def run_turn(client, session: Session, message: str, base: Spec, ops: list[dict], page: np.ndarray | None,
             binary: np.ndarray | None, px_to_mm: list | None, log_dir: Path) -> Iterator[dict]:
    try:
        yield from _turn(client, session, message, base, ops, page, binary, px_to_mm)
    finally:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{session.id}.json").write_text(json.dumps(asdict(session), indent=1, default=str))
    yield {"event": "done"}


def _ask(client, messages: list[dict]):
    r = client.ask_json(list(messages), AreaPlan, effort="medium", temperature=0.0,
                        deadline=time.monotonic() + CALL_TIMEOUT_S)
    if not r.valid:
        return None, DOWN if r.transport else "Jawaban Strata tidak bisa dibaca, coba lagi atau perbaiki manual"
    return AreaPlan.model_validate(r.parsed), None


def _turn(client, s: Session, message: str, base: Spec, ops: list[dict], page, binary, px_to_mm) -> Iterator[dict]:
    try:
        work = apply(base, ops, "editor", base.meta.version + 1)
    except OpError as e:
        yield {"event": "error", "text": f"Perubahan lokal tidak bisa diterapkan ({e.message}); simpan atau undo dulu"}
        return
    ctx = area_context(work, s.box, s.selection, page, px_to_mm)
    yield {"event": "step", "text": f"Membaca {len(ctx.wall_ids)} dinding, {len(ctx.opening_ids)} bukaan dan "
                                    f"{len(ctx.room_ids)} ruang di area…"}
    if ctx.image is None:
        yield {"event": "step", "text": "Tanpa gambar denah: Strata hanya membaca daftar elemen, dinding baru tidak di-snap"}
    user = [{"type": "text", "text": f"{ctx.text}\n\nInstruction: {message}"}]
    if ctx.image is not None:
        user.append(png_part(ctx.image))
    messages = [{"role": "system", "content": load_prompt("AF")}, *s.messages, {"role": "user", "content": user}]
    s.messages.append({"role": "user", "content": message})

    before = _errors(work)
    for attempt in range(2):
        yield {"event": "step", "text": "Menunggu Strata…" if attempt == 0 else "Strata merevisi rencana…"}
        t0 = time.monotonic()
        plan, err = _ask(client, messages)
        if err:
            yield {"event": "error", "text": err}
            return
        yield {"event": "step", "text": f"Strata menjawab dalam {time.monotonic() - t0:.0f} s"}
        answer = plan.model_dump_json(exclude_none=True)
        s.messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "assistant", "content": answer})
        if plan.question and not plan.actions:
            if s.questions >= MAX_QUESTIONS:
                yield {"event": "error", "text": "Sudah 3 pertanyaan. Tulis instruksi yang lebih spesifik: sebut ID "
                                                 "elemennya atau pilih dulu elemen yang dimaksud."}
                return
            s.questions += 1
            yield {"event": "question", "text": plan.question}
            return
        if not plan.actions:
            yield {"event": "error", "text": plan.explanation or "Strata tidak mengusulkan perubahan"}
            return
        yield {"event": "step", "text": f"Menerjemahkan {len(plan.actions)} aksi ke op…"}
        tr = translate(plan, work, ctx, message, binary, px_to_mm)
        problems, issues = _check(base, ops, tr, before)
        if not problems or attempt == 1:
            break
        yield {"event": "step", "text": f"Validasi gagal ({len(problems)} masalah), dikirim balik ke Strata, revisi 1/1"}
        fix = "Problems with your plan:\n" + "\n".join(f"- {p}" for p in problems) + "\nAnswer with a corrected plan."
        messages.append({"role": "user", "content": fix})
        s.messages.append({"role": "user", "content": fix})
    yield {"event": "step", "text": "Validasi: 0 error baru" if not problems else f"Masih ada {len(problems)} masalah"}
    proposal = {"ops": tr.ops, "deleted": tr.deleted, "added": tr.added, "moved": tr.moved, "openings": tr.openings,
                "explanation": plan.explanation, "notes": tr.notes + problems, "issues": issues,
                "valid": not problems and bool(tr.ops)}
    s.proposals.append({**proposal, "instruction": message})
    yield {"event": "proposal", **proposal}
