import pytest

from core.interior.check import check
from core.interior.devices import fill
from core.interior.layout import Placement
from core.interior.library import load_library
from core.interior.rules import load_rules
from core.interior.space import room_space
from tests.interior.conftest import hall

R = load_rules()
RACK = "rack-42u-600x1200"


@pytest.fixture(scope="module")
def lib(library_dir):
    return load_library(library_dir)


def rack(x, y, rot=0.0, z=0.0):
    return Placement(RACK, "1.1.0", x, y, z, rot, (600, 1200, 2000))


def space(lib, **kw):
    spec = hall(**kw)
    return room_space(spec, spec.rooms[0].id, None, 3000, lib, R)


def codes(issues):
    return sorted({i["code"] for i in issues})


def test_overlap_is_an_error(lib):
    issues = check([rack(3000, 3000), rack(3300, 3000)], space(lib), lib, R)
    assert "O001" in codes(issues) and any(i["severity"] == "error" for i in issues if i["code"] == "O001")


def test_roof_over_racks_is_not_an_overlap(lib):
    roof = Placement("containment-roof-600", "1.1.0", 3000, 3000, 2000, 0, (600, 1200, 60))
    assert "O001" not in codes(check([rack(3000, 3000), roof], space(lib), lib, R))


def test_front_too_close_to_a_wall(lib):
    # room face at y = 7900; a rack facing north with its front 500 mm from it
    assert "O002" in codes(check([rack(3000, 7900 - 500 - 600)], space(lib), lib, R))


def test_rack_in_a_door_zone(lib):
    sp = space(lib, doors=[(0, 4500, 900)])
    assert "O003" in codes(check([rack(4950, 1500)], sp, lib, R))


def test_engine_result_is_clean(lib):
    sp = space(lib, doors=[(0, 4500, 900)])
    lay = fill(sp, lib, {RACK: None, "pdu-floor-generic": None}, {"containment": True, "cooling": "inrow"}, "rows", R)
    assert check(lay.placements, sp, lib, R) == []


def test_full_hall_with_devices_near_the_door_is_clean(lib):
    """14 x 10 m, door on the south wall: the reader beside the door and a CRAC on that wall, a containment aisle
    ending near the door (found by the check, 2026-11-03)."""
    spec = hall(w=14000, h=10000, doors=[(0, 6500, 1200)])
    sp = room_space(spec, spec.rooms[0].id, None, 3200, lib, R)
    items = {RACK: None, "pdu-floor-generic": None, "crac-unit-generic": 2, "fire-control-panel": 1,
             "access-reader-generic": 1, "cctv-camera-bullet": 2, "fire-cylinder-generic": None}
    lay = fill(sp, lib, items, {"cooling": "crac", "containment": True}, "rows", R)
    assert check(lay.placements, sp, lib, R) == []
    assert any(p.template_id == "access-reader-generic" for p in lay.placements)


def test_big_hall_with_columns_is_clean(lib):
    """20 x 15 m with two columns: facing rows of unequal length (found by the check, 2026-11-03)."""
    spec = hall(w=20000, h=15000, doors=[(0, 2000, 1800)], columns=[(7000, 7500, 600), (13000, 7500, 600)])
    sp = room_space(spec, spec.rooms[0].id, None, 3200, lib, R)
    items = {RACK: None, "pdu-floor-generic": None, "crac-unit-generic": 2, "fire-control-panel": 1,
             "access-reader-generic": 1, "cctv-camera-bullet": 2, "fire-cylinder-generic": None}
    lay = fill(sp, lib, items, {"cooling": "crac", "containment": True}, "rows", R)
    assert check(lay.placements, sp, lib, R) == []
