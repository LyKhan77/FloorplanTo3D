import math

import cv2
import pymupdf as fitz
import pytest

from core.extraction.preprocess import PDF_DPI, load_raster
from core.extraction.vector.lines import read_lines

K = PDF_DPI / 72
IDENTITY = [1, 0, 0, 0, 1, 0]  # px_to_mm: 1 mm per original px


def _pdf(tmp_path, draw, rotate=0, size=(600, 400)):
    doc = fitz.open()
    page = doc.new_page(width=size[0], height=size[1])
    draw(page)
    page.set_rotation(rotate)
    path = tmp_path / "p.pdf"
    doc.save(path)
    return path


def _read(path):
    with fitz.open(path) as d:
        r = d[0].rect
    return read_lines(path, 1, IDENTITY, (0, 0, round(r.width * K), round(r.height * K)), PDF_DPI)


def test_collinear_pieces_merge(tmp_path):
    def draw(p):  # 1 mm = 1 px here, so pieces of 100 px with 20 px gaps
        for i in range(40):
            x = 10 + i * 120 / K
            p.draw_line((x, 100), (x + 100 / K, 100))
    pl = _read(_pdf(tmp_path, draw, size=(1300, 400)))
    assert len(pl.lines) == 1
    assert math.dist(pl.lines[0].a, pl.lines[0].b) == pytest.approx(39 * 120 + 100, abs=3)


def test_skewed_lines_merge(tmp_path):
    t = math.radians(30)

    def draw(p):
        for i in range(30):
            s = i * 120 / K
            p.draw_line((10 + s * math.cos(t), 10 + s * math.sin(t)),
                        (10 + (s + 100 / K) * math.cos(t), 10 + (s + 100 / K) * math.sin(t)))
    assert len(_read(_pdf(tmp_path, draw)).lines) == 1


@pytest.mark.parametrize("rotate", [90, 180, 270])
def test_rotated_page_maps_like_the_raster(tmp_path, rotate):
    def draw(p):
        for i in range(600):  # stays vector-heavy; nothing to strip, only to map
            p.draw_line((5, 5), (6, 5))
        p.draw_line((100, 50), (500, 50), width=3)
    path = _pdf(tmp_path, draw, rotate=rotate)
    long = max(_read(path).lines, key=lambda s: math.dist(s.a, s.b))
    img = cv2.cvtColor(load_raster(path, 1), cv2.COLOR_BGR2GRAY)
    mid = [round((long.a[i] + long.b[i]) / 2) for i in (0, 1)]
    assert img[mid[1] - 3:mid[1] + 4, mid[0] - 3:mid[0] + 4].min() < 100


def test_dark_rect_is_kept_with_its_width(tmp_path):
    def draw(p):
        p.draw_rect(fitz.Rect(50, 50, 450, 50 + 40 / K), color=(0, 0, 0), fill=(0, 0, 0))
    pl = _read(_pdf(tmp_path, draw))
    assert len(pl.dark) == 1 and pl.dark[0][1] == pytest.approx(40, abs=2)


def test_coloured_annotation_lines_are_skipped(tmp_path):
    def draw(p):
        p.draw_line((50, 50), (500, 50), color=(1, 0, 1))  # magenta leader
        p.draw_line((50, 100), (500, 100), color=(0, 0, 0))
    pl = _read(_pdf(tmp_path, draw))
    assert len(pl.lines) == 1
