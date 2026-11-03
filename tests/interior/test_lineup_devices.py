import math

import pytest

from core.interior.devices import fill
from core.interior.layout import Layout
from core.interior.library import load_library
from core.interior.lineup import layout_lineup
from core.interior.rules import load_rules
from core.interior.space import room_space
from tests.interior.conftest import hall

RACK, UPS, ATS, MDB, BAT = ("rack-42u-600x1200", "ups-cabinet-generic", "ats-cabinet-generic", "panel-mdb-generic",
                            "battery-rack-generic")
R = load_rules()


@pytest.fixture(scope="module")
def lib(library_dir):
    return load_library(library_dir)


def space_of(spec, lib, ceiling=3000):
    return room_space(spec, spec.rooms[0].id, None, ceiling, lib, R)


def of(lay: Layout, tid):
    return [p for p in lay.placements if p.template_id == tid]


def overlaps(lay):
    fps = [p.footprint() for p in lay.placements if p.z == 0]
    return [(i, j) for i in range(len(fps)) for j in range(i + 1, len(fps)) if fps[i].intersection(fps[j]).area > 1]


def test_lineup_on_the_longest_free_wall(lib):
    spec = hall(w=6000, h=4000, doors=[(3, 1500, 900)])  # door on the west (short) wall
    sp = space_of(spec, lib)
    lay = layout_lineup(sp, lib, {UPS: 1, ATS: 1, MDB: 1}, R)
    line = [p for p in lay.placements if p.template_id in (UPS, ATS, MDB)]
    assert [p.template_id for p in sorted(line, key=lambda p: p.x)] in ([UPS, ATS, MDB], [MDB, ATS, UPS])
    face = sp.room.exterior  # backs 1 mm off a long wall face (room y 100..3900): touching, not inside the wall
    assert all(p.footprint().distance(face) < 2 for p in line)
    assert all(min(abs(p.y - 100), abs(p.y - 3900)) < p.dims[1] / 2 + 2 for p in line)
    for p in line:
        (zone,) = p.zones(lib[p.template_id], R)[:1]
        assert zone.area == pytest.approx(p.dims[0] * R.electrical_front_mm, rel=0.01)
        assert sp.room.buffer(1).covers(zone)


def test_battery_rows_with_aisles(lib):
    spec = hall(w=8000, h=6000, doors=[(3, 2000, 900)])
    lay = layout_lineup(space_of(spec, lib), lib, {UPS: 1, BAT: None}, R)
    assert len(of(lay, BAT)) >= 4 and not overlaps(lay)


def test_crac_on_end_walls(lib):
    spec = hall(doors=[(0, 4500, 900)])
    sp = space_of(spec, lib)
    lay = fill(sp, lib, {RACK: None, "crac-unit-generic": 2}, {"cooling": "crac", "containment": False, "rows": "auto"},
               "rows", R)
    cracs, racks = of(lay, "crac-unit-generic"), of(lay, RACK)
    assert len(cracs) == 2 and racks and not overlaps(lay)
    row_dir = (1, 0) if round(racks[0].rotation) % 180 == 0 else (0, 1)
    from shapely import affinity
    for c in cracs:
        f = c.front()
        assert abs(f[0] * row_dir[0] + f[1] * row_dir[1]) == pytest.approx(1)  # faces along the rows
        airflow = affinity.translate(c.footprint(), f[0] * R.row_end_clear_mm, f[1] * R.row_end_clear_mm)
        assert all(r.footprint().intersection(airflow).area < 1 for r in racks)  # rows end before its airflow zone


def test_containment_over_cold_aisles(lib):
    sp = space_of(hall(), lib)
    lay = fill(sp, lib, {RACK: None}, {"cooling": None, "containment": True, "rows": "ew"}, "rows", R)
    roofs, doors = of(lay, "containment-roof-600"), of(lay, "containment-door-1200")
    assert roofs and all(r.z == pytest.approx(2000) for r in roofs)
    assert len(doors) == 2 and all(d.z == 0 for d in doors)
    racks = of(lay, RACK)
    aisle_y = sorted({round(r.y) for r in racks})
    assert all(min(aisle_y) < r.y < max(aisle_y) for r in roofs)  # over the cold aisle between the pair
    assert not overlaps(lay)


def test_wall_devices(lib):
    spec = hall(doors=[(0, 4500, 900)])
    sp = space_of(spec, lib, ceiling=3200)
    items = {RACK: None, "fire-control-panel": 1, "access-reader-generic": 1, "cctv-camera-bullet": 1}
    lay = fill(sp, lib, items, {"cooling": None, "containment": False, "rows": "auto"}, "rows", R)
    (panel,), (reader,), (cam,) = of(lay, "fire-control-panel"), of(lay, "access-reader-generic"), of(lay, "cctv-camera-bullet")
    door = sp.doors[0].center
    assert math.dist((panel.x, panel.y), door) <= 450 + 300 + 600 and panel.z == 1400
    assert reader.z == 1100 and (panel.x - door[0]) * (reader.x - door[0]) < 0  # either side of the door
    assert cam.z == pytest.approx(3200 - 300 - 150)
    c = sp.room.centroid
    to_c = math.atan2(c.y - cam.y, c.x - cam.x)
    f = cam.front()
    assert abs((math.atan2(f[1], f[0]) - to_c + math.pi) % (2 * math.pi) - math.pi) <= math.radians(45) + 1e-6
    faces = sp.room.exterior
    for p in (panel, reader, cam):
        assert sp.room.buffer(1).covers(p.footprint()) and p.footprint().distance(faces) < 2


def test_fire_cylinders_by_area(lib):
    for (w, h), n in (((7200, 7200), 1), ((12200, 10200), 3)):  # inside 7 x 7 = 49 m2 -> 1; 12 x 10 = 120 m2 -> 3
        sp = space_of(hall(w=w, h=h, doors=[(0, 1000, 900)]), lib)
        lay = fill(sp, lib, {"fire-cylinder-generic": None}, {}, "lineup", R)
        cyl = of(lay, "fire-cylinder-generic")
        assert len(cyl) == n
        assert all(c.footprint().intersection(sp.doors[0].zone).area < 1 for c in cyl)
        assert all(c.footprint().distance(sp.room.exterior) < 2 for c in cyl)
