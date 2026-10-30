import pytest

from core.installation.models import Installation, InstallMeta
from core.installation.ops import apply
from core.spec.ops import OpError

LINE = [(0, 0), (5000, 0)]


def base() -> Installation:
    return Installation(meta=InstallMeta(version=1, layout_version=3))


def test_add_tray_defaults_width_by_class():
    inst = apply(base(), [{"op": "add_tray", "path": LINE, "tray_class": "data"},
                          {"op": "add_tray", "path": LINE, "tray_class": "power"}], "editor", 2)
    assert [(t.id, t.width) for t in inst.cable_trays] == [("T1", 200), ("T2", 400)]
    assert inst.cable_trays[0].provenance.changed_in == 2


def test_move_and_delete_need_a_reason():
    inst = apply(base(), [{"op": "add_tray", "path": LINE, "tray_class": "data"}], "editor", 2)
    for op in ({"op": "move_tray_path", "id": "T1", "path": [(0, 0), (4000, 0)]}, {"op": "delete_tray", "id": "T1"}):
        with pytest.raises(OpError):
            apply(inst, [op], "editor", 3)
    moved = apply(inst, [{"op": "move_tray_path", "id": "T1", "path": [(0, 0), (4000, 0)], "reason": "geser ke pita"}], "editor", 3)
    assert moved.cable_trays[0].path == [(0, 0), (4000, 0)] and moved.provenance_log[-1].reason == "geser ke pita"
    assert apply(moved, [{"op": "delete_tray", "id": "T1", "reason": "duplikat"}], "editor", 4).cable_trays == []


def test_deleted_ids_are_not_reused():
    inst = apply(base(), [{"op": "add_tray", "path": LINE, "tray_class": "data"},
                          {"op": "delete_tray", "id": "T1", "reason": "x"},
                          {"op": "add_tray", "path": LINE, "tray_class": "data"}], "editor", 2)
    assert [t.id for t in inst.cable_trays] == ["T2"]


def test_update_object_position_needs_a_reason_label_does_not():
    add = {"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.0.0",
           "position": (1000, 1000, 0), "dims": (600, 1200, 2000)}
    inst = apply(base(), [add], "editor", 2)
    assert inst.objects[0].id == "RK1"  # never O<n>: layout objects use that prefix (review I2)
    assert apply(inst, [{"op": "update_object", "id": "RK1", "label": "R01"}], "editor", 3).objects[0].label == "R01"
    with pytest.raises(OpError):
        apply(inst, [{"op": "update_object", "id": "RK1", "position": (1500, 1000, 0)}], "editor", 3)
    with pytest.raises(OpError):
        apply(inst, [{"op": "delete_object", "id": "RK1"}], "editor", 3)


def test_width_outside_standard_sizes_is_rejected():
    with pytest.raises(OpError):
        apply(base(), [{"op": "add_tray", "path": LINE, "tray_class": "data", "width": 250}], "editor", 2)
    inst = apply(base(), [{"op": "add_tray", "path": LINE, "tray_class": "data"}], "editor", 2)
    with pytest.raises(OpError):
        apply(inst, [{"op": "set_tray", "id": "T1", "side_height": 120}], "editor", 3)


def test_meta_and_tray_settings():
    inst = apply(base(), [{"op": "add_tray", "path": LINE, "tray_class": "data"},
                          {"op": "set_tray", "id": "T1", "mounting": "underfloor", "elevation": -500},
                          {"op": "set_installation_meta", "raised_floor_height": 600, "ceiling_height": 3200}], "editor", 2)
    t = inst.cable_trays[0]
    assert (t.mounting, t.elevation, inst.meta.raised_floor_height, inst.meta.ceiling_height) == ("underfloor", -500, 600, 3200)
    cleared = apply(inst, [{"op": "set_tray", "id": "T1", "elevation": None}], "editor", 3)
    assert cleared.cable_trays[0].elevation is None
