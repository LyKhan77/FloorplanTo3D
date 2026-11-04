"""Room-tracing gates (docs/superpowers/specs/2026-11-04-room-tracing-design.md §7).

uv run python -m benchmarks.run_room_tracing_bench --spec data/projects/<id>/specs/spec.v1.json
"""

import argparse
import itertools
import math
from pathlib import Path

from shapely.geometry import Polygon

from benchmarks.extraction_metrics import wall_metrics
from core.spec.models import Spec

GT = Path("benchmarks/ancol/gt_v8.json")  # frozen review of Ancol p13; client-derived, git-ignored
ANCOL_REVIEWED_BELOW = -38848  # mm: only the bottom of p13 is reviewed
TOL_MM = 200
ROOM_IOU = 0.6
ROOM_MIN_MM2 = 3e6
DUP_GAP_MM = 100
DUP_OVERLAP_MM = 300


def _region(spec: Spec, y_below: float | None) -> Spec:
    if y_below is None:
        return spec
    walls = [w for w in spec.walls if (w.a[1] + w.b[1]) / 2 < y_below]
    ids = {w.id for w in walls}
    return spec.model_copy(update={"walls": walls, "openings": [o for o in spec.openings if o.wall_id in ids]})


def _rooms(spec: Spec, y_below: float | None) -> list[Polygon]:
    polys = [Polygon(r.polygon, r.holes).buffer(0) for r in spec.rooms]
    return [p for p in polys if p.area >= ROOM_MIN_MM2 and (y_below is None or p.centroid.y < y_below)]


def _duplicates(spec: Spec) -> int:
    n = 0
    for u, v in itertools.combinations(spec.walls, 2):
        lu = math.dist(u.a, u.b)
        if not lu:
            continue
        dx, dy = (u.b[0] - u.a[0]) / lu, (u.b[1] - u.a[1]) / lu
        lv = math.dist(v.a, v.b)
        if not lv or abs(dx * (v.b[1] - v.a[1]) - dy * (v.b[0] - v.a[0])) / lv > 0.05:  # not parallel
            continue
        if abs(dx * (v.a[1] - u.a[1]) - dy * (v.a[0] - u.a[0])) > DUP_GAP_MM:
            continue
        s, t = sorted(dx * (p[0] - u.a[0]) + dy * (p[1] - u.a[1]) for p in (v.a, v.b))
        n += min(t, lu) - max(s, 0) > DUP_OVERLAP_MM
    return n


def gate_metrics(pred: Spec, gt: Spec, y_below: float | None) -> dict:
    p, g = _region(pred, y_below), _region(gt, y_below)
    wm = wall_metrics(p, g, tol_mm=TOL_MM)
    want, have = _rooms(gt, y_below), _rooms(pred, y_below)
    matched = sum(any(a.intersection(b).area / a.union(b).area >= ROOM_IOU for b in have) for a in want)
    return {"wall_recall": wm["wall_recall"], "wall_precision": wm["wall_precision"], "rooms_matched": matched,
            "rooms_total": len(want), "duplicates": _duplicates(p)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--gt", type=Path, default=GT)
    ap.add_argument("--below", type=float, default=ANCOL_REVIEWED_BELOW)
    a = ap.parse_args()
    m = gate_metrics(Spec.model_validate_json(a.spec.read_text()), Spec.model_validate_json(a.gt.read_text()), a.below)
    print({k: round(v, 3) if isinstance(v, float) else v for k, v in m.items()})


if __name__ == "__main__":
    main()
