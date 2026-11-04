"""Doors for the vector path: the raster arc detector, in mm. Arcs in these PDFs are loose ~50 mm pieces with no
shared end points, so the vector side has nothing to chain (Ancol p13 and Gatsu p3: 0 arcs; raster: 38 and 34)."""

import math
from dataclasses import dataclass

import numpy as np

from core.extraction.door_scale import door_arcs
from core.extraction.vector.lines import Point


@dataclass(frozen=True)
class Door:
    hinge: Point
    radius: float
    ends: tuple[Point, Point]


def find_doors(binary: np.ndarray, bbox_px: tuple[int, int, int, int], px_to_mm: list[float]) -> list[Door]:
    """px_to_mm: the transform of `binary`'s px."""
    A = np.array(px_to_mm, float).reshape(2, 3)

    def mm(p) -> Point:
        v = A @ (p[0], p[1], 1.0)
        return float(v[0]), float(v[1])

    scale = math.sqrt(abs(np.linalg.det(A[:, :2])))
    return sorted((Door(mm(a["center"]), a["radius_px"] * scale, tuple(mm(e) for e in a["ends"]))
                   for a in door_arcs(binary, bbox_px)), key=lambda d: d.hinge)
