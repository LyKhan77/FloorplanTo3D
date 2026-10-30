from core.installation.derive import drops, lengths, tray_elevation
from core.installation.models import CableTray, Installation, InstallMeta
from core.installation.validate import validate_installation
from core.spec.models import PlacedObject
from tests.spec.fixtures import spec_with_rooms

TEMPLATES = {"rack-42u-600x1200": "rack"}


def rack(oid: str, x: int, y: int) -> PlacedObject:
    return PlacedObject(id=oid, template_id="rack-42u-600x1200", template_version="1.0.0", position=(x, y, 0),
                        dims=(600, 1200, 2000))


def inst(trays: list[CableTray], objects=(), **meta) -> Installation:
    return Installation(meta=InstallMeta(version=1, layout_version=1, **meta), cable_trays=trays, objects=list(objects))


def tray(tid: str, path, cls="data", **kw) -> CableTray:
    return CableTray(id=tid, path=path, tray_class=cls, **kw)


def codes(issues, code):
    return [i for i in issues if i.code == code]


def test_default_elevations():
    layout = spec_with_rooms()  # wall_height 3000
    t = tray("T1", [(1000, 1000), (4000, 1000)])
    assert tray_elevation(t, inst([t]).meta, layout) == 2600
    under = tray("T2", [(1000, 1000), (4000, 1000)], mounting="underfloor")
    assert tray_elevation(under, inst([under], raised_floor_height=600).meta, layout) == -500
    assert tray_elevation(t, inst([t], ceiling_height=3500).meta, layout) == 3100


def test_drop_to_nearest_rack_per_class():
    layout = spec_with_rooms()
    data = tray("T1", [(1000, 3000), (4500, 3000)])
    power = tray("T2", [(1000, 1800), (4500, 1800)], "power")
    r = rack("O1", 2000, 2000)  # 1000 mm from the data tray, 200 mm from the power tray
    far = rack("O2", 2000, 4700)  # 1700 mm from the data tray: out of range
    got = {(d["rack_id"], d["tray_id"]) for d in drops(inst([data, power], [r, far]), layout, TEMPLATES)}
    assert got == {("O1", "T1"), ("O1", "T2")}
    nearer = tray("T3", [(1000, 2500), (4500, 2500)])
    got = {(d["rack_id"], d["tray_id"]) for d in drops(inst([data, power, nearer], [r]), layout, TEMPLATES)}
    assert got == {("O1", "T3"), ("O1", "T2")}  # one data drop, from the nearest data tray
    issues = validate_installation(inst([data, power], [r, far]), layout, TEMPLATES)
    assert {i.element_ids[0] for i in codes(issues, "I006")} == {"O2"}


def test_lengths_sum_horizontal_and_drops():
    layout = spec_with_rooms()
    t = tray("T1", [(0, 3000), (5000, 3000)])
    got = lengths(inst([t], [rack("O1", 2000, 2700)]), layout, TEMPLATES)
    assert got["data"] == {"horizontal": 5000, "drops": 300 + 600, "total": 5900}
    assert got["power"] == {"horizontal": 0, "drops": 0, "total": 0}


def test_layout_objects_count_as_racks():
    layout = spec_with_rooms()
    layout.objects = [rack("O9", 2000, 2700)]
    assert [d["rack_id"] for d in drops(inst([tray("T1", [(0, 3000), (5000, 3000)])]), layout, TEMPLATES)] == ["O9"]
