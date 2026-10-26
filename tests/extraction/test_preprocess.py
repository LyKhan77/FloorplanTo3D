from pathlib import Path

import cv2
import numpy as np
import pytest

from core.extraction.preprocess import load_raster, preprocess

PLAN = Path("floorplan/plan.jpeg")


def rotated(img: np.ndarray, deg: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(img, m, (w, h), borderValue=(255, 255, 255))


@pytest.mark.slow
def test_gatsu_preprocess_meta():
    r = preprocess(load_raster(PLAN))
    m = r.meta
    assert r.status == "succeeded"
    assert m["upscale"] == 2 and m["work_size"] == [3200, 1890] and m["original_size"] == [1600, 945]
    assert abs(m["deskew_deg"]) <= 0.2
    assert m["work_from_original"] == pytest.approx([2, 0, 0, 0, 2, 0])
    x0, y0, x1, y1 = (v / 2 for v in m["drawing_bbox"])  # back to original px
    assert x0 <= 102 and y0 <= 36 and x1 >= 1383 and y1 >= 695  # the whole building outline
    assert x0 > 52 and y1 < 846  # grid bubbles (left centres x≈30, bottom centres y≈868, r≈22) stay outside
    assert set(np.unique(r.binary)) <= {0, 255}
    assert (r.binary == 255).mean() < 0.25


def test_deskew_rotates_small_tilt_and_refuses_large():
    img = load_raster(PLAN)
    r = preprocess(rotated(img, 2.0))
    assert r.status == "succeeded"
    assert r.meta["deskew_deg"] == pytest.approx(2.0, abs=0.3)
    r = preprocess(rotated(img, 8.0))
    assert r.status == "needs_attention"
    assert r.message == "Gambar miring > 5°; scan di luar cakupan"


def test_pdf_rasterized_at_300dpi_and_page_selected(tmp_path):
    import pymupdf as fitz

    pdf = tmp_path / "plan.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(20, 20, 575, 350), filename=str(PLAN))
    doc.save(pdf)
    img = load_raster(pdf, page=2)
    assert img.shape[1] == pytest.approx(2480, abs=2) and img.shape[0] == pytest.approx(3508, abs=2)
    assert img.ndim == 3 and img.std() > 10
    with pytest.raises(ValueError, match="page 3 not in 1..2"):
        load_raster(pdf, page=3)


def test_png_with_alpha_flattened_on_white(tmp_path):
    rgba = np.zeros((20, 30, 4), np.uint8)
    rgba[5:10, 5:10] = (0, 0, 0, 255)
    p = tmp_path / "a.png"
    cv2.imwrite(str(p), rgba)
    img = load_raster(p)
    assert img.shape == (20, 30, 3)
    assert (img[0, 0] == 255).all() and (img[7, 7] == 0).all()
