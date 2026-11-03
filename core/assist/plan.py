"""The LLM's plan for an area (design §6.2) and its deterministic translation into spec ops (§6.3).

The LLM names elements and rough positions; geometry comes from the spec and the drawing: merged walls on their
midline, new walls and openings snapped to the page binary, corners closed on the other wall's axis.
"""

import math
from dataclasses import dataclass, field
from typing import Annotated, Literal, get_args

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import LineString
from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon as SPolygon
from shapely.geometry import box as sbox
from shapely.ops import unary_union

from core.assist.context import AreaContext, rep_point
from core.extraction.geometry.stairs import detect_stairs
from core.extraction.geometry.strokes import extract_strokes
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
RISER_MM, GOING_MM = 175, 280  # a designed stair: riser target and tread depth (validation V019: 150-200 / >= 250)
STAIR_WIDTH = (800, 2500)
STAIR_GAP_MM = 100  # between the two flights of a U stair
PLACE_STEP_MM = 100
UP = {"north": (0, 1), "south": (0, -1), "east": (1, 0), "west": (-1, 0)}
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


class DeleteStair(_A):
    type: Literal["delete_stair"]
    id: str


class DeleteOpening(_A):
    type: Literal["delete_opening"]
    id: str


class AddStair(_A):
    type: Literal["add_stair"]
    room: str | None = None
    at: tuple[float, float] | None = None
    shape: Literal["straight", "u"] | None = None
    up: Literal["north", "south", "east", "west"] | None = None
    width: float | None = None


class FillItem(_A):
    template: str
    count: int | None = None


class FillOptions(_A):
    containment: bool | None = None
    cooling: Literal["crac", "inrow"] | None = None
    rows: Literal["auto", "ns", "ew"] | None = None


class FillRoom(_A):
    type: Literal["fill_room"]
    room: str | None = None
    layout: Literal["rows", "lineup"] | None = None
    items: list[FillItem] = Field(min_length=1)
    options: FillOptions = FillOptions()


class PlaceDrawn(_A):
    type: Literal["place_drawn"]
    boxes: list[str] = Field(min_length=1)
    template: str


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
    DeleteWall | MergeWalls | AddWall | ExtendWall | SplitWall | AddOpening | SetDoor | DeleteOpening | AddStair
    | DeleteStair | FillRoom | PlaceDrawn | SetRoomType | RenameRoom,
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
    stairs: list[dict] = field(default_factory=list)  # {flights, landings, snapped}
    objects: list[dict] = field(default_factory=list)  # {template_id, corners, front, zones, z, snapped}
    notes: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


@dataclass
class Interior:
    """What generate interior needs beside the spec: the template library, the rules, the boxes the user pointed at."""
    library: dict
    rules: object
    drawn: list[dict] = field(default_factory=list)
    ceiling: float = 3000.0


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


EQUIPMENT = frozenset({"fill_room", "place_drawn"})
ARCHITECTURE = frozenset({"delete_wall", "merge_walls", "add_wall", "extend_wall", "split_wall", "add_opening",
                          "set_door", "delete_opening", "add_stair", "delete_stair", "set_room_type", "rename_room"})
WRONG_MODE = {"fill_room": "isi ruang di mode Instalasi & Interior", "place_drawn": "isi ruang di mode Instalasi & Interior"}


def translate(plan: AreaPlan, spec: Spec, ctx: AreaContext, instruction: str, binary: np.ndarray | None,
              px_to_mm: list | None, interior: Interior | None = None, allowed: frozenset[str] | None = None) -> Translation:
    out = Translation()
    if allowed is not None:  # layout mode edits the architecture, Instalasi & Interior the equipment
        for a in plan.actions:
            if a.type not in allowed:
                out.rejected.append(f"{a.type}: {WRONG_MODE.get(a.type, 'ubah denah di mode Layout')}")
        plan = plan.model_copy(update={"actions": [a for a in plan.actions if a.type in allowed]})
    reason = "asisten: " + (instruction.strip()[:60] or "perbaiki area")
    walls = {w.id: w for w in spec.walls if w.id in ctx.wall_ids}
    openings = {o.id: o for o in spec.openings if o.id in ctx.opening_ids}
    rooms = {r.id: r for r in spec.rooms if r.id in ctx.room_ids}
    geo = {wid: (tuple(w.a), tuple(w.b)) for wid, w in walls.items()}  # wall axes as the ops so far leave them
    default_t = round(spec.meta.defaults.wall_thickness)
    box = sbox(*ctx.box)
    buckets: dict[str, list[dict]] = {
        k: [] for k in ("del", "merge", "split", "extend", "add", "opening", "stair", "object", "room")}

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
    stairs = {st.id: st for st in spec.stairs if st.id in ctx.stair_ids}
    for act in by_type.get("delete_stair", []):
        if known(act.id, stairs, "tangga") and act.id not in out.deleted:
            buckets["del"].append({"op": "delete_stair", "id": act.id, "reason": reason})
            out.deleted.append(act.id)
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

    for act in by_type.get("add_stair", []):
        if act.room is not None and act.room not in rooms:
            known(act.room, rooms, "ruang")
            continue
        region = box if act.room is None else SPolygon(rooms[act.room].polygon, rooms[act.room].holes).intersection(box)
        stair = None
        if binary is not None and px_to_mm:
            stair, dup = _drawn_stair(binary, px_to_mm, region, spec, set(out.deleted))
            if stair is None and dup:
                out.rejected.append(f"tangga di gambar sudah ada di spec ({dup}); ubah lewat panel tangga")
                continue
        if stair is None:
            ftf = spec.meta.defaults.floor_to_floor
            # the room may be cut up by the very stair lines it should hold (test-2 R48/R49): then the marked box
            stair = _design_stair(region, ftf, act) or (act.room and _design_stair(box, ftf, act)) or None
            if stair is None:
                stair, note = _fill_box(box, ftf, act)
                if stair is None:
                    n = math.ceil(ftf / RISER_MM)
                    w = min(max(act.width or 1200, STAIR_WIDTH[0]), STAIR_WIDTH[1])
                    out.rejected.append(
                        f"tangga tidak muat di {'ruang ' + act.room if act.room else 'area'}: tangga U standar butuh "
                        f"±{(2 * w + STAIR_GAP_MM) / 1000:.1f} × {(math.ceil(n / 2) * GOING_MM + w) / 1000:.1f} m, "
                        f"lurus {w / 1000:.1f} × {n * GOING_MM / 1000:.1f} m; jangan kecilkan lebarnya, tandai area "
                        "tangga yang lebih besar")
                    continue
                out.notes.append(note)
            out.notes.append("tangga baru dirancang, tidak dari gambar: periksa posisi dan arah naiknya (kuning)")
        elif act.up:
            stair = _orient(stair, act.up)
        buckets["stair"].append({"op": "add_stair", "flights": stair["flights"], "landings": stair["landings"]})
        out.stairs.append(stair)

    if by_type.get("fill_room") or by_type.get("place_drawn"):
        if interior is None:
            out.rejected.append("isi ruang tidak tersedia: library template tidak terbaca")
        else:
            buckets["object"] = _objects(by_type, spec, ctx, interior, out)

    out.ops = [op for k in ("del", "merge", "split", "extend", "add", "opening", "stair", "object", "room")
               for op in buckets[k]]
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


def _stair_dict(flights: list[dict], landings: list, snapped: bool) -> dict:
    return {"flights": flights, "landings": landings, "snapped": snapped}


def _drawn_stair(binary, px_to_mm, region, spec: Spec, gone: set[str] = frozenset()) -> tuple[dict | None, str | None]:
    """The stair the drawing shows in the region (the pipeline's tread detector on a crop), and the ID of a spec stair
    it duplicates, if any."""
    a, b, c, d, e, f = px_to_mm
    s = math.hypot(a, d)
    to_px = px_from_mm(px_to_mm)
    x0, y0, x1, y1 = region.buffer(300).bounds
    xs, ys = zip(*[to_px(x, y) for x in (x0, x1) for y in (y0, y1)])
    h, w = binary.shape[:2]
    c0, r0 = max(0, int(min(xs))), max(0, int(min(ys)))
    c1, r1 = min(w, math.ceil(max(xs))), min(h, math.ceil(max(ys)))
    crop = binary[r0:r1, c0:c1]
    if crop.size == 0:
        return None, None
    stairs, _ = detect_stairs(extract_strokes(crop, 0, s), [], crop, s)
    mm = lambda p: [round(a * (p[0] + c0) + b * (p[1] + r0) + c), round(d * (p[0] + c0) + e * (p[1] + r0) + f)]
    existing = [(st.id, LineString([fl.start, fl.end])) for st in spec.stairs if st.id not in gone for fl in st.flights]
    dup = None
    for st in stairs:
        flights = [{"start": mm(fl["start"]), "end": mm(fl["end"]), "width": round(fl["width_px"] * s),
                    "risers": fl["risers"]} for fl in st["flights"]]
        mids = [SPoint((fl["start"][0] + fl["end"][0]) / 2, (fl["start"][1] + fl["end"][1]) / 2) for fl in flights]
        if not all(region.buffer(300).covers(m) for m in mids):
            continue
        hit = next((sid for sid, line in existing for m in mids if line.distance(m) <= 500), None)
        if hit:
            dup = dup or hit
            continue
        landings = [[mm(p) for p in poly] for poly in st["landings"]]
        return _stair_dict(flights, landings, True), None
    return None, dup


def _orient(stair: dict, up: str) -> dict:
    """Reverse the climb when the first flight runs against the asked up direction."""
    ux, uy = UP[up]
    f0 = stair["flights"][0]
    if (f0["end"][0] - f0["start"][0]) * ux + (f0["end"][1] - f0["start"][1]) * uy >= 0:
        return stair
    flights = [{**fl, "start": fl["end"], "end": fl["start"]} for fl in reversed(stair["flights"])]
    return {**stair, "flights": flights}


def _design_stair(region, floor_to_floor: float, act: AddStair) -> dict | None:
    """A new stair fitted in the region: straight when it fits, else a U stair; nearest to `at` (else the region's
    centre). Built with +y as up, turned to `up`, then placed on a 100 mm grid."""
    n = max(2, math.ceil(floor_to_floor / RISER_MM))
    w = min(max(act.width or 1200, STAIR_WIDTH[0]), STAIR_WIDTH[1])
    x0, y0, x1, y1 = region.bounds
    ups = [act.up] if act.up else (["north", "east"] if y1 - y0 >= x1 - x0 else ["east", "north"])
    shapes = [act.shape] if act.shape else ["straight", "u"]
    target = act.at if act.at is not None else (region.centroid.x, region.centroid.y)
    inside = region.buffer(1)
    for shape in shapes:
        if shape == "straight":
            flights = [((w / 2, 0), (w / 2, n * GOING_MM), n)]
            landings = []
        else:
            n1 = math.ceil(n / 2)
            run = n1 * GOING_MM
            x2 = w + STAIR_GAP_MM + w / 2
            flights = [((w / 2, 0), (w / 2, run), n1), ((x2, run), (x2, (n1 - (n - n1)) * GOING_MM), n - n1)]
            landings = [[(0, run), (2 * w + STAIR_GAP_MM, run), (2 * w + STAIR_GAP_MM, run + w), (0, run + w)]]
        for up in ups:
            ux, uy = UP[up]
            turn = lambda p, ux=ux, uy=uy: (p[0] * uy + p[1] * ux, -p[0] * ux + p[1] * uy)  # local +y onto (ux, uy)
            fl = [(turn(a), turn(b), r) for a, b, r in flights]
            la = [[turn(p) for p in poly] for poly in landings]
            local = unary_union([LineString([a, b]).buffer(w / 2, cap_style="flat") for a, b, _ in fl]
                                + [SPolygon(poly) for poly in la])
            lx0, ly0, lx1, ly1 = local.bounds
            best = None
            for px in np.arange(x0, x1 - (lx1 - lx0) + 1, PLACE_STEP_MM):
                for py in np.arange(y0, y1 - (ly1 - ly0) + 1, PLACE_STEP_MM):
                    dx, dy = px - lx0, py - ly0
                    cx, cy = (lx0 + lx1) / 2 + dx, (ly0 + ly1) / 2 + dy
                    dist = math.dist((cx, cy), target)
                    if (best is None or dist < best[0]) and inside.covers(
                            SPolygon([(lx0 + dx, ly0 + dy), (lx1 + dx, ly0 + dy), (lx1 + dx, ly1 + dy),
                                      (lx0 + dx, ly1 + dy)])):
                        best = (dist, dx, dy)
            if best is None:
                continue
            _, dx, dy = best
            at = lambda p, dx=dx, dy=dy: [round(p[0] + dx), round(p[1] + dy)]
            return _stair_dict([{"start": at(a), "end": at(b), "width": round(w), "risers": r} for a, b, r in fl],
                               [[at(p) for p in poly] for poly in la], False)
    return None


FILL_WIDTH_MIN = 600  # a stair fitted to the marked box: narrowest flight
FILL_GOING_MIN = 200  # ... and shallowest tread; below that the box cannot be a stair


def _fill_box(box, floor_to_floor: float, act: AddStair) -> tuple[dict | None, str | None]:
    """When no standard stair fits, a stair filling the user's box exactly (the drawn stair is usually what the box
    marks): a U stair of two flights across the box, else one straight flight. Treads shrink to the box length."""
    x0, y0, x1, y1 = box.bounds
    up = act.up or ("north" if y1 - y0 >= x1 - x0 else "east")
    ux, uy = UP[up]
    length, cross = (y1 - y0, x1 - x0) if uy else (x1 - x0, y1 - y0)
    n = max(2, math.ceil(floor_to_floor / RISER_MM))
    shapes = [act.shape] if act.shape else ["u", "straight"]
    for shape in shapes:
        if shape == "u":
            w = (cross - STAIR_GAP_MM) / 2
            n1 = math.ceil(n / 2)
            going = (length - w) / n1
            if w < FILL_WIDTH_MIN or going < FILL_GOING_MIN:
                continue
            run = n1 * going
            flights = [((w / 2, 0), (w / 2, run), n1), ((cross - w / 2, run), (cross - w / 2, run - (n - n1) * going), n - n1)]
            landings = [[(0, run), (cross, run), (cross, length), (0, length)]]
        else:
            w, going = min(cross, STAIR_WIDTH[1]), length / n
            if w < FILL_WIDTH_MIN or going < FILL_GOING_MIN:
                continue
            flights, landings = [((cross / 2, 0), (cross / 2, length), n)], []
        turn = lambda p: (p[0] * uy + p[1] * ux, -p[0] * ux + p[1] * uy)
        corners = [turn(p) for p in ((0, 0), (cross, 0), (cross, length), (0, length))]
        dx, dy = x0 - min(p[0] for p in corners), y0 - min(p[1] for p in corners)
        at = lambda p, dx=dx, dy=dy: [round(p[0] + dx), round(p[1] + dy)]
        stair = _stair_dict([{"start": at(turn(a)), "end": at(turn(b)), "width": round(w), "risers": r}
                             for a, b, r in flights], [[at(turn(p)) for p in poly] for poly in landings], False)
        note = (f"tangga mengikuti kotak: lebar flight {w:.0f} mm, injakan {going:.0f} mm"
                + (" (di bawah standar 250 mm)" if going < 250 else "")
                + (" (lebar di bawah 800 mm)" if w < STAIR_WIDTH[0] else ""))
        return stair, note
    return None, None


def _room_at(spec: Spec, ctx: AreaContext, x: float, y: float) -> str | None:
    pt = SPoint(x, y)
    hit = next((r.id for r in spec.rooms if SPolygon(r.polygon, r.holes).covers(pt)), None)
    if hit:
        return hit
    box = sbox(*ctx.box)
    near = [(SPolygon(r.polygon, r.holes).intersection(box).area, r.id) for r in spec.rooms if r.id in ctx.room_ids]
    return max(near)[1] if near and max(near)[0] > 0 else None


def _preview(p) -> dict:
    fp = list(p.footprint().exterior.coords)[:4]
    f = p.front()
    reach = p.dims[1] / 2 + 400
    return {"template_id": p.template_id, "corners": [[round(x), round(y)] for x, y in fp],
            "front": [[round(p.x), round(p.y)], [round(p.x + f[0] * reach), round(p.y + f[1] * reach)]],
            "zones": [], "z": round(p.z), "snapped": p.source == "drawing"}


def _objects(by_type: dict, spec: Spec, ctx: AreaContext, it: Interior, out: Translation) -> list[dict]:
    """fill_room / place_drawn through the interior engine; O001 is a problem for the revision round."""
    from core.interior.check import check
    from core.interior.devices import fill
    from core.interior.drawn import place_drawn
    from core.interior.library import layout_kind
    from core.interior.space import Space, room_space

    lib, rules = it.library, it.rules
    groups = []  # (placements, space)
    for act in by_type.get("fill_room", []):
        rid = act.room if act.room in {r.id for r in spec.rooms} else None
        if rid is None:
            c = sbox(*ctx.box).centroid
            rid = _room_at(spec, ctx, c.x, c.y)
        if rid is None:
            out.rejected.append("tidak ada ruang di area untuk diisi")
            continue
        items = {}
        for item in act.items:
            if item.template not in lib:
                out.rejected.append(f"template {item.template} tidak ada di library")
            else:
                items[item.template] = item.count
        if not items:
            continue
        space = room_space(spec, rid, ctx.box, it.ceiling, lib, rules)
        lay = fill(space, lib, items, act.options.model_dump(), act.layout or layout_kind(list(items), lib), rules)
        # a unit that does not fit but has a same-category alternative that does: a problem, so the revision swaps it
        out.rejected += [n for n in lay.notes if "; yang muat dari kategori" in n]
        out.notes += [n for n in lay.notes if "; yang muat dari kategori" not in n]
        groups.append((lay.placements, space))
    boxes = {b["id"]: b for b in it.drawn}
    for act in by_type.get("place_drawn", []):
        if act.template not in lib:
            out.rejected.append(f"template {act.template} tidak ada di library")
            continue
        chosen = []
        for kid in act.boxes:
            if kid in boxes:
                chosen.append(boxes[kid])
            else:
                out.rejected.append(f"kotak {kid} tidak ada (kotak yang ditunjuk: {', '.join(boxes) or 'belum ada'})")
        if not chosen:
            continue
        rid = _room_at(spec, ctx, *chosen[0]["center"])
        space = room_space(spec, rid, None, it.ceiling, lib, rules) if rid else None
        ps, notes = place_drawn(chosen, lib[act.template], space, rules)
        out.notes += notes
        groups.append((ps, space))
    placements = [p for ps, _ in groups for p in ps]
    issues = []
    for ps, space in groups:
        if space is not None:
            issues += check(ps, space, lib, rules)
    whole = Space(sbox(*ctx.box).buffer(1e6))  # cross-group overlaps (and drawn boxes outside any room)
    issues += [i for i in check(placements, whole, lib, rules) if i["code"] == "O001"]
    seen = set()
    for i in issues:
        if i["message"] in seen:
            continue
        seen.add(i["message"])
        (out.rejected if i["severity"] == "error" else out.notes).append(i["message"])
    out.objects = [_preview(p) for p in placements]
    return [p.op() for p in placements]
