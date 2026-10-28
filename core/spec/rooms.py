"""Room formation from walls + columns (PRD/04 stage 4, steps 1-3 and 2b) and room ID reconciliation (§5.4b)."""

from collections.abc import Callable
from dataclasses import dataclass

from shapely import set_precision
from shapely.geometry import MultiPolygon
from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon as SPolygon
from shapely.ops import unary_union

from core.spec.derive import column_footprint, derive, id_key, wall_footprint
from core.spec.ids import take_id
from core.spec.models import Point, Provenance, Room, Spec

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


def _on_mm_grid(poly: SPolygon) -> list[SPolygon]:
    """The spec stores integer mm. A ring that self-intersects once rounded is snapped to the 1 mm grid instead."""
    rounded = SPolygon(_ring(poly.exterior.coords), [_ring(h.coords) for h in poly.interiors])
    return [poly] if rounded.is_valid else _parts(set_precision(poly, 1.0))


NECK_SPLIT_MM = 300  # narrower than any door or passage: free space this thin is a sliver between solids


def _split_necks(p: SPolygon) -> list[SPolygon]:
    """Cut a free-space piece where it narrows below NECK_SPLIT_MM (the sliver between a fin and the band lines,
    a column set a few cm off a wall): each side of such a neck is its own room. Only the neck itself is removed,
    so a room never reaches through a thin divider and narrow alcoves stay with their room."""
    r = NECK_SPLIT_MM / 2
    opened = p.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")
    cores = [c for c in _parts(opened) if c.area >= MIN_ROOM_AREA_MM2]
    if len(cores) < 2:
        return [p]
    necks = [t for t in _parts(p.difference(opened)) if sum(t.buffer(1).intersects(c) for c in cores) >= 2]
    if not necks:
        return [p]
    pieces = [q for q in _parts(p.difference(unary_union(necks))) if q.area >= MIN_ROOM_AREA_MM2]
    return pieces or [p]


OUTLINE_CLOSE_MM = 1500  # gaps in the outer walls up to 2 x 1500 mm are bridged when taking the building shell
MASS_MIN_MM2 = 2_000_000  # a closed shell this big is a building mass of its own (Gatsu's capacitor annex: ~3 m²)


def _closed(union):
    """The wall/column union with gaps up to 3 m closed, one building mass at a time.

    A mass is a closed shell of at least MASS_MIN_MM2; every other piece (a stretch of a broken outer wall) joins
    the nearest mass within 3 m, and each mass is closed (mitre) on its own. One missed stretch of outer wall no
    longer opens the building shell, and two separate masses are never bridged into one slab.

    ponytail: a genuine recess narrower than 3 m is filled (gross area slightly high), and only gaps whose two ends
    face each other are bridged (stubs offset across a facade jog stay open). Rooms never come from this shell:
    form_rooms cuts them from the unclosed one.
    """
    r = OUTLINE_CLOSE_MM
    parts = _parts(union)
    shells = [SPolygon(p.exterior) for p in parts]
    # a mass encloses space: an open strip of broken wall (however long) is a piece to bridge, not a mass
    masses = [i for i, (sh, p) in enumerate(zip(shells, parts, strict=True))
              if sh.area >= MASS_MIN_MM2 and sh.area - p.area >= MIN_ROOM_AREA_MM2
              and not any(j != i and shells[j].covers(sh) for j in range(len(shells)))]
    groups: dict[int, list] = {}
    for i, p in enumerate(parts):
        near = min(masses, key=lambda m: shells[m].distance(p), default=None)
        key = near if near is not None and shells[near].distance(p) <= 2 * r else -1  # -1: loose pieces together
        groups.setdefault(key, []).append(p)
    closed = [unary_union([g, g.buffer(r, join_style="mitre").buffer(-r, join_style="mitre")])
              for g in (unary_union(ps) for ps in groups.values())]
    return unary_union(closed)


def _masses(shells: list[SPolygon]) -> list[SPolygon]:
    """Building masses: shells not inside another (lift shafts, free columns are islands), largest first."""
    out = [s for i, s in enumerate(shells) if not any(j != i and o.covers(s) for j, o in enumerate(shells))]
    return sorted(out, key=lambda o: (-o.area, o.bounds))


def form_rooms(spec: Spec) -> tuple[list[SPolygon], list[SPolygon]]:
    """Return (room polygons with holes, outline per building mass). Openings do not cut footprints."""
    cols = [column_footprint(c) for c in spec.columns]
    union = unary_union([wall_footprint(w, spec) for w in spec.walls] + cols)
    # Low walls (planter edges, rails) belong to the building mass but do not divide rooms.
    dividers = unary_union([wall_footprint(w, spec) for w in spec.walls if w.kind != "low"] + cols)
    # the outline (gross area, slabs) bridges gaps in the outer walls; rooms come only from what the walls enclose,
    # so a porch or recess under 3 m never becomes a room the editor cannot delete
    outlines = _masses([SPolygon(p.exterior).simplify(0) for p in _parts(_closed(union))])  # closing: collinear pts
    drawn = _masses([SPolygon(p.exterior) for p in _parts(union)])
    interior = unary_union(drawn).difference(dividers) if drawn else SPolygon()
    # necks are cut only next to the outer contour (the outer band's bays, PRD/04 §2b); inner rooms keep their shape
    reach = max((w.thickness for w in spec.walls), default=0) + 1
    rings = [o.exterior for o in outlines]
    pieces = [q for p in _parts(interior)
              for part in (_split_necks(p) if any(ring.distance(p) <= reach for ring in rings) else [p])
              for q in _on_mm_grid(part.simplify(0))]  # simplify: collinear vertices
    rooms = [p for p in pieces if p.area >= MIN_ROOM_AREA_MM2 and _aspect(p) <= MAX_ASPECT]
    return rooms, outlines


def _ring(coords) -> list[tuple[int, int]]:
    return [(round(x), round(y)) for x, y in list(coords)[:-1]]


def rebuild_rooms(spec: Spec, labels: list[RoomLabel] | None = None,
                  pick: Callable[[list[RoomLabel]], RoomLabel | None] | None = None, source: str = "manual") -> Spec:
    """`pick` chooses among several labels inside one room (default: the first). New rooms get provenance `source`
    ("cv" when the pipeline forms them)."""
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
            provenance=prev.provenance if prev else Provenance(source=source),
        )
        inside = [lb for lb in labels or [] if p.covers(SPoint(lb.at))]
        label = pick(inside) if pick else next(iter(inside), None)
        if label:
            rtype = label.type if label.type != "other" else room.type  # an unknown word does not undo stair/lift
            room = room.model_copy(update={"name": label.name, "type": rtype, "label_pos": label.at})
            room = Room.model_validate(room.model_dump())  # re-validate the literal room type
        new_rooms.append(room)

    s.rooms = sorted(new_rooms, key=lambda r: id_key(r.id))
    s.meta.building_outline = [_ring(o.exterior.coords) for o in outlines]
    return derive(Spec.model_validate(s.model_dump()))
