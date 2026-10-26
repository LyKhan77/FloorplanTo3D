"""Stage 4 (PRD/04 Tahap 4): a stage-3 candidate becomes a full spec with rooms, labels and room types."""

import math

from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as SPolygon
from shapely.ops import unary_union

from core.extraction.geometry.elements import elements_to_spec
from core.extraction.rooms.labels import best_label
from core.spec.carryover import assign_ids
from core.spec.derive import column_footprint, derive, endpoint_connected, wall_footprint
from core.spec.models import Defaults, ImageInfo, Spec
from core.spec.rooms import RoomLabel, rebuild_rooms

BAND_MAX_MM = 2000  # an unlabelled strip this narrow along the outline is the outer band (§2b): outdoor
NECK_MM = 600
CLOSE_REACH_MM = 1200  # dangling wall ends are extended this far to meet the next wall (rooms must close)
CLOSED_CONF = 0.55  # a wall extended by more than CLOSE_REVIEW_MM goes to review
CLOSE_REVIEW_MM = 300
SITE_TYPES = ("data_hall", "data_center", "office", "mixed", "other")


def _with_meta(spec: Spec, meta_info: dict) -> Spec:
    s = spec.model_copy(deep=True)
    s.meta.project_id = meta_info.get("project_id", s.meta.project_id)
    if meta_info.get("image"):
        s.meta.image = ImageInfo(**meta_info["image"])
    s.meta.floor_name = meta_info.get("floor_name") or ""
    s.meta.site_type = meta_info.get("site_type") if meta_info.get("site_type") in SITE_TYPES else "other"
    s.meta.defaults = Defaults(**{k: v for k, v in (meta_info.get("defaults") or {}).items()
                                  if k in Defaults.model_fields})
    return s


def close_ends(spec: Spec, reach_mm: float = CLOSE_REACH_MM) -> Spec:
    """Extend every dangling wall end along the wall, up to `reach_mm`, onto the first wall or column it meets.

    Stage 3 leaves gaps where a wall line was broken or missed; without this the rooms leak into each other and
    the building outline falls apart (Gatsu: 48 loose wall groups, 4 rooms). The end goes to the host wall's
    centreline, so the footprint closes the L/T. Door offsets follow a moved `a` end.
    """
    s = spec.model_copy(deep=True)
    solids = [(w.id, wall_footprint(w, s), w.thickness / 2) for w in s.walls]
    solids += [(None, column_footprint(c), 0.0) for c in s.columns]
    moved: dict[str, float] = {}
    for w in s.walls:
        length = math.dist(w.a, w.b)
        if not length:
            continue
        ux, uy = (w.b[0] - w.a[0]) / length, (w.b[1] - w.a[1]) / length
        for end, sign in (("a", -1), ("b", 1)):
            if endpoint_connected(spec, w, end):
                continue
            p = w.a if end == "a" else w.b
            ray = LineString([p, (p[0] + sign * ux * reach_mm, p[1] + sign * uy * reach_mm)])
            hits = [(Point(p).distance(ray.intersection(fp)), half) for oid, fp, half in solids
                    if oid != w.id and ray.intersects(fp)]
            hits = [(d, half) for d, half in hits if d > 1]
            if not hits:
                continue
            d, half = min(hits)
            ext = min(reach_mm, d + half)
            q = (round(p[0] + sign * ux * ext), round(p[1] + sign * uy * ext))
            if end == "a":
                w.a = q
                for o in s.openings:
                    if o.wall_id == w.id:
                        o.offset += round(ext)
            else:
                w.b = q
            moved[w.id] = moved.get(w.id, 0) + round(ext)
    for w in s.walls:
        if w.id in moved:
            ev = w.provenance.evidence | {"extended_to_close_mm": moved[w.id]}
            conf = min(w.provenance.confidence, CLOSED_CONF) if moved[w.id] > CLOSE_REVIEW_MM else w.provenance.confidence
            w.provenance = w.provenance.model_copy(update={"evidence": ev, "confidence": conf})
    return s


def _short_side(poly: SPolygon) -> float:
    xs, ys = poly.minimum_rotated_rectangle.exterior.coords.xy
    return min(math.hypot(xs[i + 1] - xs[i], ys[i + 1] - ys[i]) for i in range(4))


def _type_rooms(spec: Spec, labels: list[RoomLabel], lifts: list[list[int]]) -> Spec:
    s = spec.model_copy(deep=True)
    rings = [SPolygon(o).exterior for o in s.meta.building_outline]
    reach = max((w.thickness for w in s.walls), default=0) + 1  # rooms stop at the wall faces, never at the outline
    for r in s.rooms:
        shape = SPolygon(r.polygon, r.holes)
        labelled = r.type != "other"
        if not labelled and any(shape.covers(Point((f.start[0] + f.end[0]) / 2, (f.start[1] + f.end[1]) / 2))
                                for st in s.stairs for f in st.flights):
            r.type = "stair"
        elif not labelled and any(shape.covers(Point((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)) for b in lifts):
            r.type = "lift"
        elif not r.name and not labelled and any(ring.distance(shape) <= reach for ring in rings) \
                and _short_side(SPolygon(r.polygon)) <= BAND_MAX_MM:
            r.type = "outdoor"
    return s


def _door_centres(spec: Spec) -> dict[str, Point]:
    walls = {w.id: w for w in spec.walls}
    out = {}
    for o in spec.openings:
        w = walls.get(o.wall_id)
        if w:
            line = LineString([w.a, w.b])
            out[o.id] = line.interpolate(o.offset + o.width / 2)
    return out


def leak_issues(spec: Spec, labels: list[RoomLabel]) -> list[dict]:
    """Rooms that probably leak (§6b): two labels of different types inside, or a neck < 600 mm without a door.
    No synthetic wall is added; the correction panel closes the gap."""
    doors = _door_centres(spec)
    issues = []
    for r in spec.rooms:
        shape = SPolygon(r.polygon, r.holes)
        types = {lb.type for lb in labels if shape.covers(Point(lb.at)) and lb.type != "other"}
        leak = len(types) >= 2
        if not leak:
            parts = [p for p in getattr(shape.buffer(-NECK_MM / 2), "geoms", [shape.buffer(-NECK_MM / 2)])
                     if not p.is_empty and p.buffer(NECK_MM / 2).area >= 1_000_000]
            if len(parts) >= 2:
                neck = shape.difference(unary_union(parts).buffer(NECK_MM / 2 + 1))
                leak = not any(doors[d].distance(neck) <= NECK_MM for d in r.doors if d in doors)
        if leak:
            c = shape.representative_point()
            issues.append({"code": "ROOM_LEAK", "severity": "warning", "element_ids": [r.id],
                           "message": "ruang kemungkinan bocor (dua label berbeda atau leher sempit tanpa pintu)",
                           "at": [round(c.x), round(c.y)]})
    return issues


def assemble_spec(elements: dict, grid_doc: dict, labels: list[RoomLabel], meta_info: dict) -> tuple[Spec, list[dict]]:
    spec = assign_ids(close_ends(_with_meta(elements_to_spec(elements, grid_doc), meta_info)))
    spec = rebuild_rooms(spec, labels, pick=best_label)
    spec = derive(Spec.model_validate(_type_rooms(spec, labels, elements.get("lifts", [])).model_dump()))
    return spec, leak_issues(spec, labels)
