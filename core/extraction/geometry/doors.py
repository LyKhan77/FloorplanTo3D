"""Doors (PRD/04 §3.4): swing arcs fitted to circles (hinge = centre), doubles, and arc-less gaps. Working px.

Arc pixels are the skeleton of `clean` minus the axis-aligned strokes (walls, door leaves); what is left is curves,
each fitted with an algebraic (Kåsa) circle.
"""

import math

import cv2
import numpy as np
from skimage.morphology import skeletonize

from core.extraction.geometry.postprocess import _rebuild

COVER_DEG = (60, 100)
RADIUS_MM = (500, 1300)
MAX_RESIDUAL = 0.08
MIN_ARC_PX = 15
JAMB_MARGIN_MM = 60  # V008 wants >= 50 mm of wall either side of an opening
EXTENDED_CONF = 0.55  # a door that needed its wall extended goes to review


def curve_skeleton(clean: np.ndarray, strokes: list[dict]) -> np.ndarray:
    sk = (skeletonize(clean > 0) * 255).astype(np.uint8)
    straight = np.zeros_like(sk)
    for x in strokes:
        if x["orient"] in ("h", "v"):
            cv2.line(straight, (round(x["p0"][0]), round(x["p0"][1])), (round(x["p1"][0]), round(x["p1"][1])), 255,
                     max(3, round(x["width"]) + 2))
    return np.where(straight > 0, 0, sk).astype(np.uint8)


def _fit_circle(pts: np.ndarray) -> tuple[float, float, float, float]:
    x, y = pts[:, 0].astype(float), pts[:, 1].astype(float)
    a = np.column_stack([x, y, np.ones_like(x)])
    sol, *_ = np.linalg.lstsq(a, -(x ** 2 + y ** 2), rcond=None)
    cx, cy = -sol[0] / 2, -sol[1] / 2
    r = math.sqrt(max(cx ** 2 + cy ** 2 - sol[2], 0))
    rms = float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - r) ** 2)))
    return cx, cy, r, rms


def _ordered(pts: np.ndarray) -> np.ndarray:
    """Pixels of a thin curve ordered along it, walking from an end (branches beyond the walk are dropped)."""
    idx = {(int(x), int(y)): i for i, (x, y) in enumerate(pts)}

    def nbrs(p):
        return [(p[0] + dx, p[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if (dx or dy) and (p[0] + dx, p[1] + dy) in idx]

    start = next((p for p in sorted(idx) if len(nbrs(p)) == 1), min(idx))
    path, seen, cur = [start], {start}, start
    while True:
        nxt = [q for q in nbrs(cur) if q not in seen]
        if not nxt:
            break
        cur = min(nxt, key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))  # 4-neighbours before diagonals
        seen.add(cur)
        path.append(cur)
    return np.array(path)


def _arc(pts: np.ndarray, s: float) -> dict | None:
    cx, cy, r, rms = _fit_circle(pts)
    if not RADIUS_MM[0] <= r * s <= RADIUS_MM[1] or rms > MAX_RESIDUAL * r:
        return None
    ang = np.sort(np.degrees(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)) % 360)
    gaps = np.diff(np.concatenate([ang, [ang[0] + 360]]))
    k = int(np.argmax(gaps))
    cover = 360 - gaps[k]
    if not COVER_DEG[0] <= cover <= COVER_DEG[1]:
        return None
    a_start, a_end = ang[(k + 1) % len(ang)], ang[k]
    ends = [(cx + r * math.cos(math.radians(t)), cy + r * math.sin(math.radians(t))) for t in (a_start, a_end)]
    return {"center": [cx, cy], "radius_px": r, "residual": rms, "ends": ends}


def _arcs_in(path: np.ndarray, s: float, depth: int = 0) -> list[dict]:
    """A path that is not one arc is split in the middle (two leaves of a double door touch where they meet)."""
    if len(path) < MIN_ARC_PX:
        return []
    if a := _arc(path, s):
        return [a]
    if depth >= 3:
        return []
    mid = len(path) // 2
    return _arcs_in(path[:mid], s, depth + 1) + _arcs_in(path[mid:], s, depth + 1)


def _branches(comp: np.ndarray) -> list[np.ndarray]:
    """Split a skeleton component at its junction pixels (>= 3 neighbours)."""
    k = np.ones((3, 3), np.uint8)
    deg = cv2.filter2D((comp > 0).astype(np.uint8), -1, k) - 1
    junction = cv2.dilate(((comp > 0) & (deg >= 3)).astype(np.uint8), k)
    pieces = np.where(junction > 0, 0, comp).astype(np.uint8)
    n, labels = cv2.connectedComponents(pieces, connectivity=8)
    out = []
    for i in range(1, n):
        ys, xs = np.nonzero(labels == i)
        if len(xs) >= MIN_ARC_PX:
            out.append(np.column_stack([xs, ys]))
    return out


def find_arcs(curves: np.ndarray, s: float) -> list[dict]:
    n, labels, stats, _ = cv2.connectedComponentsWithStats(curves, connectivity=8)
    arcs = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < MIN_ARC_PX:
            continue
        # work on the component's own bbox (padded): full-image masks per component cost seconds
        x0, y0 = max(0, x - 1), max(0, y - 1)
        comp = (labels[y0:y + h + 1, x0:x + w + 1] == i).astype(np.uint8) * 255
        ys, xs = np.nonzero(comp)
        pts = np.column_stack([xs + x0, ys + y0])
        whole = _arc(pts, s)
        if whole:
            arcs.append(whole)
            continue
        for piece in _branches(comp):
            arcs += _arcs_in(_ordered(piece + np.array([x0, y0])), s)
    return sorted(arcs, key=lambda a: (round(a["center"][1]), round(a["center"][0])))


def _along_across(w: dict, p) -> tuple[float, float]:
    return (p[0], p[1]) if w["orient"] == "h" else (p[1], p[0])


def _left_of(w: dict, p) -> bool:
    """Is p on the left of the wall a->b in spec mm (y up)?"""
    ux, uy = w["p1"][0] - w["p0"][0], -(w["p1"][1] - w["p0"][1])
    vx, vy = p[0] - w["p0"][0], -(p[1] - w["p0"][1])
    return ux * vy - uy * vx > 0


def _ink_along(clean: np.ndarray, p, q) -> float:
    n = max(2, int(math.dist(p, q)))
    h, w = clean.shape
    hits = 0
    for t in np.linspace(0, 1, n):
        x, y = round(p[0] + (q[0] - p[0]) * t), round(p[1] + (q[1] - p[1]) * t)
        hits += 0 <= x < w and 0 <= y < h and bool(clean[max(0, y - 1):y + 2, max(0, x - 1):x + 2].any())
    return hits / n


def _door(wi: int, w: dict, lo: float, hi: float, s: float, **fields) -> dict:
    return {"wall": wi, "category": "door", "offset": round((lo - w["a"]) * s), "width": round((hi - lo) * s),
            "lo": lo, "hi": hi, **fields}


def doors_from_arcs(arcs: list[dict], walls: list[dict], clean: np.ndarray, s: float) -> list[dict]:
    singles = []
    for arc in arcs:
        hx, hy = arc["center"]
        r = arc["radius_px"]
        best = None
        for wi, w in enumerate(walls):
            if w["orient"] == "o":
                continue
            along, across = _along_across(w, (hx, hy))
            if abs(across - w["c"]) <= w["thickness_mm"] / s + 100 / s and w["a"] - r <= along <= w["b"] + r:
                # the host carries the hinge and the closed leaf end on its line and the leaf over its extent; a
                # perpendicular wall ending at the hinge has the leaf off its line or beyond its end
                closed = min(arc["ends"], key=lambda e: abs(_along_across(w, e)[1] - w["c"]))
                lo, hi = sorted((along, _along_across(w, closed)[0]))
                d = abs(across - w["c"]) + abs(_along_across(w, closed)[1] - w["c"]) + max(0, w["a"] - lo) \
                    + max(0, hi - w["b"])
                if best is None or d < best[0]:
                    best = (d, wi)
        if best is None:
            continue
        wi = best[1]
        w = walls[wi]
        e0, e1 = arc["ends"]
        closed, opened = (e0, e1) if abs(_along_across(w, e0)[1] - w["c"]) <= abs(_along_across(w, e1)[1] - w["c"]) else (e1, e0)
        h_along = _along_across(w, (hx, hy))[0]
        c_along = _along_across(w, closed)[0]
        lo, hi = sorted((h_along, c_along))
        fit = max(0.0, 1 - arc["residual"] / (MAX_RESIDUAL * r))
        leaf = _ink_along(clean, (hx, hy), opened) >= 0.6
        gap = any(min(hi, gb) - max(lo, ga) >= 0.7 * (hi - lo) for ga, gb in w["evidence"].get("gaps", []))
        singles.append(_door(wi, w, lo, hi, s, door_type="single_swing", hinge="start" if h_along <= c_along else "end",
                             swing="left" if _left_of(w, opened) else "right", radius=r, hinge_along=h_along,
                             confidence=round(min(1.0, 0.35 + 0.35 * fit + 0.15 * leaf + 0.15 * gap), 3),
                             evidence={"arc_residual_px": round(arc["residual"], 2), "leaf": leaf, "gap": gap}))
    out, used = [], set()
    for i, a in enumerate(singles):  # two arcs hinged at both ends of one opening, facing each other
        if i in used:
            continue
        for j in range(i + 1, len(singles)):
            b = singles[j]
            if j in used or b["wall"] != a["wall"] or abs(a["radius"] - b["radius"]) > 0.15 * max(a["radius"], b["radius"]):
                continue
            first, second = (a, b) if a["lo"] <= b["lo"] else (b, a)
            if abs(first["hi"] - second["lo"]) <= 0.15 * first["radius"] and first["hinge"] == "start" \
                    and second["hinge"] == "end":
                w = walls[a["wall"]]
                swing = first["swing"]  # double leaves swing to the same side; the first one decides
                out.append(_door(a["wall"], w, first["lo"], second["hi"], s, door_type="double_swing", hinge="both",
                                 swing=swing, confidence=round(min(a["confidence"], b["confidence"]), 3),
                                 evidence={"arcs": 2}))
                used.update((i, j))
                break
        else:
            out.append(a)
            used.add(i)
    return out


def doors_from_gaps(gap_openings: list[dict], strokes: list[dict], walls: list[dict], s: float) -> list[dict]:
    out = []
    for g in gap_openings:
        w = walls[g["wall_index"]]
        lo = w["a"] + g["offset_mm"] / s
        hi = lo + g["width_mm"] / s
        band = w["thickness_mm"] / s / 2 + 2
        sliding = any(x["orient"] == w["orient"] and abs(x["c"] - w["c"]) <= band and x["a"] >= lo - 2
                      and x["b"] <= hi + 2 and x["b"] - x["a"] >= 0.5 * (hi - lo) for x in strokes)
        out.append(_door(g["wall_index"], w, lo, hi, s, door_type="sliding" if sliding else "opening", hinge=None,
                         swing=None, confidence=0.55 if sliding else 0.4, evidence={"gap": True, "arc": False}))
    return out


def find_doors(clean: np.ndarray, strokes: list[dict], walls: list[dict], gap_openings: list[dict], s: float) -> list[dict]:
    arcs = doors_from_arcs(find_arcs(curve_skeleton(clean, strokes), s), walls, clean, s)
    gaps = [g for g in doors_from_gaps(gap_openings, strokes, walls, s)
            if not any(a["wall"] == g["wall"] and min(a["hi"], g["hi"]) - max(a["lo"], g["lo"]) > 0.5 * (g["hi"] - g["lo"])
                       for a in arcs)]
    keep = ("wall", "category", "offset", "width", "door_type", "hinge", "swing", "confidence", "evidence")
    return sorted(({k: d[k] for k in keep} for d in arcs + gaps), key=lambda d: (d["wall"], d["offset"]))


def fit_to_walls(doors: list[dict], walls: list[dict], s: float) -> tuple[list[dict], list[dict]]:
    """Keep every opening inside its wall (V008) and openings on one wall apart (V009).

    Of two overlapping openings the more confident stays. A door overhanging its wall end (the far jamb's wall was
    not detected) extends the wall over it; such a door is sent to review.
    """
    margin = JAMB_MARGIN_MM / s
    spans = []
    for d in sorted(doors, key=lambda d: (-d["confidence"], d["wall"], d["offset"])):
        w = walls[d["wall"]]
        lo, hi = w["a"] + d["offset"] / s, w["a"] + (d["offset"] + d["width"]) / s
        if not any(k["wall"] == d["wall"] and min(hi, khi) > max(lo, klo) for k, klo, khi in spans):
            spans.append((d, lo, hi))
    out_walls = list(walls)
    for wi in {d["wall"] for d, _, _ in spans}:
        w = walls[wi]
        on = [(lo, hi) for d, lo, hi in spans if d["wall"] == wi]
        a, b = min([w["a"]] + [lo - margin for lo, _ in on]), max([w["b"]] + [hi + margin for _, hi in on])
        if (a, b) != (w["a"], w["b"]):
            ev = w["evidence"] | {"extended_for_door_mm": round((w["a"] - a + b - w["b"]) * s)}
            out_walls[wi] = _rebuild(w, a=a, b=b, evidence=ev)
    out = []
    for d, lo, hi in spans:
        w, nw = walls[d["wall"]], out_walls[d["wall"]]
        n = {**d, "offset": round((lo - nw["a"]) * s)}
        if lo - margin < w["a"] or hi + margin > w["b"]:
            n |= {"confidence": min(d["confidence"], EXTENDED_CONF), "evidence": d["evidence"] | {"wall_extended": True}}
        out.append(n)
    return sorted(out, key=lambda d: (d["wall"], d["offset"])), out_walls
