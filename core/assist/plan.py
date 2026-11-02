"""The LLM's plan for an area (design §6.2) and its deterministic translation into spec ops (§6.3).

The LLM names elements and rough positions; geometry comes from the spec and the drawing: merged walls on their
midline, new walls and openings snapped to the page binary, corners closed on the other wall's axis.
"""

import math
from dataclasses import dataclass, field
from typing import Annotated, Literal, get_args

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import Point as SPoint
from shapely.geometry import box as sbox

from core.assist.context import AreaContext, rep_point
from core.extraction.rooms.overlay import px_from_mm
from core.extraction.snap import snap_wall
from core.spec.derive import id_key
from core.spec.models import RoomType, Spec

PARALLEL_DEG = 3.0
COLLINEAR_MM = 20  # parallel walls this close share one axis: the editor's merge_walls joins them
MERGE_GAP_MM = 100  # parallel walls up to max thickness + this apart are one wall drawn twice
EXTEND_MAX_MM = 1500
SPLIT_END_MM = 100
END_CLEAR_MM = 50  # validation: an opening keeps 50 mm from the wall ends
GAP_SEARCH_MM = 1500
GAP_MIN_MM, GAP_MAX_MM = 600, 3000
DEFAULT_WIDTH = {"door": 900, "window": 1200}
FLIP = {"start": "end", "end": "start", "left": "right", "right": "left"}
DoorType = Literal["single_swing", "double_swing", "sliding", "opening", "rolling"]


class _A(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DeleteWall(_A):
    type: Literal["delete_wall"]
    id: str


class MergeWalls(_A):
    type: Literal["merge_walls"]
    ids: list[str] = Field(min_length=2)


class AddWall(_A):
    type: Literal["add_wall"]
    a: tuple[float, float]
    b: tuple[float, float]


class ExtendWall(_A):
    type: Literal["extend_wall"]
    id: str
    to: str


class SplitWall(_A):
    type: Literal["split_wall"]
    id: str
    at: tuple[float, float]


class AddOpening(_A):
    type: Literal["add_opening"]
    wall: str
    category: Literal["door", "window"]
    at: tuple[float, float]
    width: float | None = None


class SetDoor(_A):
    type: Literal["set_door"]
    id: str
    width: float | None = None
    swing: Literal["left", "right"] | None = None
    hinge: Literal["start", "end", "both"] | None = None
    door_type: DoorType | None = None


class DeleteOpening(_A):
    type: Literal["delete_opening"]
    id: str


class SetRoomType(_A):
    type: Literal["set_room_type"]
    room: str
    value: str
    at: tuple[float, float] | None = None  # a point in the part meant, when new walls split the room


class RenameRoom(_A):
    type: Literal["rename_room"]
    room: str
    name: str
    at: tuple[float, float] | None = None


Action = Annotated[
    DeleteWall | MergeWalls | AddWall | ExtendWall | SplitWall | AddOpening | SetDoor | DeleteOpening | SetRoomType
    | RenameRoom,
    Field(discriminator="type"),
]


class AreaPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    question: str | None = None
    actions: list[Action] = []
    explanation: str = ""


@dataclass
class Translation:
    ops: list[dict] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    added: list[dict] = field(default_factory=list)  # {a, b, thickness, snapped}
    moved: list[dict] = field(default_factory=list)  # {id, a, b}
    openings: list[dict] = field(default_factory=list)  # {a, b, category, snapped}
    notes: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


def _unit(a, b) -> tuple[float, float, float]:
    length = math.dist(a, b)
    return (b[0] - a[0]) / length, (b[1] - a[1]) / length, length


def _pt(x: float, y: float) -> list[int]:
    return [round(x), round(y)]


def _snap(binary, px_to_mm, a, b, default_t: int) -> tuple[dict, bool]:
    s = snap_wall(binary, px_to_mm, a, b, default_mm=default_t) if binary is not None and px_to_mm else None
    if s:
        return {"a": s["a"], "b": s["b"], "thickness": s["thickness"]}, True
    return {"a": _pt(*a), "b": _pt(*b), "thickness": default_t}, False


def _gap(binary, px_to_mm, a, ux, uy, length: float, t: float, half: float,
         taken: list[tuple[float, float]] = ()) -> tuple[float, float] | None:
    """The ink-free run along the wall axis nearest to t, as (start, end) offsets, or None. `taken` spans (the wall's
    existing openings) count as ink: their gap is already a door."""
    to_px = px_from_mm(px_to_mm)
    step = abs(px_to_mm[0]) / 2 or 1.0
    nx, ny = -uy, ux
    h, w = binary.shape[:2]
    ts = np.arange(max(0.0, t - GAP_SEARCH_MM), min(length, t + GAP_SEARCH_MM) + step, step)
    across = np.arange(-half, half + step, step)
    ink = np.zeros(len(ts), bool)
    for i, d in enumerate(ts):
        if any(s0 <= d <= s1 for s0, s1 in taken):
            ink[i] = True
            continue
        for o in across:
            x, y = to_px(a[0] + ux * d + nx * o, a[1] + uy * d + ny * o)
            xi, yi = round(x), round(y)
            if 0 <= xi < w and 0 <= yi < h and binary[yi, xi] > 0:
                ink[i] = True
                break
    best = None
    i = 0
    while i < len(ts):
        if ink[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(ts) and not ink[j + 1]:
            j += 1
        s, e = float(ts[i]), float(ts[j])
        dist = 0.0 if s <= t <= e else min(abs(t - s), abs(t - e))
        if GAP_MIN_MM <= e - s <= GAP_MAX_MM and (best is None or dist < best[0]):
            best = (dist, s, e)
        i = j + 1
    return (best[1], best[2]) if best else None


def translate(plan: AreaPlan, spec: Spec, ctx: AreaContext, instruction: str, binary: np.ndarray | None,
              px_to_mm: list | None) -> Translation:
    out = Translation()
    reason = "asisten: " + (instruction.strip()[:60] or "perbaiki area")
    walls = {w.id: w for w in spec.walls if w.id in ctx.wall_ids}
    openings = {o.id: o for o in spec.openings if o.id in ctx.opening_ids}
    rooms = {r.id: r for r in spec.rooms if r.id in ctx.room_ids}
    geo = {wid: (tuple(w.a), tuple(w.b)) for wid, w in walls.items()}  # wall axes as the ops so far leave them
    default_t = round(spec.meta.defaults.wall_thickness)
    box = sbox(*ctx.box)
    buckets: dict[str, list[dict]] = {k: [] for k in ("del", "merge", "split", "extend", "add", "opening", "room")}

    def known(eid: str, pool: dict, what: str) -> bool:
        if eid in pool:
            return True
        out.rejected.append(f"{what} {eid} tidak ada di area")
        return False

    def alive(wid: str) -> bool:
        """A wall known to the area that an earlier action of this plan did not delete or merge away."""
        if not known(wid, walls, "dinding"):
            return False
        if wid not in geo:
            out.rejected.append(f"dinding {wid} sudah dihapus atau digabung oleh aksi lain di rencana ini")
            return False
        return True

    shift: dict[str, float] = {}  # opening offsets added on walls whose a end moved

    by_type: dict[str, list] = {}
    for act in plan.actions:
        by_type.setdefault(act.type, []).append(act)

    for act in by_type.get("delete_wall", []):
        if known(act.id, walls, "dinding") and act.id not in out.deleted:
            buckets["del"].append({"op": "delete_wall", "id": act.id, "reason": reason})
            out.deleted.append(act.id)
            geo.pop(act.id, None)
    for act in by_type.get("delete_opening", []):
        if known(act.id, openings, "bukaan"):
            buckets["del"].append({"op": "delete_opening", "id": act.id, "reason": reason})
            out.deleted.append(act.id)

    for act in by_type.get("merge_walls", []):
        if not all(known(i, walls, "dinding") for i in act.ids):
            continue
        _merge([walls[i] for i in act.ids], spec, reason, binary, px_to_mm, buckets, out, geo)

    for act in by_type.get("split_wall", []):
        if not alive(act.id):
            continue
        a, b = geo[act.id]
        ux, uy, length = _unit(a, b)
        t = (act.at[0] - a[0]) * ux + (act.at[1] - a[1]) * uy
        on = [o for o in spec.openings if o.wall_id == act.id]
        if not SPLIT_END_MM <= t <= length - SPLIT_END_MM:
            out.rejected.append(f"titik pecah {act.id} terlalu dekat ke ujung dinding")
        elif any(o.offset < t < o.offset + o.width for o in on):
            out.rejected.append(f"titik pecah {act.id} memotong bukaan")
        else:
            buckets["split"].append({"op": "split_wall", "id": act.id, "at_offset": round(t)})
            p = (a[0] + ux * t, a[1] + uy * t)
            geo[act.id] = (a, p)

    for act in by_type.get("extend_wall", []):
        if not (alive(act.id) and alive(act.to)):
            continue
        a, b = geo[act.id]
        c, d = geo[act.to]
        ux, uy, _ = _unit(a, b)
        vx, vy, _ = _unit(c, d)
        cross = ux * vy - uy * vx
        if abs(cross) < math.sin(math.radians(PARALLEL_DEG)):
            out.rejected.append(f"{act.id} sejajar dengan {act.to}, tidak bisa disambung")
            continue
        s = ((c[0] - a[0]) * vy - (c[1] - a[1]) * vx) / cross
        x = (a[0] + ux * s, a[1] + uy * s)
        end = "a" if math.dist(a, x) < math.dist(b, x) else "b"
        if math.dist(a if end == "a" else b, x) > EXTEND_MAX_MM:
            out.rejected.append(f"ujung {act.id} harus bergeser lebih dari {EXTEND_MAX_MM} mm ke {act.to}")
            continue
        p = _pt(*x)
        buckets["extend"].append({"op": "move_wall", "id": act.id, end: p})
        if end == "a":
            # offsets run from a: keep every opening where it is on the drawing
            moved_by = -((p[0] - a[0]) * ux + (p[1] - a[1]) * uy)
            shift[act.id] = shift.get(act.id, 0.0) + moved_by
            for o in (o for o in spec.openings if o.wall_id == act.id and o.id not in out.deleted):
                off = round(o.offset + shift[act.id])
                if o.category == "door":
                    buckets["opening"].append({"op": "set_door", "id": o.id, "offset": off})
                else:
                    buckets["del"].append({"op": "delete_opening", "id": o.id, "reason": reason})
                    fields = o.model_dump(include={"category", "width", "height", "sill"}, exclude_none=True)
                    buckets["opening"].append({"op": "add_opening", "wall_id": act.id, **fields, "offset": off})
        geo[act.id] = (tuple(p), b) if end == "a" else (a, tuple(p))
        na, nb = geo[act.id]
        out.moved.append({"id": act.id, "a": _pt(*na), "b": _pt(*nb)})

    for act in by_type.get("add_wall", []):
        if math.dist(act.a, act.b) < 100:
            out.rejected.append("dinding baru terlalu pendek")
            continue
        w, snapped = _snap(binary, px_to_mm, act.a, act.b, default_t)
        buckets["add"].append({"op": "add_wall", **w, "kind": "interior"})
        out.added.append({**w, "snapped": snapped})
        if not snapped:
            out.notes.append("dinding baru tidak menempel ke garis gambar, periksa posisinya (kuning)")

    for act in by_type.get("add_opening", []):
        if not alive(act.wall):
            continue
        a, b = geo[act.wall]
        ux, uy, length = _unit(a, b)
        t = (act.at[0] - a[0]) * ux + (act.at[1] - a[1]) * uy
        width = act.width or DEFAULT_WIDTH[act.category]
        gap = None
        if binary is not None and px_to_mm:
            taken = [(o.offset + shift.get(act.wall, 0.0), o.offset + o.width + shift.get(act.wall, 0.0))
                     for o in spec.openings if o.wall_id == act.wall and o.id not in out.deleted]
            gap = _gap(binary, px_to_mm, a, ux, uy, length, t, walls[act.wall].thickness / 2 + 30, taken)
        snapped = gap is not None
        start, width = (gap[0], gap[1] - gap[0]) if gap else (t - width / 2, width)
        width = round(width / 10) * 10
        if width > length - 2 * END_CLEAR_MM:
            out.rejected.append(f"{act.category} {width} mm tidak muat di {act.wall}")
            continue
        start = round(min(max(start, END_CLEAR_MM), length - END_CLEAR_MM - width) / 10) * 10
        op = {"op": "add_opening", "wall_id": act.wall, "category": act.category, "offset": start, "width": width}
        if act.category == "door":
            double = width >= 1500
            op |= {"door_type": "double_swing" if double else "single_swing", "hinge": "both" if double else "start",
                   "swing": "left"}
        buckets["opening"].append(op)
        out.openings.append({"a": _pt(a[0] + ux * start, a[1] + uy * start),
                             "b": _pt(a[0] + ux * (start + width), a[1] + uy * (start + width)),
                             "category": act.category, "snapped": snapped})
        if not snapped:
            out.notes.append(f"{act.category} baru di {act.wall} tidak menempel ke celah gambar, periksa posisinya")

    for act in by_type.get("set_door", []):
        if not known(act.id, openings, "pintu"):
            continue
        d = openings[act.id]
        if d.category != "door":
            out.rejected.append(f"{act.id} bukan pintu")
            continue
        op = {"op": "set_door", "id": act.id}
        if act.width is not None:
            op |= {"width": round(act.width), "offset": round(d.offset - (act.width - d.width) / 2)}
        op |= {k: v for k in ("swing", "hinge", "door_type") if (v := getattr(act, k)) is not None}
        buckets["opening"].append(op)
        w = spec.walls[[x.id for x in spec.walls].index(d.wall_id)]
        ux, uy, _ = _unit(w.a, w.b)
        o, wd = op.get("offset", d.offset), op.get("width", d.width)
        out.openings.append({"a": _pt(w.a[0] + ux * o, w.a[1] + uy * o),
                             "b": _pt(w.a[0] + ux * (o + wd), w.a[1] + uy * (o + wd)), "category": "door",
                             "snapped": True})

    room_types = set(get_args(RoomType))
    for act in plan.actions:
        if act.type not in ("set_room_type", "rename_room"):
            continue
        if act.at is not None and box.covers(SPoint(act.at)):
            at = _pt(*act.at)
        elif known(act.room, rooms, "ruang"):
            at = list(rep_point(rooms[act.room]))
        else:
            continue
        if act.type == "set_room_type":
            value = act.value if act.value in room_types else "other"
            if value != act.value:
                out.notes.append(f"tipe ruang '{act.value}' tidak dikenal, dipakai 'other'")
            buckets["room"].append({"op": "set_room_type_at", "at": at, "type": value})
        else:
            buckets["room"].append({"op": "rename_room_at", "at": at, "name": act.name})

    out.ops = [op for k in ("del", "merge", "split", "extend", "add", "opening", "room") for op in buckets[k]]
    return out


def _merge(ws, spec: Spec, reason: str, binary, px_to_mm, buckets, out: Translation, geo) -> None:
    ids = [w.id for w in ws]
    first = ws[0]
    ux, uy, _ = _unit(first.a, first.b)
    nx, ny = -uy, ux
    for w in ws[1:]:
        wx, wy, _ = _unit(w.a, w.b)
        if abs(wx * uy - wy * ux) > math.sin(math.radians(PARALLEL_DEG)):
            out.rejected.append(f"{w.id} tidak sejajar dengan {first.id}, tidak bisa digabung")
            return
    side = [((p[0] - first.a[0]) * nx + (p[1] - first.a[1]) * ny) for w in ws for p in (w.a, w.b)]
    max_t = max(w.thickness for w in ws)
    if max(side) - min(side) <= COLLINEAR_MM:
        buckets["merge"].append({"op": "merge_walls", "ids": ids, "reason": reason})
        keep = min(ws, key=lambda w: id_key(w.id))  # as core.spec.ops._merge_walls
        kx, ky, _ = _unit(keep.a, keep.b)
        ts = [(p[0] - keep.a[0]) * kx + (p[1] - keep.a[1]) * ky for w in ws for p in (w.a, w.b)]
        for w in ws:
            geo.pop(w.id, None)
        geo[keep.id] = tuple((keep.a[0] + kx * t, keep.a[1] + ky * t) for t in (min(ts), max(ts)))
        return
    if max(side) - min(side) > max_t + MERGE_GAP_MM:
        out.rejected.append(f"{', '.join(ids)} terlalu jauh untuk digabung ({max(side) - min(side):.0f} mm)")
        return
    along = [((p[0] - first.a[0]) * ux + (p[1] - first.a[1]) * uy) for w in ws for p in (w.a, w.b)]
    mid = (max(side) + min(side)) / 2
    t0, t1 = min(along), max(along)
    a = (first.a[0] + ux * t0 + nx * mid, first.a[1] + uy * t0 + ny * mid)
    b = (first.a[0] + ux * t1 + nx * mid, first.a[1] + uy * t1 + ny * mid)
    w, snapped = _snap(binary, px_to_mm, a, b, round(max_t))
    if not snapped:
        w["thickness"] = round(max_t)
    kind = "exterior" if any(x.kind == "exterior" for x in ws) else first.kind
    # openings of the merged walls ride on the new wall, projected onto it
    na, nb = w["a"], w["b"]
    vx, vy, length = _unit(na, nb)
    carried = []
    for o in (o for o in spec.openings if o.wall_id in ids and o.id not in out.deleted):
        src = next(x for x in ws if x.id == o.wall_id)
        sx, sy, _ = _unit(src.a, src.b)
        c = (src.a[0] + sx * (o.offset + o.width / 2), src.a[1] + sy * (o.offset + o.width / 2))
        start = (c[0] - na[0]) * vx + (c[1] - na[1]) * vy - o.width / 2
        if END_CLEAR_MM <= start and start + o.width <= length - END_CLEAR_MM:
            fields = o.model_dump(include={"category", "width", "height", "sill", "door_type", "hinge", "swing",
                                           "leaf_split"}, exclude_none=True)
            if sx * vx + sy * vy < 0:  # hinge/swing are relative to a->b; the new wall runs the other way
                fields = {**fields, **({"hinge": FLIP[o.hinge]} if o.hinge in FLIP else {}),
                          **({"swing": FLIP[o.swing]} if o.swing in FLIP else {})}
            carried.append({**fields, "offset": round(start)})
        else:
            out.notes.append(f"{o.id} tidak muat di dinding gabungan dan tidak dibawa")
    for i in ids:
        buckets["del"].append({"op": "delete_wall", "id": i, "reason": reason})
        out.deleted.append(i)
        geo.pop(i, None)
    buckets["add"].append({"op": "add_wall", **w, "kind": kind, **({"openings": carried} if carried else {})})
    out.added.append({**w, "snapped": snapped})
