"""Placements the interior engine produces, and their footprints and clearance zones."""

import math
from dataclasses import dataclass, field
from typing import Literal

from shapely import affinity
from shapely.geometry import Polygon
from shapely.geometry import box as sbox

from core.interior.library import Tpl
from core.interior.rules import Rules


@dataclass
class Placement:
    template_id: str
    version: str
    x: float
    y: float
    z: float
    rotation: float  # degrees CCW; the front is (-sin, cos)
    dims: tuple[float, float, float]
    source: Literal["rules", "drawing"] = "rules"

    def _place(self, g):
        return affinity.translate(affinity.rotate(g, self.rotation, origin=(0, 0)), self.x, self.y)

    def footprint(self) -> Polygon:
        w, d, _ = self.dims
        return self._place(sbox(-w / 2, -d / 2, w / 2, d / 2))

    def zones(self, tpl: Tpl, rules: Rules) -> list[Polygon]:
        """Front and back clearance rectangles (empty when the template asks for none)."""
        w, d, _ = self.dims
        front, back = clearance(tpl, rules)
        out = []
        if front:
            out.append(self._place(sbox(-w / 2, d / 2, w / 2, d / 2 + front)))
        if back:
            out.append(self._place(sbox(-w / 2, -d / 2 - back, w / 2, -d / 2)))
        return out

    def front(self) -> tuple[float, float]:
        t = math.radians(self.rotation)
        return (-math.sin(t), math.cos(t))

    def op(self) -> dict:
        return {"op": "add_object", "template_id": self.template_id, "template_version": self.version,
                "position": [round(self.x), round(self.y), round(self.z)], "rotation": round(self.rotation % 360, 1),
                "dims": [round(v) for v in self.dims]}


@dataclass
class Layout:
    placements: list[Placement] = field(default_factory=list)
    capacity: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)  # rows: {"runs": [[Placement]], "rows": [...]} for containment / devices


def rotation_for(front: tuple[float, float]) -> float:
    """Rotation (degrees) whose front (-sin, cos) is `front`."""
    return math.degrees(math.atan2(-front[0], front[1]))


def clearance(tpl: Tpl, rules: Rules) -> tuple[float, float]:
    """(front, back) working space: the template's, and electrical gear's front working space (NEC 110.26)."""
    front = tpl.front_clear
    if tpl.category in ("power", "battery"):
        front = max(front, rules.electrical_front_mm)
    return front, tpl.back_clear
