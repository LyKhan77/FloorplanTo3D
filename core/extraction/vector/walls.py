"""Walls as pairs of parallel lines (a CAD wall is two lines a wall thickness apart), minus trays and equipment."""

from dataclasses import dataclass, field

import numpy as np

from core.extraction.vector.lines import Line, PageLines, Point, angle_of, by_direction, frame

PAIR_MM = (70, 420)  # plausible wall thickness; rack rows sit wider
MIN_OVERLAP_MM = 300
MIN_WALL_MM = 900  # shorter pairs are mostly tray rungs and equipment; they stay only if a room needs them
MIN_SINGLE_MM = 1500
SINGLE_THICKNESS_MM = 100
RUNG_REACH_MM = 15  # a rung meets both rails within this
RUNG_OVERSHOOT_MM = 60
RUNGS_PER_M = 1.5
HATCH_REACH = 2.5  # wall thicknesses to look either side of a skewed pair
HATCH_MIN_LINES = 4


@dataclass
class WallCand:
    a: Point
    b: Point
    thickness: float
    evidence: dict = field(default_factory=dict)


def _wall(a: Point, b: Point, thickness: float, **evidence) -> WallCand:
    length = float(np.hypot(a[0] - b[0], a[1] - b[1]))
    if length < MIN_WALL_MM:
        evidence["short"] = True
    return WallCand(a, b, thickness, evidence)


def _is_hatch(rows: list, c: float, c2: float, o0: float, o1: float) -> bool:
    """Diagonal hatch is a run of equally spaced parallels; a skewed wall has two lines."""
    reach = HATCH_REACH * (c2 - c)
    near = [r for r in rows if c - reach <= r[0] <= c2 + reach and min(r[2], o1) - max(r[1], o0) > 0.5 * (o1 - o0)]
    return len(near) >= HATCH_MIN_LINES


def _pairs(angle: float, group: list[Line], short: list[Line]) -> list[WallCand]:
    d, n = frame(angle)
    rows = sorted((float((np.dot(s.a, n) + np.dot(s.b, n)) / 2),
                    *sorted((float(np.dot(s.a, d)), float(np.dot(s.b, d))))) for s in group)
    cross = [s for s in short if abs((angle_of(s) - angle) % 180 - 90) < 10]
    ct = np.array([(np.dot(s.a, d) + np.dot(s.b, d)) / 2 for s in cross])
    cp = np.array([min(np.dot(s.a, n), np.dot(s.b, n)) for s in cross])
    cq = np.array([max(np.dot(s.a, n), np.dot(s.b, n)) for s in cross])
    out = []
    paired: set[int] = set()
    for i, (c, a, b) in enumerate(rows):
        for j in range(i + 1, len(rows)):
            c2, a2, b2 = rows[j]
            gap = c2 - c
            if gap > PAIR_MM[1]:
                break
            if gap < PAIR_MM[0]:
                continue
            o0, o1 = max(a, a2), min(b, b2)
            if o1 - o0 < MIN_OVERLAP_MM:
                continue
            if any(c < r[0] < c2 and min(r[2], o1) - max(r[1], o0) > 0.5 * (o1 - o0) for r in rows[i + 1:j]):
                continue
            if len(cross):
                rungs = ((ct >= o0) & (ct <= o1) & (cp <= c + RUNG_REACH_MM) & (cq >= c2 - RUNG_REACH_MM)
                         & (cq - cp <= gap + RUNG_OVERSHOOT_MM)).sum()
                if rungs / max((o1 - o0) / 1000, 0.3) > RUNGS_PER_M:
                    paired.update((i, j))  # rails stay out of the single-line walls too
                    continue
            if angle % 90 and _is_hatch(rows, c, c2, o0, o1):
                continue
            m = (c + c2) / 2
            paired.update((i, j))
            out.append(_wall(tuple(float(v) for v in o0 * d + m * n), tuple(float(v) for v in o1 * d + m * n), gap,
                             source="pair"))
    for i, (c, a, b) in enumerate(rows):  # a thin partition is one line; it counts only if it bounds a room
        if angle % 90 == 0 and i not in paired and b - a >= MIN_SINGLE_MM:
            out.append(WallCand(tuple(float(v) for v in a * d + c * n), tuple(float(v) for v in b * d + c * n),
                                SINGLE_THICKNESS_MM, {"source": "single", "short": True}))
    return out


def pair_walls(pl: PageLines) -> list[WallCand]:
    walls = [_wall(s.a, s.b, w, source="bar") for s, w in pl.dark if PAIR_MM[0] <= w <= PAIR_MM[1]]
    for angle, group in by_direction(pl.lines):
        walls += _pairs(angle, group, pl.short)
    return walls
