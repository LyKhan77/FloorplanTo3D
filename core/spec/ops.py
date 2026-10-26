"""Spec operations (PRD/03 §11). `apply` is pure and atomic: it works on a deep copy and raises OpError."""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from core.spec.derive import derive, id_key
from core.spec.ids import seed_id_seq, take_id
from core.spec.models import (
    Defaults,
    Flight,
    Mm,
    Opening,
    PlacedObject,
    Point,
    Polygon,
    Provenance,
    ProvenanceLogEntry,
    RoomType,
    Spec,
    Stair,
    Wall,
)
from core.spec.rooms import rebuild_rooms

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
WallKind = Literal["exterior", "interior", "partition", "glass", "low"]
DoorType = Literal["single_swing", "double_swing", "sliding", "opening", "rolling"]
PARALLEL_TOL_DEG = 1.5


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Optional op fields mean "leave unchanged"; an explicit null is only allowed where the target field is nullable.
    nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _no_null_on_required(self):
        bad = [k for k in self.model_fields_set if getattr(self, k) is None and k not in self.nullable]
        if bad:
            raise ValueError(f"{', '.join(sorted(bad))} must not be null")
        return self


class AddObject(_Op):
    op: Literal["add_object"]
    template_id: str
    template_version: str
    position: tuple[Mm, Mm, Mm]
    rotation: float = 0
    dims: tuple[Mm, Mm, Mm]
    label: str | None = None


class UpdateObject(_Op):
    op: Literal["update_object"]
    nullable: ClassVar[frozenset[str]] = frozenset({"label"})
    id: str
    position: tuple[Mm, Mm, Mm] | None = None
    rotation: float | None = None
    dims: tuple[Mm, Mm, Mm] | None = None
    label: str | None = None
    locked: bool | None = None


class DeleteObject(_Op):
    op: Literal["delete_object"]
    id: str


class SetWallHeight(_Op):
    op: Literal["set_wall_height"]
    nullable: ClassVar[frozenset[str]] = frozenset({"height"})
    id: str  # wall ID or "*"
    height: Mm | None


class SetDefault(_Op):
    op: Literal["set_default"]
    key: str
    value: Mm


class RenameRoom(_Op):
    op: Literal["rename_room"]
    id: str
    name: str


class SetRoomType(_Op):
    op: Literal["set_room_type"]
    id: str
    type: RoomType


class DeleteWall(_Op):
    op: Literal["delete_wall"]
    id: str
    reason: Reason


class MergeWalls(_Op):
    op: Literal["merge_walls"]
    ids: list[str] = Field(min_length=2)
    reason: Reason


class SplitWall(_Op):
    op: Literal["split_wall"]
    id: str
    at_offset: Mm


class MoveWall(_Op):
    op: Literal["move_wall"]
    id: str
    a: Point | None = None
    b: Point | None = None
    thickness: Mm | None = None
    kind: WallKind | None = None


class AddWall(_Op):
    op: Literal["add_wall"]
    a: Point
    b: Point
    thickness: Mm
    kind: WallKind


class SetDoor(_Op):
    op: Literal["set_door"]
    nullable: ClassVar[frozenset[str]] = frozenset({"door_type", "hinge", "swing", "height"})
    id: str
    door_type: DoorType | None = None
    hinge: Literal["start", "end", "both"] | None = None
    swing: Literal["left", "right"] | None = None
    width: Mm | None = None
    offset: Mm | None = None
    height: Mm | None = None


class DeleteOpening(_Op):
    op: Literal["delete_opening"]
    id: str
    reason: Reason


class AddOpening(_Op):
    op: Literal["add_opening"]
    nullable: ClassVar[frozenset[str]] = frozenset({"height", "sill", "door_type", "hinge", "swing", "leaf_split"})
    wall_id: str
    category: Literal["door", "window"]
    offset: Mm
    width: Mm
    height: Mm | None = None
    sill: Mm | None = None
    door_type: DoorType | None = None
    hinge: Literal["start", "end", "both"] | None = None
    swing: Literal["left", "right"] | None = None
    leaf_split: float | None = None


class SetStair(_Op):
    op: Literal["set_stair"]
    nullable: ClassVar[frozenset[str]] = frozenset({"top_z"})
    id: str
    flights: list[Flight] | None = Field(None, min_length=1)
    landings: list[Polygon] | None = None
    top_z: Mm | None = None


class DeleteStair(_Op):
    op: Literal["delete_stair"]
    id: str
    reason: Reason


class AddStair(_Op):
    op: Literal["add_stair"]
    nullable: ClassVar[frozenset[str]] = frozenset({"top_z"})
    flights: list[Flight] = Field(min_length=1)
    landings: list[Polygon] = []
    top_z: Mm | None = None


SpecOp = Annotated[
    AddObject | UpdateObject | DeleteObject | SetWallHeight | SetDefault | RenameRoom | SetRoomType | DeleteWall | MergeWalls | SplitWall | MoveWall | AddWall | SetDoor | DeleteOpening | AddOpening | SetStair | DeleteStair | AddStair,
    Field(discriminator="op"),
]
_OP_ADAPTER: TypeAdapter = TypeAdapter(SpecOp)
GEOMETRY_OPS = {"delete_wall", "merge_walls", "split_wall", "move_wall", "add_wall"}


class OpError(Exception):
    def __init__(self, index: int, op: str, message: str):
        super().__init__(f"op[{index}] {op}: {message}")
        self.index, self.op, self.message = index, op, message


@dataclass
class Ctx:
    by: str
    version: int

    def prov(self, prev: Provenance | None = None) -> Provenance:
        source = "cv" if self.by == "pipeline" else self.by
        confidence = 1.0 if self.by in ("editor", "manual") or prev is None else prev.confidence
        return Provenance(source=source, confidence=confidence, changed_in=self.version)


def _find(items: list, eid: str):
    for it in items:
        if it.id == eid:
            return it
    raise ValueError(f"unknown id {eid}")


def _log(s: Spec, ctx: Ctx, op: str, eid: str | None, reason: str | None = None) -> None:
    s.provenance_log.append(ProvenanceLogEntry(op=op, id=eid, by=ctx.by, reason=reason))


def _touch(el: Any, ctx: Ctx, **changes: Any) -> None:
    for k, v in changes.items():
        setattr(el, k, v)
    el.provenance = ctx.prov(el.provenance)


def _set_fields(op: _Op, skip: set[str]) -> dict[str, Any]:
    return {k: getattr(op, k) for k in op.model_fields_set if k not in skip}


def _unit(w: Wall) -> tuple[float, float, float]:
    dx, dy = w.b[0] - w.a[0], w.b[1] - w.a[1]
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError(f"wall {w.id} has zero length")
    return dx / length, dy / length, length


def _pt(x: float, y: float) -> tuple[int, int]:
    return (round(x), round(y))


# --- handlers -------------------------------------------------------------------------------------


def _add_object(s: Spec, op: AddObject, ctx: Ctx) -> None:
    oid = take_id(s, "O")
    fields = op.model_dump(exclude={"op"})
    s.objects.append(PlacedObject(id=oid, provenance=ctx.prov(), **fields))
    _log(s, ctx, op.op, oid)


def _update_object(s: Spec, op: UpdateObject, ctx: Ctx) -> None:
    _touch(_find(s.objects, op.id), ctx, **_set_fields(op, {"op", "id"}))
    _log(s, ctx, op.op, op.id)


def _delete_object(s: Spec, op: DeleteObject, ctx: Ctx) -> None:
    s.objects.remove(_find(s.objects, op.id))
    _log(s, ctx, op.op, op.id)


def _set_wall_height(s: Spec, op: SetWallHeight, ctx: Ctx) -> None:
    for w in s.walls if op.id == "*" else [_find(s.walls, op.id)]:
        _touch(w, ctx, height=op.height)
    _log(s, ctx, op.op, op.id)


def _set_default(s: Spec, op: SetDefault, ctx: Ctx) -> None:
    if op.key not in Defaults.model_fields:
        raise ValueError(f"unknown default {op.key}")
    s.meta.defaults = Defaults.model_validate({**s.meta.defaults.model_dump(), op.key: op.value})
    _log(s, ctx, op.op, None, f"{op.key}={op.value}")


def _rename_room(s: Spec, op: RenameRoom, ctx: Ctx) -> None:
    _touch(_find(s.rooms, op.id), ctx, name=op.name)
    _log(s, ctx, op.op, op.id)


def _set_room_type(s: Spec, op: SetRoomType, ctx: Ctx) -> None:
    _touch(_find(s.rooms, op.id), ctx, type=op.type)
    _log(s, ctx, op.op, op.id)


def _delete_wall(s: Spec, op: DeleteWall, ctx: Ctx) -> None:
    s.walls.remove(_find(s.walls, op.id))
    for o in [o for o in s.openings if o.wall_id == op.id]:
        s.openings.remove(o)
        _log(s, ctx, "delete_opening", o.id, f"cascade: wall {op.id} deleted")
    _log(s, ctx, op.op, op.id, op.reason)


def _merge_walls(s: Spec, op: MergeWalls, ctx: Ctx) -> None:
    walls = [_find(s.walls, i) for i in op.ids]
    keep = min(walls, key=lambda w: id_key(w.id))
    ux, uy, _ = _unit(keep)
    max_t = max(w.thickness for w in walls)

    def along(p) -> float:
        return (p[0] - keep.a[0]) * ux + (p[1] - keep.a[1]) * uy

    for w in walls:
        wx, wy, _ = _unit(w)
        if abs(wx * uy - wy * ux) > math.sin(math.radians(PARALLEL_TOL_DEG)):
            raise ValueError(f"wall {w.id} is not parallel to {keep.id}")
        for p in (w.a, w.b):
            if abs((p[0] - keep.a[0]) * uy - (p[1] - keep.a[1]) * ux) > max_t:
                raise ValueError(f"wall {w.id} is not collinear with {keep.id}")
    ts = [along(p) for w in walls for p in (w.a, w.b)]
    t0, t1 = min(ts), max(ts)
    for o in s.openings:
        w = next((w for w in walls if w.id == o.wall_id), None)
        if w:
            wx, wy, _ = _unit(w)
            ends = [along((w.a[0] + wx * d, w.a[1] + wy * d)) for d in (o.offset, o.offset + o.width)]
            o.wall_id, o.offset = keep.id, round(min(ends) - t0)
            if wx * ux + wy * uy < 0:  # hinge/swing are relative to a->b; a reversed wall mirrors them
                o.hinge = {"start": "end", "end": "start"}.get(o.hinge, o.hinge)
                o.swing = {"left": "right", "right": "left"}.get(o.swing, o.swing)
    a = _pt(keep.a[0] + ux * t0, keep.a[1] + uy * t0)
    b = _pt(keep.a[0] + ux * t1, keep.a[1] + uy * t1)
    _touch(keep, ctx, a=a, b=b)
    for w in walls:
        if w is not keep:
            s.walls.remove(w)
    _log(s, ctx, op.op, keep.id, op.reason)


def _split_wall(s: Spec, op: SplitWall, ctx: Ctx) -> None:
    w = _find(s.walls, op.id)
    ux, uy, length = _unit(w)
    at = op.at_offset
    if not 0 < at < length:
        raise ValueError(f"at_offset {at} outside wall {w.id} (length {length:.0f})")
    on_wall = [o for o in s.openings if o.wall_id == w.id]
    if any(o.offset < at < o.offset + o.width for o in on_wall):
        raise ValueError(f"split at {at} crosses an opening")
    p = _pt(w.a[0] + ux * at, w.a[1] + uy * at)
    nid = take_id(s, "W")
    s.walls.append(w.model_copy(update={"id": nid, "a": p, "b": w.b, "provenance": ctx.prov(w.provenance)}))
    _touch(w, ctx, b=p)
    for o in on_wall:
        if o.offset >= at:
            o.wall_id, o.offset = nid, o.offset - at
    _log(s, ctx, op.op, op.id, f"new {nid}")


def _move_wall(s: Spec, op: MoveWall, ctx: Ctx) -> None:
    _touch(_find(s.walls, op.id), ctx, **_set_fields(op, {"op", "id"}))
    _log(s, ctx, op.op, op.id)


def _add_wall(s: Spec, op: AddWall, ctx: Ctx) -> None:
    wid = take_id(s, "W")
    s.walls.append(Wall(id=wid, a=op.a, b=op.b, thickness=op.thickness, kind=op.kind, provenance=ctx.prov()))
    _log(s, ctx, op.op, wid)


def _set_door(s: Spec, op: SetDoor, ctx: Ctx) -> None:
    d = _find(s.openings, op.id)
    if d.category != "door":
        raise ValueError(f"{op.id} is not a door")
    _touch(d, ctx, **_set_fields(op, {"op", "id"}))
    _log(s, ctx, op.op, op.id)


def _delete_opening(s: Spec, op: DeleteOpening, ctx: Ctx) -> None:
    s.openings.remove(_find(s.openings, op.id))
    _log(s, ctx, op.op, op.id, op.reason)


def _add_opening(s: Spec, op: AddOpening, ctx: Ctx) -> None:
    _find(s.walls, op.wall_id)
    oid = take_id(s, "D" if op.category == "door" else "N")
    fields = _set_fields(op, {"op"})
    if op.sill is None:
        fields["sill"] = s.meta.defaults.window_sill if op.category == "window" else 0
    s.openings.append(Opening(id=oid, provenance=ctx.prov(), **fields))
    _log(s, ctx, op.op, oid)


def _set_stair(s: Spec, op: SetStair, ctx: Ctx) -> None:
    _touch(_find(s.stairs, op.id), ctx, **_set_fields(op, {"op", "id"}))
    _log(s, ctx, op.op, op.id)


def _delete_stair(s: Spec, op: DeleteStair, ctx: Ctx) -> None:
    s.stairs.remove(_find(s.stairs, op.id))
    _log(s, ctx, op.op, op.id, op.reason)


def _add_stair(s: Spec, op: AddStair, ctx: Ctx) -> None:
    sid = take_id(s, "S")
    s.stairs.append(Stair(id=sid, flights=op.flights, landings=op.landings, top_z=op.top_z, provenance=ctx.prov()))
    _log(s, ctx, op.op, sid)


HANDLERS: dict[str, Callable[[Spec, Any, Ctx], None]] = {
    "add_object": _add_object, "update_object": _update_object, "delete_object": _delete_object,
    "set_wall_height": _set_wall_height, "set_default": _set_default, "rename_room": _rename_room,
    "set_room_type": _set_room_type, "delete_wall": _delete_wall, "merge_walls": _merge_walls,
    "split_wall": _split_wall, "move_wall": _move_wall, "add_wall": _add_wall, "set_door": _set_door,
    "delete_opening": _delete_opening, "add_opening": _add_opening, "set_stair": _set_stair,
    "delete_stair": _delete_stair, "add_stair": _add_stair,
}


def apply(spec: Spec, ops: list[Any], by: Literal["editor", "llm", "manual", "pipeline"], version: int) -> Spec:
    work = spec.model_copy(deep=True)
    work.provenance_log = []  # the log describes the ops that form this version only
    seed_id_seq(work)
    ctx = Ctx(by=by, version=version)
    geometry_changed = False
    for i, raw in enumerate(ops):
        name = raw.get("op", "?") if isinstance(raw, dict) else getattr(raw, "op", "?")
        try:
            op = raw if isinstance(raw, _Op) else _OP_ADAPTER.validate_python(raw)
            HANDLERS[op.op](work, op, ctx)
        except (ValidationError, ValueError) as e:
            raise OpError(i, str(name), str(e)) from e
        geometry_changed |= op.op in GEOMETRY_OPS
    try:
        work = Spec.model_validate(work.model_dump())  # re-run field validation (rounding, enums)
    except ValidationError as e:
        raise OpError(len(ops) - 1, "result", str(e)) from e
    return rebuild_rooms(work) if geometry_changed else derive(work)
