import math

import pytest
from shapely.geometry import LineString

from benchmarks.synth.perturb import load_base, no_ops, perturb
from core.spec.derive import column_footprint, endpoint_connected
from core.spec.validate import validate


@pytest.fixture(scope="module")
def base():
    return load_base()


def _offsets(spec, orientation):
    return sorted(a.offset for a in spec.grid.axes if a.orientation == orientation)


def _length(w):
    return math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1])


def test_no_ops_keeps_geometry(base):
    s, _ = perturb(base, 0, no_ops(base))
    assert [w.model_dump() for w in s.walls] == [w.model_dump() for w in base.walls]
    assert [o.model_dump() for o in s.openings] == [o.model_dump() for o in base.openings]
    assert [c.center for c in s.columns] == [c.center for c in base.columns]
    assert len(s.rooms) == 48


def test_same_seed_same_spec(base):
    a, ops_a = perturb(base, 7)
    b, ops_b = perturb(base, 7)
    assert ops_a == ops_b and a.model_dump() == b.model_dump()


def test_bays_move_axes_and_walls_on_them(base):
    ops = no_ops(base) | {"bays": [5000] * 5 + [7000] * 2}
    s, _ = perturb(base, 0, ops)
    assert _offsets(s, "vertical") == [0, 5000, 10000, 15000, 20000, 25000]
    assert _offsets(s, "horizontal") == [0, 7000, 14000]
    on_b = [i for i, w in enumerate(base.walls) if w.a[0] == 6000]
    assert on_b and all(s.walls[i].a[0] == 5000 for i in on_b)


def test_mirror_flips_swing_keeps_frame(base):
    s, _ = perturb(base, 0, no_ops(base) | {"mirror": True})
    span = max(_offsets(base, "vertical"))
    assert _offsets(s, "vertical") == sorted(span - o for o in _offsets(base, "vertical"))
    left = min(s.grid.axes, key=lambda a: (a.orientation != "vertical", a.offset))
    assert left.label == "A" and left.offset == 0
    for g, p in zip(base.walls, s.walls):
        assert p.a == (span - g.a[0], g.a[1]) and p.b == (span - g.b[0], g.b[1])
    flip = {"left": "right", "right": "left", None: None}
    for g, p in zip(base.openings, s.openings):
        assert p.swing == flip[g.swing] and p.hinge == g.hinge


def test_dropped_partitions_host_no_openings(base):
    s, _ = perturb(base, 0, no_ops(base) | {"drop_partitions": 3})
    gone = {w.id for w in base.walls} - {w.id for w in s.walls}
    assert len(gone) == 3
    assert not any(o.wall_id in gone for o in base.openings)
    assert all(w.kind in ("partition", "interior") for w in base.walls if w.id in gone)


def test_added_partition_splits_a_room(base):
    s, _ = perturb(base, 0, no_ops(base) | {"add_partitions": 1})
    new = [w for w in s.walls if w.id not in {g.id for g in base.walls}]
    assert len(new) == 1 and new[0].kind == "partition" and new[0].thickness == 100
    w = new[0]
    assert endpoint_connected(s, w, "a") and endpoint_connected(s, w, "b")
    line = LineString([w.a, w.b])
    walls = {x.id: x for x in s.walls}
    for o in s.openings:
        h = walls[o.wall_id]
        ux, uy = (h.b[0] - h.a[0]) / _length(h), (h.b[1] - h.a[1]) / _length(h)
        seg = LineString([(h.a[0] + ux * o.offset, h.a[1] + uy * o.offset),
                          (h.a[0] + ux * (o.offset + o.width), h.a[1] + uy * (o.offset + o.width))])
        assert not line.intersects(seg.buffer(h.thickness / 2))
    assert not any(line.intersects(column_footprint(c)) for c in s.columns)
    assert not any(line.intersects(LineString([f.start, f.end]).buffer(f.width / 2)) for st in s.stairs for f in st.flights)
    assert len(s.rooms) == 49


@pytest.mark.parametrize("seed", range(20))
def test_openings_stay_on_their_walls(base, seed):
    s, _ = perturb(base, seed)
    walls = {w.id: w for w in s.walls}
    for o in s.openings:
        assert o.offset >= 0 and o.offset + o.width <= _length(walls[o.wall_id]) + 1


@pytest.mark.parametrize("seed", range(20))
def test_variants_validate_without_errors(base, seed):
    s, _ = perturb(base, seed)
    assert [i.code for i in validate(s).issues if i.severity == "error"] == []
