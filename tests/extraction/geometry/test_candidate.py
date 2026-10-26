import time

import numpy as np
import pytest

from core.extraction.geometry.confidence import wall_confidence
from core.extraction.geometry.walls_s2 import _wall

S = 12.5


def test_confidence_penalises_hatch_and_dangling():
    box = [_wall("h", 100, 100, 400, 150, {"pair_overlap": 1.0, "partial_mm": 0}),
           _wall("v", 100, 100, 300, 150, {"pair_overlap": 1.0, "partial_mm": 0}),
           _wall("v", 400, 100, 300, 150, {"pair_overlap": 1.0, "partial_mm": 0})]
    hatch = np.zeros((500, 600), np.uint8)
    axes = {"vertical": [], "horizontal": []}
    clean = wall_confidence(box[0], hatch, [], axes, box, S)
    hatch[90:110, 100:400] = 255
    hatched = wall_confidence(box[0], hatch, [], axes, box, S)
    assert clean - hatched >= 0.25
    lone = _wall("h", 450, 100, 400, 150, {"pair_overlap": 1.0, "partial_mm": 0})
    assert wall_confidence(lone, np.zeros_like(hatch), [], axes, box + [lone], S) < clean
    near_text = wall_confidence(box[0], np.zeros_like(hatch), [{"bbox": [200, 112, 260, 124], "cls": "annotation"}], axes, box, S)
    assert near_text == pytest.approx(clean - 0.15)
    # a pair 3x thicker than the plan's typical wall (Gatsu: the unhatched cable trench, ~400 mm) is suspicious
    thick = dict(box[0], thickness_mm=450)
    assert wall_confidence(thick, np.zeros_like(hatch), [], axes, [thick, *box[1:]], S) == pytest.approx(clean - 0.25)



def test_treads_paired_as_walls_are_not_confident():
    """Treads the flight test missed (railing-split, too few) pair as ~300 mm 'walls' (Gatsu east stair)."""
    from core.extraction.geometry.strokes import extract_strokes
    from core.extraction.geometry.walls_s2 import s2_walls
    from tests.extraction.geometry.synth import canvas, line

    img = canvas()
    for k in range(4):  # four treads, 280 mm apart, 1000 mm wide: below MIN_TREADS
        line(img, (200, 100 + round(k * 22.4)), (280, 100 + round(k * 22.4)), 2)
    strokes = extract_strokes(img, 0, S)
    walls = s2_walls(strokes, S, 80, 450)
    assert walls
    hatch, axes = np.zeros_like(img), {"vertical": [], "horizontal": []}
    assert all(wall_confidence(w, hatch, [], axes, walls, S, strokes) < 0.6 for w in walls)
    # a plain double-line wall next to them keeps its confidence
    real = [_wall("h", 300, 100, 400, 280, {"pair_overlap": 1.0, "partial_mm": 0})]
    assert wall_confidence(real[0], hatch, [], axes, real, S, strokes) == wall_confidence(real[0], hatch, [], axes, real, S)


@pytest.mark.slow
def test_gatsu_candidate_runs_and_is_plausible():
    from core.extraction.geometry.candidate import extract_candidate
    from core.extraction.geometry.elements import elements_to_spec
    from tests.extraction.geometry.gatsu import gatsu

    g = gatsu()
    t0 = time.monotonic()
    el = extract_candidate(g["page"], g["binary"], g["colour"], g["ocr"], g["grid"], g["meta"],
                           {"strategy": "S2", "sauvola_k": 0.2, "t_min": 80, "t_max": 450, "l_fix": 0}, {})
    elapsed = time.monotonic() - t0
    assert len(el["walls"]) >= 60 and len(el["openings"]) >= 10 and len(el["stairs"]) >= 1 and len(el["columns"]) >= 16
    spec = elements_to_spec(el, g["grid"])
    assert len(spec.walls) == len(el["walls"])
    assert elapsed < 20, elapsed


@pytest.mark.slow
def test_cable_trench_has_no_confident_wall():
    from core.extraction.geometry.candidate import extract_candidate
    from tests.extraction.geometry.gatsu import gatsu

    g = gatsu()
    el = extract_candidate(g["page"], g["binary"], g["colour"], g["ocr"], g["grid"], g["meta"],
                           {"strategy": "S2", "sauvola_k": 0.2, "t_min": 80, "t_max": 450, "l_fix": 0}, {})
    a, b, c, d, e, f = g["grid"]["px_to_mm_original"]
    def mm(u, v): return (a * u + b * v + c, d * u + e * v + f)
    (x0, y_top), (x1, y_bot) = mm(830, 598), mm(1580, 613)
    inside = [w for w in el["walls"] if w["confidence"] >= 0.6 and all(
        x0 <= p[0] <= x1 and y_bot <= p[1] <= y_top for p in (w["a"], w["b"]))]
    assert inside == [], inside
