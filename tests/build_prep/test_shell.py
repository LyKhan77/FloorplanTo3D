import pytest
from shapely.ops import unary_union

from core.build_prep.mesh import is_closed
from core.build_prep.shell import column_items, floor_items, stair_items, wall_items, wall_solids
from core.spec.derive import derive, wall_footprint
from core.spec.models import Flight, Stair, Wall
from tests.build_prep.meshutil import area_up
from tests.spec.fixtures import spec_with_rooms


def test_wall_solids_do_not_overlap_and_cover_footprints():
    s = spec_with_rooms()
    solids = wall_solids(s)
    union = unary_union([wall_footprint(w, s) for w in s.walls])
    assert sum(p.area for p in solids.values()) == pytest.approx(union.area, rel=1e-6)
    ids = list(solids)
    assert all(solids[a].intersection(solids[b]).area < 1 for a in ids for b in ids if a < b)


def test_wall_solid_split_into_pieces_stays_one_mesh():
    s = spec_with_rooms()
    # crosses W1 completely, so W6's footprint is cut in two by the earlier W1
    s.walls.append(Wall(id="W6", a=(2500, -500), b=(2500, 500), thickness=100, kind="interior", free_ends=True))
    items = {i["name"]: i for i in wall_items(s)}
    assert "wall_W6" in items and is_closed(items["wall_W6"])
    assert wall_solids(s)["W6"].geom_type == "MultiPolygon"


def test_wall_item_height_and_props():
    s = spec_with_rooms()
    s.walls[0].height = 4500
    w1 = next(i for i in wall_items(s) if i["name"] == "wall_W1")
    zs = [v[2] for v in w1["verts"]]
    assert (min(zs), max(zs)) == (0, 4500)
    assert w1["props"] == {"spec_id": "W1", "spec_type": "wall", "height_mm": 4500}
    assert w1["material"] == "wall_ext" and w1["collection"] == "Walls" and w1["location"] == [0, 0, 0]


def test_floor_mesh_area_matches_room_with_hole():
    s = spec_with_rooms()
    s.rooms[0].holes = [[(1000, 1000), (1000, 1400), (1400, 1400), (1400, 1000)]]
    s = derive(s)
    r1 = next(i for i in floor_items(s) if i["name"] == "room_R1")
    assert area_up(r1) == pytest.approx(s.rooms[0].area_m2 * 1e6, rel=1e-4)
    assert r1["props"]["area_m2"] == s.rooms[0].area_m2


def test_slab_per_outline():
    s = spec_with_rooms()
    s.meta.building_outline = [[(-100, -100), (10100, -100), (10100, 6100), (-100, 6100)]]
    slab = next(i for i in floor_items(s) if i["name"] == "slab_1")
    zs = [v[2] for v in slab["verts"]]
    assert (min(zs), max(zs)) == (-150, 0) and slab["props"]["spec_type"] == "slab"


def test_h_section_profile_area():
    s = spec_with_rooms()
    s.columns[0] = s.columns[0].model_copy(update={"shape": "h_section", "size": (400, 400)})
    c = column_items(s)[0]
    assert area_up(c) == pytest.approx(2 * 400 * 40 + 40 * (400 - 80))
    assert c["name"] == "column_C1" and c["material"] == "column"


def test_stair_steps_and_landing():
    s = spec_with_rooms()
    s.stairs = [Stair(id="S1", flights=[Flight(start=(1000, 1000), end=(1000, 3750), width=1000, risers=11)],
                      landings=[[(500, 3750), (1500, 3750), (1500, 4750), (500, 4750)]], top_z=1925)]
    empties, meshes = stair_items(s)
    f1 = next(m for m in meshes if m["name"] == "stair_S1_f1")
    l1 = next(m for m in meshes if m["name"] == "stair_S1_l1")
    assert len(f1["faces"]) == 11 * 6 and max(v[2] for v in f1["verts"]) == pytest.approx(1925)
    assert max(v[2] for v in l1["verts"]) == pytest.approx(1925)
    assert empties[0]["name"] == "stair_S1" and f1["parent"] == "stair_S1"
