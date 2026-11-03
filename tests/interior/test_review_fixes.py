"""Final review findings (2026-11-03), each pinned by a test."""

import pytest
from shapely.geometry import box as sbox

from core.interior.check import check
from core.interior.devices import fill
from core.interior.drawn import place_drawn
from core.interior.library import load_library
from core.interior.lineup import layout_lineup
from core.interior.rules import load_rules
from core.interior.space import room_space
from tests.interior.conftest import hall

R = load_rules()
RACK = "rack-42u-600x1200"


@pytest.fixture(scope="module")
def lib(library_dir):
    return load_library(library_dir)


def sp(spec, lib, box=None):
    return room_space(spec, spec.rooms[0].id, box, 3000, lib, R)


def test_a_drawn_row_slightly_short_is_still_clean(lib):
    s = sp(hall(), lib)
    ps, _ = place_drawn([{"id": "K1", "center": [5000, 4000], "size": [1200, 4790], "rotation": 0}], lib[RACK], s, R)
    assert len(ps) == 8 and not [i for i in check(ps, s, lib, R) if i["code"] == "O001"]


def test_containment_roofs_skip_a_column(lib):
    col = sbox(4700, 3700, 5300, 4300)
    s = sp(hall(w=14000, h=10000, columns=[(5000, 4000, 600)]), lib)
    lay = fill(s, lib, {RACK: None}, {"containment": True, "rows": "ew"}, "rows", R)
    roofs = [p for p in lay.placements if p.template_id == "containment-roof-600"]
    assert roofs and all(r.footprint().intersection(col).area < 1 for r in roofs)


def test_null_rows_option_does_not_crash(lib):
    lay = fill(sp(hall(), lib), lib, {RACK: None}, {"rows": None, "cooling": None, "containment": None}, "rows", R)
    assert lay.placements


def test_the_box_edge_is_not_a_wall(lib):
    """A box over the west half of a 10 x 8 hall: its east edge (x = 5000) runs mid-room."""
    s = sp(hall(), lib, box=(-500, -500, 5000, 8500))
    assert all(not (abs(e.coords[0][0] - 5000) < 1 and abs(e.coords[1][0] - 5000) < 1) for e in s.walls)


def test_lineup_places_what_fits_and_says_so(lib):
    s = sp(hall(w=6000, h=5000, doors=[(3, 1500, 900)]), lib)
    lay = layout_lineup(s, lib, {"ups-cabinet-generic": 8, "battery-rack-generic": 50}, R)
    ups = [p for p in lay.placements if p.template_id == "ups-cabinet-generic"]
    assert 0 < len(ups) < 8 and any(f"muat {len(ups)} dari 8" in n for n in lay.notes)
    bats = [p for p in lay.placements if p.template_id == "battery-rack-generic"]
    assert any(f"muat {len(bats)} dari 50" in n for n in lay.notes)


def test_new_object_on_an_existing_one_is_an_overlap(lib):
    existing = {"id": "O1", "template_id": "ups-cabinet-generic", "template_version": "1.1.0",
                "position": (3000, 3000, 0), "rotation": 0, "dims": (1200, 800, 2000)}
    s = sp(hall(objects=[existing]), lib)
    ps, _ = place_drawn([{"id": "K1", "center": [3000, 3000], "size": [800, 1200], "rotation": 90}],
                        lib["ups-cabinet-generic"], s, R)
    assert any(i["code"] == "O001" for i in check(ps, s, lib, R))


def test_cooling_in_a_lineup_room_goes_on_a_wall(lib):
    """Strata asked for a CRAC with layout 'lineup' (test-2 AHU room, 2026-11-03: dropped silently). A 3 x 4.4 m room:
    the 2.5 m CRAC on the north wall with 1.2 m airflow in front, clear of the south door's zone."""
    s = sp(hall(w=3200, h=4600, doors=[(0, 300, 900)]), lib)
    lay = fill(s, lib, {"crac-unit-generic": None}, {}, "lineup", R)
    (crac,) = [p for p in lay.placements if p.template_id == "crac-unit-generic"]
    assert s.room.buffer(1).covers(crac.footprint()) and crac.footprint().distance(s.room.exterior) < 2
    assert not check(lay.placements, s, lib, R)


def test_one_rack_in_a_small_room_goes_on_a_wall(lib):
    """Rows need about 3 x 3.4 m; one rack in 2.5 x 3.5 m stands against a wall with its front space free."""
    s = sp(hall(w=2700, h=3700, doors=[(0, 300, 900)]), lib)
    lay = fill(s, lib, {RACK: 1}, {}, "rows", R)
    racks = [p for p in lay.placements if p.template_id == RACK]
    assert len(racks) == 1 and any("dinding" in n for n in lay.notes)
    assert not any(n.startswith("muat 0") for n in lay.notes)  # the shortfall was covered
    assert check(lay.placements, s, lib, R) == []  # no back working space asked of a rack set against a wall
    (front,) = racks[0].zones(lib[RACK], R)[:1]
    assert s.room.buffer(1).covers(front)


def test_an_item_that_cannot_be_placed_is_named(lib):
    s = sp(hall(w=1500, h=1500), lib)
    lay = fill(s, lib, {"crac-unit-generic": 1}, {}, "lineup", R)
    assert not lay.placements and any("crac-unit-generic" in n for n in lay.notes)


def test_a_unit_that_does_not_fit_suggests_one_that_does(lib):
    """test-2 AHU room: a CRAC (2.5 m + 1.2 m airflow) does not fit 2.5 x 3.5 m; an in-row cooler does."""
    s = sp(hall(w=2700, h=3700, doors=[(0, 300, 900)]), lib)
    lay = fill(s, lib, {"crac-unit-generic": None}, {}, "lineup", R)
    assert any("crac-unit-generic tidak muat" in n and "inrow-cooler-300x1200" in n for n in lay.notes)
