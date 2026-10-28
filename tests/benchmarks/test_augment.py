import os

import numpy as np
import pytest

from benchmarks.augment.variants import VARIANTS, render_variant, variants_from_seed
from benchmarks.run_augment_bench import relative_pass, run_variant


def test_variants_are_deterministic_and_identity_first():
    assert len(VARIANTS) == 30
    assert VARIANTS[0] == {"id": "a00", "scale": 1.0, "jpeg_q": 95, "rotate_deg": 0.0, "margin_px": 0, "blur": 0.0,
                           "noise": 0.0}
    assert VARIANTS == variants_from_seed()
    assert len({v["id"] for v in VARIANTS}) == 30
    for v in VARIANTS[1:]:
        assert v["scale"] in (0.6, 0.75, 1.0, 1.5, 2.0) and v["jpeg_q"] in (40, 60, 80, 95)
        assert -2 <= v["rotate_deg"] <= 2 and v["margin_px"] in (-40, 0, 80)
        assert v["blur"] in (0.0, 0.6, 1.0) and v["noise"] in (0.0, 4.0, 8.0)


def test_render_variant_scale_and_white_border():
    v = {"id": "x", "scale": 0.5, "jpeg_q": 95, "rotate_deg": 2.0, "margin_px": 10, "blur": 0.0, "noise": 0.0}
    out = render_variant(np.full((100, 200), 255, np.uint8), v)
    assert out.shape[:2] == (60, 110) and out[0, 0] > 240


def test_render_variant_crop_and_colour_kept():
    v = {"id": "y", "scale": 1.0, "jpeg_q": 95, "rotate_deg": 0.0, "margin_px": -10, "blur": 1.0, "noise": 4.0}
    out = render_variant(np.full((100, 200, 3), 200, np.uint8), v)
    assert out.shape == (80, 180, 3)
    assert np.array_equal(out, render_variant(np.full((100, 200, 3), 200, np.uint8), v))  # noise is seeded by id


def test_relative_pass_rules():
    base = {"wall_recall": 0.8, "gross_area_err": 0.03, "room_match": 0.0}
    assert relative_pass({"wall_recall": 0.73, "gross_area_err": 0.033, "room_match": 0.0}, base) == (True, [])
    assert relative_pass({"wall_recall": 0.70, "gross_area_err": 0.04, "room_match": 0.0}, base) == \
        (False, ["gross_area_err", "wall_recall"])
    # base had them, the variant lost them (evaluate always returns every key, so absent means lost)
    assert relative_pass({"wall_recall": None}, base) == (False, ["gross_area_err", "wall_recall"])


def test_failed_stage_counts_as_failed(tmp_path):
    def grid_fails(project, work, *a, **kw):
        work.mkdir(parents=True, exist_ok=True)
        return {"status": "needs_attention", "message": "skala tidak terbaca"}

    v = {"id": "a07", "scale": 0.6, "jpeg_q": 40, "rotate_deg": 0.0, "margin_px": 0, "blur": 0.0, "noise": 0.0}
    row = run_variant(v, tmp_path, base=None, stage_overrides={"02_grid": grid_fails})
    assert row["passed"] is False and row["reason"].startswith("stage 2") and "skala" in row["reason"]


def test_sweep_workers_env(monkeypatch):
    from core.extraction.geometry.sweep import run_sweep

    monkeypatch.setenv("SWEEP_WORKERS", "1")
    pids = run_sweep(lambda i, p: {"pid": os.getpid(), "index": i}, [{}, {}, {}])
    assert {r["pid"] for r in pids} == {os.getpid()}  # in-process: no pool when one worker is asked for


def test_crop_never_cuts_drawing_content():
    img = np.full((100, 200), 255, np.uint8)
    img[40:60, 3:8] = 0  # ink 3 px from the left edge (a grid bubble), plenty of paper on the right
    v = {"id": "c", "scale": 1.0, "jpeg_q": 95, "rotate_deg": 0.0, "margin_px": -40, "blur": 0.0, "noise": 0.0}
    out = render_variant(img, v)
    assert out.shape[1] == 200 - 40 and (out[:, :10] < 128).any()  # left kept (ink at 3 px), right cut by 40
    assert out.shape[0] == 100 - 2 * 35  # top/bottom: 40 requested, limited to the paper before the ink (40 - 5)


def test_best_shift_recovers_a_translation():
    from benchmarks.run_augment_bench import best_shift, translate
    from tests.spec.fixtures import spec_with_rooms

    gt = spec_with_rooms()
    moved = translate(gt, 700, -400)
    assert moved.walls[0].a == (gt.walls[0].a[0] + 700, gt.walls[0].a[1] - 400)
    assert moved.rooms[0].polygon[0] == (gt.rooms[0].polygon[0][0] + 700, gt.rooms[0].polygon[0][1] - 400)
    dx, dy = best_shift(moved, gt)
    assert abs(dx + 700) <= 50 and abs(dy - 400) <= 50
    assert best_shift(gt, gt) == (0, 0)


def test_scale_err_uses_the_variant_scale():
    from benchmarks.run_augment_bench import gt_for

    v = {"id": "s", "scale": 2.0, "jpeg_q": 95, "rotate_deg": 0.0, "margin_px": 0, "blur": 0.0, "noise": 0.0}
    from benchmarks.llm_items import GT_PATH
    from core.spec.models import Spec

    gt = Spec.model_validate_json(GT_PATH.read_text())
    assert gt_for(v).meta.mm_per_px == pytest.approx(gt.meta.mm_per_px / 2)


def test_single_factor_variants_come_first():
    from benchmarks.augment.variants import IDENTITY

    singles = [v for v in VARIANTS[1:20]]
    for v in singles:
        changed = [k for k in IDENTITY if k != "id" and v[k] != IDENTITY[k]]
        assert len(changed) == 1, v


def test_robustness_score():
    from benchmarks.run_augment_bench import robustness_score

    rows = [{"id": "a00", "metrics": {"wall_recall": 0.8, "wall_precision": 0.8}, "failed_metrics": []},
            {"id": "a01", "metrics": {"wall_recall": 0.8}, "failed_metrics": ["wall_precision"]},
            {"id": "a02", "metrics": {}, "failed_metrics": []}]  # stopped run
    assert robustness_score(rows) == (0.5 + 0.0) / 2
