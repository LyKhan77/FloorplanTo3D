"""M8: the located task list of the review step (gaps, leaks, loose walls, room types)."""

from core.spec.models import Wall
from core.spec.review_tasks import review_tasks
from core.spec.rooms import RoomLabel, rebuild_rooms
from tests.spec.fixtures import spec_with_rooms


def _kinds(tasks):
    return [t["kind"] for t in tasks]


def _split_partition(gap_mm=900):
    """W5 (the partition at x = 5000) broken at y 2000 .. 2000 + gap, its door gone: two dangling ends face each other."""
    s = spec_with_rooms()
    s.openings = [o for o in s.openings if o.id != "D1"]
    s.walls = [w for w in s.walls if w.id != "W5"] + [
        Wall(id="W5", a=(5000, 0), b=(5000, 2000), thickness=100, kind="interior"),
        Wall(id="W8", a=(5000, 2000 + gap_mm), b=(5000, 6000), thickness=100, kind="interior")]
    return rebuild_rooms(s.model_copy(update={"rooms": []}))


def test_gap_between_collinear_dangling_ends():
    gaps = [t for t in review_tasks(_split_partition()) if t["kind"] == "gap"]
    assert len(gaps) == 1
    fix = gaps[0]["fix"]
    assert (tuple(fix["a"]), tuple(fix["b"])) == ((5000, 2000), (5000, 2900))
    assert fix["thickness"] == 100 and fix["kind"] == "interior"
    assert fix["ends"] == [{"wall": "W5", "end": "b"}, {"wall": "W8", "end": "a"}]  # which wall end sits at a, at b
    assert gaps[0]["id"] == "gap:W5,W8" and gaps[0]["at"] == [5000, 2450]


def test_gap_wider_than_a_door_is_not_a_gap():
    assert "gap" not in _kinds(review_tasks(_split_partition(gap_mm=2000)))


def test_connected_end_is_not_a_gap():
    assert "gap" not in _kinds(review_tasks(spec_with_rooms()))


def test_leak_needs_two_label_types():
    s = spec_with_rooms()
    s.openings = [o for o in s.openings if o.id != "D1"]
    s.walls = [w for w in s.walls if w.id != "W5"]
    s = rebuild_rooms(s.model_copy(update={"rooms": []}))
    two = [RoomLabel((2500, 3000), "KIRI", "office"), RoomLabel((7500, 3000), "KANAN", "storage")]
    same = [RoomLabel((2500, 3000), "WC", "toilet"), RoomLabel((7500, 3000), "WC", "toilet")]
    assert _kinds(review_tasks(s, two)).count("leak") == 1
    assert "leak" not in _kinds(review_tasks(s, same))
    assert "leak" not in _kinds(review_tasks(s, None))


def test_loose_wall_both_ends_dangling():
    s = spec_with_rooms()
    s.walls += [Wall(id="W9", a=(1000, 2000), b=(2500, 2000), thickness=100, kind="partition"),
                Wall(id="W10", a=(1000, 4000), b=(4500, 4000), thickness=100, kind="partition")]  # 3.5 m: not loose
    loose = [t for t in review_tasks(s) if t["kind"] == "loose"]
    assert [t["element_ids"] for t in loose] == [["W9"]]


def test_other_room_is_a_type_task():
    s = spec_with_rooms()
    s.rooms[0].type = "other"
    types = [t for t in review_tasks(s) if t["kind"] == "type"]
    assert [t["element_ids"] for t in types] == [[s.rooms[0].id]]


def test_tasks_are_ordered_gap_leak_loose_type():
    s = _split_partition()
    s.walls += [Wall(id="W9", a=(1000, 2000), b=(2500, 2000), thickness=100, kind="partition")]
    s.rooms[0].type = "other"
    kinds = _kinds(review_tasks(s))
    assert kinds == sorted(kinds, key=["gap", "leak", "loose", "type"].index)


def test_gap_from_one_dangling_end_to_the_next_wall():
    """Gatsu: most door gaps have one dangling jamb; the other side is a wall the end runs into."""
    s = spec_with_rooms()
    s.walls = [w for w in s.walls if w.id != "W5"] + [Wall(id="W5", a=(5000, 0), b=(5000, 5100), thickness=100, kind="interior")]
    s = rebuild_rooms(s.model_copy(update={"rooms": []}))
    gaps = [t for t in review_tasks(s) if t["kind"] == "gap"]
    assert len(gaps) == 1
    fix = gaps[0]["fix"]
    assert (tuple(fix["a"]), tuple(fix["b"])) == ((5000, 5100), (5000, 6000))  # onto W3's centreline
    assert fix["ends"] == [{"wall": "W5", "end": "b"}]


def test_one_sided_gap_stays_on_the_wall_line_and_its_door_saves():
    """M8 final review C1: the far wall's end is offset sideways (the ray only grazes it); the fix must stay on W5's
    line, and extending W5 with a door there must validate (no V008)."""
    from core.spec.ops import apply
    from core.spec.validate import validate

    s = spec_with_rooms()
    s.walls = [w for w in s.walls if w.id != "W5"] + [
        Wall(id="W5", a=(5000, 0), b=(5000, 2000), thickness=100, kind="interior"),
        Wall(id="W8", a=(4930, 2900), b=(2000, 2900), thickness=100, kind="partition")]  # ends 70 mm beside W5's line
    s.openings = [o for o in s.openings if o.id != "D1"]
    s = rebuild_rooms(s.model_copy(update={"rooms": []}))
    gap = next(t for t in review_tasks(s) if t["kind"] == "gap" and t["fix"]["ends"][0]["wall"] == "W5")
    assert gap["fix"]["b"][0] == 5000  # on W5's own line, not W8's centreline projection
    length = gap["fix"]["b"][1]
    ops = [{"op": "move_wall", "id": "W5", "b": gap["fix"]["b"]},
           {"op": "add_opening", "wall_id": "W5", "category": "door", "offset": 2000, "width": length - 2000 - 50,
            "door_type": "single_swing", "hinge": "start", "swing": "left"}]
    out = apply(s, ops, "editor", s.meta.version + 1)
    assert [i.code for i in validate(out).issues if i.severity == "error"] == []
