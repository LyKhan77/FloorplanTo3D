import pytest

from core.extraction.geometry.strokes import directional_close, extract_strokes
from tests.extraction.geometry.synth import canvas, line

S = 12.5


def test_double_line_wall_gives_two_strokes():
    img = canvas()
    line(img, (200, 50), (200, 350))
    line(img, (212, 50), (212, 350))
    st = [x for x in extract_strokes(img, 0, S) if x["orient"] == "v"]
    assert len(st) == 2
    assert st[0]["c"] == pytest.approx(200, abs=1) and st[1]["c"] == pytest.approx(212, abs=1)
    assert all(x["b"] - x["a"] >= 290 and x["width"] == pytest.approx(4, abs=1.2) for x in st)


def test_fragments_merged_and_jpeg_breaks_fixed():
    img = canvas()
    line(img, (50, 200), (550, 200))
    for x in (150, 300, 450):
        img[195:206, x:x + 2] = 0
    for l_fix in (0, 5):
        st = [x for x in extract_strokes(img, l_fix, S) if x["orient"] == "h"]
        assert len(st) == 1 and st[0]["a"] <= 55 and st[0]["b"] >= 545


def test_slanted_kept_separately():
    img = canvas()
    line(img, (100, 300), (400, 191))  # 20 degrees
    st = extract_strokes(img, 0, S)
    assert st and all(x["orient"] == "o" for x in st)


def test_directional_close_keeps_gap_between_wall_lines():
    img = canvas()
    line(img, (200, 50), (200, 350), 2)
    line(img, (206, 50), (206, 350), 2)
    closed = directional_close(img, 5)
    assert not closed[200, 203]
    assert (directional_close(img, 0) == img).all()


@pytest.mark.slow
def test_gatsu_w50_strokes():
    from core.extraction.geometry.masks import build_masks
    from tests.extraction.geometry.gatsu import gatsu

    g = gatsu()
    m = build_masks(g["binary"], g["colour"], g["ocr"], g["meta"]["drawing_bbox"], g["s"])
    st = [x for x in extract_strokes(m["clean"], 0, g["s"]) if x["orient"] == "v" and 1850 < x["c"] < 1890]
    for cx in (1863, 1875):
        hit = [x for x in st if abs(x["c"] - cx) <= 2]
        assert hit, (cx, st)
        assert min(x["a"] for x in hit) <= 237 and max(x["b"] for x in hit) >= 720
