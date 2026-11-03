"""One conversation turn of area assist (design §5, §6.4): context, Strata, translation, validation, one revision."""

import json
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from core.assist.context import area_context
from core.assist.plan import AreaPlan, Interior, translate
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
             binary: np.ndarray | None, px_to_mm: list | None, log_dir: Path, templates_dir: Path | None = None,
             drawn: list[dict] | None = None, ceiling: float | None = None) -> Iterator[dict]:
    try:
        interior = None
        if templates_dir is not None:
            from core.interior.library import load_library
            from core.interior.rules import load_rules

            interior = Interior(load_library(templates_dir), load_rules(), list(drawn or []),
                                ceiling or base.meta.defaults.wall_height)
        yield from _turn(client, session, message, base, ops, page, binary, px_to_mm, interior)
    except Exception as e:  # noqa: BLE001 - a bug must still end the chat turn with a message, not a cut-off stream
        yield {"event": "error", "text": f"Kesalahan di asisten ({type(e).__name__}: {e}); coba lagi atau perbaiki manual"}
    finally:
        save_log(session, log_dir)
    yield {"event": "done"}


def save_log(session: Session, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{session.id}.json").write_text(json.dumps(asdict(session), indent=1, default=str))


def _summary(tr, problems: list[str]) -> str:
    parts = []
    if tr.deleted:
        parts.append("delete " + ", ".join(tr.deleted))
    parts += [f"new wall {w['a']}->{w['b']} t={w['thickness']}" + ("" if w["snapped"] else " (not on the drawing)")
              for w in tr.added]
    parts += [f"move {m['id']} to {m['a']}->{m['b']}" for m in tr.moved]
    parts += [f"{o['category']} {o['a']}->{o['b']}" + ("" if o["snapped"] else " (not on a drawn gap)") for o in tr.openings]
    parts += [f"stair {[(f['start'], f['end'], f['width'], f['risers']) for f in st['flights']]}"
              + ("" if st["snapped"] else " (designed, not from the drawing)") for st in tr.stairs]
    counts: dict[str, int] = {}
    for o in tr.objects:
        counts[o["template_id"]] = counts.get(o["template_id"], 0) + 1
    parts += [f"{n} x {tid}" for tid, n in counts.items()]
    parts += [f"room {op['op'].removesuffix('_at')} at {op['at']}: {op.get('type') or op.get('name')}"
              for op in tr.ops if op["op"] in ("set_room_type_at", "rename_room_at")]
    parts += [f"problem: {p}" for p in problems]
    return "; ".join(parts) or "no change"


def _ask(client, messages: list[dict]):
    r = client.ask_json(list(messages), AreaPlan, effort="medium", temperature=0.0,
                        deadline=time.monotonic() + CALL_TIMEOUT_S)
    if not r.valid:
        return None, DOWN if r.transport else "Jawaban Strata tidak bisa dibaca, coba lagi atau perbaiki manual"
    return AreaPlan.model_validate(r.parsed), None


def _turn(client, s: Session, message: str, base: Spec, ops: list[dict], page, binary, px_to_mm,
          interior: Interior | None = None) -> Iterator[dict]:
    try:
        work = apply(base, ops, "editor", base.meta.version + 1)
    except OpError as e:
        yield {"event": "error", "text": f"Perubahan lokal tidak bisa diterapkan ({e.message}); simpan atau undo dulu"}
        return
    ctx = area_context(work, s.box, s.selection, page, px_to_mm, interior.library if interior else None,
                       interior.drawn if interior else None)
    yield {"event": "step", "text": f"Membaca {len(ctx.wall_ids)} dinding, {len(ctx.opening_ids)} bukaan dan "
                                    f"{len(ctx.room_ids)} ruang di area…"}
    if ctx.image is None:
        yield {"event": "step", "text": "Tanpa gambar denah: Strata hanya membaca daftar elemen, dinding baru tidak di-snap"}
    note = ""
    last = len(s.proposals) - 1
    if last >= 0 and not any(d.get("proposal") == last for d in s.decisions):
        # the user answers the open proposal instead of Terima/Tolak: a revision, and nothing of it was applied
        s.decisions.append({"proposal": last, "revised": True})
        note = ("Your previous proposal was NOT applied; the user replies to it instead of accepting it.\n"
                f"What it would have done: {s.proposals[last]['summary']}\n"
                "Answer with a complete revised plan: every action still wanted, not only the changes.\n\n")
    user = [{"type": "text", "text": f"{ctx.text}\n\n{note}Instruction: {message}"}]
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
        tr = translate(plan, work, ctx, message, binary, px_to_mm, interior)
        problems, issues = _check(base, ops, tr, before)
        if not problems or attempt == 1:
            break
        yield {"event": "step", "text": f"Validasi gagal ({len(problems)} masalah), dikirim balik ke Strata, revisi 1/1"}
        fix = "Problems with your plan:\n" + "\n".join(f"- {p}" for p in problems) + "\nAnswer with a corrected plan."
        messages.append({"role": "user", "content": fix})
        s.messages.append({"role": "user", "content": fix})
    if not tr.ops:
        # nothing survived translation: say why in the chat instead of a card with Terima disabled
        s.proposals.append({"ops": [], "valid": False, "instruction": message, "summary": _summary(tr, problems),
                            "explanation": plan.explanation, "notes": tr.notes + problems})
        why = "; ".join(problems or tr.notes) or "rencana Strata tidak menghasilkan objek atau perubahan yang bisa ditempatkan"
        yield {"event": "error", "text": f"Tidak ada perubahan yang bisa diusulkan: {why}. Perjelas instruksinya atau ubah area."}
        return
    yield {"event": "step", "text": "Validasi: 0 error baru" if not problems else f"Masih ada {len(problems)} masalah"}
    proposal = {"ops": tr.ops, "deleted": tr.deleted, "added": tr.added, "moved": tr.moved, "openings": tr.openings,
                "stairs": tr.stairs, "objects": tr.objects,
                "explanation": plan.explanation, "notes": tr.notes + problems, "issues": issues,
                "valid": not problems and bool(tr.ops)}
    s.proposals.append({**proposal, "instruction": message, "summary": _summary(tr, problems)})
    yield {"event": "proposal", **proposal}
