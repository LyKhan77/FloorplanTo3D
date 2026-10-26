import numpy as np
import pytest

from core.extraction.geometry.walls_s1 import solid_walls
from tests.extraction.geometry.synth import canvas, line

S = 10.0


def test_s1_poche_wall():
    img = canvas()
    img[100:120, 150:450] = 255  # 200 mm x 3000 mm solid wall
    w = solid_walls(img, np.zeros_like(img), S, 80)
    assert len(w) == 1 and w[0]["orient"] == "h" and w[0]["strategy"] == "S1"
    assert w[0]["thickness_mm"] == pytest.approx(200, abs=20)
    assert (w[0]["b"] - w[0]["a"]) * S >= 2700


def test_s1_ignores_thin_double_lines():
    img = canvas()
    line(img, (100, 50), (100, 350))
    line(img, (112, 50), (112, 350))
    assert solid_walls(img, np.zeros_like(img), S, 80) == []


def test_s1_ignores_filled_symbol():
    img = canvas()
    img[100:160, 200:260] = 255
    sym = np.zeros_like(img)
    sym[95:165, 195:265] = 255
    assert solid_walls(img, sym, S, 80) == []
