"""Strata tasks T0-T3 (PRD/05 §2, §3.3-3.4): answer schemas, versioned prompts, few-shot examples, message
layout, self-consistency voting and the spec ops an agreed answer turns into."""

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from pydantic import BaseModel

from core.spec.models import RoomType, Spec

PROMPTS_DIR = Path(__file__).parent / "prompts"
FEWSHOT_DIR = Path(__file__).resolve().parents[2] / "benchmarks" / "gatsu" / "fewshot"
HUMAN_SOURCES = ("editor", "manual")
FEWSHOT_TASKS = ("T2", "T3")  # benchmarks/DECISIONS.md: few-shot cut T1's delete precision from 1.0 to 0.76
DELETE_MAX_CONF = 0.8  # same limit as the T4 tools (§4)
# PRD/05 §2 asks "low" for T1/T2; measured on Gatsu, "none" gives the same answers in ~6 s instead of 7-10 s
# (budgeted) or > 75 s (unbudgeted), and stage 6 has 600 s for up to 60 elements x ~2.3 votes
EFFORT = {"T0": "low", "T1": "none", "T2": "none", "T3": "none", "T4": "medium"}


class PromptParams(BaseModel):
    wall_height: int | None = None
    door_height: int | None = None
    wall_thickness: int | None = None
    floor_name: str | None = None
    site_type: Literal["data_hall", "data_center", "office", "mixed", "other"] | None = None


class T1Answer(BaseModel):
    id: str
    verdict: Literal["wall", "annotation", "unsure"]


class T2Answer(BaseModel):
    id: str
    is_door: bool
    door_type: Literal["single_swing", "double_swing", "sliding", "opening", "rolling"] | None = None
    hinge: Literal["start", "end", "both"] | None = None
    swing: Literal["left", "right"] | None = None


class T3Answer(BaseModel):
    id: str
    type: RoomType
    name_normalized: str


SCHEMAS: dict[str, type[BaseModel]] = {"T0": PromptParams, "T1": T1Answer, "T2": T2Answer, "T3": T3Answer}


@dataclass
class ReviewItem:
    task: str
    element: str
    evidence: str
    image: np.ndarray | None
    context: np.ndarray | None
    label: str = ""


@dataclass
class FewShot:
    item: ReviewItem
    answer: dict


def load_prompt(task: str, version: str = "v1") -> str:
    return (PROMPTS_DIR / task / f"{version}.md").read_text().strip()


def load_fewshot(task: str, root: Path = FEWSHOT_DIR) -> list[FewShot]:
    """root/<task>/items.json + PNGs; a missing folder means no examples."""
    d = root / task
    if not (d / "items.json").exists():
        return []

    def img(name: str | None) -> np.ndarray | None:
        return cv2.imread(str(d / name)) if name else None

    return [FewShot(ReviewItem(task, x["element"], x["evidence"], img(x.get("image")), img(x.get("context")),
                               x.get("label", "")), x["answer"])
            for x in json.loads((d / "items.json").read_text())]


def png_part(img: np.ndarray) -> dict:
    data = base64.b64encode(cv2.imencode(".png", img)[1].tobytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}}


def _user(item: ReviewItem, evidence: bool) -> dict:
    lines = [f"Question about element {item.element}."]
    if evidence:
        lines.append(item.evidence)
    elif item.label:
        lines.append(f'OCR label: "{item.label}"')
    lines.append("Answer with JSON matching this schema: " + json.dumps(SCHEMAS[item.task].model_json_schema()))
    parts = [{"type": "text", "text": "\n".join(lines)}]
    parts += [png_part(x) for x in (item.image, item.context) if x is not None]
    return {"role": "user", "content": parts}


def messages_for(item: ReviewItem, fewshot: list[FewShot], *, version: str = "v1", evidence: bool = True) -> list[dict]:
    msgs = [{"role": "system", "content": load_prompt(item.task, version)}]
    for fs in fewshot:
        msgs += [_user(fs.item, evidence), {"role": "assistant", "content": json.dumps(fs.answer)}]
    return [*msgs, _user(item, evidence)]


def agree_key(task: str, ans: BaseModel) -> tuple:
    if task == "T1":
        return (ans.verdict,)
    if task == "T2":
        return (ans.is_door, ans.door_type, ans.hinge, ans.swing)
    return (ans.type, ans.name_normalized.strip().upper())


def majority(task: str, answers: list[BaseModel | None], min_agree: int = 2) -> BaseModel | None:
    """First answer of the largest agreeing group of at least min_agree valid answers (ties: earliest group)."""
    groups: dict[tuple, list[BaseModel]] = {}
    for a in answers:
        if a is not None:
            groups.setdefault(agree_key(task, a), []).append(a)
    best = max(groups.values(), key=len, default=[])
    return best[0] if len(best) >= min_agree else None


def _element(spec: Spec, eid: str):
    return next((x for x in [*spec.walls, *spec.openings, *spec.rooms] if x.id == eid), None)


def ops_for(task: str, spec: Spec, element: str, ans: BaseModel) -> list[dict]:
    """Spec ops for an agreed answer about `element`; [] when nothing changes or the answer may not apply."""
    el = _element(spec, element)
    if el is None or ans.id != element or el.provenance.source in HUMAN_SOURCES:
        return []
    if task == "T1":
        if ans.verdict == "annotation" and el.provenance.confidence < DELETE_MAX_CONF:
            return [{"op": "delete_wall", "id": element, "reason": "strata: annotation"}]
        return []
    if task == "T2":
        if not ans.is_door:
            if el.provenance.confidence < DELETE_MAX_CONF:
                return [{"op": "delete_opening", "id": element, "reason": "strata: not a door"}]
            return []
        changed = {f: getattr(ans, f) for f in ("door_type", "hinge", "swing") if getattr(ans, f) != getattr(el, f)}
        return [{"op": "set_door", "id": element, **changed}] if changed else []
    ops = []
    if ans.type != el.type:
        ops.append({"op": "set_room_type", "id": element, "type": ans.type})
    name = ans.name_normalized.strip()
    if name and name != el.name:
        ops.append({"op": "rename_room", "id": element, "name": name})
    return ops


def parse_prompt_llm(client, prompt: str) -> dict:
    """T0 (PRD/04 Tahap 0): the fields Strata read from the prompt; {} when the answer is invalid."""
    if not prompt.strip():
        return {}
    r = client.ask_json([{"role": "system", "content": load_prompt("T0")}, {"role": "user", "content": prompt}],
                        PromptParams, effort=EFFORT["T0"], temperature=0)
    return {k: v for k, v in (r.parsed or {}).items() if v is not None} if r.valid else {}
