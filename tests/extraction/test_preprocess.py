from pathlib import Path

import cv2
import numpy as np
import pytest

import core.extraction.preprocess as pre
from core.extraction.preprocess import drawing_bbox, load_raster, preprocess
from tests.inputs import ANCOL, requires_ancol

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


def _png(colour: int, size: int = 50) -> bytes:
    return cv2.imencode(".png", np.full((size, size, 3), colour, np.uint8))[1].tobytes()


def test_vector_pdf_photo_removed_lines_kept(tmp_path):
    import pymupdf as fitz

    pdf = tmp_path / "plan.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    for i in range(600):  # a vector-heavy page, as a CAD export is
        page.draw_line((5 + (i % 60) * 9, 300 + i // 60 * 9), (9 + (i % 60) * 9, 300 + i // 60 * 9))
    page.draw_line((50, 200), (550, 200), width=2)  # a wall the photo covers
    page.insert_image(fitz.Rect(100, 150, 300, 250), stream=_png(0))
    page.draw_rect(fitz.Rect(100, 150, 300, 250), width=0.5)  # the photo's frame
    doc.save(pdf)
    img = load_raster(pdf, page=1)
    k = 300 / 72
    assert img[int(160 * k):int(190 * k), int(110 * k):int(290 * k)].min() > 200  # photo gone
    assert img[int(200 * k), int(200 * k)].max() < 100  # wall under the photo kept
    assert img[int(150 * k), int(200 * k)].min() > 200  # frame outline erased


def test_scanned_pdf_keeps_its_image(tmp_path):
    import pymupdf as fitz

    pdf = tmp_path / "scan.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    page.insert_image(page.rect, stream=_png(0), keep_proportion=False)
    doc.save(pdf)
    assert load_raster(pdf, page=1).mean() < 50


@requires_ancol
def test_ancol_p13_has_no_photo_pixels():
    img = load_raster(ANCOL, page=13)
    sat = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1]
    assert (sat > 60).mean() < 0.002  # site photos were the only large colourful areas


def test_bbox_skips_sheet_frame_and_unions_blocks():
    b = np.zeros((1500, 2000), np.uint8)
    cv2.rectangle(b, (40, 40), (1960, 1460), 255, 3)  # sheet frame
    cv2.rectangle(b, (1650, 40), (1960, 1460), 255, 3)  # title block attached to it
    for x0, y0, x1, y1 in ((300, 200, 900, 600), (400, 650, 1200, 1300)):  # two blocks, 50 px apart
        for x in range(x0, x1 + 1, 20):
            cv2.line(b, (x, y0), (x, y1), 255, 3)
        for y in range(y0, y1 + 1, 20):
            cv2.line(b, (x0, y), (x1, y), 255, 3)
    assert drawing_bbox(b, sheet=True) == pytest.approx((299, 199, 1202, 1302), abs=5)


@requires_ancol
@pytest.mark.parametrize("dpi", [300, 600])
def test_ancol_p13_bbox_is_the_building(dpi, monkeypatch):
    monkeypatch.setattr(pre, "PDF_DPI", dpi)
    r = preprocess(load_raster(ANCOL, page=13), sheet=True)
    k = dpi / 300
    x0, y0, x1, y1 = r.meta["drawing_bbox"]
    assert x0 <= (611 + 20) * k and y0 <= (238 + 20) * k and x1 >= (2261 - 20) * k and y1 >= (2295 - 20) * k  # building
    assert x1 < 0.8 * r.meta["work_size"][0]  # no title block


def test_sparse_tight_crop_keeps_its_building():
    b = np.zeros((2000, 3000), np.uint8)
    cv2.rectangle(b, (200, 150), (2800, 1850), 255, 3)  # outline filling ~85% of the image, little ink
    for x in (800, 1500, 2100):
        cv2.line(b, (x, 150), (x, 1850), 255, 3)
    assert drawing_bbox(b) == pytest.approx((199, 149, 2802, 1852), abs=5)


def test_raster_underlay_survives_photo_removal(tmp_path):
    import pymupdf as fitz

    pdf = tmp_path / "plan.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    for i in range(600):
        page.draw_line((5 + (i % 60) * 9, 380 + i // 60), (9 + (i % 60) * 9, 380 + i // 60))
    page.insert_image(fitz.Rect(0, 0, 500, 300), stream=_png(128), keep_proportion=False)  # underlay, 62% of page
    page.insert_image(fitz.Rect(100, 100, 200, 200), stream=_png(0))  # photo on top
    doc.save(pdf)
    img = load_raster(pdf, page=1)
    k = 300 / 72
    assert 100 < img[int(250 * k), int(400 * k)].mean() < 160  # underlay kept outside the photo
    assert img[int(150 * k), int(150 * k)].min() > 100  # photo gone
