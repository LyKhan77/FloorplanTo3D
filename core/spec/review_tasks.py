"""The review step's located task list (M8): what a person checks after stage 5, in the order a correction goes.

gap   two collinear walls whose dangling ends face each other 0.6-1.3 m apart (a door opening the walls lost)
leak  a room holding labels of two room types (it swallowed its neighbour)
loose a short wall with both ends dangling (usually an annotation line read as a wall)
type  a room still typed "other"
"""

import math
from collections import Counter

from shapely.geometry import LineString, Point
from shapely.geometry import Polygon as SPolygon

from core.spec.derive import endpoint_connected
from core.spec.models import Spec
from core.spec.rooms import RoomLabel

GAP_MIN_MM, GAP_MAX_MM = 600, 1300  # door widths
GAP_LATERAL_SLACK_MM = 50
PARALLEL_DEG = 3
LOOSE_MAX_MM = 3000
LABEL_REPEATS = 3  # a text this frequent labels equipment (PAC), not a room
LABEL_JOIN_MM = 2500  # lines of one room label sit this close
OPEN_REACH_MM = 10000
TYPE_MIN_M2 = 4


def _unit(a, b):
    n = math.dist(a, b)
    return ((b[0] - a[0]) / n, (b[1] - a[1]) / n) if n else (0.0, 0.0)


def _dangling(spec: Spec) -> list[tuple]:
    """(wall, point, outward unit, "a" | "b") of every end that touches nothing."""
    out = []
    for w in spec.walls:
        if not math.dist(w.a, w.b):
            continue
        u = _unit(w.a, w.b)
        for end, p, d in (("a", w.a, (-u[0], -u[1])), ("b", w.b, u)):
            if not endpoint_connected(spec, w, end):
                out.append((w, tuple(p), d, end))
    return out


def _gaps(spec: Spec) -> list[dict]:
    walls = {w.id: w for w in spec.walls}
    doors = []
    for o in spec.openings:
        w = walls.get(o.wall_id)
        if w and math.dist(w.a, w.b):
            t = (o.offset + o.width / 2) / math.dist(w.a, w.b)
            doors.append(Point(w.a[0] + t * (w.b[0] - w.a[0]), w.a[1] + t * (w.b[1] - w.a[1])))
    ends = _dangling(spec)
    pairs = []
    for i, (w1, p1, d1, e1) in enumerate(ends):
        for w2, p2, d2, e2 in ends[i + 1:]:
            if w1.id == w2.id or abs(d1[0] * d2[1] - d1[1] * d2[0]) > math.sin(math.radians(PARALLEL_DEG)):
                continue
            v = (p2[0] - p1[0], p2[1] - p1[1])
            along = v[0] * d1[0] + v[1] * d1[1]  # p2 lies ahead of p1's end, and p1 ahead of p2's
            lateral = abs(v[0] * d1[1] - v[1] * d1[0])
            if not (GAP_MIN_MM <= along <= GAP_MAX_MM) or -(v[0] * d2[0] + v[1] * d2[1]) <= 0 \
                    or lateral > max(w1.thickness, w2.thickness) / 2 + GAP_LATERAL_SLACK_MM:
                continue
            seg = LineString([p1, p2])
            if any(seg.distance(c) <= max(w1.thickness, w2.thickness) / 2 + 1 for c in doors):
                continue
            pairs.append((along, w1, p1, e1, w2, p2, e2))
    used, out = set(), []
    for along, w1, p1, e1, w2, p2, e2 in sorted(pairs, key=lambda t: t[0]):
        if (w1.id, p1) in used or (w2.id, p2) in used:
            continue
        used |= {(w1.id, p1), (w2.id, p2)}
        ids = sorted([w1.id, w2.id])
        out.append({"id": f"gap:{','.join(ids)}", "kind": "gap",
                    "message": f"Celah {along / 1000:.1f} m di antara ujung dinding segaris",
                    "at": [round((p1[0] + p2[0]) / 2), round((p1[1] + p2[1]) / 2)], "element_ids": ids,
                    "fix": {"a": [round(v) for v in p1], "b": [round(v) for v in p2],
                            "thickness": round((w1.thickness + w2.thickness) / 2), "kind": w1.kind,
                            "ends": [{"wall": w1.id, "end": e1}, {"wall": w2.id, "end": e2}]}})
    # one dangling jamb whose wall, continued, runs into another wall 0.6-1.3 m on (the far jamb is that wall)
    for w, p, d, e in ends:
        if (w.id, p) in used:
            continue
        ray = LineString([p, (p[0] + d[0] * GAP_MAX_MM, p[1] + d[1] * GAP_MAX_MM)])
        hits = []
        for h in spec.walls:
            if h.id == w.id:
                continue
            centre = LineString([h.a, h.b])
            near = ray.intersection(centre.buffer(h.thickness / 2 + GAP_LATERAL_SLACK_MM))
            if near.is_empty:
                continue
            reach = Point(p).distance(near)
            cross = ray.intersection(centre)  # a wall across the ray: end on its centreline
            q = (cross.x, cross.y) if isinstance(cross, Point) else tuple(centre.interpolate(centre.project(Point(p))).coords[0])
            hits.append((reach, q, h))
        if not hits:
            continue
        reach, q, h = min(hits, key=lambda t: t[0])
        along = (q[0] - p[0]) * d[0] + (q[1] - p[1]) * d[1]
        q = (p[0] + d[0] * along, p[1] + d[1] * along)  # stay on the wall's own line: closing it never turns the wall
        gap = math.dist(p, q)
        if not (GAP_MIN_MM <= gap <= GAP_MAX_MM) or any(LineString([p, q]).distance(c) <= w.thickness / 2 + 1 for c in doors):
            continue
        out.append({"id": f"gap:{w.id}:{e}", "kind": "gap", "message": f"Celah {gap / 1000:.1f} m dari ujung dinding ke dinding {h.id}",
                    "at": [round((p[0] + q[0]) / 2), round((p[1] + q[1]) / 2)], "element_ids": [w.id, h.id],
                    "fix": {"a": [round(v) for v in p], "b": [round(v) for v in q], "thickness": round(w.thickness),
                            "kind": w.kind, "ends": [{"wall": w.id, "end": e}]}})
    return out


def _leaks(spec: Spec, labels: list[RoomLabel] | None) -> list[dict]:
    out = []
    for r in spec.rooms if labels else []:
        shape = SPolygon(r.polygon, r.holes)
        inside = [lb for lb in labels if lb.type != "other" and shape.covers(Point(lb.at))]
        if len({lb.type for lb in inside}) >= 2:
            p = shape.representative_point()
            names = ", ".join(sorted({lb.name or lb.type for lb in inside}))
            out.append({"id": f"leak:{r.id}", "kind": "leak", "message": f"Satu ruang memuat {len(inside)} label: {names}",
                        "at": [round(p.x), round(p.y)], "element_ids": [r.id], "fix": {}})
    return out


def _room_open(spec: Spec, labels: list[RoomLabel] | None) -> list[dict]:
    """A room label with no room around it, located at the nearest wall end that hangs open."""
    if not any("source" in w.provenance.evidence for w in spec.walls):
        return []  # raster walls carry no trace: labels there are mostly annotations nobody can close
    names = Counter(lb.name for lb in labels or [])
    shapes = [SPolygon(r.polygon, r.holes) for r in spec.rooms]
    ends = [(p, w) for w in spec.walls for e, p in (("a", w.a), ("b", w.b)) if not endpoint_connected(spec, w, e)]
    out, seen = [], []
    for lb in labels or []:
        if names[lb.name] >= LABEL_REPEATS or any(math.dist(lb.at, q) <= LABEL_JOIN_MM for q in seen) \
                or any(sh.covers(Point(lb.at)) for sh in shapes):
            continue
        seen.append(lb.at)
        near = [(math.dist(lb.at, p), p, w) for p, w in ends if math.dist(lb.at, p) <= OPEN_REACH_MM]
        if near:
            _, p, w = min(near, key=lambda t: (t[0], t[1]))
            out.append({"id": f"room_open:{round(lb.at[0])}:{round(lb.at[1])}", "kind": "room_open", "message": f"Ruang {lb.name} belum tertutup",
                        "at": [round(p[0]), round(p[1])], "element_ids": [w.id], "fix": {}})
    return out


def _loose(spec: Spec) -> list[dict]:
    out = []
    for w in spec.walls:
        length = math.dist(w.a, w.b)
        if length and length < LOOSE_MAX_MM and not endpoint_connected(spec, w, "a") \
                and not endpoint_connected(spec, w, "b"):
            out.append({"id": f"loose:{w.id}", "kind": "loose", "message": "Garis pendek, kedua ujung menggantung",
                        "at": [round((w.a[0] + w.b[0]) / 2), round((w.a[1] + w.b[1]) / 2)], "element_ids": [w.id],
                        "fix": {}})
    return out


def _types(spec: Spec) -> list[dict]:
    out = []
    for r in spec.rooms:
        shape = SPolygon(r.polygon, r.holes)
        if r.type == "other" and shape.area / 1e6 >= TYPE_MIN_M2:
            q = shape.representative_point()
            p = r.label_pos or (q.x, q.y)
            out.append({"id": f"type:{r.id}", "kind": "type", "message": f"Tipe ruang belum pasti ({r.name or r.id})",
                        "at": [round(p[0]), round(p[1])], "element_ids": [r.id], "fix": {}})
    return out


def review_tasks(spec: Spec, labels: list[RoomLabel] | None = None) -> list[dict]:
    """Tasks in correction order: gaps and leaks shape the rooms, so they come before loose walls and types."""
    return _gaps(spec) + _leaks(spec, labels) + _room_open(spec, labels) + _loose(spec) + _types(spec)
