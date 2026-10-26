"""Gatsu stage 0-2 outputs computed once per test session (shared by the stage-3 tests)."""

import hashlib
import json
import tempfile
from functools import cache
from pathlib import Path

import cv2

from core.extraction.stages import stage_grid, stage_input, stage_preprocess

PLAN = Path("floorplan/plan.jpeg")


@cache
def gatsu_stages() -> Path:
    root = Path(tempfile.mkdtemp(prefix="gatsu-stages-"))
    data = PLAN.read_bytes()
    (root / "input").mkdir()
    (root / "input" / "original.jpg").write_bytes(data)
    (root / "input" / "input.json").write_text(json.dumps({
        "filename": "plan.jpeg", "sha256": hashlib.sha256(data).hexdigest(), "prompt": "", "params": {}, "page": None,
        "type": "jpg"}))
    stages = root / "runs" / "r" / "stages"
    stage_input(root, stages / "00_input")
    stage_preprocess(root, stages / "01_preprocess")
    stage_grid(root, stages / "02_grid")
    return stages


@cache
def gatsu() -> dict:
    st = gatsu_stages()
    pre, grid = st / "01_preprocess", st / "02_grid"
    g = json.loads((grid / "grid.json").read_text())
    return {
        "page": cv2.imread(str(pre / "page.png"), cv2.IMREAD_GRAYSCALE),
        "binary": cv2.imread(str(pre / "bin.png"), cv2.IMREAD_GRAYSCALE),
        "colour": cv2.imread(str(pre / "colour.png"), cv2.IMREAD_GRAYSCALE),
        "meta": json.loads((pre / "meta.json").read_text()),
        "ocr": json.loads((grid / "ocr.json").read_text()),
        "grid": g,
        "s": g["mm_per_px_work"],
        "stages": st,
    }


def work(x_orig: float, y_orig: float) -> tuple[int, int]:
    """Original plan.jpeg pixel -> working pixel (Gatsu: 2x upscale, no deskew)."""
    return round(2 * x_orig), round(2 * y_orig)
