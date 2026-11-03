from core.installation.models import CableTray, Installation, InstallMeta
from core.installation.validate import validate_installation
from tests.spec.fixtures import spec_with_rooms


def check(trays, layout_head=None, **meta):
    inst = Installation(meta=InstallMeta(version=1, layout_version=1, **meta), cable_trays=trays)
    return validate_installation(inst, spec_with_rooms(), {}, layout_head=layout_head)


def codes(issues, code, severity=None):
    return [i for i in issues if i.code == code and (severity is None or i.severity == severity)]


def test_repeated_point_is_I001():
    assert codes(check([CableTray(id="T1", path=[(1000, 1000), (1000, 1000), (3000, 1000)], tray_class="data")]), "I001", "error")
    assert codes(check([CableTray(id="T1", path=[(1000, 1000)], tray_class="data")]), "I001", "error")
    assert codes(check([CableTray(id="T1", path=[(1000, 1000), (1050, 1000), (3000, 1000)], tray_class="data")]), "I001")


def test_underfloor_without_raised_floor_is_I002():
    issues = check([CableTray(id="T1", path=[(1000, 1000), (3000, 1000)], tray_class="data", mounting="underfloor")])
    assert codes(issues, "I002", "error") and "raised floor" in codes(issues, "I002")[0].message
    assert not codes(check([CableTray(id="T1", path=[(1000, 1000), (3000, 1000)], tray_class="data",
                                      mounting="underfloor")], raised_floor_height=600), "I002")


def test_overhead_above_ceiling_is_I002():
    assert codes(check([CableTray(id="T1", path=[(1000, 1000), (3000, 1000)], tray_class="data", elevation=2950)]), "I002")


def test_tray_crossing_a_wall_is_I003():
    issues = check([CableTray(id="T1", path=[(3000, 3000), (7000, 3000)], tray_class="data")])  # crosses W5 at x=5000
    assert [i.element_ids for i in codes(issues, "I003", "warning")] == [["T1", "W5"]]
    assert not codes(check([CableTray(id="T1", path=[(1000, 3000), (4000, 3000)], tray_class="data")]), "I003")


def test_power_data_too_close_is_I004():
    near = [CableTray(id="T1", path=[(1000, 3000), (4000, 3000)], tray_class="data"),
            CableTray(id="T2", path=[(1000, 3500), (4000, 3500)], tray_class="power")]  # 500 between axes: 200 between edges
    assert codes(check(near), "I004", "warning")
    far = [near[0], CableTray(id="T2", path=[(1000, 3700), (4000, 3700)], tray_class="power")]  # 400 between edges
    assert not codes(check(far), "I004")


def test_old_layout_version_is_I007():
    assert codes(check([], layout_head=4), "I007", "warning") and not codes(check([], layout_head=1), "I007")


def devices(*objs):
    from core.spec.models import PlacedObject

    os_ = [PlacedObject(id=f"O{i + 1}", template_id=t, template_version="1.1.0", position=p, rotation=0, dims=d)
           for i, (t, p, d) in enumerate(objs)]
    inst = Installation(meta=InstallMeta(version=1, layout_version=1), objects=os_)
    return validate_installation(inst, spec_with_rooms(), {})


RACK = ((600, 1200, 2000))


def test_device_in_a_wall_is_I009():
    # W5 runs along x = 5000
    assert codes(devices(("rack-42u-600x1200", (5000, 3000, 0), RACK)), "I009", "warning")


def test_overlapping_devices_are_I010():
    issues = devices(("rack-42u-600x1200", (2000, 3000, 0), RACK), ("rack-42u-600x1200", (2300, 3000, 0), RACK))
    assert codes(issues, "I010", "warning")


def test_a_roof_over_a_rack_is_no_overlap():
    issues = devices(("rack-42u-600x1200", (2000, 3000, 0), RACK),
                     ("containment-roof-600", (2000, 3000, 2000), (600, 1200, 60)))
    assert not codes(issues, "I010") and not codes(issues, "I009")


def test_a_clean_device_adds_nothing():
    assert not [i for i in devices(("rack-42u-600x1200", (2000, 3000, 0), RACK)) if i.code in ("I009", "I010")]
