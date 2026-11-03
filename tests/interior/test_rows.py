import math

import pytest
from shapely.geometry import box as sbox

from core.interior.library import load_library
from core.interior.rows import layout_rows
from core.interior.rules import load_rules
from core.interior.space import room_space
from tests.interior.conftest import hall

RACK = "rack-42u-600x1200"


@pytest.fixture(scope="module")
def lib(library_dir):
    return load_library(library_dir)


def run(spec, lib, items, **options):
    space = room_space(spec, spec.rooms[0].id, None, 3000, lib, load_rules())
    return space, layout_rows(space, lib, items, {"containment": False, "cooling": None, "rows": "auto", **options},
                              load_rules())


def front(p):
    t = math.radians(p.rotation)
    return (-math.sin(t), math.cos(t))


def racks(lay):
    return [p for p in lay.placements if p.template_id == RACK]


def test_capacity_hand_count(lib):
    """Hall 10 x 8 m on the wall axes, 9.8 x 7.8 m inside, no door.
    Rows north-south: x walk 100 +1000 back | row 1200 | cold 1200 | row 1200 | hot 1000 | row 1200 | front 1200 =
    8100 <= 9900, a fourth row needs 10300: 3 rows. Along y: 7800 - 2 x 1200 end clearance = 5400 / 600 = 9. -> 27.
    Rows east-west: one pair (100 + 1000 + 3600 + 1000 = 5700 <= 7900; a third row would end at 8100 > 7900),
    9800 - 2400 = 7400 / 600 = 12 per row -> 24."""
    _, lay = run(hall(), lib, {RACK: None})
    assert lay.capacity[RACK] == 27 and len(racks(lay)) == 27
    _, lay = run(hall(), lib, {RACK: None}, rows="ew")
    assert lay.capacity[RACK] == 24


def test_hall_rows_face_the_cold_aisle(lib):
    _, lay = run(hall(), lib, {RACK: None}, rows="ew")
    by_y = {}
    for p in racks(lay):
        by_y.setdefault(round(p.y), []).append(p)
    (ya, row_a), (yb, row_b) = sorted(by_y.items())
    fa, fb = front(row_a[0]), front(row_b[0])
    assert fa[1] == pytest.approx(1) and fb[1] == pytest.approx(-1)  # facing each other across the cold aisle
    assert yb - ya == pytest.approx(1200 + 1200)  # depth + cold aisle


def test_target_smaller_fills_from_the_door(lib):
    spec = hall(doors=[(0, 4500, 900)])
    space, lay = run(spec, lib, {RACK: 6})
    door = space.doors[0].center
    kept = racks(lay)
    assert len(kept) == 6
    _, full = run(spec, lib, {RACK: None})
    unused = [p for p in racks(full) if all(math.dist((p.x, p.y), (q.x, q.y)) > 1 for q in kept)]
    mean = lambda ps: sum(math.dist((p.x, p.y), door) for p in ps) / len(ps)
    assert mean(kept) < mean(unused)


def test_target_larger_notes_capacity(lib):
    _, lay = run(hall(), lib, {RACK: 999})
    assert len(racks(lay)) == 27 and any("muat 27 dari 999" in n for n in lay.notes)


def test_door_zone_kept_clear(lib):
    space, lay = run(hall(doors=[(0, 4500, 900), (3, 3000, 1800)]), lib, {RACK: None, "pdu-floor-generic": None})
    zones = [d.zone for d in space.doors]
    assert lay.placements and all(p.footprint().intersection(z).area < 1 for p in lay.placements for z in zones)


def test_column_splits_a_row(lib):
    col = sbox(4700, 3700, 5300, 4300)
    _, lay = run(hall(columns=[(5000, 4000, 600)]), lib, {RACK: None}, rows="ew")
    assert lay.placements and all(p.footprint().intersection(col).area < 1 for p in lay.placements)


def test_l_shaped_room(lib):
    spec = hall(w=12000, h=10000, l_cut=(7000, 5000))
    space, lay = run(spec, lib, {RACK: None})
    assert lay.placements and all(space.room.buffer(1).covers(p.footprint()) for p in lay.placements)


def test_existing_objects_avoided(lib):
    crac = {"id": "O1", "template_id": "crac-unit-generic", "template_version": "1.1.0", "position": (5000, 7400, 0),
            "rotation": 180, "dims": (2500, 900, 1950)}
    spec = hall(objects=[crac])
    _, lay = run(spec, lib, {RACK: None})
    blocker = sbox(3750, 6950, 6250, 7850)
    assert lay.placements and all(p.footprint().intersection(blocker).area < 1 for p in lay.placements)


def test_inrow_and_pdu(lib):
    spec = hall(doors=[(0, 4500, 900)])
    _, lay = run(spec, lib, {RACK: None, "pdu-floor-generic": None}, cooling="inrow", rows="ew")
    rows = {}
    for p in lay.placements:
        rows.setdefault(round(p.y + 1e-6 if p.template_id != "pdu-floor-generic" else p.y), []).append(p)
    seqs = [[p.template_id for p in sorted(r, key=lambda p: p.x)] for r in lay.meta["runs"]]
    for seq in seqs:
        racks_between = 0
        for t in seq:
            if t == RACK:
                racks_between += 1
                assert racks_between <= 4
            elif t.startswith("inrow"):
                assert racks_between == 4
                racks_between = 0
    assert sum(1 for p in lay.placements if p.template_id == "pdu-floor-generic") == len(lay.meta["runs"])
