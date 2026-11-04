"""Rooms one by one on the wall graph (spec §6.5).

Walls that clearly form a room are accepted first. A room left open is retried with closers in order of certainty:
door, door-wide gap, column, sheet cut. Only closers on an accepted room's boundary survive, and each becomes a real
wall or opening, because stage 4 rebuilds rooms from wall footprints. A room that cannot close is not forced.
"""

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
from shapely import STRtree
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as SPoint
from shapely.ops import polygonize, unary_union

from core.extraction.vector.doors import Door
from core.extraction.vector.lines import Point
from core.extraction.vector.walls import MIN_WALL_MM, WallCand

DUP_MM = 100  # parallel walls this close are one wall (the review gate counts them as duplicates)
JOIN_GAP_MM = 50
SNAP_MM = 300  # a wall end this short of another wall reaches it: wall lines stop at faces, not centre lines
TOUCH_MM = 20
DOOR_GAP_MM = 1400  # widest doorway bridged without evidence of a door
DOUBLE_DOOR_MM = 2600  # with door arcs beside it
MIN_ROOM_HALF_MM = 500  # a face narrower than twice this is a tray or a rack, not a room
LATERAL_MM = 200  # the two ends of a doorway may sit this far off one axis
DOOR_NEAR_MM = 300
CUT_REACH_MM = 3000
FRAME_NEAR_MM = 600
JAMB_MM = 60  # V008 wants >= 50 mm of wall either side of an opening
DOOR_ATTACH_MM = 200
MIN_ROOM_M2 = 1
OVERLAP_MAX = 0.05
POCKET_SHARE = 0.7  # of a single line's run: a rack against a long partition does not make it a rack
CLOSER_ON_ROOM_MM = 40  # a closer may run past the room it closes
ON_ROOM_MM = 300  # a long line may bound a room along only part of its run
CLOSER_ORDER = ("door", "gap", "column", "corner", "cap", "sheet_cut")


@dataclass
class Trace:
    walls: list[WallCand]
    openings: list[dict]
    rooms: list[Polygon]
    open_labels: list[Point] = field(default_factory=list)


def _norm(w: WallCand) -> WallCand:
    return w if w.a <= w.b else WallCand(w.b, w.a, w.thickness, w.evidence)


def _dir(a: Point, b: Point) -> np.ndarray:
    v = np.array(b, float) - np.array(a, float)
    return v / max(float(np.linalg.norm(v)), 1e-9)


def _cross(u: np.ndarray, v: np.ndarray) -> float:
    return float(u[0] * v[1] - u[1] * v[0])


def _length(w: WallCand) -> float:
    return math.dist(w.a, w.b)


def _merge_evidence(k: WallCand, w: WallCand) -> None:
    """A closer that runs a drawn wall on is part of that wall: only a closer with no drawn wall stays tagged, so a
    tag such as `sheet_cut` marks what can be deleted."""
    if "closer" in k.evidence and "closer" not in w.evidence:
        k.evidence = {**w.evidence, "extended_by": k.evidence["closer"]}
    elif "closer" in w.evidence and "closer" not in k.evidence:
        k.evidence["extended_by"] = w.evidence["closer"]


def _collapse(walls) -> list[WallCand]:
    """Parallel walls on one line become one: a pair shared by three lines, or a wall read in two pieces."""
    kept: list[WallCand] = []
    for w in sorted((_norm(w) for w in walls), key=lambda w: (-_length(w), w.a, w.b)):
        d = _dir(w.a, w.b)
        for k in kept:
            kd = _dir(k.a, k.b)
            if abs(_cross(kd, d)) > 0.05:
                continue
            ka = np.array(k.a, float)
            if max(abs(_cross(kd, np.array(p, float) - ka)) for p in (w.a, w.b)) > DUP_MM:
                continue
            s, t = sorted(float(np.dot(kd, np.array(p, float) - ka)) for p in (w.a, w.b))
            if s > _length(k) + JOIN_GAP_MM or t < -JOIN_GAP_MM:
                continue
            lo, hi = min(s, 0.0), max(t, _length(k))
            k.a, k.b = tuple(float(v) for v in ka + lo * kd), tuple(float(v) for v in ka + hi * kd)
            if _length(k) >= MIN_WALL_MM:
                k.evidence.pop("short", None)
            _merge_evidence(k, w)
            break
        else:
            kept.append(WallCand(w.a, w.b, w.thickness, dict(w.evidence)))
    return kept


def _line(w: WallCand, reach: float = 0) -> LineString:
    d = _dir(w.a, w.b)
    return LineString([tuple(np.array(w.a) - reach * d), tuple(np.array(w.b) + reach * d)])


def _hit(origin: Point, d: np.ndarray, reach: float, lines: list, tree: STRtree, skip: int) -> Point | None:
    """Nearest point on another line along a ray from `origin`."""
    ray = LineString([origin, tuple(np.array(origin) + reach * d)])
    best = None
    for i in tree.query(ray):
        if int(i) == skip:
            continue
        x = ray.intersection(lines[int(i)])
        for p in ([x] if x.geom_type == "Point" else getattr(x, "geoms", [])):
            if p.geom_type == "Point":
                dist = math.dist(origin, (p.x, p.y))
                if dist > 1 and (best is None or dist < best[0]):
                    best = (dist, (p.x, p.y))
    return best[1] if best else None


def _snap_ends(walls: list[WallCand]) -> list[WallCand]:
    """Ends that stop just short of another wall reach its axis, also where both walls stop short of the corner."""
    lines = [_line(w, SNAP_MM) for w in walls]
    tree = STRtree(lines)
    out = []
    for i, w in enumerate(walls):
        d = _dir(w.a, w.b)
        a = _hit(w.a, -d, SNAP_MM, lines, tree, i) or w.a
        b = _hit(w.b, d, SNAP_MM, lines, tree, i) or w.b
        out.append(WallCand(a, b, w.thickness, w.evidence))
    return out


def _structure(walls: list[WallCand]) -> list[WallCand]:
    """Only what hangs together with a firm wall: equipment drawn in single lines stands free of the building."""
    lines = [_line(w) for w in walls]
    tree = STRtree(lines)
    seen = {i for i, w in enumerate(walls) if "short" not in w.evidence}
    todo = list(seen)
    while todo:
        i = todo.pop()
        for j in tree.query(lines[i].buffer(TOUCH_MM)):
            j = int(j)
            if j not in seen and lines[j].distance(lines[i]) <= TOUCH_MM:
                seen.add(j)
                todo.append(j)
    return [w for i, w in enumerate(walls) if i in seen]


def _dangling(walls: list[WallCand]) -> list[tuple[int, Point, np.ndarray]]:
    """(wall index, end, outward direction) of every end touching no other wall."""
    lines = [_line(w) for w in walls]
    tree = STRtree(lines)
    out = []
    for i, w in enumerate(walls):
        d = _dir(w.a, w.b)
        for end, out_d in ((w.a, -d), (w.b, d)):
            near = tree.query(SPoint(end).buffer(TOUCH_MM))
            if not any(int(j) != i and lines[int(j)].distance(SPoint(end)) <= TOUCH_MM for j in near):
                out.append((i, end, out_d))
    return sorted(out, key=lambda e: e[1])


def _closer(a: Point, b: Point, thickness: float, kind: str) -> WallCand:
    return _norm(WallCand(a, b, thickness, {"closer": kind}))


def _column_hit(end: Point, d: np.ndarray, columns: list[dict]) -> Point | None:
    ray = LineString([end, tuple(np.array(end) + DOOR_GAP_MM * d)])  # a column in a doorway's reach
    best = None
    for c in columns:
        (cx, cy), (sx, sy) = c["center"], c["size"]
        if ray.intersects(box(cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2)):
            dist = math.dist(end, (cx, cy))
            if best is None or dist < best[0]:
                best = (dist, (float(cx), float(cy)))
    return best[1] if best else None


def _end_ahead(i: int, end: Point, d: np.ndarray, ends: list, reach: float) -> Point | None:
    """The facing end of another wall across a doorway."""
    best = None
    for j, other, other_d in ends:
        v = np.array(other, float) - np.array(end, float)
        along = float(np.dot(v, d))
        if j != i and 0 < along <= reach and abs(_cross(d, v)) <= LATERAL_MM and float(np.dot(d, other_d)) < 0 \
                and (best is None or along < best[0]):
            best = (along, other)
    return best[1] if best else None


def _door_at(a: Point, b: Point, doors: list[Door]) -> bool:
    seg = LineString([a, b])
    return any(seg.distance(SPoint(p)) <= DOOR_NEAR_MM for d in doors for p in (d.hinge, *d.ends))


def _gap_closers(walls: list[WallCand], ends: list, doors: list[Door], columns: list[dict]) -> list[WallCand]:
    lines = [_line(w) for w in walls]
    tree = STRtree(lines)
    found: dict[tuple, WallCand] = {}
    for i, end, d in ends:
        t = walls[i].thickness
        col = _column_hit(end, d, columns)
        target = _end_ahead(i, end, d, ends, DOOR_GAP_MM) or _hit(end, d, DOOR_GAP_MM, lines, tree, i)
        if target is None:  # a double door: wider, but only with its arcs there
            wide = _end_ahead(i, end, d, ends, DOUBLE_DOOR_MM) or _hit(end, d, DOUBLE_DOOR_MM, lines, tree, i)
            if wide and _door_at(end, wide, doors):
                target = wide
        if col and (target is None or math.dist(end, col) <= math.dist(end, target)):
            c = _closer(end, col, t, "column")
        elif target:
            c = _closer(end, target, t, "door" if _door_at(end, target, doors) else "gap")
        else:
            continue
        found.setdefault((tuple(round(v) for v in c.a), tuple(round(v) for v in c.b)), c)
    return [found[k] for k in sorted(found)]


def _corner_closers(walls: list[WallCand], ends: list) -> list[WallCand]:
    """Two ends that would meet at a corner if both ran on: walls stop at the faces of a corner column."""
    out: list[WallCand] = []
    for n, (i, p, d) in enumerate(ends):
        for j, q, e in ends[n + 1:]:
            if i == j or abs(_cross(d, e)) < 0.5:
                continue
            ray_p = LineString([p, tuple(np.array(p) + DOOR_GAP_MM * d)])
            ray_q = LineString([q, tuple(np.array(q) + DOOR_GAP_MM * e)])
            x = ray_p.intersection(ray_q)
            if x.geom_type == "Point":
                out += [_closer(p, (x.x, x.y), walls[i].thickness, "corner"),
                        _closer(q, (x.x, x.y), walls[j].thickness, "corner")]
    return out


def _cap_closers(walls: list[WallCand], ends: list) -> list[WallCand]:
    """Two ends side by side, pointing the same way: the back of a recess."""
    out: list[WallCand] = []
    for n, (i, p, d) in enumerate(ends):
        for j, q, e in ends[n + 1:]:
            v = np.array(q, float) - np.array(p, float)
            if i != j and float(np.dot(d, e)) > 0.95 and abs(float(np.dot(v, d))) <= LATERAL_MM \
                    and 0 < abs(_cross(d, v)) <= DOOR_GAP_MM:
                out.append(_closer(p, q, walls[i].thickness, "cap"))
    return out


def _cut_closers(ends: list, walls: list[WallCand], cut: tuple[float, float, float, float]) -> list[WallCand]:
    """Ends running out at the sheet's cut reach it, and the cut edge joins them."""
    x0, y0, x1, y1 = cut
    sides = {"s": ((x0, y0), (x1, y0)), "e": ((x1, y0), (x1, y1)), "n": ((x1, y1), (x0, y1)), "w": ((x0, y1), (x0, y0))}
    out: list[WallCand] = []
    for a, b in sides.values():
        edge = LineString([a, b])
        hits = []
        for i, end, d in ends:
            ray = LineString([tuple(np.array(end) - CUT_REACH_MM * d), tuple(np.array(end) + CUT_REACH_MM * d)])
            x = ray.intersection(edge)
            if x.geom_type == "Point":
                hits.append((edge.project(x), (x.x, x.y), i, end))
        hits.sort(key=lambda h: h[0])
        for _, p, i, end in hits:
            if math.dist(p, end) > TOUCH_MM:
                out.append(_closer(end, p, walls[i].thickness, "sheet_cut"))
        for u, v in itertools.pairwise(hits):
            if v[0] - u[0] > 1:
                out.append(_closer(u[1], v[1], walls[u[2]].thickness, "sheet_cut"))
    return out


def _accept(walls: list[WallCand], closers: list[WallCand], seeds: list[Point]) -> tuple[list[Polygon], list[WallCand], list[Point], list[Polygon]]:
    """Stage by stage, surest closers first; closers stay only if an accepted room needs them."""
    active = [_line(w) for w in walls]
    rooms: list[Polygon] = []
    used: list[WallCand] = []
    pending = list(seeds)
    points = {s: SPoint(s) for s in seeds}
    for n in range(len(CLOSER_ORDER) + 1):
        allowed = CLOSER_ORDER[:n]
        cand = [c for c in closers if c.evidence["closer"] in allowed and c not in used]
        faces = list(polygonize(unary_union(active + [_line(c) for c in cand])))
        for s in list(pending):
            f = next((p for p in faces if p.contains(points[s])), None)
            if f is None or f.area < MIN_ROOM_M2 * 1e6 or sum(f.contains(q) for q in points.values()) != 1 \
                    or any(f.intersection(r).area > OVERLAP_MAX * f.area for r in rooms):
                continue
            rooms.append(f)
            pending.remove(s)
            edge = f.boundary.buffer(5)
            for c in cand:
                line = _line(c)
                if c not in used and line.intersection(edge).length >= min(0.9 * line.length, CLOSER_ON_ROOM_MM):
                    used.append(c)
        active = [_line(w) for w in walls] + [_line(c) for c in used]
    for f in polygonize(unary_union(active)):  # closed faces no label asked for
        if f.area >= MIN_ROOM_M2 * 1e6 and not f.buffer(-MIN_ROOM_HALF_MM).is_empty \
                and not any(f.intersection(r).area > OVERLAP_MAX * f.area for r in rooms) \
                and not any(f.contains(points[s]) for s in pending):
            rooms.append(f)
    pockets = [f for f in polygonize(unary_union(active))
               if not any(f.equals(r) for r in rooms) and not any(f.contains(points[s]) for s in pending)]
    return rooms, used, pending, pockets


def _bounds_a_pocket(w: WallCand, pockets: list[Polygon]) -> bool:
    """A closed face too small to be a room is equipment, and a single line around it is the equipment's outline."""
    line = _line(w)
    return any(line.intersection(f.boundary.buffer(5)).length >= POCKET_SHARE * line.length for f in pockets)


def _keep(walls: list[WallCand], rooms: list[Polygon], pockets: list[Polygon]) -> list[WallCand]:
    """Walls on a room stay. Off one, only long walls joined to another wall: an open room keeps its sides, but
    equipment floating in a room goes."""
    ring = unary_union([r.boundary for r in rooms]) if rooms else None
    lines = [_line(w) for w in walls]
    tree = STRtree(lines)
    out = []
    for i, (w, line) in enumerate(zip(walls, lines, strict=True)):
        on = ring is not None and line.intersection(ring.buffer(w.thickness / 2 + TOUCH_MM)).length >= ON_ROOM_MM
        joined = any(int(j) != i and lines[int(j)].distance(line) <= TOUCH_MM for j in tree.query(line.buffer(TOUCH_MM)))
        if w.evidence.get("source") == "single" and _bounds_a_pocket(w, pockets):
            continue
        if on or ("short" not in w.evidence and joined):
            out.append(w)
    return out


def _opening(index: int, c: WallCand, length: float, doors: list[Door]) -> dict:
    near = [d for d in doors if _line(c).distance(SPoint(d.hinge)) <= DOOR_NEAR_MM]
    base = {"wall": index, "category": "door", "offset": JAMB_MM, "width": round(length), "confidence": 0.6,
            "evidence": {"closer": c.evidence["closer"]}}
    if c.evidence["closer"] == "gap" or not near:
        return {**base, "door_type": "opening", "hinge": None, "swing": None}
    if len(near) > 1:
        return {**base, "door_type": "double_swing", "hinge": "both", "swing": "left"}
    d = near[0]
    v = _dir(c.a, c.b)
    tip = max(d.ends, key=lambda e: abs(_cross(v, np.array(e) - np.array(c.a))))
    side = _cross(v, np.array(tip) - np.array(c.a))
    hinge = "start" if math.dist(d.hinge, c.a) <= math.dist(d.hinge, c.b) else "end"
    return {**base, "door_type": "single_swing", "hinge": hinge, "swing": "left" if side > 0 else "right"}


def _attach_doors(walls: list[WallCand], openings: list[dict], doors: list[Door], taken: list[Door]) -> None:
    """Doors with no doorway to close sit on the nearest wall, when it has room for them."""
    for d in doors:
        if d in taken:
            continue
        best = min(range(len(walls)), key=lambda i: _line(walls[i]).distance(SPoint(d.hinge)), default=None)
        if best is None or _line(walls[best]).distance(SPoint(d.hinge)) > DOOR_ATTACH_MM:
            continue
        w = walls[best]
        at = _line(w).project(SPoint(d.hinge))
        lo = at if _line(w).project(SPoint(d.ends[0])) >= at else at - d.radius
        if lo >= JAMB_MM and lo + d.radius <= _length(w) - JAMB_MM \
                and not any(o["wall"] == best and abs(o["offset"] - lo) < d.radius for o in openings):
            openings.append({"wall": best, "category": "door", "offset": round(lo), "width": round(d.radius),
                             "door_type": "single_swing", "hinge": None, "swing": None, "confidence": 0.5,
                             "evidence": {"arc": True}})


def _on_cut(w: WallCand, cut: tuple[float, float, float, float]) -> bool:
    """A lone line along the drawing's edge is the sheet frame."""
    if w.evidence.get("source") != "single":
        return False
    x0, y0, x1, y1 = cut
    return any(abs(w.a[i] - v) <= FRAME_NEAR_MM and abs(w.b[i] - v) <= FRAME_NEAR_MM
               for i, v in ((0, x0), (0, x1), (1, y0), (1, y1)))


def trace_rooms(walls: list[WallCand], doors: list[Door], columns: list[dict], seeds: list[Point],
                cut: tuple[float, float, float, float]) -> Trace:
    """cut: the drawing's bbox in mm (x0, y0, x1, y1), where a sheet may cut the plan off."""
    base = _structure(_snap_ends(_collapse(w for w in walls if not _on_cut(w, cut))))
    ends = _dangling(base)
    closers = _gap_closers(base, ends, doors, columns) + _corner_closers(base, ends) + _cap_closers(base, ends) \
        + _cut_closers(ends, base, cut)
    seeds = sorted(seeds)
    rooms, used, pending, pockets = _accept(base, closers, seeds)
    bridges = [c for c in used if c.evidence["closer"] in ("door", "gap")]
    solid = [c for c in used if c.evidence["closer"] not in ("door", "gap")]
    out = sorted(_collapse(_keep(base, rooms, pockets) + solid), key=lambda w: (w.a, w.b))
    openings: list[dict] = []
    taken: list[Door] = []
    for c in sorted(bridges, key=lambda w: (-_length(w), w.a, w.b)):
        line = _line(c)
        if any(line.intersection(_line(w).buffer(DUP_MM)).length >= 0.95 * line.length for w in out):
            continue  # a second closer along the same edge, or along a wall
        d = _dir(c.a, c.b)  # the wall reaches into its neighbours so the opening has jambs
        out.append(WallCand(tuple(float(v) for v in np.array(c.a) - JAMB_MM * d),
                            tuple(float(v) for v in np.array(c.b) + JAMB_MM * d), c.thickness, c.evidence))
        openings.append(_opening(len(out) - 1, c, _length(c), doors))
        taken += [dr for dr in doors if line.distance(SPoint(dr.hinge)) <= DOOR_NEAR_MM]
    _attach_doors(out, openings, doors, taken)
    return Trace(out, openings, sorted(rooms, key=lambda r: (r.centroid.x, r.centroid.y)), pending)
