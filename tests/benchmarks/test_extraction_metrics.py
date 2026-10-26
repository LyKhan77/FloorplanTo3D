import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

from benchmarks.extraction_metrics import (
    door_metrics,
    evaluate,
    grid_metrics,
    scale_metrics,
    stair_metrics_cmp,
    wall_metrics,
)
from core.spec.models import Spec

GT_PATH = Path("benchmarks/gatsu/gt_spec.json")


@pytest.fixture(scope="module")
def gt() -> Spec:
    return Spec.model_validate_json(GT_PATH.read_text())


def shifted(spec: Spec, dx: int, dy: int) -> Spec:
    s = spec.model_copy(deep=True)
    for w in s.walls:
        w.a = (w.a[0] + dx, w.a[1] + dy)
        w.b = (w.b[0] + dx, w.b[1] + dy)
    return s


def test_gt_against_itself_is_perfect(gt):
    r = evaluate(gt, gt)
    assert r["wall_recall"] == r["wall_precision"] == 1.0
    assert r["wall_pos_median_mm"] == 0
    assert r["door_recall"] == 1.0 and r["door_dir_ok"] == 1.0 and r["door_width_ok"] == 1.0
    assert r["room_match"] == 1.0
    assert r["wall_iou"] == pytest.approx(1.0)
    assert r["gross_area_err"] == 0
    assert r["stair_dir_ok"] == 1.0 and r["stair_risers_ok"] == 1.0 and r["stair_pos_ok"] == 1.0
    assert all(r["passed"].values()), r["passed"]


def test_shifted_walls_raise_position_error(gt):
    r = wall_metrics(shifted(gt, 100, 100), gt)
    assert r["wall_pos_median_mm"] == pytest.approx(100, abs=5)
    assert r["wall_recall"] == 1.0
    assert wall_metrics(shifted(gt, 200, 200), gt)["wall_recall"] < 0.95


def test_missing_wall_lowers_recall_not_precision(gt):
    longest = max(gt.walls, key=lambda w: math.dist(w.a, w.b))
    pred = gt.model_copy(deep=True)
    pred.walls = [w for w in pred.walls if w.id != longest.id]
    total = sum(math.dist(w.a, w.b) for w in gt.walls)
    r = wall_metrics(pred, gt)
    assert r["wall_precision"] == 1.0
    assert r["wall_recall"] == pytest.approx(1 - math.dist(longest.a, longest.b) / total, abs=0.02)
    assert r["wall_recall"] < 1.0


def test_flipped_swing_counts_as_wrong_direction(gt):
    doors = [o for o in gt.openings if o.category == "door" and o.swing]
    pred = gt.model_copy(deep=True)
    d = next(o for o in pred.openings if o.id == doors[0].id)
    d.swing = "right" if d.swing == "left" else "left"
    assert door_metrics(pred, gt)["door_dir_ok"] == pytest.approx((len(doors) - 1) / len(doors))

    # reversing the host wall (a<->b) with mirrored hinge/swing/offset describes the same door
    pred = gt.model_copy(deep=True)
    d = next(o for o in pred.openings if o.id == doors[0].id)
    w = next(x for x in pred.walls if x.id == d.wall_id)
    length = math.dist(w.a, w.b)
    w.a, w.b = w.b, w.a
    for o in pred.openings:
        if o.wall_id == w.id:
            o.offset = round(length - o.offset - o.width)
            o.hinge = {"start": "end", "end": "start"}.get(o.hinge, o.hinge)
            o.swing = {"left": "right", "right": "left"}.get(o.swing, o.swing)
    r = door_metrics(pred, gt)
    assert r["door_dir_ok"] == 1.0 and r["door_recall"] == 1.0 and r["door_width_ok"] == 1.0


def test_stairs_and_scale_and_grid(gt):
    pred = gt.model_copy(deep=True)
    pred.stairs[0].flights = [f.model_copy(update={"start": f.end, "end": f.start}) for f in pred.stairs[0].flights]
    assert stair_metrics_cmp(pred, gt)["stair_dir_ok"] < 1.0
    assert scale_metrics(gt.meta.mm_per_px * 1.004, gt)["scale_err"] == pytest.approx(0.004, abs=1e-6)
    assert evaluate_scale_passes(gt, 1.004) and not evaluate_scale_passes(gt, 1.006)
    axes = [{"label": a.label, "orientation": a.orientation, "offset": a.offset} for a in gt.grid.axes]
    g = grid_metrics(axes, gt)
    assert g["label_ok"] and g["offset_max_err_mm"] == 0 and g["axes_found"] == g["axes_expected"] == 9
    g = grid_metrics(axes[:-1], gt)
    assert not g["label_ok"]


def evaluate_scale_passes(gt: Spec, factor: float) -> bool:
    from benchmarks.extraction_metrics import THRESHOLDS
    return scale_metrics(gt.meta.mm_per_px * factor, gt)["scale_err"] <= THRESHOLDS["scale_err"]


def test_cli_writes_markdown_and_json(tmp_path):
    out = tmp_path / "bench"
    subprocess.run([sys.executable, "-m", "benchmarks.run_extraction_bench", "--spec", str(GT_PATH), "--out", str(out)],
                   check=True)
    assert "wall_recall" in out.with_suffix(".md").read_text()
    doc = json.loads(out.with_suffix(".json").read_text())
    assert doc["passed"]["wall_recall"] is True


def test_cli_grid_mode(tmp_path, gt):
    grid = tmp_path / "grid.json"
    grid.write_text(json.dumps({"mm_per_px": gt.meta.mm_per_px, "axes": [
        {"label": a.label, "orientation": a.orientation, "offset": a.offset} for a in gt.grid.axes]}))
    out = tmp_path / "g"
    subprocess.run([sys.executable, "-m", "benchmarks.run_extraction_bench", "--grid", str(grid), "--out", str(out)],
                   check=True)
    doc = json.loads(out.with_suffix(".json").read_text())
    assert doc["scale_err"] == 0 and doc["label_ok"] is True and set(doc["passed"]) == {"scale_err"}
