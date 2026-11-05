"""Merge rooms: plans of ordinary ops. Rooms are rebuilt from walls, so a merge marks the walls between them."""
from itertools import permutations

from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as SPolygon

from core.spec.ids import seed_id_seq, take_id
from core.spec.models import Room, Spec, Wall
from core.spec.ops import OpError, apply

PROBE_MM = 50  # past the wall face, inside the room on that side
MIN_SHARED_MM = 100  # a room corner touching across a wall is not a shared stretch
END_SNAP_MM = 300  # a shared stretch this close to a wall end takes the end, not a stub


class MergeError(ValueError):
    """Why the rooms cannot merge, in words for the reviewer."""


def _shape(room: Room) -> SPolygon:
    return SPolygon(room.polygon, room.holes)


def _spans(probe: LineString, shape: SPolygon) -> list[tuple[float, float]]:
    """Where a probe runs inside a room, as distances along it."""
    cut = probe.intersection(shape)
    parts = [g for g in getattr(cut, "geoms", [cut]) if isinstance(g, LineString) and g.length]
    return [tuple(sorted(probe.project(Point(c)) for c in (g.coords[0], g.coords[-1]))) for g in parts]


def _shared(wall: Wall, rooms: list[Room]) -> list[tuple[int, int]]:
    """Stretches of a wall with one selected room on one side and another on the other, from its a end, snapped."""
    line = LineString([wall.a, wall.b])
    if not line.length:
        return []
    side = wall.thickness / 2 + PROBE_MM
    nx, ny = (wall.a[1] - wall.b[1]) / line.length * side, (wall.b[0] - wall.a[0]) / line.length * side
    left = LineString([(wall.a[0] + nx, wall.a[1] + ny), (wall.b[0] + nx, wall.b[1] + ny)])
    right = LineString([(wall.a[0] - nx, wall.a[1] - ny), (wall.b[0] - nx, wall.b[1] - ny)])
    spans = {r.id: (_spans(left, _shape(r)), _spans(right, _shape(r))) for r in rooms}
    found = sorted((max(p[0], q[0]), min(p[1], q[1])) for a, b in permutations(rooms, 2)
                   for p in spans[a.id][0] for q in spans[b.id][1])
    merged: list[list[float]] = []
    for s, e in found:
        if e - s < MIN_SHARED_MM:
            continue
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(0 if s <= END_SNAP_MM else round(s), round(line.length) if line.length - e <= END_SNAP_MM else round(e))
            for s, e in merged]


def _open_stretches(spec: Spec, rooms: list[Room]) -> list[dict]:
    ids = spec.model_copy(deep=True)  # the ids the splits will take, in the order the ops run
    seed_id_seq(ids)
    ops: list[dict] = []
    for wall in spec.walls:
        if not wall.divides_room or wall.kind == "low":
            continue
        head, length = wall.id, round(LineString([wall.a, wall.b]).length)
        for start, end in reversed(_shared(wall, rooms)):  # far first: the piece from a keeps the wall's id and offsets
            if end < length:
                ops.append({"op": "split_wall", "id": head, "at_offset": end})
                take_id(ids, "W")
            piece = head
            if start > 0:
                ops.append({"op": "split_wall", "id": head, "at_offset": start})
                piece = take_id(ids, "W")
            ops.append({"op": "set_wall_divides", "id": piece, "divides": False})
            length = start
    return ops


def _point(room: Room) -> tuple[int, int]:
    p = _shape(room).representative_point()
    return round(p.x), round(p.y)


def _prove(spec: Spec, rooms: list[Room], ops: list[dict]) -> None:
    try:
        after = apply(spec, ops, "editor", (spec.meta.version or 0) + 1)
    except OpError as e:
        if e.op == "split_wall":
            raise MergeError("Batas ruangan mengenai bukaan; geser bukaannya dulu") from e
        raise MergeError(e.message) from e
    points = [Point(_point(r)) for r in rooms]
    holders = {r.id for r in after.rooms for p in points if _shape(r).covers(p)}
    if len(holders) != 1:
        raise MergeError("Ruangan belum menyatu; periksa kolom atau dinding di antaranya")
    picked = {r.id for r in rooms}
    now = {r.id: r for r in after.rooms}
    for r in spec.rooms:
        if r.id not in picked and (r.id not in now or abs(_shape(now[r.id]).area - _shape(r).area) > 0.01 * _shape(r).area):
            raise MergeError("Ruangan tidak bisa digabung tanpa mengubah ruangan lain")


def merge_plan(spec: Spec, room_ids: list[str]) -> list[dict]:
    """The ops that make these rooms one. Name and type come from the first named room, in selection order."""
    by_id = {r.id: r for r in spec.rooms}
    if len(set(room_ids)) < 2 or any(i not in by_id for i in room_ids):
        raise MergeError("Pilih minimal dua ruangan")
    rooms = [by_id[i] for i in dict.fromkeys(room_ids)]
    ops = _open_stretches(spec, rooms)
    if not ops:
        raise MergeError("Ruangan tidak berbagi dinding")
    at = _point(rooms[0])
    first = next((r for r in rooms if r.name), rooms[0])
    if first.name:
        ops.append({"op": "rename_room_at", "at": at, "name": first.name})
    if first.type:
        ops.append({"op": "set_room_type_at", "at": at, "type": first.type})
    _prove(spec, rooms, ops)
    return ops


def unmerge_plan(spec: Spec, room_id: str) -> list[dict]:
    """The ops that give a merged room its walls back; a wall split for the merge stays split."""
    room = next((r for r in spec.rooms if r.id == room_id), None)
    shape = _shape(room) if room else None
    inside = [w for w in spec.walls if shape and not w.divides_room
              and shape.covers(Point((w.a[0] + w.b[0]) / 2, (w.a[1] + w.b[1]) / 2))]
    if not inside:
        raise MergeError("Ruangan ini bukan hasil gabungan")
    return [{"op": "set_wall_divides", "id": w.id, "divides": True} for w in inside]
