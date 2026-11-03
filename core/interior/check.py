"""Checks of an interior proposal (design §6.5): O001 overlap, O002 clearance, O003 door zone.

They run on the proposal only; core/spec/validate stays as it is, so hand-placed objects in old projects keep their
status and the validator score does not change.
"""

from shapely.ops import unary_union

from core.interior.layout import Placement
from core.interior.library import Tpl
from core.interior.rules import Rules
from core.interior.space import Space

OVERHEAD_MM = 2000  # objects from this height up (containment roofs) take no floor space


def _z_overlap(a: Placement, b: Placement) -> bool:
    return a.z < b.z + b.dims[2] and b.z < a.z + a.dims[2]


def check(placements: list[Placement], space: Space, lib: dict[str, Tpl], rules: Rules) -> list[dict]:
    issues = []
    fps = [p.footprint() for p in placements]
    name = lambda i: f"{placements[i].template_id} #{i + 1}"
    for i in range(len(placements)):
        for j in range(i + 1, len(placements)):
            if _z_overlap(placements[i], placements[j]) and fps[i].intersection(fps[j]).area > 1:
                issues.append({"code": "O001", "severity": "error", "index": i,
                               "message": f"{name(i)} tumpang tindih dengan {name(j)}"})
    floor = [i for i, p in enumerate(placements) if p.z < OVERHEAD_MM and p.template_id not in rules.wall_mounted]
    room = space.room.buffer(1)
    for i in floor:
        p, tpl = placements[i], lib.get(placements[i].template_id)
        if tpl is None:
            continue
        for zone in p.zones(tpl, rules):
            others = unary_union([fps[j] for j in floor if j != i])
            if not room.covers(zone) or (not others.is_empty and zone.intersection(others).area > 1):
                issues.append({"code": "O002", "severity": "warning", "index": i,
                               "message": f"ruang kerja {name(i)} terhalang dinding atau objek lain"})
                break
        if any(fps[i].intersection(d.zone).area > 1 for d in space.doors):
            issues.append({"code": "O003", "severity": "warning", "index": i,
                           "message": f"{name(i)} menghalangi jalur pintu"})
    return issues
