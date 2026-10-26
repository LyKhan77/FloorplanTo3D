"""Element confidence (PRD/04 §3.7). Elements below 0.6 go to the review queue (stage 6)."""

import numpy as np
from shapely.geometry import LineString, box

from core.extraction.geometry.postprocess import _touches

REVIEW_BELOW = 0.6


def wall_confidence(w: dict, hatch: np.ndarray, ocr_items: list[dict], axes_px: dict, walls: list[dict], s: float) -> float:
    ev = w.get("evidence", {})
    if w.get("strategy") == "S1":
        pair = float(ev.get("mask_density", 1.0))
    else:
        pair = 0.3 if ev.get("unpaired") else min(1.0, float(ev.get("pair_overlap", 1.0)))
    ends = sum(_touches(w, which, walls, s) for which in ("a", "b"))
    axes = axes_px["horizontal"] if w["orient"] == "h" else axes_px["vertical"] if w["orient"] == "v" else []
    grid = 1.0 if any(abs(w["c"] - a) * s <= 150 for a in axes) else 0.5
    partial = 1 - min(1.0, ev.get("partial_mm", 0) / 1500)
    conf = 0.35 * pair + 0.25 * (ends / 2) + 0.2 * grid + 0.2 * partial
    line = LineString([w["p0"], w["p1"]])
    n = max(2, int(line.length))
    h, wd = hatch.shape
    pts = [line.interpolate(t, normalized=True) for t in np.linspace(0, 1, n)]
    in_hatch = sum(0 <= round(p.x) < wd and 0 <= round(p.y) < h and hatch[round(p.y), round(p.x)] > 0 for p in pts) / n
    conf -= 0.3 * in_hatch
    if any(t.get("cls") == "annotation" and line.distance(box(*t["bbox"])) * s <= 300 for t in ocr_items):
        conf -= 0.15
    typical = float(np.median([x["thickness_mm"] for x in walls])) if walls else w["thickness_mm"]
    if w["thickness_mm"] > 2 * typical:  # far thicker than the plan's walls (V005 territory): e.g. a cable trench
        conf -= 0.25
    return round(float(np.clip(conf, 0, 1)), 3)
