"""Correction effort (M7a-2): the editor operations, and the minutes, a person needs to turn an extracted spec into
the GT — MVP success criterion #2 ("sisa galat terkoreksi lewat panel koreksi <= 15 menit").

Rooms have no geometry operation of their own: the editor forms rooms from walls, so adding and deleting walls
fixes their shape; only their type and name are set by hand. The seconds per operation are a stated model, to be
calibrated with a timed editor session.
"""

import numpy as np
from shapely.geometry import Polygon

from benchmarks.extraction_metrics import _door_geom, _same_direction
from benchmarks.failure_modes import wall_coverage
from core.spec.models import Spec

SECONDS = {"delete_wall": 5, "add_wall": 20, "delete_opening": 5, "add_opening": 15, "set_door": 10,
           "set_room_type": 8, "rename_room": 8, "set_stair": 20}
DOOR_MATCH_MM, DOOR_WIDTH_MM, STAIR_MATCH_MM = 500, 100, 1000


def _doors(spec: Spec) -> list[tuple]:
    walls = {w.id: w for w in spec.walls}
    return [(o, g) for o in spec.openings if o.category == "door" and (g := _door_geom(o, walls))]


def _door_ops(pred: Spec, gt: Spec) -> dict[str, int]:
    gd, pd = _doors(gt), _doors(pred)
    pairs = sorted((float(np.linalg.norm(g["center"] - p["center"])), i, j)
                   for i, (_, g) in enumerate(gd) for j, (_, p) in enumerate(pd))
    used_g, used_p, fix = set(), set(), 0
    for d, i, j in pairs:
        if d > DOOR_MATCH_MM:
            break
        if i in used_g or j in used_p:
            continue
        used_g.add(i)
        used_p.add(j)
        (go, g), (po, p) = gd[i], pd[j]
        directional = g["both"] or g["hinge"] is not None
        fix += (go.door_type != po.door_type or abs(g["width"] - p["width"]) > DOOR_WIDTH_MM
                or (directional and not _same_direction(p, g)))
    return {"add_opening": len(gd) - len(used_g), "delete_opening": len(pd) - len(used_p), "set_door": fix}


def _room_ops(pred: Spec, gt: Spec) -> dict[str, int]:
    shapes = [(r, Polygon(r.polygon, r.holes)) for r in pred.rooms]
    types = names = 0
    for g in gt.rooms:
        gs = Polygon(g.polygon, g.holes)
        best = None
        for r, ps in shapes:
            inter = gs.intersection(ps).area
            if inter and inter / gs.union(ps).area >= 0.5:
                best = r
                break
        types += g.type != "other" and (best is None or best.type != g.type)
        names += bool(g.name) and (best is None or best.name != g.name)
    return {"set_room_type": types, "rename_room": names}


def _stair_ops(pred: Spec, gt: Spec) -> int:
    pf = [f for s in pred.stairs for f in s.flights]
    mid = lambda f: (np.array(f.start, float) + np.array(f.end, float)) / 2
    fixes = 0
    for g in (f for s in gt.stairs for f in s.flights):
        p = min(pf, key=lambda f: float(np.linalg.norm(mid(f) - mid(g))), default=None)
        if p is None or float(np.linalg.norm(mid(p) - mid(g))) > STAIR_MATCH_MM or abs(p.risers - g.risers) > 1 \
                or float(np.subtract(p.end, p.start) @ np.subtract(g.end, g.start)) <= 0:
            fixes += 1
    return fixes


def correction_ops(pred: Spec | None, gt: Spec) -> dict[str, int]:
    """Operations per kind; pred None (a stopped run) means drawing every GT element from scratch."""
    if pred is None:
        return {"delete_wall": 0, "add_wall": len(gt.walls), "delete_opening": 0,
                "add_opening": sum(o.category == "door" for o in gt.openings), "set_door": 0,
                "set_room_type": sum(r.type != "other" for r in gt.rooms),
                "rename_room": sum(bool(r.name) for r in gt.rooms),
                "set_stair": sum(len(s.flights) for s in gt.stairs)}
    return {"delete_wall": sum(wall_coverage(w, gt.walls) < 0.5 for w in pred.walls),
            "add_wall": sum(wall_coverage(g, pred.walls) < 0.5 for g in gt.walls),
            **_door_ops(pred, gt), **_room_ops(pred, gt), "set_stair": _stair_ops(pred, gt)}


def correction_minutes(ops: dict[str, int]) -> float:
    return round(sum(SECONDS[k] * n for k, n in ops.items()) / 60, 1)
