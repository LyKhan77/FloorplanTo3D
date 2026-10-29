"""Correction effort (M7a-2): the editor operations, and the minutes, a person needs to turn an extracted spec into
the GT — MVP success criterion #2 ("sisa galat terkoreksi lewat panel koreksi <= 15 menit").

Rooms have no geometry operation of their own: the editor forms rooms from walls, so adding and deleting walls
fixes their shape; only their type and name are set by hand. The seconds per operation are a stated model, to be
calibrated with a timed editor session.

The bulk model (M7a-3) prices the editor's bulk actions: one delete for every selected false wall, one room-type
action per target type, and chained wall drawing (one click and Enter per wall).
"""

import numpy as np
from shapely.geometry import LineString, Point, Polygon

from benchmarks.extraction_metrics import _door_geom, _same_direction
from benchmarks.failure_modes import wall_coverage
from core.spec.models import Spec

SECONDS = {"delete_wall": 5, "add_wall": 20, "delete_opening": 5, "add_opening": 15, "set_door": 10,
           "set_room_type": 8, "rename_room": 8, "set_stair": 20}
# per action + per element selected: delete N walls, set the type of N rooms in G groups; chained add per wall
BULK_SECONDS = {"action": 10, "select": 2, "add_wall": 10}
# M8 review tools: a two-click gap closure (wall extension + door) and a guide line snapped onto the drawing
REVIEW_SECONDS = {"gap": 8, "guide_line": 12}
GAP_MATCH_MM = 150
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
    groups = set()
    for g in gt.rooms:
        gs = Polygon(g.polygon, g.holes)
        best = None
        for r, ps in shapes:
            inter = gs.intersection(ps).area
            if inter and inter / gs.union(ps).area >= 0.5:
                best = r
                break
        if g.type != "other" and (best is None or best.type != g.type):
            types += 1
            groups.add(g.type)
        names += bool(g.name) and (best is None or best.name != g.name)
    return {"set_room_type": types, "room_type_groups": len(groups), "rename_room": names}


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


def _gap_ops(pred: Spec, gt: Spec) -> dict[str, int]:
    """Review gap tasks of the prediction that lie on a GT wall, and how many of those hold a GT door."""
    from core.spec.review_tasks import review_tasks

    gwalls = [LineString([w.a, w.b]) for w in gt.walls]
    doors = [Point(d["center"]) for _, d in _doors(gt)]
    closures = door_gaps = 0
    for t in (t for t in review_tasks(pred) if t["kind"] == "gap"):
        seg = LineString([t["fix"]["a"], t["fix"]["b"]])
        if any(g.distance(seg.centroid) <= GAP_MATCH_MM for g in gwalls):
            closures += 1
            door_gaps += any(seg.distance(c) <= t["fix"]["thickness"] / 2 + GAP_MATCH_MM for c in doors)
    return {"gap_closures": closures, "gap_doors": door_gaps}


def correction_ops(pred: Spec | None, gt: Spec) -> dict[str, int]:
    """Operations per kind; pred None (a stopped run) means drawing every GT element from scratch."""
    if pred is None:
        return {"delete_wall": 0, "add_wall": len(gt.walls), "delete_opening": 0,
                "add_opening": sum(o.category == "door" for o in gt.openings), "set_door": 0,
                "set_room_type": sum(r.type != "other" for r in gt.rooms),
                "room_type_groups": len({r.type for r in gt.rooms if r.type != "other"}),
                "rename_room": sum(bool(r.name) for r in gt.rooms),
                "set_stair": sum(len(s.flights) for s in gt.stairs), "gap_closures": 0, "gap_doors": 0}
    return {"delete_wall": sum(wall_coverage(w, gt.walls) < 0.5 for w in pred.walls),
            "add_wall": sum(wall_coverage(g, pred.walls) < 0.5 for g in gt.walls),
            **_door_ops(pred, gt), **_room_ops(pred, gt), "set_stair": _stair_ops(pred, gt), **_gap_ops(pred, gt)}


def _seconds(ops: dict[str, int], bulk: bool) -> float:
    priced = {k for k in SECONDS if not (bulk and k in ("delete_wall", "set_room_type", "add_wall"))}
    seconds = sum(SECONDS[k] * n for k, n in ops.items() if k in priced)
    if bulk:
        b, dw, rt = BULK_SECONDS, ops.get("delete_wall", 0), ops.get("set_room_type", 0)
        seconds += ((b["action"] if dw else 0) + b["select"] * dw + b["action"] * ops.get("room_type_groups", 0)
                    + b["select"] * rt + b["add_wall"] * ops.get("add_wall", 0))
    return seconds


def correction_minutes(ops: dict[str, int], bulk: bool = False, review: bool = False) -> float:
    """`review`: the bulk model with the M8 tools; a gap closure replaces a missing door (or wall) on that gap, every
    other missing wall is a snapped guide line."""
    if not review:
        return round(_seconds(ops, bulk) / 60, 1)
    doors = min(ops.get("gap_doors", 0), ops.get("add_opening", 0))
    walls = min(ops.get("gap_closures", 0) - ops.get("gap_doors", 0), ops.get("add_wall", 0))
    rest = {**ops, "add_opening": ops.get("add_opening", 0) - doors, "add_wall": 0}
    extra = REVIEW_SECONDS["gap"] * (doors + walls) + REVIEW_SECONDS["guide_line"] * (ops.get("add_wall", 0) - walls)
    return round((_seconds(rest, True) + extra) / 60, 1)


def capped_minutes(pred: Spec | None, gt: Spec, bulk: bool = False, review: bool = False) -> float:
    """Minutes to correct, never more than redrawing from scratch: a reading worse than nothing is redrawn."""
    redraw = correction_minutes(correction_ops(None, gt), bulk, review)
    return redraw if pred is None else min(redraw, correction_minutes(correction_ops(pred, gt), bulk, review))
