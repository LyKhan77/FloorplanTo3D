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
from core.spec.validate import validate
from tests.extraction.geometry.gatsu import gatsu_stages

pytestmark = pytest.mark.slow
GT = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
FLOORS = {  # metric: (floor, "min" | "max")
    "wall_recall": (0.73, "min"), "wall_precision": (0.82, "min"),
    "wall_pos_median_mm": (50, "max"), "wall_pos_p95_mm": (150, "max"),
    "door_recall": (0.42, "min"), "door_width_ok": (0.31, "min"), "door_dir_ok": (0.16, "min"),
    "stair_risers_ok": (0.33, "min"), "stair_dir_ok": (0.66, "min"), "wall_iou": (0.49, "min"),
}
COLUMN_FLOORS = {"structural_found": 18, "pilaster_found": 21, "structural_false_confident": 0,
                 "pilaster_false_confident": 9}


def _columns(pred: Spec) -> dict:
    out = {}
    for kind in ("structural", "pilaster"):
        gt = [c for c in GT.columns if c.kind == kind]
        mine = [c for c in pred.columns if c.kind == kind]
        out[f"{kind}_found"] = sum(any(math.dist(c.center, p.center) <= 300 for p in mine) for c in gt)
        out[f"{kind}_false_confident"] = sum(c.provenance.confidence >= 0.6
                                             and not any(math.dist(c.center, g.center) <= 300 for g in gt) for c in mine)
    return out


@cache
def run(tmp_root: str) -> dict:
    """Every candidate scored: {"stage": stage result, "candidates": [{index, error, metrics, errors}]}."""
    src = gatsu_stages()
    stages = Path(tmp_root) / "stages"
    for d in ("00_input", "01_preprocess", "02_grid"):
        shutil.copytree(src / d, stages / d)
    stage = stage_extract(src.parents[2], stages / "03_extract", 12)
    grid = json.loads((stages / "02_grid/grid.json").read_text())
    out = []
    for c in json.loads((stages / "03_extract/candidates.json").read_text()):
        if c["error"]:
            out.append({"index": c["index"], "error": c["error"]})
            continue
        el = json.loads((stages / f"03_extract/candidates/{c['index']}/elements.json").read_text())
        pred = elements_to_spec(el, grid)
        m = {**wall_metrics(pred, GT), **door_metrics(pred, GT), **stair_metrics_cmp(pred, GT),
             "wall_iou": wall_iou(pred, GT), **_columns(pred)}
        errors = sorted({i.code for i in validate(pred).issues if i.severity == "error"})
        out.append({"index": c["index"], "error": None, "metrics": m, "errors": errors})
    return {"stage": stage, "candidates": out}


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    return run(str(tmp_path_factory.mktemp("gatsu-m5b")))


def _check_floors(m: dict) -> None:
    for k, (floor, kind) in FLOORS.items():
        assert (m[k] >= floor) if kind == "min" else (m[k] <= floor), (k, m[k], floor)


def test_gatsu_stage3_every_candidate_runs_and_validates(result):
    assert result["stage"]["status"] == "succeeded" and not result["stage"]["warnings"]
    for c in result["candidates"]:
        assert c["error"] is None, c
        assert c["errors"] == [], (c["index"], c["errors"])  # V002/V008/V009... block stage 5


def test_gatsu_stage3_candidate0_meets_regression_floors(result):
    """Candidate 0 (S2, k 0.2, t_min 80, l_fix 0) is the default and the best on Gatsu: pinned, not oracle-picked."""
    m = result["candidates"][0]["metrics"]
    _check_floors(m)
    assert m["structural_found"] >= COLUMN_FLOORS["structural_found"]
    assert m["pilaster_found"] >= COLUMN_FLOORS["pilaster_found"]
    assert m["structural_false_confident"] <= COLUMN_FLOORS["structural_false_confident"]
    assert m["pilaster_false_confident"] <= COLUMN_FLOORS["pilaster_false_confident"]


def test_gatsu_stage3_best_candidate_meets_regression_floors(result):
    ok = [c for c in result["candidates"] if not c["error"]]
    _check_floors(max(ok, key=lambda c: (c["metrics"]["wall_recall"] + c["metrics"]["wall_precision"], -c["index"]))["metrics"])


@pytest.mark.xfail(strict=False, reason="NFR-AC-02..06, 08, 10 not reached yet on Gatsu (see ROADMAP Status M5b)")
def test_gatsu_meets_nfr(result):
    m = result["candidates"][0]["metrics"]
    assert all(passed(m).values()), {k: (round(m[k], 3), THRESHOLDS[k]) for k, ok in passed(m).items() if not ok}
