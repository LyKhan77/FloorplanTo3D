import pytest

from benchmarks.run_room_tracing_bench import ANCOL_REVIEWED_BELOW, GT, gate_metrics
from core.extraction.preprocess import load_raster, preprocess
from core.extraction.vector.lines import Line, PageLines, read_lines
from core.extraction.vector.walls import MIN_WALL_MM, pair_walls
from core.spec.models import Spec, Wall
from tests.inputs import ANCOL, requires_ancol


def _h(y, x0=0, x1=5000):
    return Line((x0, y), (x1, y))


def _pl(lines, short=(), dark=()):
    return PageLines(list(lines), list(short), list(dark))


def _long(walls):
    return [w for w in walls if not w.evidence.get("short")]


def test_double_line_is_one_wall():
    w = _long(pair_walls(_pl([_h(0), _h(150)])))
    assert len(w) == 1 and w[0].thickness == pytest.approx(150)
    assert w[0].a[1] == pytest.approx(75) and abs(w[0].b[0] - w[0].a[0]) == pytest.approx(5000)


def test_vertical_and_skewed_pairs():
    v = [Line((0, 0), (0, 4000)), Line((150, 0), (150, 4000))]
    s = [Line((0, 0), (3000, 3000)), Line((100, -100), (3100, 2900))]
    assert len(_long(pair_walls(_pl(v)))) == 1
    assert len(_long(pair_walls(_pl(s)))) == 1


def test_three_lines_pair_neighbours_only():
    assert sorted(round(w.thickness) for w in _long(pair_walls(_pl([_h(0), _h(150), _h(300)])))) == [150, 150]


def test_filled_bar_is_a_wall():
    w = _long(pair_walls(_pl([], dark=[(_h(0), 200.0)])))
    assert len(w) == 1 and w[0].thickness == 200


def test_tray_is_not_a_wall():
    rungs = [Line((x, -10), (x, 317)) for x in range(0, 5000, 353)]
    assert not _long(pair_walls(_pl([_h(0), _h(307)], short=rungs)))


def test_rack_row_is_not_a_wall():
    assert not _long(pair_walls(_pl([_h(0), _h(800)])))


def test_short_pair_is_flagged():
    w = pair_walls(_pl([_h(0, 0, 600), _h(150, 0, 600)]))
    assert len(w) == 1 and w[0].evidence["short"] and MIN_WALL_MM > 600


@requires_ancol
@pytest.mark.skipif(not GT.exists(), reason="frozen Ancol review is local")
def test_ancol_bottom_walls_match_the_spike():
    gt = Spec.model_validate_json(GT.read_text())
    r = preprocess(load_raster(ANCOL, 13), sheet=True)
    pl = read_lines(ANCOL, 13, gt.meta.px_to_mm, tuple(r.meta["drawing_bbox"]), 300)
    walls = _long(pair_walls(pl))
    pred = gt.model_copy(update={"walls": [Wall(id=f"W{i}", a=w.a, b=w.b, thickness=max(10, round(w.thickness)), kind="interior")
                                           for i, w in enumerate(walls)], "rooms": []})
    m = gate_metrics(pred, gt, ANCOL_REVIEWED_BELOW)
    assert m["wall_recall"] >= 0.77 and m["wall_precision"] >= 0.8, m


def test_diagonal_hatch_is_not_a_wall():
    hatch = [Line((i * 200, 0), (i * 200 + 3000, 3000)) for i in range(8)]  # spacing ~141 mm across
    assert not _long(pair_walls(_pl(hatch)))


def test_single_line_is_a_conditional_wall():
    w = pair_walls(_pl([_h(0)]))
    assert len(w) == 1 and w[0].evidence["source"] == "single" and w[0].evidence["short"]


def test_line_of_a_pair_is_not_also_single():
    assert all(w.evidence["source"] == "pair" for w in pair_walls(_pl([_h(0), _h(150)])))


def test_rails_of_a_tray_are_not_single_walls():
    rungs = [Line((x, -10), (x, 317)) for x in range(0, 5000, 353)]
    assert not pair_walls(_pl([_h(0), _h(307)], short=rungs))


def test_skewed_single_line_is_not_a_wall():
    assert not pair_walls(_pl([Line((0, 0), (3000, 2000))]))
