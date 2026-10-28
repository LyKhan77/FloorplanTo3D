"""Gatsu end to end through stages 0-5 (M5c): spec metrics against GT, typed rooms, determinism (NFR-RL-06) and
the stage 1-5 time budget (NFR-PF-01). Floors are the measured values rounded down; the full NFR set is xfail."""

import hashlib
import json
import shutil
import time
from pathlib import Path

import pytest

from benchmarks.extraction_metrics import THRESHOLDS, evaluate, passed, typed_room_count
from core.extraction.stages import (
    stage_extract,
    stage_grid,
    stage_input,
    stage_preprocess,
    stage_rooms,
    stage_validate,
)
from core.spec.models import Spec
from core.spec.store import SpecStore

pytestmark = pytest.mark.slow
PLAN = Path("floorplan/plan.jpeg")
GT = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
FLOORS = {  # metric: (floor, "min" | "max"); NFR values where met (scale, wall position), else measured rounded down
    "scale_err": (0.005, "max"),
    "wall_recall": (0.77, "min"), "wall_precision": (0.77, "min"),  # M7a Task 5: stage 5 switched candidate
    "wall_pos_median_mm": (50, "max"), "wall_pos_p95_mm": (150, "max"),
    "door_recall": (0.47, "min"), "door_width_ok": (0.36, "min"),
    "stair_dir_ok": (0.66, "min"), "wall_iou": (0.48, "min"),
    "room_match": (0.04, "min"), "gross_area_err": (0.04, "max"),
}
TYPED_FLOOR = 4  # named GT rooms matched (IoU >= 0.5) with the right type; measured 4 of 17
STAGES_1_5_S = 120


def new_project(root: Path) -> Path:
    data = PLAN.read_bytes()
    (root / "input").mkdir(parents=True)
    (root / "input" / "original.jpg").write_bytes(data)
    (root / "input" / "input.json").write_text(json.dumps({
        "filename": "plan.jpeg", "sha256": hashlib.sha256(data).hexdigest(), "prompt": "", "params": {}, "page": None,
        "type": "jpg"}))
    return root


def run_pipeline(root: Path, from_stages: Path | None = None) -> dict:
    """Stages 0-5 (or 3-5 on top of copied 0-2 folders) in a fresh project; returns spec, stage 5 result, times."""
    project = new_project(root)
    st = project / "runs" / "r" / "stages"
    times = []
    steps = [(0, "00_input", stage_input), (1, "01_preprocess", stage_preprocess), (2, "02_grid", stage_grid)]
    if from_stages:
        for _, d, _ in steps:
            shutil.copytree(from_stages / d, st / d)
        times = [0.0, 0.0, 0.0]
    else:
        for _, d, fn in steps:
            t = time.perf_counter()
            fn(project, st / d)
            times.append(time.perf_counter() - t)
    for d, fn in (("03_extract", lambda p, w: stage_extract(p, w, 12)), ("04_rooms", stage_rooms),
                  ("05_validate", lambda p, w: stage_validate(p, w, "r"))):
        t = time.perf_counter()
        result = fn(project, st / d)
        times.append(time.perf_counter() - t)
    spec = SpecStore(project / "specs").load("HEAD")
    return {"spec": spec, "stage5": result, "times": [round(x, 1) for x in times], "stages": st}


def named_rooms_typed_right(pred: Spec, gt: Spec) -> int:
    return typed_room_count(pred, gt)


@pytest.fixture(scope="module")
def first(tmp_path_factory):
    return run_pipeline(tmp_path_factory.mktemp("gatsu-e2e"))


def test_stages_1_to_5_within_two_minutes(first):
    assert sum(first["times"][1:]) <= STAGES_1_5_S, first["times"]


def test_spec_meets_floors(first):
    m = evaluate(first["spec"], GT)
    for k, (floor, kind) in FLOORS.items():
        assert (m[k] >= floor) if kind == "min" else (m[k] <= floor), (k, m[k], floor)


def test_rooms_typed_from_labels(first):
    assert named_rooms_typed_right(first["spec"], GT) >= TYPED_FLOOR


def test_rerun_gives_identical_spec(first, tmp_path):
    again = run_pipeline(tmp_path / "b", from_stages=first["stages"])
    drop = {"meta": {"created_at", "run_id", "version", "parent_version", "project_id"}}  # second project
    assert again["spec"].model_dump(mode="json", exclude=drop) == first["spec"].model_dump(mode="json", exclude=drop)


@pytest.mark.xfail(strict=False, reason="NFR-AC-01..11 not all reached on Gatsu yet (see ROADMAP Status M5c)")
def test_nfr_full(first):
    m = evaluate(first["spec"], GT)
    assert all(passed(m).values()), {k: (m[k], THRESHOLDS[k]) for k, ok in passed(m).items() if not ok}


def test_stage6_skipped_keeps_stage5_spec(first):
    """Strata off (MVP success criterion #5): stage 6 is skipped and the spec stage 7 builds is stage 5's."""
    import dataclasses

    from core.config import load_settings
    from core.llm_review.stage import stage_review

    project = first["stages"].parents[2]
    head = SpecStore(project / "specs").head()
    r = stage_review(project, first["stages"] / "06_review", "r", dataclasses.replace(load_settings(), llm_tasks_enabled=()),
                     version=head, use_strata=True)
    assert r["status"] == "skipped" and r["metrics"]["reason"] == "disabled"
    assert SpecStore(project / "specs").head() == head and not (first["stages"] / "06_review").exists()
