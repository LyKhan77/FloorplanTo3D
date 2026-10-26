import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from core.spec.derive import derive, stair_metrics, wall_footprint
from core.spec.models import Defaults, Flight, Room, Stair, Wall
from tests.spec.fixtures import spec_with_rooms, two_room_spec


def test_l_corner_footprints_close_outer_corner():
    s = two_room_spec()
    u = unary_union([wall_footprint(w, s) for w in s.walls])
    assert u.envelope.bounds == (-100, -100, 10100, 6100)
    assert Polygon(u.exterior).area == pytest.approx(10200 * 6200)


def test_free_end_not_extended():
    s = two_room_spec()
    stub = Wall(id="W9", a=(2000, 3000), b=(3000, 3000), thickness=100, kind="partition", free_ends=True)
    s = s.model_copy(update={"walls": [*s.walls, stub]})
    assert wall_footprint(stub, s).bounds == (2000, 2950, 3000, 3050)


def test_room_derived_fields():
    s = spec_with_rooms()
    r1 = next(r for r in s.rooms if r.id == "R1")
    assert r1.area_m2 == pytest.approx(round(4850 * 5800 / 1e6, 2))
    assert r1.perimeter_m == pytest.approx(round(2 * (4850 + 5800) / 1000, 2))
    assert r1.bounding_walls == ["W1", "W3", "W4", "W5"]
    assert r1.doors == ["D1", "D2"]


def test_door_counts_only_for_rooms_it_opens_into():
    s = spec_with_rooms()
    r2 = next(r for r in s.rooms if r.id == "R2")
    assert "W1" in r2.bounding_walls and r2.doors == ["D1"]  # D2 sits on W1 but in front of R1 only


def test_area_subtracts_holes():
    room = Room(id="R9", polygon=[(0, 0), (2000, 0), (2000, 2000), (0, 2000)],
                holes=[[(500, 500), (500, 900), (900, 900), (900, 500)]])
    s = derive(two_room_spec().model_copy(update={"rooms": [room]}))
    assert s.rooms[0].area_m2 == pytest.approx(4.0 - 0.16)


def test_gross_area_from_outline():
    s = two_room_spec()
    s.meta.building_outline = [[(-100, -100), (10100, -100), (10100, 6100), (-100, 6100)]]
    assert derive(s).meta.gross_area_m2 == pytest.approx(63.24)


def test_stair_metrics_two_flights():
    st = Stair(id="S1", flights=[Flight(start=(0, 0), end=(0, 3300), width=1100, risers=12),
                                 Flight(start=(1500, 3300), end=(1500, 0), width=1100, risers=12)])
    m = stair_metrics(st, Defaults())
    assert m[0].riser_mm == pytest.approx(4000 / 24) and m[0].tread_mm == pytest.approx(275)
    assert (m[1].start_z, m[1].end_z) == pytest.approx((2000, 4000))
