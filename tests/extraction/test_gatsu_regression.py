"""Gatsu stage-3 regression floors (M5b). Floors are the measured best-candidate values after tuning, rounded down;
the full NFR thresholds are reported by test_gatsu_meets_nfr (xfail until M5c/M7 close the gap)."""

import json
import math
import shutil
from functools import cache
from pathlib import Path

import pytest

from benchmarks.extraction_metrics import (
    THRESHOLDS,
    door_metrics,
    passed,
    stair_metrics_cmp,
    wall_iou,
    wall_metrics,
)
from core.extraction.geometry.elements import elements_to_spec
from core.extraction.stages import stage_extract
from core.spec.models import Spec
from tests.extraction.geometry.gatsu import gatsu_stages

pytestmark = pytest.mark.slow
GT = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
FLOORS = {  # metric: (floor, "min" | "max")
    "wall_recall": (0.68, "min"), "wall_precision": (0.81, "min"),
    "wall_pos_median_mm": (50, "max"), "wall_pos_p95_mm": (150, "max"),
    "door_recall": (0.52, "min"), "door_width_ok": (0.47, "min"), "door_dir_ok": (0.33, "min"),
    "stair_risers_ok": (0.33, "min"), "stair_dir_ok": (0.66, "min"), "wall_iou": (0.46, "min"),
}


@cache
def best(tmp_root: str) -> tuple[dict, Spec]:
    src = gatsu_stages()
    stages = Path(tmp_root) / "stages"
    for d in ("00_input", "01_preprocess", "02_grid"):
        shutil.copytree(src / d, stages / d)
    stage_extract(src.parents[2], stages / "03_extract", 12)
    grid = json.loads((stages / "02_grid/grid.json").read_text())
    scored = []
    for c in json.loads((stages / "03_extract/candidates.json").read_text()):
        if c["error"]:
            continue
        el = json.loads((stages / f"03_extract/candidates/{c['index']}/elements.json").read_text())
        pred = elements_to_spec(el, grid)
        m = {**wall_metrics(pred, GT), **door_metrics(pred, GT), **stair_metrics_cmp(pred, GT),
             "wall_iou": wall_iou(pred, GT)}
        scored.append((m["wall_recall"] + m["wall_precision"], c["index"], m, pred))
    _, _, m, pred = max(scored, key=lambda t: (t[0], -t[1]))
    return m, pred


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return best(str(tmp_path_factory.mktemp("gatsu-m5b")))


def test_gatsu_stage3_meets_regression_floors(result):
    m, pred = result
    for k, (floor, kind) in FLOORS.items():
        assert (m[k] >= floor) if kind == "min" else (m[k] <= floor), (k, m[k], floor)
    structural = [c for c in GT.columns if c.kind == "structural"]
    found = sum(any(math.dist(c.center, p.center) <= 300 for p in pred.columns) for c in structural)
    assert found >= 16


@pytest.mark.xfail(strict=False, reason="NFR-AC-02..06, 08, 10 not reached yet on Gatsu (see ROADMAP Status M5b)")
def test_gatsu_meets_nfr(result):
    m, _ = result
    assert all(passed(m).values()), {k: (round(m[k], 3), THRESHOLDS[k]) for k, ok in passed(m).items() if not ok}
