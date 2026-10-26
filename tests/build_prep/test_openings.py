import pytest

from core.build_prep.openings import cutters, door_items, window_items
from core.spec.models import Opening
from tests.spec.fixtures import spec_with_rooms


def test_cutter_spans_opening_and_wall_thickness():
    s = spec_with_rooms()  # D2 on W1: offset 1000, width 1800, t 200
    c = next(c for c in cutters(s) if c["target"] == "wall_W1")
    xs, ys, zs = zip(*c["verts"])
    assert (min(xs), max(xs)) == pytest.approx((1000, 2800))
    assert (min(ys), max(ys)) == pytest.approx((-110, 110)) and (min(zs), max(zs)) == pytest.approx((0, 2100))


def test_single_door_leaf_pivot_at_hinge():
    s = spec_with_rooms()  # D1 on W5 (vertical, a=(5000,0)), offset 2000, hinge start
    empties, meshes = door_items(s)
    d1 = next(e for e in empties if e["name"] == "door_D1")
    assert d1["location"] == pytest.approx([5000, 2000, 0]) and d1["rot_z"] == pytest.approx(90)
    assert d1["props"]["door_type"] == "single_swing" and d1["props"]["spec_type"] == "door"
    leaf = next(m for m in meshes if m["name"] == "leaf_D1_a")
    assert leaf["parent"] == "door_D1" and leaf["location"] == pytest.approx([0, 0, 0])
    xs = [v[0] for v in leaf["verts"]]
    assert (min(xs), max(xs)) == pytest.approx((0, 900)) and max(v[2] for v in leaf["verts"]) == pytest.approx(2090)


def test_double_door_two_leaves_meet_in_middle():
    s = spec_with_rooms()  # D2 double, width 1800
    _, meshes = door_items(s)
    a = next(m for m in meshes if m["name"] == "leaf_D2_a")
    b = next(m for m in meshes if m["name"] == "leaf_D2_b")
    assert b["location"][0] == pytest.approx(1800)
    assert max(v[0] for v in a["verts"]) == pytest.approx(900) and min(v[0] for v in b["verts"]) == pytest.approx(-900)


def test_opening_type_has_frame_only():
    s = spec_with_rooms()
    s.openings[0].door_type = "opening"
    _, meshes = door_items(s)
    assert not any(m["name"].startswith("leaf_D1") for m in meshes) and any(m["name"] == "frame_D1" for m in meshes)


def test_window_sits_at_sill():
    s = spec_with_rooms()
    s.openings.append(Opening(id="N1", category="window", wall_id="W3", offset=1000, width=1200, sill=900))
    w = window_items(s)[0]
    zs = [v[2] for v in w["verts"]]
    assert (min(zs), max(zs)) == pytest.approx((900, 2100)) and w["material"] == "glass"
    assert w["name"] == "window_N1" and w["props"]["spec_type"] == "window"
