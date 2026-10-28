"""S2 double-line walls (PRD/04 §3.2): pairs of parallel strokes, assigned per interval.

A stroke keeps a list of still-free intervals. Candidate pairs are taken nearest gap first (the 110 mm skin of
Gatsu's outer band pairs before skin+rail), and a pair only consumes the part of both strokes it overlaps, so one
long line can pair with several partners along its length.
"""

import statistics

MIN_OVERLAP_FRAC = 0.6
MIN_WALL_MM = 300
PARTIAL_MAX_MM = 1500
PARTITION_MIN_MM = 1000


def _sub(intervals: list[tuple[float, float]], a: float, b: float) -> list[tuple[float, float]]:
    out = []
    for x, y in intervals:
        if y <= a or x >= b:
            out.append((x, y))
            continue
        if x < a:
            out.append((x, a))
        if y > b:
            out.append((b, y))
    return out


def _wall(orient: str, c: float, a: float, b: float, thickness_mm: float, evidence: dict) -> dict:
    p0, p1 = ((a, c), (b, c)) if orient == "h" else ((c, a), (c, b))
    r = lambda v: round(float(v), 2)
    return {"orient": orient, "c": r(c), "a": r(a), "b": r(b), "p0": [r(p0[0]), r(p0[1])], "p1": [r(p1[0]), r(p1[1])],
            "thickness_mm": round(thickness_mm), "strategy": "S2", "evidence": evidence}


def pair_strokes(strokes: list[dict], s: float, t_min_mm: float, t_max_mm: float) -> tuple[list[dict], list[list]]:
    """(walls, free intervals per stroke index)."""
    free = [[(x["a"], x["b"])] for x in strokes]
    cands = []
    for i, p in enumerate(strokes):
        if p["orient"] == "o":
            continue
        for j, q in enumerate(strokes):
            if j == i or q["orient"] != p["orient"] or q["c"] <= p["c"]:
                continue
            g = q["c"] - p["c"]
            if not t_min_mm / s <= g <= t_max_mm / s:
                continue
            overlap = min(p["b"], q["b"]) - max(p["a"], q["a"])
            # faces broken at different places overlap only in part: an absolute overlap of one minimum wall
            # length makes them candidates; the per-interval assignment below still takes nearest gaps first
            if overlap >= MIN_OVERLAP_FRAC * min(p["b"] - p["a"], q["b"] - q["a"]) or overlap * s >= MIN_WALL_MM:
                cands.append((g, p["c"], p["a"], i, j))
    walls = []
    for g, _, _, i, j in sorted(cands):
        for fa, fb in list(free[i]):
            for ga, gb in list(free[j]):
                a, b = max(fa, ga), min(fb, gb)
                if (b - a) * s < MIN_WALL_MM:
                    continue
                p = strokes[i]
                walls.append(_wall(p["orient"], p["c"] + g / 2, a, b, g * s,
                                   {"pair_overlap": round((b - a) / max(1e-9, min(p["b"] - p["a"], strokes[j]["b"] - strokes[j]["a"])), 3),
                                    "partial_mm": 0, "from": [i, j]}))
                free[i] = _sub(free[i], a, b)
                free[j] = _sub(free[j], a, b)
    return walls, free


def partial_pairs(walls: list[dict], strokes: list[dict], s: float) -> list[dict]:
    """Join two collinear walls across a gap <= 1500 mm when one side line runs on through the gap."""
    out: list[dict] = []
    for w in sorted(walls, key=lambda w: (w["orient"], round(w["c"]), w["a"])):
        last = out[-1] if out else None
        if last and last["orient"] == w["orient"] and abs(last["c"] - w["c"]) <= 2 \
                and abs(last["thickness_mm"] - w["thickness_mm"]) <= 0.2 * last["thickness_mm"]:
            gap = w["a"] - last["b"]
            if 0 < gap * s <= PARTIAL_MAX_MM:
                half = last["thickness_mm"] / s / 2
                side = any(x["orient"] == w["orient"] and x["a"] <= last["b"] + 1 and x["b"] >= w["a"] - 1
                           and min(abs(x["c"] - (w["c"] - half)), abs(x["c"] - (w["c"] + half))) <= 2 for x in strokes)
                if side:
                    ev = dict(last["evidence"]) | {"partial_mm": round(gap * s)}
                    out[-1] = _wall(w["orient"], (last["c"] + w["c"]) / 2, last["a"], w["b"], last["thickness_mm"], ev)
                    continue
        out.append(w)
    return out


def unpaired_partitions(strokes: list[dict], free: list[list], s: float, default_thickness_mm: float) -> list[dict]:
    widths = [x["width"] for x in strokes if x["orient"] != "o"]
    if not widths:
        return []
    med = statistics.median(widths)
    walls = []
    for x, intervals in zip(strokes, free, strict=True):
        if x["orient"] == "o" or x["width"] < 2 * med:
            continue
        for a, b in intervals:
            if (b - a) * s >= PARTITION_MIN_MM:
                walls.append(_wall(x["orient"], x["c"], a, b, default_thickness_mm,
                                   {"pair_overlap": 0.0, "partial_mm": 0, "unpaired": True}))
    return walls


def s2_walls(strokes: list[dict], s: float, t_min_mm: float, t_max_mm: float,
             default_thickness_mm: float = 100) -> list[dict]:
    walls, free = pair_strokes(strokes, s, t_min_mm, t_max_mm)
    walls = partial_pairs(walls, strokes, s)
    walls += unpaired_partitions(strokes, free, s, default_thickness_mm)
    return sorted(walls, key=lambda w: (w["orient"], w["c"], w["a"]))
