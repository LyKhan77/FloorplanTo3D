"""Regression tests for the M1 final-review findings."""

import pytest
from pydantic import ValidationError
from shapely.geometry import Polygon as SPolygon

from core.spec.models import Column, Room, Stair, Wall
from core.spec.ops import OpError, apply
from core.spec.rooms import form_rooms, rebuild_rooms
from core.spec.store import SpecStore
from core.spec.validate import validate
from tests.spec.fixtures import spec_with_rooms, two_room_spec


def test_deleted_ids_are_never_reused_without_seeded_id_seq():
    s = spec_with_rooms()
    s.meta.id_seq = {}
    s = apply(s, [{"op": "delete_opening", "id": "D2", "reason": "x"}], "editor", 2)
    s = apply(s, [{"op": "add_opening", "wall_id": "W1", "category": "door", "offset": 3000, "width": 900}], "editor", 3)
    assert [o.id for o in s.openings] == ["D1", "D3"]


def test_deleted_highest_wall_id_not_reused():
    s = spec_with_rooms()
    s.meta.id_seq = {}
    s = apply(s, [{"op": "delete_wall", "id": "W5", "reason": "x"}], "editor", 2)
    s = apply(s, [{"op": "add_wall", "a": (5000, 0), "b": (5000, 6000), "thickness": 100, "kind": "interior"}], "editor", 3)
    assert s.walls[-1].id == "W6"


def test_t_junction_does_not_notch_far_room_or_count_as_bounding():
    s = two_room_spec()
    s.walls.append(Wall(id="W6", a=(5000, 3000), b=(10000, 3000), thickness=200, kind="interior"))
    s = rebuild_rooms(s)
    left = next(r for r in s.rooms if SPolygon(r.polygon).centroid.x < 5000)
    assert len(left.polygon) == 4 and "W6" not in left.bounding_walls


def test_null_on_required_field_reports_its_index():
    ops = [{"op": "move_wall", "id": "W5", "thickness": None},
           {"op": "rename_room", "id": "R1", "name": "A"}]
    with pytest.raises(OpError) as e:
        apply(spec_with_rooms(), ops, "editor", 2)
    assert (e.value.index, e.value.op) == (0, "move_wall")


def test_nullable_fields_still_accept_null():
    s = apply(spec_with_rooms(), [{"op": "set_wall_height", "id": "W1", "height": None},
                                  {"op": "set_door", "id": "D1", "height": None}], "editor", 2)
    assert s.walls[0].height is None


def test_validator_reports_bad_grid_ref_instead_of_crashing():
    s = spec_with_rooms()
    s.columns.append(Column(id="C9", center=(0, 0), shape="rect", size=(200, 200), grid_ref=("GA", "GB")))
    r = validate(s)
    assert any(i.code == "V014" and "C9" in i.element_ids for i in r.issues)


def test_room_needs_three_points():
    with pytest.raises(ValidationError):
        Room(id="R9", polygon=[(0, 0), (1, 1)])


def test_provenance_log_holds_only_this_versions_ops(tmp_path):
    st = SpecStore(tmp_path)
    st.save_new(spec_with_rooms(), "manual")
    st.commit_ops(1, [{"op": "rename_room", "id": "R1", "name": "A"}], "editor")
    v3, _ = st.commit_ops(2, [{"op": "rename_room", "id": "R2", "name": "B"}], "editor")
    assert [(e.op, e.id) for e in v3.provenance_log] == [("rename_room", "R2")]


def test_merge_flips_hinge_and_swing_of_reversed_wall():
    s = two_room_spec()
    s.walls[0] = s.walls[0].model_copy(update={"b": (5000, 0)})
    s.walls.append(Wall(id="W6", a=(10000, 0), b=(5000, 0), thickness=200, kind="exterior"))
    s.openings = [o for o in s.openings if o.id != "D2"]
    s.openings.append(s.openings[0].model_copy(update={"id": "D3", "wall_id": "W6", "offset": 1000, "width": 900,
                                                      "hinge": "start", "swing": "left"}))
    s = apply(rebuild_rooms(s), [{"op": "merge_walls", "ids": ["W1", "W6"], "reason": "x"}], "manual", 2)
    d3 = next(o for o in s.openings if o.id == "D3")
    assert (d3.wall_id, d3.offset, d3.hinge, d3.swing) == ("W1", 8100, "end", "right")


def test_stair_landings_normalized_ccw():
    from core.spec.models import Flight, signed_area
    st = Stair(id="S1", flights=[Flight(start=(0, 0), end=(0, 3000), width=1000, risers=12)],
               landings=[[(0, 0), (0, 1000), (1000, 1000), (1000, 0)]])
    assert signed_area(st.landings[0]) > 0


def test_low_walls_do_not_split_rooms():
    s = two_room_spec()
    s.walls.append(Wall(id="W6", a=(100, 3000), b=(4950, 3000), thickness=100, kind="low", height=1000))
    rooms, _ = form_rooms(s)
    assert len(rooms) == 2


def test_wall_end_reaching_a_column_closes_the_gap():
    s = two_room_spec()
    s.walls = [w for w in s.walls if w.id != "W5"]
    s.columns += [Column(id="C2", center=(5000, 200), shape="rect", size=(400, 400)),
                  Column(id="C3", center=(5000, 5800), shape="rect", size=(400, 400))]
    s.walls.append(Wall(id="W5", a=(5000, 410), b=(5000, 5590), thickness=100, kind="interior"))  # 10 mm short
    rooms, _ = form_rooms(s)
    assert len(rooms) == 2
