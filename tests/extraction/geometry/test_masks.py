import numpy as np
import pytest

from core.extraction.geometry.masks import build_masks, stroke_width
from tests.extraction.geometry.synth import canvas, double_wall, line, room, text_item

S = 12.5
FULL = (0, 0, 600, 400)


def no_colour(img):
    return np.zeros_like(img)


def test_text_masked_with_small_dilation():
    img = canvas()
    line(img, (100, 50), (100, 350))
    img[200:220, 106:180] = 255  # text glyphs 5 px right of the wall line
    m = build_masks(img, no_colour(img), [text_item("GUDANG", (106, 200, 180, 220), "room_label")], FULL, S)
    assert m["clean"][100:150, 98:103].all()  # wall untouched
    assert not m["clean"][200:220, 106:180].any()


def test_colour_and_outside_removed():
    img = canvas()
    line(img, (100, 50), (100, 350))
    line(img, (300, 50), (300, 350))
    colour = no_colour(img)
    colour[:, 290:310] = 255
    m = build_masks(img, colour, [], (50, 0, 600, 400), S)
    assert not m["clean"][:, 290:310].any()
    img2 = canvas()
    line(img2, (10, 50), (10, 350))
    m2 = build_masks(img2, no_colour(img2), [], (100, 0, 600, 400), S)  # margin 300 mm = 24 px
    assert not m2["clean"].any()


def test_leader_removed_and_pointer_recorded():
    img = canvas()
    img[50:62, 300:380] = 255  # "PROPOSED" glyphs
    line(img, (300, 62), (300 - 28, 62 + 28), 2)  # 400 mm diagonal leader from the bbox corner
    m = build_masks(img, no_colour(img), [text_item("PROPOSED", (300, 50, 380, 62), "proposed")], FULL, S)
    assert not m["clean"][70:88, 274:298].any()
    p = m["pointers"][0]
    assert p["cls"] == "proposed" and abs(p["point"][0] - 272) <= 3 and abs(p["point"][1] - 90) <= 3


def test_filled_symbol_masked():
    img = canvas()
    room(img, 100, 80, 500, 330)
    img[180:220, 250:290] = 255
    m = build_masks(img, no_colour(img), [], FULL, S)
    assert m["symbol"][200, 270] and not m["clean"][180:220, 250:290].any()
    assert m["clean"][80 - 6, 200] and m["clean"][330 + 6, 200]  # walls intact
    assert m["clean"][200, 100 - 6] and m["clean"][200, 500 + 6]


def test_hatch_marks_dense_short_parallel_lines():
    img = canvas()
    for x in range(200, 400, 8):
        line(img, (x, 200), (x, 230), 2)
    double_wall(img, (50, 100), (550, 100))
    m = build_masks(img, no_colour(img), [], FULL, S)
    assert m["hatch"][215, 300] > 0
    assert m["hatch"][100, 100] == 0


def test_stroke_width():
    img = canvas()
    line(img, (100, 50), (100, 350), 4)
    assert stroke_width(img) == pytest.approx(4, abs=1.2)


@pytest.mark.slow
def test_gatsu_masks():
    from tests.extraction.geometry.gatsu import gatsu, work

    g = gatsu()
    m = build_masks(g["binary"], g["colour"], g["ocr"], g["meta"]["drawing_bbox"], g["s"])
    meeting = next(i for i in g["ocr"] if "MEETING" in i["text"].upper())
    x0, y0, x1, y1 = (int(v) for v in meeting["bbox"])
    assert not m["clean"][y0:y1, x0:x1].any()
    bx, by = work(890, 540)  # a filled panel in the Battery Room
    assert m["symbol"][by - 20:by + 20, bx - 20:bx + 20].any()
    # the PROPOSED SDP leader is a shallow polyline crossing two wall lines, broken by Hough into < 300 mm pieces:
    # it is not traced; the existing-condition rule falls back to "<= 1000 mm from the text" (Task 7)
    assert all(p["cls"] != "proposed" or abs(p["point"][0] / 2 - 1120) <= 60 for p in m["pointers"])
    # wall lines ending next to a text are not leaders: the south band line (y≈690, x 103..1184) survives
    x, y = work(600, 690)
    assert m["clean"][y - 4:y + 5, x].any()


def test_poche_wall_network_is_not_a_symbol():
    """Solid (S1) walls form one connected network with a square-ish bbox; only compact filled blobs are symbols."""
    from core.extraction.geometry.walls_s1 import solid_walls

    s, t = 12.5, 16  # 200 mm poche walls
    img = canvas(1600, 1200)
    x0, y0, x1, y1 = 200, 200, 1400, 1000
    for a, b, c, d in ((x0, y0, x1, y0 + t), (x0, y1 - t, x1, y1), (x0, y0, x0 + t, y1), (x1 - t, y0, x1, y1),
                       (700, y0, 700 + t, y1)):
        img[b:d, a:c] = 255
    for k in range(40):  # thin lines (furniture, hatch) so that the thin stroke width dominates
        line(img, (250 + k * 10, 300), (250 + k * 10, 900), 2)
    img[500:540, 1000:1040] = 255  # a 500 mm filled MEP symbol inside the room
    m = build_masks(img, None, [], [0, 0, 1600, 1200], s)
    assert not m["symbol"][y0 + 4, 300] and not m["symbol"][600, 704]  # wall pixels stay in clean
    assert m["symbol"][520, 1020]
    assert len(solid_walls(m["clean"], m["symbol"], s, 80)) >= 5
