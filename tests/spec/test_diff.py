from core.spec.diff import diff_specs
from core.spec.ops import apply
from tests.spec.fixtures import spec_with_rooms


def test_diff_reports_added_removed_changed():
    a = spec_with_rooms()
    b = apply(a, [{"op": "add_wall", "a": (2500, 100), "b": (2500, 5900), "thickness": 100, "kind": "partition"},
                  {"op": "set_wall_height", "id": "W1", "height": 4500},
                  {"op": "delete_opening", "id": "D2", "reason": "x"}], "editor", 2)
    d = diff_specs(a, b)
    assert d["walls"] == {"added": ["W6"], "removed": [], "changed": ["W1"]}
    assert d["openings"]["removed"] == ["D2"] and "R3" in d["rooms"]["added"]
    assert [e.op for e in d["ops"]][:2] == ["add_wall", "set_wall_height"]


def test_diff_ignores_derived_fields():
    a = spec_with_rooms()
    b = a.model_copy(deep=True)
    b.rooms[0].area_m2 = 999
    assert diff_specs(a, b)["rooms"] == {"added": [], "removed": [], "changed": []}
