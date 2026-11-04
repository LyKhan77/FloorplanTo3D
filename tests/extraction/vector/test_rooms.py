import pytest

from core.extraction.vector.doors import Door
from core.extraction.vector.rooms import trace_rooms
from core.extraction.vector.walls import WallCand

CUT = (-5000, -5000, 25000, 15000)


def _w(a, b, t=150, **ev):
    return WallCand(a, b, t, ev)


def _box(x0=0, y0=0, x1=6000, y1=4000):
    return [_w((x0, y0), (x1, y0)), _w((x1, y0), (x1, y1)), _w((x1, y1), (x0, y1)), _w((x0, y1), (x0, y0))]


def _closers(t):
    return [w.evidence["closer"] for w in t.walls if "closer" in w.evidence]


def _gapped_box(gap=1000):
    """The bottom wall has a gap centred at x=3000."""
    h = gap / 2
    return [_w((0, 0), (3000 - h, 0)), _w((3000 + h, 0), (6000, 0)), *_box()[1:]]


def test_closed_room_has_no_closers():
    t = trace_rooms(_box(), [], [], [(3000, 2000)], CUT)
    assert len(t.rooms) == 1 and not _closers(t) and t.open_labels == []
    assert t.rooms[0].area == pytest.approx(24e6, rel=0.01)


def test_door_gap_closes_with_a_door():
    door = Door((2500, 0), 1000, ((3500, 0), (2500, 1000)))
    t = trace_rooms(_gapped_box(), [door], [], [(3000, 2000)], CUT)
    assert _closers(t) == ["door"] and len(t.rooms) == 1
    (o,) = t.openings
    assert o["door_type"] == "single_swing" and o["category"] == "door" and o["width"] == pytest.approx(1000, abs=5)
    assert t.walls[o["wall"]].evidence["closer"] == "door"


def test_gap_without_arc_closes_as_opening():
    t = trace_rooms(_gapped_box(), [], [], [(3000, 2000)], CUT)
    assert _closers(t) == ["gap"] and t.openings[0]["door_type"] == "opening"


def test_wide_gap_stays_open():
    t = trace_rooms(_gapped_box(2500), [], [], [(3000, 2000)], CUT)
    assert not t.rooms and not _closers(t) and t.open_labels == [(3000, 2000)]


def test_column_closes_between_wall_ends():
    col = {"center": [3000, 0], "size": [400, 400], "shape": "rect"}
    t = trace_rooms(_gapped_box(1800), [], [col], [(3000, 2000)], CUT)
    assert len(t.rooms) == 1 and {w.evidence.get("extended_by") for w in t.walls} >= {"column"}


def test_sheet_cut_only_on_the_open_side():
    walls = [_w((0, 0), (0, 4000)), _w((0, 4000), (6000, 4000)), _w((6000, 4000), (6000, 0))]
    t = trace_rooms(walls, [], [], [(3000, 2000)], (-5000, 0, 25000, 15000))
    assert len(t.rooms) == 1 and "sheet_cut" in _closers(t)
    cut = [w for w in t.walls if w.evidence.get("closer") == "sheet_cut"]
    assert all(w.a[1] <= 1 and w.b[1] <= 1 for w in cut)  # along y=0 only, none along the drawn sides
    assert not _closers(trace_rooms(_box(0, 0), [], [], [(3000, 2000)], (-5000, 0, 25000, 15000)))


def test_neighbour_reuses_the_shared_wall():
    walls = [*_box(), _w((6000, 0), (12000, 0)), _w((12000, 0), (12000, 4000)), _w((12000, 4000), (6000, 4000))]
    t = trace_rooms(walls, [], [], [(3000, 2000), (9000, 2000)], CUT)
    assert len(t.rooms) == 2 and not _closers(t)
    assert sum(w.a[0] == w.b[0] == 6000 for w in t.walls) == 1


def test_doubled_wall_collapses():
    t = trace_rooms([*_box(), _w((0, 40), (6000, 40))], [], [], [(3000, 2000)], CUT)
    assert len(t.walls) == 4


def test_rack_inside_a_room_is_dropped():
    t = trace_rooms([*_box(), _w((2000, 2000), (4000, 2000))], [], [], [(3000, 1000)], CUT)
    assert len(t.walls) == 4


def test_leaking_face_with_two_labels_is_not_a_room():
    walls = [*_box(), _w((3000, 0), (3000, 1000)), _w((3000, 3000), (3000, 4000))]  # a 2 m hole in the partition
    t = trace_rooms(walls, [], [], [(1500, 2000), (4500, 2000)], CUT)
    assert not t.rooms and sorted(t.open_labels) == [(1500, 2000), (4500, 2000)]


def test_trace_is_deterministic():
    walls = _gapped_box()
    a = trace_rooms(walls, [], [], [(3000, 2000)], CUT)
    b = trace_rooms(list(reversed(walls)), [], [], [(3000, 2000)], CUT)
    assert sorted((w.a, w.b) for w in a.walls) == sorted((w.a, w.b) for w in b.walls)


def test_equipment_box_drawn_in_single_lines_is_dropped():
    rack = [_w((2000, 1500), (4000, 1500), 100, source="single", short=True),
            _w((4000, 1500), (4000, 2500), 100, source="single", short=True),
            _w((4000, 2500), (2000, 2500), 100, source="single", short=True),
            _w((2000, 2500), (2000, 1500), 100, source="single", short=True)]
    t = trace_rooms([*_box(), *rack], [], [], [(1000, 1000)], CUT)
    assert len(t.walls) == 4 and len(t.rooms) == 1


def test_single_line_along_the_cut_is_the_sheet_frame():
    frame = _w((-4000, -5000), (24000, -5000), 100, source="single", short=True)
    assert len(trace_rooms([*_box(), frame], [], [], [(3000, 2000)], CUT).walls) == 4


def test_corner_gap_closes():
    # walls stop short of the corner on both sides, as they do against a corner column the raster missed
    walls = [_w((0, 0), (5400, 0)), _w((6000, 600), (6000, 4000)), _w((6000, 4000), (0, 4000)), _w((0, 4000), (0, 0))]
    t = trace_rooms(walls, [], [], [(3000, 2000)], CUT)
    assert len(t.rooms) == 1 and {w.evidence.get("extended_by") for w in t.walls} >= {"corner"} and not t.openings


def test_ends_past_the_cut_still_reach_it():
    walls = [_w((0, -300), (0, 4000)), _w((0, 4000), (6000, 4000)), _w((6000, 4000), (6000, -300))]
    t = trace_rooms(walls, [], [], [(3000, 2000)], (-5000, 0, 25000, 15000))
    assert len(t.rooms) == 1 and "sheet_cut" in _closers(t)


def test_recess_cap_closes():
    # two stubs end side by side: the back of a recess in an outer wall
    walls = [_w((0, 0), (6000, 0)), _w((6000, 0), (6000, 4000)), _w((6000, 4000), (0, 4000)),
             _w((0, 4000), (0, 2500)), _w((0, 1500), (0, 0)), _w((0, 2500), (-800, 2500)), _w((0, 1500), (-800, 1500))]
    t = trace_rooms(walls, [], [], [(3000, 2000)], CUT)
    assert len(t.rooms) == 1 and "cap" in _closers(t) and not t.openings


def test_double_door_gap_closes_only_with_arcs():
    gap = _gapped_box(2000)
    doors = [Door((2000, 0), 1000, ((3000, 0), (2000, 1000))), Door((4000, 0), 1000, ((3000, 0), (4000, 1000)))]
    t = trace_rooms(gap, doors, [], [(3000, 2000)], CUT)
    assert len(t.rooms) == 1 and t.openings[0]["door_type"] == "double_swing"
    assert not trace_rooms(gap, [], [], [(3000, 2000)], CUT).rooms


def test_single_lines_of_a_narrow_strip_are_dropped():
    strip = [_w((1000, 1500), (5000, 1500), 100, source="single", short=True),
             _w((1000, 2000), (5000, 2000), 100, source="single", short=True),
             _w((1000, 1500), (0, 1500), 100, source="single", short=True),
             _w((1000, 2000), (0, 2000), 100, source="single", short=True),
             _w((5000, 1500), (5000, 2000), 100, source="single", short=True),
             _w((1000, 1500), (1000, 2000), 100, source="single", short=True)]
    t = trace_rooms([*_box(), *strip], [], [], [(3000, 3000)], CUT)
    assert not [w for w in t.walls if w.evidence.get("source") == "single"]


def test_long_single_wall_with_a_rack_against_it_stays():
    partition = _w((3000, 0), (3000, 4000), 100, source="single", short=True)
    rack = [_w((3000, 1000), (3400, 1000), 100, source="single", short=True),
            _w((3400, 1000), (3400, 1600), 100, source="single", short=True),
            _w((3400, 1600), (3000, 1600), 100, source="single", short=True)]
    t = trace_rooms([*_box(), partition, *rack], [], [], [(1500, 2000), (4500, 3000)], CUT)
    assert any(w.a[0] == w.b[0] == 3000 for w in t.walls) and len(t.rooms) == 2


def test_drawn_wall_extended_to_the_cut_is_not_tagged_as_cut():
    walls = [_w((0, 900), (0, 4000), source="pair"), _w((0, 4000), (6000, 4000), source="pair"),
             _w((6000, 4000), (6000, 900), source="pair")]
    t = trace_rooms(walls, [], [], [(3000, 2000)], (-5000, 0, 25000, 15000))
    tagged = [w for w in t.walls if w.evidence.get("closer") == "sheet_cut"]
    assert len(t.rooms) == 1 and len(tagged) == 1 and tagged[0].a[1] == tagged[0].b[1] == 0
    assert all(w.evidence.get("source") == "pair" for w in t.walls if w not in tagged)
