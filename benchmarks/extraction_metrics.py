"""Extraction accuracy against a ground-truth spec (PRD/01 NFR-AC-01..11). Pure functions; the CLI is run_extraction_bench."""

import math

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from core.spec.derive import column_footprint, wall_footprint
from core.spec.models import Opening, Spec, Wall

THRESHOLDS: dict[str, float] = {
    "scale_err": 0.005,  # max
    "wall_pos_median_mm": 50,  # max
    "wall_pos_p95_mm": 150,  # max
    "wall_recall": 0.95,
    "wall_precision": 0.95,
    "door_recall": 0.90,
    "door_width_ok": 0.90,
    "door_dir_ok": 0.80,
    "room_match": 0.90,
    "wall_iou": 0.85,
    "stair_risers_ok": 1.0,
    "stair_dir_ok": 1.0,
    "stair_pos_ok": 1.0,
    "gross_area_err": 0.01,  # max
}
LOWER_IS_BETTER = {"scale_err", "wall_pos_median_mm", "wall_pos_p95_mm", "gross_area_err"}
SAMPLE_MM = 50


def scale_metrics(mm_per_px: float, gt: Spec) -> dict:
    return {"scale_err": abs(mm_per_px - gt.meta.mm_per_px) / gt.meta.mm_per_px}


def grid_metrics(axes: list[dict], gt: Spec) -> dict:
    expected = {(a.orientation, a.label): a.offset for a in gt.grid.axes}
    found = {(a["orientation"], a["label"]): a["offset"] for a in axes}
    common = expected.keys() & found.keys()
    return {
        "axes_found": len(found), "axes_expected": len(expected), "label_ok": found.keys() == expected.keys(),
        "offset_max_err_mm": max((abs(found[k] - expected[k]) for k in common), default=None),
    }


# --- walls --------------------------------------------------------------------------------------------------------

def _samples(walls: list[Wall]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Centerline samples: points (n,2), per-sample length (n,), direction angle in [0, pi) (n,)."""
    pts, lens, angs = [], [], []
    for w in walls:
        (ax, ay), (bx, by) = w.a, w.b
        length = math.hypot(bx - ax, by - ay)
        if length == 0:
            continue
        n = max(1, round(length / SAMPLE_MM))
        t = (np.arange(n) + 0.5) / n
        pts.append(np.column_stack([ax + (bx - ax) * t, ay + (by - ay) * t]))
        lens.append(np.full(n, length / n))
        angs.append(np.full(n, math.atan2(by - ay, bx - ax) % math.pi))
    if not pts:
        return np.zeros((0, 2)), np.zeros(0), np.zeros(0)
    return np.vstack(pts), np.concatenate(lens), np.concatenate(angs)


def _nearest(points: np.ndarray, angles: np.ndarray, walls: list[Wall], angle_deg: float) -> np.ndarray:
    """Distance from each point to the nearest wall centerline whose direction is within angle_deg (inf if none)."""
    best = np.full(len(points), np.inf)
    tol = math.radians(angle_deg)
    for w in walls:
        a, b = np.array(w.a, float), np.array(w.b, float)
        ab = b - a
        L2 = float(ab @ ab)
        if L2 == 0:
            continue
        wang = math.atan2(ab[1], ab[0]) % math.pi
        diff = np.abs(angles - wang)
        ok = np.minimum(diff, math.pi - diff) <= tol
        if not ok.any():
            continue
        t = np.clip(((points - a) @ ab) / L2, 0, 1)
        d = np.linalg.norm(points - (a + t[:, None] * ab), axis=1)
        best = np.where(ok, np.minimum(best, d), best)
    return best


def wall_metrics(pred: Spec, gt: Spec, tol_mm: float = 150, angle_deg: float = 5) -> dict:
    gp, gl, ga = _samples(gt.walls)
    pp, pl, pa = _samples(pred.walls)
    gd = _nearest(gp, ga, pred.walls, angle_deg)
    pd = _nearest(pp, pa, gt.walls, angle_deg)
    hit = pd <= tol_mm
    err = pd[hit]
    return {
        "wall_recall": float(gl[gd <= tol_mm].sum() / gl.sum()) if gl.sum() else 0.0,
        "wall_precision": float(pl[hit].sum() / pl.sum()) if pl.sum() else 0.0,
        "wall_pos_median_mm": float(np.median(err)) if len(err) else None,
        "wall_pos_p95_mm": float(np.percentile(err, 95)) if len(err) else None,
    }


# --- doors --------------------------------------------------------------------------------------------------------

def _door_geom(o: Opening, walls: dict[str, Wall]) -> dict | None:
    w = walls.get(o.wall_id)
    if w is None:
        return None
    (ax, ay), (bx, by) = w.a, w.b
    length = math.hypot(bx - ax, by - ay) or 1.0
    ux, uy = (bx - ax) / length, (by - ay) / length
    at = lambda d: np.array([ax + ux * d, ay + uy * d])  # noqa: E731
    hinge = {"start": at(o.offset), "end": at(o.offset + o.width)}.get(o.hinge or "")
    normal = np.array([-uy, ux]) * (1 if o.swing == "left" else -1) if o.swing else None
    return {"center": at(o.offset + o.width / 2), "width": o.width, "hinge": hinge, "both": o.hinge == "both",
            "normal": normal}


def _same_direction(p: dict, g: dict, tol_mm: float = 300) -> bool:
    if g["both"]:
        hinge_ok = p["both"]
    else:
        hinge_ok = p["hinge"] is not None and float(np.linalg.norm(p["hinge"] - g["hinge"])) <= tol_mm
    swing_ok = g["normal"] is None or (p["normal"] is not None and float(p["normal"] @ g["normal"]) > 0)
    return hinge_ok and swing_ok


def door_metrics(pred: Spec, gt: Spec, match_mm: float = 500) -> dict:
    def doors(spec: Spec) -> list[dict]:
        walls = {w.id: w for w in spec.walls}
        return [g for o in spec.openings if o.category == "door" and (g := _door_geom(o, walls))]

    gd, pd = doors(gt), doors(pred)
    pairs = sorted((float(np.linalg.norm(g["center"] - p["center"])), i, j)
                   for i, g in enumerate(gd) for j, p in enumerate(pd))
    used_g, used_p, matched = set(), set(), []
    for d, i, j in pairs:
        if d > match_mm:
            break
        if i not in used_g and j not in used_p:
            used_g.add(i), used_p.add(j)
            matched.append((gd[i], pd[j]))
    directional = sum(g["both"] or g["hinge"] is not None for g in gd)
    n = len(gd) or 1
    return {
        "door_recall": len(matched) / n,
        "door_width_ok": sum(abs(g["width"] - p["width"]) <= 100 for g, p in matched) / n,
        "door_dir_ok": sum(_same_direction(p, g) for g, p in matched if g["both"] or g["hinge"] is not None)
        / directional if directional else None,
    }


# --- rooms, footprint, stairs, gross area -------------------------------------------------------------------------

def _room_shape(r) -> Polygon:
    return Polygon(r.polygon, r.holes)


def room_metrics(pred: Spec, gt: Spec) -> dict:
    gs, ps = [_room_shape(r) for r in gt.rooms], [_room_shape(r) for r in pred.rooms]
    pairs = []
    for i, g in enumerate(gs):
        for j, p in enumerate(ps):
            if g.intersects(p):
                inter = g.intersection(p).area
                iou = inter / (g.area + p.area - inter) if inter else 0.0
                if iou >= 0.5:
                    pairs.append((iou, i, j))
    used_g, used_p, errs = set(), set(), []
    for _, i, j in sorted(pairs, reverse=True):
        if i not in used_g and j not in used_p:
            used_g.add(i), used_p.add(j)
            errs.append(abs(ps[j].area - gs[i].area) / gs[i].area if gs[i].area else 0.0)
    return {"room_match": sum(e <= 0.03 for e in errs) / (len(gs) or 1), "rooms_pred": len(ps), "rooms_gt": len(gs),
            "area_err_max": max(errs, default=None)}


def _footprint(spec: Spec):
    return unary_union([wall_footprint(w, spec) for w in spec.walls] + [column_footprint(c) for c in spec.columns])


def wall_iou(pred: Spec, gt: Spec) -> float:
    a, b = _footprint(pred), _footprint(gt)
    union = a.union(b).area
    return a.intersection(b).area / union if union else 0.0


def stair_metrics_cmp(pred: Spec, gt: Spec) -> dict:
    gf = [f for s in gt.stairs for f in s.flights]
    if not gf:
        return {"stair_risers_ok": None, "stair_dir_ok": None, "stair_pos_ok": None}
    pf = [f for s in pred.stairs for f in s.flights]
    mid = lambda f: (np.array(f.start, float) + np.array(f.end, float)) / 2  # noqa: E731
    risers = dirs = pos = 0
    for g in gf:
        if not pf:
            break
        p = min(pf, key=lambda f: float(np.linalg.norm(mid(f) - mid(g))))
        risers += abs(p.risers - g.risers) <= 1
        dirs += float((np.subtract(p.end, p.start)) @ np.subtract(g.end, g.start)) > 0
        pos += float(np.linalg.norm(mid(p) - mid(g))) <= 100
    n = len(gf)
    return {"stair_risers_ok": risers / n, "stair_dir_ok": dirs / n, "stair_pos_ok": pos / n}


def gross_area_metrics(pred: Spec, gt: Spec) -> dict:
    g = gt.meta.gross_area_m2
    return {"gross_area_err": abs(pred.meta.gross_area_m2 - g) / g if g else None}


def passed(metrics: dict) -> dict[str, bool]:
    out = {}
    for k, limit in THRESHOLDS.items():
        v = metrics.get(k)
        if v is None:
            continue
        out[k] = v <= limit if k in LOWER_IS_BETTER else v >= limit
    return out


def evaluate(pred: Spec, gt: Spec) -> dict:
    m = {**scale_metrics(pred.meta.mm_per_px, gt), **wall_metrics(pred, gt), **door_metrics(pred, gt),
         **room_metrics(pred, gt), "wall_iou": wall_iou(pred, gt), **stair_metrics_cmp(pred, gt),
         **gross_area_metrics(pred, gt)}
    return m | {"passed": passed(m)}
