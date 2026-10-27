"""T4 tools (PRD/05 §4): a whitelist of spec ops Strata may call, each with its limits. Free geometry
(add_wall, move_wall) is never offered: a 2-bit model is not reliable with coordinates."""

import math
from typing import get_args

from pydantic import ValidationError

from core.llm_review.tasks import DELETE_MAX_CONF, HUMAN_SOURCES
from core.spec.models import RoomType, Spec
from core.spec.ops import _OP_ADAPTER, PARALLEL_TOL_DEG, DoorType


def _fn(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "properties": props, "required": required, "additionalProperties": False}}}


_ID = {"type": "string", "description": "element ID as shown in the image"}
_REASON = {"type": "string", "description": "short reason"}
TOOLS: list[dict] = [
    _fn("delete_wall", "Delete a detected wall that is not architectural (only confidence < 0.8).",
        {"id": _ID, "reason": _REASON}, ["id", "reason"]),
    _fn("merge_walls", "Merge collinear, adjacent pieces of one wall.",
        {"ids": {"type": "array", "items": {"type": "string"}, "minItems": 2}, "reason": _REASON}, ["ids", "reason"]),
    _fn("set_door", "Correct a door's type, hinge or swing.",
        {"id": _ID, "door_type": {"type": ["string", "null"], "enum": [*get_args(DoorType), None]},
         "hinge": {"type": ["string", "null"], "enum": ["start", "end", "both", None]},
         "swing": {"type": ["string", "null"], "enum": ["left", "right", None]}}, ["id"]),
    _fn("delete_opening", "Delete a detected opening that is not a door (only confidence < 0.8).",
        {"id": _ID, "reason": _REASON}, ["id", "reason"]),
    _fn("set_room_type", "Set a room's type.", {"id": _ID, "type": {"type": "string", "enum": list(get_args(RoomType))}},
        ["id", "type"]),
    _fn("rename_room", "Set a room's name.", {"id": _ID, "name": {"type": "string"}}, ["id", "name"]),
    _fn("finish", "End the review when no remaining fix is clear.", {"summary": {"type": "string"}}, ["summary"]),
]
_ALLOWED = {t["function"]["name"]: set(t["function"]["parameters"]["properties"]) for t in TOOLS}


def _merge_problem(spec: Spec, ids: list[str]) -> str | None:
    walls = [next(w for w in spec.walls if w.id == i) for i in ids]
    keep = walls[0]
    length = math.dist(keep.a, keep.b) or 1.0
    ux, uy = (keep.b[0] - keep.a[0]) / length, (keep.b[1] - keep.a[1]) / length
    max_t = max(w.thickness for w in walls)
    for w in walls[1:]:
        lw = math.dist(w.a, w.b) or 1.0
        wx, wy = (w.b[0] - w.a[0]) / lw, (w.b[1] - w.a[1]) / lw
        off = max(abs((p[0] - keep.a[0]) * uy - (p[1] - keep.a[1]) * ux) for p in (w.a, w.b))
        if abs(wx * uy - wy * ux) > math.sin(math.radians(PARALLEL_TOL_DEG)) or off > max_t:
            return "not_collinear"
    spans = sorted(sorted(((p[0] - keep.a[0]) * ux + (p[1] - keep.a[1]) * uy) for p in (w.a, w.b)) for w in walls)
    reach = spans[0][1]
    for lo, hi in spans[1:]:
        if lo - reach > max_t:
            return "not_adjacent"
        reach = max(reach, hi)
    return None


def check_call(spec: Spec, name: str, args: dict | None) -> tuple[list[dict], str | None]:
    """(ops, None) when the call may be applied, ([], reason) when it is rejected; finish -> ([], None)."""
    if name not in _ALLOWED:
        return [], "unknown_tool"
    if name == "finish":
        return [], None
    if not isinstance(args, dict) or set(args) - _ALLOWED[name]:
        extra = sorted(set(args) - _ALLOWED[name]) if isinstance(args, dict) else "arguments are not a JSON object"
        return [], f"bad_args:{extra}"
    op = {"op": name, **args}
    try:
        _OP_ADAPTER.validate_python(op)
    except ValidationError as e:
        return [], f"bad_args:{str(e).splitlines()[0]}"
    ids = args["ids"] if name == "merge_walls" else [args["id"]]
    pool = spec.walls if name in ("delete_wall", "merge_walls") else spec.openings if name in (
        "set_door", "delete_opening") else spec.rooms
    by_id = {x.id: x for x in pool}
    for i in ids:
        if i not in by_id:
            return [], f"unknown_id:{i}"
        if by_id[i].provenance.source in HUMAN_SOURCES:
            return [], f"human_edit:{i}"
        if name in ("delete_wall", "delete_opening") and by_id[i].provenance.confidence >= DELETE_MAX_CONF:
            return [], f"confidence>=0.8:{i}"
    if name == "merge_walls" and (problem := _merge_problem(spec, ids)):
        return [], problem
    return [op], None
