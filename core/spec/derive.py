"""Derived spec fields and shared footprint geometry (PRD/03 §5-§8b)."""

import math
import re
from dataclasses import dataclass
from typing import Literal

from shapely import affinity
from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as SPolygon

from core.spec.models import Column, Defaults, Spec, Stair, Wall


def id_key(eid: str) -> tuple[str, int]:
    """Natural sort key: W2 < W10."""
    m = re.fullmatch(r"([A-Z]+)(\d+)", eid)
    return (m[1], int(m[2])) if m else (eid, 0)


def column_footprint(col: Column) -> SPolygon:
    if col.shape == "circle":
        return Point(col.center).buffer(col.size[0] / 2, quad_segs=6)  # 24 segments
    w, d = col.size
    x, y = col.center
    box = SPolygon([(x - w / 2, y - d / 2), (x + w / 2, y - d / 2), (x + w / 2, y + d / 2), (x - w / 2, y + d / 2)])
    return affinity.rotate(box, col.rotation, origin=(x, y)) if col.rotation else box


def _host_walls(spec: Spec, wall: Wall, end: Literal["a", "b"]) -> list[Wall]:
    p = Point(wall.a if end == "a" else wall.b)
    tol = wall.thickness / 2
    return [o for o in spec.walls if o.id != wall.id and LineString([o.a, o.b]).distance(p) <= tol]


def endpoint_connected(spec: Spec, wall: Wall, end: Literal["a", "b"]) -> bool:
    """End touches another wall's centerline or a column footprint within thickness/2."""
    if _host_walls(spec, wall, end):
        return True
    p = Point(wall.a if end == "a" else wall.b)
    return any(column_footprint(c).distance(p) <= wall.thickness / 2 for c in spec.columns)


def wall_footprint(wall: Wall, spec: Spec) -> SPolygon:
    """Centerline buffered by t/2 (flat cap, mitre join).

    An end that meets another wall is extended by that wall's half thickness: an L corner closes without a
    notch, and a T stem stops at the host's far face instead of poking into the room beyond it. An end that
    only meets a column is extended by its own half thickness into the column.
    """
    (ax, ay), (bx, by) = wall.a, wall.b
    length = math.hypot(bx - ax, by - ay)
    if length == 0:
        return SPolygon()
    ux, uy = (bx - ax) / length, (by - ay) / length
    def ext(end: Literal["a", "b"]) -> float:
        hosts = _host_walls(spec, wall, end)
        if hosts:
            return max(o.thickness / 2 for o in hosts)
        # column only: push t/2 into the column (it covers the overshoot) to close hairline gaps
        return wall.thickness / 2 if endpoint_connected(spec, wall, end) else 0.0

    ext_a, ext_b = ext("a"), ext("b")
    line = LineString([(ax - ux * ext_a, ay - uy * ext_a), (bx + ux * ext_b, by + uy * ext_b)])
    return line.buffer(wall.thickness / 2, cap_style="flat", join_style="mitre")


@dataclass(frozen=True)
class FlightMetrics:
    riser_mm: float
    tread_mm: float
    start_z: float
    end_z: float


def stair_metrics(stair: Stair, defaults: Defaults) -> list[FlightMetrics]:
    top = stair.top_z if stair.top_z is not None else defaults.floor_to_floor
    riser = (top - stair.base_z) / sum(f.risers for f in stair.flights)
    out, z = [], float(stair.base_z)
    for f in stair.flights:
        length = math.hypot(f.end[0] - f.start[0], f.end[1] - f.start[1])
        out.append(FlightMetrics(riser, length / f.risers, z, z + riser * f.risers))
        z += riser * f.risers
    return out


def derive(spec: Spec) -> Spec:
    s = spec.model_copy(deep=True)
    footprints = {w.id: wall_footprint(w, s) for w in s.walls}
    walls = {w.id: w for w in s.walls}
    door_segments = {}  # door id -> (opening segment on the centerline, half wall thickness)
    for o in s.openings:
        w = walls.get(o.wall_id)
        if o.category == "door" and w:
            (ax, ay), (bx, by) = w.a, w.b
            length = math.hypot(bx - ax, by - ay) or 1.0
            ux, uy = (bx - ax) / length, (by - ay) / length
            seg = LineString([(ax + ux * o.offset, ay + uy * o.offset),
                              (ax + ux * (o.offset + o.width), ay + uy * (o.offset + o.width))])
            door_segments[o.id] = (seg, w.thickness / 2)

    room_shapes = []
    for r in s.rooms:
        outer = SPolygon(r.polygon)
        shape = SPolygon(r.polygon, r.holes)
        room_shapes.append((r, shape))
        r.area_m2 = round(shape.area / 1e6, 2)
        r.perimeter_m = round(outer.length / 1000, 2)
        # Bounding = the room's edge runs along the wall for more than its thickness (an end face does not count).
        r.bounding_walls = sorted(
            (wid for wid, fp in footprints.items()
             if outer.exterior.intersection(fp.buffer(1)).length > walls[wid].thickness + 3),  # t + 2*buffer + slack
            key=id_key)
        # A door belongs to a room only if its opening (not just its wall) faces the room.
        r.doors = sorted((d for d, (seg, half_t) in door_segments.items() if seg.distance(outer) <= half_t + 1),
                         key=id_key)

    def room_at(x: float, y: float) -> str | None:
        pt = Point(x, y)
        return next((r.id for r, shape in room_shapes if shape.covers(pt)), None)

    for obj in s.objects:
        obj.room_id = room_at(obj.position[0], obj.position[1])
    for st in s.stairs:
        f = st.flights[0]
        st.room_id = room_at((f.start[0] + f.end[0]) / 2, (f.start[1] + f.end[1]) / 2)
    s.meta.gross_area_m2 = round(sum(SPolygon(p).area for p in s.meta.building_outline) / 1e6, 2)
    return s
