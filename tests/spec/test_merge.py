from pathlib import Path

import pytest
from shapely.geometry import Point, Polygon

from core.spec.merge import MergeError, merge_plan, unmerge_plan
from core.spec.models import Opening, Spec, Wall
from core.spec.ops import OpError, apply
from core.spec.rooms import rebuild_rooms
from tests.spec.fixtures import spec_with_rooms, two_room_spec


def _three_rooms(split_bottom=False, door=None):
    """A long wall at y=3000: rooms A and C above it (split at x=6000), room B under its whole length."""
    s = two_room_spec()
    s.openings = [door] if door else []
    wall = lambda i, a, b, k="interior", t=100: Wall(id=i, a=a, b=b, thickness=t, kind=k)
    s.walls = [wall("W1", (0, 0), (12000, 0), "exterior", 200), wall("W2", (12000, 0), (12000, 6000), "exterior", 200),
               wall("W3", (12000, 6000), (0, 6000), "exterior", 200), wall("W4", (0, 6000), (0, 0), "exterior", 200),
               wall("W5", (0, 3000), (12000, 3000)), wall("W6", (6000, 3000), (6000, 6000))]
    if split_bottom:
        s.walls.append(wall("W7", (6000, 0), (6000, 3000)))
    return rebuild_rooms(s)


def _at(s, x, y):
    return next(r for r in s.rooms if Polygon(r.polygon, r.holes).covers(Point(x, y)))


def _run(s, ops):
    return apply(s, ops, "editor", s.meta.version + 1)


def test_two_rooms_sharing_a_whole_wall_merge():
    s = spec_with_rooms()
    ops = merge_plan(s, ["R1", "R2"])
    assert [o for o in ops if o["op"] == "set_wall_divides"] == [{"op": "set_wall_divides", "id": "W5", "divides": False}]
    assert not [o for o in ops if o["op"] == "split_wall"]
    after = _run(s, ops)
    assert len(after.rooms) == 1 and any(w.id == "W5" for w in after.walls)


def test_a_long_wall_opens_only_the_shared_part():
    s = _three_rooms()
    a, b, c = _at(s, 3000, 4500), _at(s, 6000, 1500), _at(s, 9000, 4500)
    after = _run(s, merge_plan(s, [a.id, b.id]))
    assert len(after.rooms) == 2 and len(after.walls) == len(s.walls) + 1
    kept = next(r for r in after.rooms if r.id == c.id)
    assert kept.area_m2 == pytest.approx(c.area_m2, rel=0.01)
    assert _at(after, 3000, 4500).id == _at(after, 6000, 1500).id != kept.id


def test_rooms_without_a_shared_wall_are_refused():
    s = _three_rooms(split_bottom=True)
    with pytest.raises(MergeError, match="tidak berbagi dinding"):
        merge_plan(s, [_at(s, 3000, 4500).id, _at(s, 9000, 1500).id])


def test_a_cut_through_a_door_is_refused():
    door = Opening(id="D1", category="door", wall_id="W5", offset=5500, width=900, door_type="single_swing",
                   hinge="start", swing="left")
    s = _three_rooms(door=door)
    with pytest.raises(MergeError, match="bukaan"):
        merge_plan(s, [_at(s, 3000, 4500).id, _at(s, 6000, 1500).id])


def test_the_first_filled_name_and_its_type_win():
    s = spec_with_rooms()
    s.rooms[0].name = ""
    after = _run(s, merge_plan(s, ["R1", "R2"]))
    assert (after.rooms[0].name, after.rooms[0].type) == ("KANAN", "storage")


def test_fewer_than_two_rooms_or_an_unknown_id_is_refused():
    s = spec_with_rooms()
    for ids in (["R1"], ["R1", "R9"]):
        with pytest.raises(MergeError, match="minimal dua"):
            merge_plan(s, ids)


def test_unmerge_restores_the_rooms():
    s = spec_with_rooms()
    merged = _run(s, merge_plan(s, ["R1", "R2"]))
    assert len(_run(merged, unmerge_plan(merged, merged.rooms[0].id)).rooms) == 2


def test_unmerge_of_a_plain_room_is_refused():
    with pytest.raises(MergeError, match="bukan hasil gabungan"):
        unmerge_plan(spec_with_rooms(), "R1")


def test_merging_a_wall_piece_that_divides_with_one_that_does_not_is_refused():
    s = _three_rooms()
    after = _run(s, merge_plan(s, [_at(s, 3000, 4500).id, _at(s, 6000, 1500).id]))
    pieces = [w.id for w in after.walls if w.a[1] == w.b[1] == 3000]
    with pytest.raises(OpError, match="divides rooms"):
        _run(after, [{"op": "merge_walls", "ids": pieces, "reason": "gabung dinding kolinear"}])


def test_a_plan_names_only_walls_that_exist():
    """The editor refuses an op on an id it would have to predict, so a cut and its mark are one op."""
    s = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    ops = merge_plan(s, ["R4", "R12"])
    known = {w.id for w in s.walls}
    assert all(o["id"] in known for o in ops if "id" in o)
    assert len(_run(s, ops).walls) == len(s.walls) + 2
