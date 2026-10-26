import pytest
from shapely.geometry import Polygon

from core.build_prep.mesh import box, flat, is_closed, merge, prism
from tests.build_prep.meshutil import area_at, faces_at, normal


def test_prism_square_closed_with_volume():
    m = prism(Polygon([(0, 0), (1000, 0), (1000, 2000), (0, 2000)]), 0, 3000)
    assert is_closed(m) and len(m["verts"]) == 8
    assert area_at(m, 3000) == pytest.approx(2_000_000)


def test_prism_with_hole_is_closed_and_area_excludes_hole():
    ring = Polygon([(0, 0), (4000, 0), (4000, 4000), (0, 4000)],
                   [[(1000, 1000), (1000, 2000), (2000, 2000), (2000, 1000)]])
    m = prism(ring, 0, 100)
    assert is_closed(m) and area_at(m, 100) == pytest.approx(16e6 - 1e6)


def test_top_faces_point_up_and_sides_out():
    m = prism(Polygon([(0, 0), (1000, 0), (1000, 1000), (0, 1000)]), 0, 1000)
    assert all(normal(m, f)[2] > 0 for f in faces_at(m, 1000))
    assert all(normal(m, f)[2] < 0 for f in faces_at(m, 0))
    side = [f for f in m["faces"] if f not in faces_at(m, 0) and f not in faces_at(m, 1000)]
    for f in side:  # outward: normal points away from the centre (500, 500)
        c = [sum(m["verts"][i][k] for i in f) / len(f) for k in range(2)]
        n = normal(m, f)
        assert n[0] * (c[0] - 500) + n[1] * (c[1] - 500) > 0


def test_box_rotated_and_merge_offsets():
    b = box(0, 0, 50, 100, 10, 100, rot_z_deg=90)
    xs = [v[0] for v in b["verts"]]
    ys = [v[1] for v in b["verts"]]
    assert (max(xs) - min(xs), max(ys) - min(ys)) == pytest.approx((10, 100))
    assert len(b["faces"]) == 6 and is_closed(b)
    m = merge(b, box(500, 0, 50, 10, 10, 10))
    assert is_closed(m) and max(i for f in m["faces"] for i in f) == 15


def test_flat_faces_up():
    m = flat(Polygon([(0, 0), (1000, 0), (1000, 1000)]), 0)
    assert m["faces"] and all(normal(m, f)[2] > 0 for f in m["faces"])
