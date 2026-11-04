"""PDF paths -> long lines, short strokes, dark bars and curve chains, in mm.

CAD exports draw a wall as many collinear pieces and flatten arcs into tiny segments, with one stroke width and no
layers, so geometry is all there is to go on.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MERGE_TOL_MM = 12  # pieces of one line lie this close across it
MERGE_GAP_MM = 40  # ...and this close along it
AXIS_TOL_MM = 5  # a piece this level is horizontal or vertical, however short
SKEW_MIN_MM = 80  # shorter pieces have no reliable angle
ANGLE_BIN_DEG = 1.0
MIN_LINE_MM = 350
SHORT_MM = (80, 700)  # strokes that can be tray rungs
DARK_MAX = 0.3  # fill brightness of a solid wall bar
BBOX_MARGIN_MM = 300
CHAIN_SEG_MM = 150  # pieces this short may be part of a flattened arc
CHAIN_JOIN_MM = 3
CURVE_MIN_MM = 400
CURVE_MAX_STRAIGHT = 0.98  # chord / length: above this a chain is a straight line in pieces
BEZIER_STEPS = 8

Point = tuple[float, float]


@dataclass(frozen=True)
class Line:
    a: Point
    b: Point


@dataclass
class PageLines:
    lines: list[Line]  # long merged lines
    short: list[Line]  # short merged strokes (rung candidates)
    dark: list[tuple[Line, float]]  # filled bars: centre line and width
    curves: list[list[Point]]  # chains of tiny pieces (flattened arcs)


def angle_of(s: Line) -> float:
    return math.degrees(math.atan2(s.b[1] - s.a[1], s.b[0] - s.a[0])) % 180


def frame(angle: float) -> tuple[np.ndarray, np.ndarray]:
    """Unit vectors along and across a direction."""
    t = math.radians(angle)
    return np.array([math.cos(t), math.sin(t)]), np.array([-math.sin(t), math.cos(t)])


def by_direction(segs: list[Line]) -> list[tuple[float, list[Line]]]:
    """Segments grouped by direction, in angle order; 179.8 degrees joins 0."""
    tagged = sorted((((a if a < 180 - ANGLE_BIN_DEG else a - 180), s) for a, s in ((angle_of(s), s) for s in segs)),
                    key=lambda x: x[0])
    groups: list[tuple[float, list[Line]]] = []
    cur: list[tuple[float, Line]] = []
    for item in tagged:
        if cur and item[0] - cur[-1][0] > ANGLE_BIN_DEG:
            groups.append((float(np.median([x[0] for x in cur])), [x[1] for x in cur]))
            cur = []
        cur.append(item)
    if cur:
        groups.append((float(np.median([x[0] for x in cur])), [x[1] for x in cur]))
    return groups


def _merge(segs: list[Line], angle: float) -> list[Line]:
    d, n = frame(angle)
    rows = sorted(((np.dot(s.a, n) + np.dot(s.b, n)) / 2, *sorted((float(np.dot(s.a, d)), float(np.dot(s.b, d)))))
                  for s in segs)
    out: list[Line] = []
    cluster: list[tuple[float, float, float]] = []

    def flush() -> None:
        c = float(np.median([r[0] for r in cluster]))
        spans = sorted((r[1], r[2]) for r in cluster)
        lo, hi = spans[0]
        for x, y in spans[1:] + [(math.inf, math.inf)]:
            if x <= hi + MERGE_GAP_MM:
                hi = max(hi, y)
                continue
            out.append(Line(tuple(lo * d + c * n), tuple(hi * d + c * n)))
            lo, hi = x, y

    for r in rows:
        if cluster and r[0] - cluster[-1][0] > MERGE_TOL_MM:
            flush()
            cluster = []
        cluster.append(r)
    if cluster:
        flush()
    return out


def _chains(tiny: list[Line]) -> list[list[Point]]:
    """Tiny pieces joined end to end; a junction ends a chain."""
    key = lambda p: (round(p[0] / CHAIN_JOIN_MM), round(p[1] / CHAIN_JOIN_MM))  # noqa: E731
    nbr: dict[tuple, list[tuple]] = defaultdict(list)
    pos: dict[tuple, Point] = {}
    for s in tiny:
        ka, kb = key(s.a), key(s.b)
        if ka != kb:
            nbr[ka].append(kb)
            nbr[kb].append(ka)
            pos.setdefault(ka, s.a)
            pos.setdefault(kb, s.b)
    seen: set[frozenset] = set()
    out = []
    for start in sorted(nbr, key=lambda k: (len(nbr[k]) != 1, k)):
        for first in sorted(nbr[start]):
            if frozenset((start, first)) in seen:
                continue
            path, prev, cur = [start, first], start, first
            seen.add(frozenset((start, first)))
            while len(nbr[cur]) == 2:
                nxt = next((k for k in nbr[cur] if k != prev), None)
                if nxt is None or frozenset((cur, nxt)) in seen:
                    break
                seen.add(frozenset((cur, nxt)))
                path.append(nxt)
                prev, cur = cur, nxt
            pts = [pos[k] for k in path]
            length = sum(math.dist(u, v) for u, v in zip(pts, pts[1:], strict=False))
            if length >= CURVE_MIN_MM and math.dist(pts[0], pts[-1]) / length <= CURVE_MAX_STRAIGHT:
                out.append(pts)
    return out


def read_lines(pdf: Path, page: int, px_to_mm: list[float], bbox_px: tuple[int, int, int, int], dpi: int) -> PageLines:
    """px_to_mm maps original raster px (the page at `dpi`); only paths inside bbox_px are kept."""
    import pymupdf as fitz

    A = np.array(px_to_mm, float).reshape(2, 3)
    k = dpi / 72
    x0, y0, x1, y1 = bbox_px
    corners = np.array([A @ (x, y, 1.0) for x, y in ((x0, y0), (x1, y1))])
    lo, hi = corners.min(0) - BBOX_MARGIN_MM, corners.max(0) + BBOX_MARGIN_MM
    pieces: list[Line] = []
    tiny: list[Line] = []
    dark: list[tuple[Line, float]] = []
    with fitz.open(pdf) as doc:
        pg = doc[page - 1]
        rot = pg.rotation_matrix

        def mm(p) -> Point:
            q = fitz.Point(p) * rot
            v = A @ (q.x * k, q.y * k, 1.0)
            return float(v[0]), float(v[1])

        def add(a: Point, b: Point) -> None:
            if not (lo[0] <= (a[0] + b[0]) / 2 <= hi[0] and lo[1] <= (a[1] + b[1]) / 2 <= hi[1]):
                return
            s = Line(a, b)
            pieces.append(s)
            if math.dist(a, b) < CHAIN_SEG_MM:
                tiny.append(s)

        for path in pg.get_drawings():
            fill = path.get("fill")
            solid = fill is not None and max(fill) < DARK_MAX
            for it in path["items"]:
                if it[0] == "l":
                    add(mm(it[1]), mm(it[2]))
                elif it[0] == "c":
                    pts = [fitz.Point(p) for p in it[1:5]]
                    ts = np.linspace(0, 1, BEZIER_STEPS + 1)
                    curve = [mm(pts[0] * (1 - t) ** 3 + pts[1] * 3 * t * (1 - t) ** 2 + pts[2] * 3 * t * t * (1 - t)
                                 + pts[3] * t ** 3) for t in ts]
                    for u, v in zip(curve, curve[1:], strict=False):
                        s = Line(u, v)
                        tiny.append(s)
                elif it[0] in ("re", "qu"):
                    q = it[1].quad if it[0] == "re" else it[1]
                    c = [mm(q.ul), mm(q.ur), mm(q.lr), mm(q.ll)]
                    if solid:
                        dark.append(_bar(c))
                    else:
                        for i in range(4):
                            add(c[i], c[(i + 1) % 4])
    level = [s for s in pieces if abs(s.a[1] - s.b[1]) <= AXIS_TOL_MM and abs(s.a[0] - s.b[0]) > 0]
    plumb = [s for s in pieces if abs(s.a[0] - s.b[0]) <= AXIS_TOL_MM and abs(s.a[1] - s.b[1]) > 0]
    axis = {id(s) for s in level} | {id(s) for s in plumb}
    skew = [s for s in pieces if id(s) not in axis and math.dist(s.a, s.b) >= SKEW_MIN_MM]
    merged = _merge(level, 0) if level else []
    merged += _merge(plumb, 90) if plumb else []
    for angle, group in by_direction(skew):
        merged += _merge(group, angle)
    size = lambda s: math.dist(s.a, s.b)  # noqa: E731
    return PageLines([s for s in merged if size(s) >= MIN_LINE_MM],
                     [s for s in merged if SHORT_MM[0] <= size(s) <= SHORT_MM[1]], dark, _chains(tiny))


def _bar(c: list[Point]) -> tuple[Line, float]:
    """A filled quad as its centre line and width."""
    mid = lambda u, v: ((u[0] + v[0]) / 2, (u[1] + v[1]) / 2)  # noqa: E731
    w, h = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    if w >= h:
        return Line(mid(c[0], c[3]), mid(c[1], c[2])), h
    return Line(mid(c[0], c[1]), mid(c[3], c[2])), w
