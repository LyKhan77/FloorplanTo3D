from core.extraction.vector.structure import select_walls
from core.extraction.vector.walls import WallCand


def _w(a, b, t=150, source="pair", short=False):
    ev = {"source": source, **({"short": True} if short else {})}
    return WallCand(a, b, t, ev)


def _room():
    return [_w((0, 0), (9000, 0)), _w((9000, 0), (9000, 6000)), _w((9000, 6000), (0, 6000)), _w((0, 6000), (0, 0))]


def _solid(walls):
    keep = {(w.a, w.b) for w in walls}
    return lambda w: 1.0 if (w.a, w.b) in keep else 0.0


def _kept(cands, solid):
    return {(w.a, w.b) for w in select_walls(cands, solid)}


def test_solid_walls_are_firm():
    room = _room()
    assert len(select_walls(room, _solid(room))) == 4


def test_long_pair_is_firm_without_solid_ink():
    w = _w((0, 0), (6000, 0))
    assert select_walls([w], lambda _: 0.0)


def test_tray_ring_inside_a_room_is_content():
    room = _room()
    ring = [_w((400, 400), (1700, 400))]  # short of FIRM length, parallel to the wall 400 mm away
    assert (ring[0].a, ring[0].b) not in _kept(room + ring, _solid(room))


def test_partition_touching_firm_walls_stays():
    room = _room()
    part = _w((4000, 0), (4000, 2400))
    assert (part.a, part.b) in _kept(room + [part], _solid(room))


def test_floating_box_is_content():
    room = _room()
    box = _w((3000, 2500), (4500, 2500))
    assert (box.a, box.b) not in _kept(room + [box], _solid(room))


def test_single_line_needs_both_ends_on_walls():
    room = _room()
    one = _w((4000, 0), (4000, 3000), 100, "single", True)
    both = _w((5000, 0), (5000, 6000), 100, "single", True)
    kept = _kept(room + [one, both], _solid(room))
    assert (one.a, one.b) not in kept and (both.a, both.b) in kept


def test_regular_grid_of_single_lines_is_floor_tile():
    room = _room()
    tiles = [_w((600 * i, 0), (600 * i, 6000), 100, "single", True) for i in range(2, 13)]
    assert not (_kept(room + tiles, _solid(room)) - {(w.a, w.b) for w in room})


def test_kept_walls_are_not_conditional_any_more():
    room = _room()
    both = _w((5000, 0), (5000, 6000), 100, "single", True)
    assert all("short" not in w.evidence for w in select_walls(room + [both], _solid(room)))
