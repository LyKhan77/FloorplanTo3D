from pathlib import Path

import pytest

from benchmarks.extraction_metrics import scale_metrics
from core.extraction.ocr import OcrItem
from core.extraction.scale import MSG_NO_SCALE, compose_original, scale_from
from core.spec.models import Spec

V = {"A": 0, "B": 240, "C": 480, "D": 640, "E": 880, "F": 1120}


def grid(h_px=(0, 240, 480)) -> dict:
    return {"vertical": [{"label": k, "px": float(v)} for k, v in V.items()],
            "horizontal": [{"label": k, "px": float(v)} for k, v in zip("123", h_px, strict=True)], "warnings": []}


def htext(value: str, x: float, y: float = 1300) -> OcrItem:
    return OcrItem(text=value, bbox=(x - 20, y - 8, x + 20, y + 8), angle=0, conf=0.99)


def vtext(value: str, y: float, x: float = -60) -> OcrItem:
    return OcrItem(text=value, bbox=(x - 8, y - 20, x + 8, y + 20), angle=90, conf=0.99)


def chain(h_px=(0, 240, 480)) -> list[OcrItem]:
    return [htext("6000", 120), htext("6000", 360), htext("4000", 560), htext("6000", 760), htext("6000", 1000),
            htext("28000", 560, 1350), vtext("6000", (h_px[0] + h_px[1]) / 2), vtext("6000", (h_px[1] + h_px[2]) / 2),
            vtext("12000", h_px[1], -90)]


def test_chain_and_total_solve():
    g = scale_from(grid(), chain(), None)
    assert g["status"] == "succeeded" and g["scale_source"] == "grid_dimensions"
    assert g["mm_per_px"] == pytest.approx(25.0, abs=1e-9)
    assert {(e["axis_from"], e["axis_to"]) for e in g["equations_used"] if e["value_mm"] in (28000, 12000)} == {
        ("A", "F"), ("1", "3")}
    offsets = {(a["orientation"], a["label"]): a["offset"] for a in g["axes"]}
    assert offsets == {("vertical", "A"): 0, ("vertical", "B"): 6000, ("vertical", "C"): 12000,
                       ("vertical", "D"): 16000, ("vertical", "E"): 22000, ("vertical", "F"): 28000,
                       ("horizontal", "3"): 0, ("horizontal", "2"): 6000, ("horizontal", "1"): 12000}
    assert g["px_to_mm"] == pytest.approx([25, 0, 0, 0, -25, 25 * 480])
    assert {a["id"] for a in g["axes"]} >= {"GA", "G1"}


def test_outlier_equation_dropped():
    g = scale_from(grid(), [*chain(), htext("9000", 60, 1250)], None)
    assert g["mm_per_px"] == pytest.approx(25.0, abs=1e-9)
    assert [e["value_mm"] for e in g["equations_dropped"]] == [9000]


def test_anisotropy_over_1pct_keeps_separate_scales():
    h = (0, 6000 / 25.5, 12000 / 25.5)
    g = scale_from(grid(h), chain(h), None)
    assert g["isotropic"] is False
    assert g["sx"] == pytest.approx(25.0) and g["sy"] == pytest.approx(25.5)


def test_manual_scale_wins_with_warning():
    g = scale_from(grid(), chain(), 26.0)
    assert g["scale_source"] == "manual" and g["mm_per_px"] == pytest.approx(26.0)
    assert len([w for w in g["warnings"] if "berbeda" in w]) == 1


def test_no_dimensions_needs_attention():
    g = scale_from(grid(), [], None)
    assert g["status"] == "needs_attention" and g["message"] == MSG_NO_SCALE == "Skala tidak dapat ditentukan, isi skala manual"
    g = scale_from(grid(), [], 25.0)
    assert g["status"] == "succeeded" and g["scale_source"] == "manual" and g["mm_per_px"] == 25.0


def test_single_total_dimension_is_total_length():
    g = scale_from(grid(), [htext("28000", 560, 1350)], None)
    assert g["scale_source"] == "total_length" and g["mm_per_px"] == pytest.approx(25.0)


def test_compose_original():
    assert compose_original([25, 0, -100, 0, -25, 500], [2, 0, 0, 0, 2, 0]) == pytest.approx([50, 0, -100, 0, -50, 500])


@pytest.mark.slow
def test_gatsu_scale_within_half_percent():
    from core.extraction.preprocess import load_raster, preprocess
    from core.extraction.textclass import classify_text, ocr_page
    from tests.extraction.test_grid import gatsu_grid

    r = preprocess(load_raster(Path("floorplan/plan.jpeg")))
    dims = [i for i in ocr_page(r.page, r.meta["upscale"])
            if classify_text(i, in_circle=False, in_building=False) == "dimension"]
    g = scale_from(gatsu_grid(), dims, None)
    orig = compose_original(g["px_to_mm"], r.meta["work_from_original"])
    mm_per_px = abs(orig[0] * orig[4] - orig[1] * orig[3]) ** 0.5
    gt = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    assert scale_metrics(mm_per_px, gt)["scale_err"] <= 0.005, mm_per_px
    assert g["scale_source"] == "grid_dimensions"
    offsets = {a["label"]: a["offset"] for a in g["axes"]}
    assert offsets == {"A": 0, "B": 6000, "C": 12000, "D": 16000, "E": 22000, "F": 28000, "3": 0, "2": 6000, "1": 12000}
