import pytest

from core.spec.models import Flight, Stair
from core.spec.ops import OpError, apply
from tests.spec.fixtures import spec_with_rooms


def test_add_wall_gets_new_id_and_provenance():
    s = apply(spec_with_rooms(), [{"op": "add_wall", "a": (2500, 100), "b": (2500, 5900),
                                   "thickness": 100, "kind": "partition"}], "editor", 2)
    w = s.walls[-1]
    assert w.id == "W6" and w.provenance.source == "editor" and w.provenance.changed_in == 2
    assert len(s.rooms) == 3


def test_apply_is_atomic_on_bad_op():
    base = spec_with_rooms()
    before = base.model_dump()
    with pytest.raises(OpError) as e:
        apply(base, [{"op": "rename_room", "id": "R1", "name": "X"},
                     {"op": "delete_wall", "id": "W99", "reason": "x"}], "editor", 2)
    assert e.value.index == 1 and base.model_dump() == before


def test_bad_schema_reports_index():
    with pytest.raises(OpError) as e:
        apply(spec_with_rooms(), [{"op": "rename_room", "id": "R1", "name": "X"}, {"op": "nope"}], "editor", 2)
    assert e.value.index == 1


def test_delete_wall_cascades_openings():
    s = apply(spec_with_rooms(), [{"op": "delete_wall", "id": "W5", "reason": "bukan dinding"}], "editor", 2)
    assert all(o.wall_id != "W5" for o in s.openings) and "D1" not in [o.id for o in s.openings]
    assert any(e.op == "delete_opening" and e.id == "D1" for e in s.provenance_log)


def test_split_wall_moves_openings():
    s = apply(spec_with_rooms(), [{"op": "split_wall", "id": "W1", "at_offset": 5000}], "manual", 2)
    w_new = s.walls[-1]
    assert w_new.a == (5000, 0) and next(o for o in s.openings if o.id == "D2").wall_id == "W1"


def test_split_through_opening_rejected():
    with pytest.raises(OpError):
        apply(spec_with_rooms(), [{"op": "split_wall", "id": "W1", "at_offset": 1500}], "manual", 2)


def test_merge_walls_keeps_lowest_id_and_reparents():
    s = apply(spec_with_rooms(), [{"op": "split_wall", "id": "W1", "at_offset": 5000},
                                  {"op": "merge_walls", "ids": ["W6", "W1"], "reason": "rejoin"}], "manual", 2)
    w1 = next(w for w in s.walls if w.id == "W1")
    assert (w1.a, w1.b) == ((0, 0), (10000, 0)) and "W6" not in [w.id for w in s.walls]
    assert next(o for o in s.openings if o.id == "D2").offset == 1000


def test_set_wall_height_star_null_resets_all():
    s = apply(spec_with_rooms(), [{"op": "set_wall_height", "id": "W1", "height": 4500},
                                  {"op": "set_wall_height", "id": "*", "height": None}], "editor", 2)
    assert all(w.height is None for w in s.walls)


def test_set_default_unknown_key_rejected():
    with pytest.raises(OpError):
        apply(spec_with_rooms(), [{"op": "set_default", "key": "colour", "value": 1}], "editor", 2)


def test_set_door_offset_and_width():
    s = apply(spec_with_rooms(), [{"op": "set_door", "id": "D1", "offset": 2500, "width": 1000}], "editor", 2)
    d = next(o for o in s.openings if o.id == "D1")
    assert (d.offset, d.width) == (2500, 1000)


def test_add_object_room_id_derived():
    s = apply(spec_with_rooms(), [{"op": "add_object", "template_id": "rack-42u-600x1200",
                                   "template_version": "1.0.0", "position": (2000, 2000, 0),
                                   "rotation": 0, "dims": (600, 1200, 2000)}], "editor", 2)
    assert s.objects[0].id == "O1" and s.objects[0].room_id == "R1"


def test_rename_and_retype_room():
    s = apply(spec_with_rooms(), [{"op": "rename_room", "id": "R2", "name": "GUDANG"},
                                  {"op": "set_room_type", "id": "R2", "type": "storage"}], "editor", 2)
    r2 = next(r for r in s.rooms if r.id == "R2")
    assert (r2.name, r2.type, r2.provenance.source) == ("GUDANG", "storage", "editor")


def test_stair_flip_via_set_stair():
    base = spec_with_rooms().model_copy(update={"stairs": [
        Stair(id="S1", flights=[Flight(start=(1000, 1000), end=(1000, 4000), width=1000, risers=12)])]})
    s = apply(base, [{"op": "set_stair", "id": "S1", "flights": [
        {"start": (1000, 4000), "end": (1000, 1000), "width": 1000, "risers": 12}]}], "editor", 2)
    assert s.stairs[0].flights[0].start == (1000, 4000)
