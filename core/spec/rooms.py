"""Room formation from walls + columns (PRD/04 stage 4, steps 1-3 and 2b) and room ID reconciliation (§5.4b)."""

from collections.abc import Callable
from dataclasses import dataclass

from shapely.geometry import MultiPolygon
from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon as SPolygon
from shapely.ops import unary_union

from core.spec.derive import column_footprint, derive, id_key, wall_footprint
from core.spec.ids import take_id
from core.spec.models import Point, Room, Spec

MIN_ROOM_AREA_MM2 = 1_000_000  # 1 m²
MAX_ASPECT = 20


@dataclass(frozen=True)
class RoomLabel:
    at: Point
    name: str
    type: str


def _parts(geom) -> list[SPolygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, SPolygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, SPolygon)]


def _aspect(poly: SPolygon) -> float:
    xs, ys = poly.minimum_rotated_rectangle.exterior.coords.xy
    sides = sorted({round(((xs[i + 1] - xs[i]) ** 2 + (ys[i + 1] - ys[i]) ** 2) ** 0.5, 6) for i in range(4)})
    return sides[-1] / sides[0] if sides[0] else float("inf")


def form_rooms(spec: Spec) -> tuple[list[SPolygon], list[SPolygon]]:
    """Return (room polygons with holes, outline per building mass). Openings do not cut footprints."""
    cols = [column_footprint(c) for c in spec.columns]
    union = unary_union([wall_footprint(w, spec) for w in spec.walls] + cols)
    # Low walls (planter edges, rails) belong to the building mass but do not divide rooms.
    dividers = unary_union([wall_footprint(w, spec) for w in spec.walls if w.kind != "low"] + cols)
    shells = [SPolygon(p.exterior) for p in _parts(union)]
    # Islands (lift shafts, free-standing columns) sit inside another mass; they are not building masses.
    outlines = [s for i, s in enumerate(shells) if not any(j != i and o.covers(s) for j, o in enumerate(shells))]
    interior = unary_union(outlines).difference(dividers) if outlines else SPolygon()
    pieces = [p.simplify(0) for p in _parts(interior)]  # drop collinear vertices left by abutting footprints
    rooms = [p for p in pieces if p.area >= MIN_ROOM_AREA_MM2 and _aspect(p) <= MAX_ASPECT]
    return rooms, outlines


def _ring(coords) -> list[tuple[int, int]]:
    return [(round(x), round(y)) for x, y in list(coords)[:-1]]


def rebuild_rooms(spec: Spec, labels: list[RoomLabel] | None = None,
                  pick: Callable[[list[RoomLabel]], RoomLabel | None] | None = None) -> Spec:
    """`pick` chooses among several labels inside one room (default: the first)."""
    s = spec.model_copy(deep=True)
    polys, outlines = form_rooms(s)
    old = [(r, SPolygon(r.polygon, r.holes)) for r in s.rooms]

    # Inherit from an old room when IoU >= 0.5 or >= 90% of the old room lies in the new one.
    pairs = []
    for i, p in enumerate(polys):
        for r, shape in old:
            inter = p.intersection(shape).area
            iou = inter / p.union(shape).area if inter else 0.0
            if iou >= 0.5 or (shape.area and inter / shape.area >= 0.9):
                pairs.append((-iou, id_key(r.id), i, r))
    match: dict[int, Room] = {}
    used: set[str] = set()
    for _, _, i, r in sorted(pairs, key=lambda t: (t[0], t[1])):
        if i not in match and r.id not in used:
            match[i] = r
            used.add(r.id)

    unmatched = sorted((i for i in range(len(polys)) if i not in match),
                       key=lambda i: (-polys[i].centroid.y, polys[i].centroid.x))
    new_rooms = []
    for i in [*match, *unmatched]:
        p = polys[i]
        prev = match.get(i)
        room = Room(
            id=prev.id if prev else take_id(s, "R"),
            polygon=_ring(p.exterior.coords),
            holes=[_ring(h.coords) for h in p.interiors],
            name=prev.name if prev else "",
            type=prev.type if prev else "other",
            label_pos=prev.label_pos if prev else None,
            provenance=prev.provenance if prev else Room.model_fields["provenance"].default,
        )
        inside = [lb for lb in labels or [] if p.covers(SPoint(lb.at))]
        label = pick(inside) if pick else next(iter(inside), None)
        if label:
            room = room.model_copy(update={"name": label.name, "type": label.type, "label_pos": label.at})
            room = Room.model_validate(room.model_dump())  # re-validate the literal room type
        new_rooms.append(room)

    s.rooms = sorted(new_rooms, key=lambda r: id_key(r.id))
    s.meta.building_outline = [_ring(o.exterior.coords) for o in outlines]
    return derive(Spec.model_validate(s.model_dump()))
