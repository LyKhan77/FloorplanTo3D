import pytest
from pydantic import ValidationError

from core.spec.models import Room, Spec, Wall, signed_area
from tests.spec.fixtures import two_room_spec


def test_fixture_roundtrips_json():
    s = two_room_spec()
    assert Spec.model_validate_json(s.model_dump_json()) == s


def test_float_mm_rounded():
    w = Wall(id="W9", a=(0.4, 10.6), b=(1000.5, 10), thickness=149.6, kind="interior")
    assert w.a == (0, 11) and w.thickness == 150
    assert w.b == (1000, 10)  # round half to even


def test_polygon_orientation_normalized():
    cw = [(0, 0), (0, 1000), (1000, 1000), (1000, 0), (0, 0)]  # CW + duplicate closing point
    r = Room(id="R9", polygon=cw, holes=[[(100, 100), (200, 100), (200, 200), (100, 200)]])
    assert r.polygon == [(0, 0), (1000, 0), (1000, 1000), (0, 1000)]  # CCW, same start point
    assert signed_area(r.holes[0]) < 0


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        Wall(id="W9", a=(0, 0), b=(1, 0), thickness=100, kind="interior", colour="red")


def test_grid_point_from_ref():
    assert two_room_spec().grid.point("B1") == (10000, 6000)
