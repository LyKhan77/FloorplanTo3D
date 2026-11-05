"""The vector path as one stage-3 candidate, in `extract_candidate`'s output format."""

import math
from collections import Counter
from pathlib import Path

import numpy as np

from core.extraction.preprocess import PDF_DPI, VECTOR_MIN_PATHS
from core.extraction.vector.doors import find_doors
from core.extraction.vector.lines import Point, read_lines
from core.extraction.vector.rooms import trace_rooms
from core.extraction.vector.structure import select_walls, solid_share
from core.extraction.vector.walls import pair_walls
from core.spec.rooms import RoomLabel

VECTOR_INDEX = 100  # candidates.json index, clear of the raster sweep's
LABEL_REPEATS = 3  # a text this frequent labels equipment (PAC), not a room
LABEL_JOIN_MM = 2500  # lines of one room label sit this close
SURE, CLOSED = 0.8, 0.6  # wall confidence: read from the drawing, or added to close a room


def pick_seeds(labels: list[RoomLabel]) -> list[Point]:
    names = Counter(lb.name for lb in labels)
    seeds: list[Point] = []
    for lb in labels:
        if names[lb.name] < LABEL_REPEATS and all(math.dist(lb.at, q) > LABEL_JOIN_MM for q in seeds):
            seeds.append(tuple(lb.at))
    return seeds


def _mm_box(px_to_mm: list[float], bbox: list[int]) -> tuple[float, float, float, float]:
    A = np.array(px_to_mm, float).reshape(2, 3)
    p, q = A @ (bbox[0], bbox[1], 1.0), A @ (bbox[2], bbox[3], 1.0)
    return min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])


def _original_box(meta: dict) -> tuple[int, int, int, int]:
    W = np.vstack([np.array(meta["work_from_original"], float).reshape(2, 3), [0, 0, 1]])
    inv = np.linalg.inv(W)
    x0, y0, x1, y1 = meta["drawing_bbox"]
    p, q = inv @ (x0, y0, 1.0), inv @ (x1, y1, 1.0)
    return round(p[0]), round(p[1]), round(q[0]), round(q[1])


def vector_elements(pdf: Path, page: int, grid: dict, meta: dict, labels: list[RoomLabel], raster: dict,
                    binary: np.ndarray) -> dict | None:
    """None when the page is not vector (a scan). Columns, stairs and lifts come from raster candidate 0."""
    import pymupdf as fitz

    with fitz.open(pdf) as doc:
        if len(doc[page - 1].get_drawings()) < VECTOR_MIN_PATHS:
            return None
    bbox = tuple(meta["drawing_bbox"])
    lines = read_lines(pdf, page, grid["px_to_mm_original"], _original_box(meta), PDF_DPI)
    columns = raster.get("columns", [])
    structure = select_walls(pair_walls(lines), solid_share(binary, grid["px_to_mm"]))
    t = trace_rooms(structure, find_doors(binary, bbox, grid["px_to_mm"]), columns, pick_seeds(labels),
                    _mm_box(grid["px_to_mm"], list(bbox)))
    walls = [{"a": [round(v) for v in w.a], "b": [round(v) for v in w.b], "thickness": max(10, round(w.thickness)),
              "kind": "interior", "strategy": "vector", "confidence": CLOSED if "closer" in w.evidence else SURE,
              "evidence": w.evidence} for w in t.walls]
    return {"params": {"strategy": "vector"}, "walls": walls, "columns": columns, "openings": t.openings,
            "stairs": raster.get("stairs", []), "lifts": raster.get("lifts", []), "line_len_m": raster.get("line_len_m", 0),
            "issues": [], "closed": True}
