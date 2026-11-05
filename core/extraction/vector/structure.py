"""Which candidate walls are structure, from the outside in (spec §6.5b).

A room in a data hall is full of lines: tray rails along its walls, equipment outlines, floor tiles. So firm walls
come first, and a line inside them is content until it proves to be a partition.
"""

import math
from collections.abc import Callable

import cv2
import numpy as np

from core.extraction.vector.lines import Point
from core.extraction.vector.walls import WallCand

SOLID_MM = 120  # ink thicker than this survives as a solid wall band; thin lines do not
SOLID_NEAR_MM = 140
SOLID_MIN_RUN_MM = 1500
SOLID_SHARE = 0.6  # of a wall's run on a solid band makes it firm
FIRM_LEN_MM = 1800  # a pair this long is firm without solid ink: thin double-line walls
RING_MM = 500  # parallel to a firm wall this close, along most of its run: tray or skirting
RING_SHARE = 0.6
TOUCH_MM = 600
MIN_PARTITION_MM = 1000
MIN_SINGLE_PARTITION_MM = 1500
GRID_TOL = 0.05  # spacing variation in a run of tile lines
GRID_RUN = 4  # lines at one pitch in a row


def solid_share(binary: np.ndarray, px_to_mm: list[float]) -> Callable[[WallCand], float]:
    """Share of a wall's run lying on solid ink in the rendered page. `px_to_mm` is `binary`'s transform."""
    A = np.vstack([np.array(px_to_mm, float).reshape(2, 3), [0, 0, 1]])
    scale = math.sqrt(abs(np.linalg.det(A[:2, :2])))
    inv = np.linalg.inv(A)
    k = max(2, round(SOLID_MM / scale))
    solid = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    _n, labels, stats, _ = cv2.connectedComponentsWithStats(solid, connectivity=8)
    longest = np.maximum(stats[:, 2], stats[:, 3]) * scale >= SOLID_MIN_RUN_MM
    longest[0] = False
    reach = max(3, round(SOLID_NEAR_MM / scale)) | 1
    near = cv2.dilate(longest[labels].astype(np.uint8), np.ones((reach, reach), np.uint8)) > 0
    h, w = near.shape

    def share(wall: WallCand) -> float:
        a, b = (inv @ (*p, 1.0) for p in (wall.a, wall.b))
        steps = max(2, int(np.hypot(a[0] - b[0], a[1] - b[1]) / 3))
        ts = np.linspace(0, 1, steps)
        xs = np.clip((a[0] + ts * (b[0] - a[0])).astype(int), 0, w - 1)
        ys = np.clip((a[1] + ts * (b[1] - a[1])).astype(int), 0, h - 1)
        return float(near[ys, xs].mean())
    return share


def _length(w: WallCand) -> float:
    return math.dist(w.a, w.b)


def _unit(w: WallCand) -> np.ndarray:
    v = np.array(w.b, float) - np.array(w.a, float)
    return v / max(float(np.linalg.norm(v)), 1e-9)


def _cross(u, v) -> float:
    return float(u[0] * v[1] - u[1] * v[0])


def _is_ring(w: WallCand, firm: list[WallCand]) -> bool:
    d, along = _unit(w), 0.0
    for o in firm:
        e = _unit(o)
        if abs(_cross(d, e)) > 0.05:
            continue
        origin = np.array(o.a, float)
        if not 1 < abs(_cross(e, np.array(w.a, float) - origin)) <= RING_MM:
            continue
        s, t = sorted(float(np.dot(e, np.array(p, float) - origin)) for p in (w.a, w.b))
        along += max(0.0, min(t, _length(o)) - max(s, 0.0))
    return along >= RING_SHARE * _length(w)


def _touch_distance(p: Point, w: WallCand) -> float:
    a, b = np.array(w.a, float), np.array(w.b, float)
    v, q = b - a, np.array(p, float)
    t = float(np.clip(np.dot(q - a, v) / max(float(np.dot(v, v)), 1e-9), 0, 1))
    return float(np.linalg.norm(q - (a + t * v)))


def _tile_lines(singles: list[WallCand]) -> set[int]:
    """Runs of parallel single lines at one pitch: a raised-floor grid."""
    out: set[int] = set()
    for axis in (0, 1):  # x of vertical lines, y of horizontal ones
        rows = sorted((w.a[axis], id(w)) for w in singles if abs(w.a[axis] - w.b[axis]) < 1)
        i = 0
        while i + 1 < len(rows):
            pitch = rows[i + 1][0] - rows[i][0]
            j = i + 1
            while j + 1 < len(rows) and pitch > 0 and abs(rows[j + 1][0] - rows[j][0] - pitch) <= GRID_TOL * pitch:
                j += 1
            if j - i + 1 >= GRID_RUN:
                out.update(r[1] for r in rows[i:j + 1])
            i = max(j, i + 1)
    return out


def select_walls(walls: list[WallCand], solid: Callable[[WallCand], float]) -> list[WallCand]:
    """Firm walls, then the partitions that hang from them. `solid` is `solid_share`."""
    singles = [w for w in walls if w.evidence.get("source") == "single"]
    tiles = _tile_lines(singles)
    firm, rest = [], []
    for w in walls:
        pair = w.evidence.get("source") != "single"
        (firm if pair and (solid(w) >= SOLID_SHARE or _length(w) >= FIRM_LEN_MM) else rest).append(w)
    pool = [w for w in rest if id(w) not in tiles and not _is_ring(w, firm)
            and _length(w) >= (MIN_SINGLE_PARTITION_MM if w.evidence.get("source") == "single" else MIN_PARTITION_MM)]
    kept = list(firm)
    grown = True
    while grown:
        grown = False
        for w in list(pool):
            touching = sum(any(_touch_distance(p, k) <= TOUCH_MM for k in kept) for p in (w.a, w.b))
            if touching >= (2 if w.evidence.get("source") == "single" else 1):
                kept.append(w)
                pool.remove(w)
                grown = True
    return [WallCand(w.a, w.b, w.thickness, {k: v for k, v in w.evidence.items() if k != "short"}) for w in kept]
