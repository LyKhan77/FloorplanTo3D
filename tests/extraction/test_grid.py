from functools import cache
from pathlib import Path

import pytest

from benchmarks.gatsu.gt_px import GRID_PX_X, GRID_PX_Y
from core.extraction.grid import detect_grid, infer_labels
from core.extraction.preprocess import load_raster, preprocess
from core.extraction.textclass import ocr_page


@cache
def gatsu_grid() -> dict:
    r = preprocess(load_raster(Path("floorplan/plan.jpeg")))
    return detect_grid(r.page, r.binary, ocr_page(r.page, r.meta["upscale"]))


@pytest.mark.slow
def test_gatsu_bubbles_labels_and_positions():
    g = gatsu_grid()
    assert [a["label"] for a in g["vertical"]] == ["A", "B", "C", "D", "E", "F"]
    assert [a["label"] for a in g["horizontal"]] == ["1", "2", "3"]
    for a in g["vertical"]:
        assert a["px"] == pytest.approx(2 * GRID_PX_X[a["label"]], abs=6 if a["label"] == "C" else 4)
    for a in g["horizontal"]:
        assert a["px"] == pytest.approx(2 * GRID_PX_Y[a["label"]], abs=4)


def b(label, x=0.0):
    return {"cx": x, "cy": 0.0, "r": 20.0, "label": label, "label_source": "ocr" if label else None}


def test_infer_labels_fills_gaps_and_fixes_misreads():
    out, warn = infer_labels([b("A", 0), b("B", 100), b(None, 200), b("D", 300)])
    assert [x["label"] for x in out] == ["A", "B", "C", "D"] and out[2]["label_source"] == "inferred" and not warn
    out, warn = infer_labels([b("1", 0), b("C", 100), b("3", 200)])
    assert [x["label"] for x in out] == ["1", "2", "3"] and len(warn) == 1
    out, warn = infer_labels([b("3", 0), b("2", 100), b(None, 200)])
    assert [x["label"] for x in out] == ["3", "2", "1"]
    out, warn = infer_labels([b(None, 0), b(None, 100)])
    assert [x["label"] for x in out] == [None, None] and len(warn) == 2
