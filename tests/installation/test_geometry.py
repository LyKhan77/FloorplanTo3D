import numpy as np
from shapely.geometry import LineString, Point

from core.installation.geometry import floor_drop, installation_items
from core.installation.models import CableTray, Installation, InstallMeta
from core.spec.models import PlacedObject
from tests.spec.fixtures import spec_with_rooms

TEMPLATES = {"rack-42u-600x1200": "rack"}


def inst(trays, objects=(), **meta):
    return Installation(meta=InstallMeta(version=1, layout_version=1, **meta), cable_trays=trays, objects=list(objects))


def by_name(items, prefix):
    return [m for m in items if m["name"].startswith(prefix)]


def bbox(item):
    v = np.array(item["verts"], float)
    return v.min(axis=0), v.max(axis=0)


def rack(oid, x, y):
    return PlacedObject(id=oid, template_id="rack-42u-600x1200", template_version="1.0.0", position=(x, y, 0), dims=(600, 1200, 2000))


def test_tray_u_section_dimensions():
    meshes, _ = installation_items(inst([CableTray(id="T1", path=[(1000, 3000), (4000, 3000)], tray_class="data")]), spec_with_rooms(), TEMPLATES)
    tray = [m for m in meshes if m["name"] == "tray_data_T1"]
    assert len(tray) == 1 and tray[0]["material"] == "tray_galv" and tray[0]["collection"] == "TrayData" and tray[0]["uv_box_mm"] == 25
    lo, hi = bbox(tray[0])
    assert np.allclose(lo, [1000, 2900, 2600], atol=0.5) and np.allclose(hi[:2], [4000, 3100], atol=0.5) and 2700 <= hi[2] <= 2702
    lip = by_name(meshes, "tray_data_T1_lip")
    assert lip and lip[0]["material"] == "tray_edge_data"


def test_corner_is_mitred():
    path = [(1000, 1000), (4000, 1000), (4000, 4000)]
    meshes, _ = installation_items(inst([CableTray(id="T1", path=path, tray_class="data")]), spec_with_rooms(), TEMPLATES)
    line = LineString(path)
    far = max(line.distance(Point(v[0], v[1])) for m in by_name(meshes, "tray_data_T1") for v in m["verts"])
    assert far <= 100 * 2 ** 0.5 + 2  # a mitre corner sits w/2 * sqrt(2) from the bend; a spike would be farther


def test_hangers_every_1500_and_at_corners():
    layout = spec_with_rooms()
    meshes, _ = installation_items(inst([CableTray(id="T1", path=[(500, 3000), (4500, 3000)], tray_class="data")]), layout, TEMPLATES)
    hangers = by_name(meshes, "hanger_T1_")
    xs = sorted(round((bbox(h)[0][0] + bbox(h)[1][0]) / 2) for h in hangers)
    assert xs == [500, 2000, 3500, 4500]
    assert all(abs(bbox(h)[1][2] - 3000) <= 1 for h in hangers)  # rods reach the ceiling (wall height)
    meshes, _ = installation_items(inst([CableTray(id="T1", path=[(500, 1000), (4000, 1000), (4000, 4500)], tray_class="data")]), layout, TEMPLATES)
    corner = [h for h in by_name(meshes, "hanger_T1_") if abs((bbox(h)[0][0] + bbox(h)[1][0]) / 2 - 4000) < 120
              and abs((bbox(h)[0][1] + bbox(h)[1][1]) / 2 - 1000) < 120]
    assert corner


def test_drops_follow_derive():
    layout = spec_with_rooms()
    layout.objects = [rack("O9", 7000, 2700)]
    tray = CableTray(id="T1", path=[(500, 3000), (9000, 3000)], tray_class="data")
    meshes, _ = installation_items(inst([tray], [rack("RK1", 2000, 2700)]), layout, TEMPLATES)
    drops = by_name(meshes, "drop_")
    assert {d["name"] for d in drops} == {"drop_RK1_T1", "drop_O9_T1"}
    lo, hi = bbox(drops[0])
    assert abs(lo[2] - 2000) <= 1 and abs(hi[2] - 2700) <= 2  # from the rack top up to the horizontal piece at tray level


def test_sleeve_cutter_on_crossed_wall():
    _, cutters = installation_items(inst([CableTray(id="T1", path=[(3000, 3000), (7000, 3000)], tray_class="data")]), spec_with_rooms(), TEMPLATES)
    assert [c["target"] for c in cutters] == ["wall_W5"]
    z = [v[2] for v in cutters[0]["verts"]]
    assert (min(z), max(z)) == (2550, 2750)


def test_raised_floor_only_when_set():
    layout = spec_with_rooms()
    tray = CableTray(id="T1", path=[(1000, 3000), (4000, 3000)], tray_class="data")
    meshes, _ = installation_items(inst([tray]), layout, TEMPLATES)
    assert not by_name(meshes, "raised_floor") and floor_drop(layout, inst([tray])) == 0
    raised = inst([tray], raised_floor_height=600)
    meshes, _ = installation_items(raised, layout, TEMPLATES)
    lo, hi = bbox(by_name(meshes, "raised_floor_panels")[0])
    assert (lo[2], hi[2]) == (-30, 0) and floor_drop(layout, raised) == -600
    assert by_name(meshes, "ceiling")
