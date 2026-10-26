
from core.extraction.geometry.postprocess import (
    apply_existing,
    classify_kind,
    drop_short,
    join_ends,
    merge_collinear,
    postprocess,
    snap_to_grid,
)
from core.extraction.geometry.walls_s2 import _wall

S = 12.5


def W(orient, c, a, b, t=150):
    return _wall(orient, c, a, b, t, {"pair_overlap": 1.0, "partial_mm": 0})


def test_text_gap_closed_by_collinear_merge():
    walls, _ = merge_collinear([W("h", 100, 0, 200), W("h", 100.5, 232, 400)], S)  # 400 mm
    assert len(walls) == 1 and (walls[0]["a"], walls[0]["b"]) == (0, 400)
    walls, _ = merge_collinear([W("h", 100, 0, 200), W("h", 100, 272, 400)], S)  # 900 mm, clean ends
    assert len(walls) == 1 and walls[0]["evidence"]["gaps"] == [[200, 272]]
    walls, _ = merge_collinear([W("h", 100, 0, 200), W("h", 100, 480, 600)], S)  # 3500 mm
    assert len(walls) == 2


def test_gap_with_a_wall_at_its_end_is_not_an_opening():
    # a cross wall meets the left part's end: the 900 mm gap is a T junction gap, not a doorway
    walls, _ = merge_collinear([W("h", 100, 0, 200), W("h", 100, 272, 400), W("v", 200, 100, 300)], S)
    assert len([w for w in walls if w["orient"] == "h"]) == 2


def test_snap_and_join_make_l_and_t():
    axes = {"vertical": [300.0], "horizontal": [100.0]}
    snapped = snap_to_grid([W("v", 308, 100, 300)], axes, S)  # 100 mm off the axis
    assert snapped[0]["c"] == 300
    joined = join_ends([W("h", 100, 0, 400), W("v", 200, 106.5, 300)], S)  # 80 mm short of the h centreline
    v = next(w for w in joined if w["orient"] == "v")
    assert v["a"] == 100


def test_short_isolated_dropped_connected_kept():
    walls = [W("h", 100, 0, 400), W("v", 200, 100, 120), W("v", 350, 250, 270)]  # two 250 mm walls
    kept = drop_short(walls, S)
    assert [(w["orient"], w["c"]) for w in kept] == [("h", 100), ("v", 200)]


def test_kind_classification():
    box = [W("h", 0, 0, 400), W("h", 300, 0, 400), W("v", 0, 0, 300), W("v", 400, 0, 300)]
    inner = [W("v", 200, 0, 300, t=100), W("h", 150, 0, 200, t=150)]
    kinds = {(w["orient"], w["c"]): w["kind"] for w in classify_kind(box + inner, S)}
    assert [kinds[("h", 0)], kinds[("h", 300)], kinds[("v", 0)], kinds[("v", 400)]] == ["exterior"] * 4
    assert kinds[("v", 200)] == "partition" and kinds[("h", 150)] == "interior"


def test_proposed_wall_skipped_dismantle_kept():
    walls = [W("h", 100, 0, 400), W("v", 200, 120, 300)]
    pointers = [{"cls": "proposed", "point": [100, 101], "text_bbox": [0, 0, 1, 1]},
                {"cls": "dismantle", "point": [201, 200], "text_bbox": [0, 0, 1, 1]}]
    kept, issues = apply_existing(walls, pointers, [], S)
    assert [w["orient"] for w in kept] == ["v"] and kept[0]["evidence"]["note"] == "to_be_dismantled"
    assert issues[0]["code"] == "EXISTING_PROPOSED" and issues[0]["severity"] == "info"
    # a proposed text without leader removes only elements lying wholly within 1000 mm (80 px) of it
    small = [W("h", 300, 400, 440), W("h", 100, 0, 600)]
    text = {"text": "PROPOSED", "bbox": [410, 320, 470, 335], "cls": "proposed"}
    kept, issues = apply_existing(small, [], [text], S)
    assert [(w["c"], w["a"]) for w in kept] == [(100, 0)]


def test_postprocess_reports_gap_openings_in_mm():
    walls, gaps, _ = postprocess([W("h", 100, 0, 200), W("h", 100, 272, 400)], {"vertical": [], "horizontal": []}, [], [], S)
    assert len(walls) == 1
    assert gaps == [{"wall_index": 0, "offset_mm": 2500, "width_mm": 900}]
