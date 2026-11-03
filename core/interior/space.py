"""The free space of a room for the interior engine: its polygon, doors with their keep-clear zones, and obstacles."""

from dataclasses import dataclass, field

from shapely.geometry import LineString, Polygon
from shapely.geometry import box as sbox
from shapely.ops import unary_union

from core.interior.layout import Placement
from core.interior.library import Tpl
from core.interior.rules import Rules
from core.spec.derive import column_footprint
from core.spec.models import Spec


@dataclass
class Door:
    center: tuple[float, float]  # on the wall axis
    along: tuple[float, float]  # unit vector of the wall
    width: float
    zone: Polygon  # the part of the keep-clear rectangle inside the room
    half: float = 100.0  # half the wall thickness: the wall face is this far from the axis


@dataclass
class Space:
    room: Polygon
    blocked: list[Polygon] = field(default_factory=list)
    doors: list[Door] = field(default_factory=list)
    walls: list[LineString] = field(default_factory=list)
    ceiling: float = 3000.0


def _largest(g) -> Polygon:
    return max(getattr(g, "geoms", [g]), key=lambda p: p.area)


def room_space(spec: Spec, room_id: str, box: tuple | None, ceiling: float, lib: dict[str, Tpl] | None,
               rules: Rules) -> Space:
    room = next(r for r in spec.rooms if r.id == room_id)
    poly = Polygon(room.polygon, room.holes)
    if box is not None:
        poly = _largest(poly.intersection(sbox(*box)))
    near = poly.buffer(400)  # walls bounding the room lie within half a thick wall of its edge
    doors, blocked = [], []
    walls = {w.id: w for w in spec.walls}
    for o in spec.openings:
        w = walls.get(o.wall_id)
        if o.category != "door" or w is None or not near.intersects(LineString([w.a, w.b])):
            continue
        (ax, ay), (bx, by) = w.a, w.b
        length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        ux, uy = (bx - ax) / length, (by - ay) / length
        nx, ny = -uy, ux
        cx, cy = ax + ux * (o.offset + o.width / 2), ay + uy * (o.offset + o.width / 2)
        reach = w.thickness / 2 + o.width + rules.door_clear_mm
        hw = o.width / 2
        rect = Polygon([(cx + ux * s * hw + nx * t * reach, cy + uy * s * hw + ny * t * reach)
                        for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
        zone = rect.intersection(poly)
        if zone.is_empty:
            continue
        doors.append(Door((cx, cy), (ux, uy), o.width, _largest(zone), w.thickness / 2))
        blocked.append(_largest(zone))
    blocked += [f for c in spec.columns if (f := column_footprint(c)).intersects(poly)]
    for o in spec.objects:
        p = Placement(o.template_id, o.template_version, o.position[0], o.position[1], o.position[2], o.rotation,
                      tuple(o.dims))
        fp = p.footprint()
        if not fp.intersects(poly):
            continue
        tpl = (lib or {}).get(o.template_id)
        blocked.append(unary_union([fp, *(p.zones(tpl, rules) if tpl else [])]))
    ring = list(poly.exterior.coords)
    edges = [LineString([ring[i], ring[i + 1]]) for i in range(len(ring) - 1)]
    return Space(poly, blocked, doors, edges, ceiling)
