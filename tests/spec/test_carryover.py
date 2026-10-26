import random

from core.spec.carryover import assign_ids, carry_over
from core.spec.models import PlacedObject, Provenance
from core.spec.rooms import RoomLabel
from tests.spec.fixtures import spec_with_rooms


def head_spec():
    s = spec_with_rooms()
    s.meta.id_seq = {"W": 5, "D": 2, "C": 1, "R": 2}
    return s


def moved(spec, wall_id, dx=0, dy=0):
    s = spec.model_copy(deep=True)
    w = next(w for w in s.walls if w.id == wall_id)
    w.a, w.b = (w.a[0] + dx, w.a[1] + dy), (w.b[0] + dx, w.b[1] + dy)
    return s


def test_assign_ids_order_is_positional():
    s = head_spec()
    shuffled = s.model_copy(deep=True)
    random.Random(1).shuffle(shuffled.walls)
    a, b = assign_ids(s), assign_ids(shuffled)
    geo = lambda spec: sorted((w.id, w.a, w.b) for w in spec.walls)
    assert geo(a) == geo(b)
    first = next(w for w in a.walls if w.id == "W1")
    assert first.a == (0, 0) and first.b == (10000, 0)  # lowest a, then leftmost
    assert next(w for w in a.walls if w.id == "W2").a == (5000, 0)
    assert {o.wall_id for o in a.openings} == {"W1", "W2"}  # references follow the renumbering


def test_matching_walls_keep_head_ids():
    head = head_spec()
    near = moved(head, "W5", dx=150)
    out, rep = carry_over(assign_ids(near), head, [])
    assert any(w.id == "W5" and w.a == (5150, 0) for w in out.walls)
    far = moved(head, "W5", dx=250)
    out, rep = carry_over(assign_ids(far), head, [])
    assert any(w.id == "W6" and w.a == (5250, 0) for w in out.walls) and not any(w.id == "W5" for w in out.walls)
    assert rep["removed"]["walls"] == ["W5"] and rep["new"]["walls"] == 1


def test_small_angle_still_matches():
    head = head_spec()
    s = head.model_copy(deep=True)
    w = next(w for w in s.walls if w.id == "W5")
    w.b = (5000 + 200, 6000)  # ~1.9°
    w.allow_skew = True
    out, _ = carry_over(assign_ids(s), head, [])
    assert any(w.id == "W5" and w.b == (5200, 6000) for w in out.walls)


def test_editor_edits_survive_reextraction():
    head = head_spec()
    head.walls[1].height = 4500  # W2
    head.rooms[0].name, head.rooms[0].type = "SERVER A", "data_hall"
    head.rooms[0].provenance = Provenance(source="editor")
    head.rooms[1].provenance = Provenance(source="cv")
    new = assign_ids(head.model_copy(update={"rooms": []}))
    for w in new.walls:
        w.height = None
    labels = [RoomLabel((2500, 3000), "DATA HALL", "data_hall"), RoomLabel((7500, 3000), "GUDANG", "storage")]
    out, _ = carry_over(new, head, labels)
    assert next(w for w in out.walls if w.id == "W2").height == 4500
    r1, r2 = (next(r for r in out.rooms if r.id == i) for i in ("R1", "R2"))
    assert (r1.name, r1.type) == ("SERVER A", "data_hall")
    assert (r2.name, r2.type) == ("GUDANG", "storage")


def test_doors_and_columns_match_by_centre():
    head = head_spec()
    s = head.model_copy(deep=True)
    s.openings[0].offset += 250
    s.columns[0].center = (350, 0)
    out, _ = carry_over(assign_ids(s), head, [])
    assert {o.id for o in out.openings} == {"D1", "D2"}
    assert [c.id for c in out.columns] == ["C2"]


def test_objects_copied_and_room_recomputed():
    head = head_spec()
    head.objects = [PlacedObject(id="O1", template_id="rack", template_version="1.0", position=(2000, 3000, 0),
                                 dims=(600, 1200, 2000))]
    out, _ = carry_over(assign_ids(head.model_copy(update={"objects": []})), head, [])
    assert [(o.id, o.room_id) for o in out.objects] == [("O1", "R1")]
    assert out.meta.defaults == head.meta.defaults


def test_lost_edit_reported():
    head = head_spec()
    head.walls[1].height = 4500  # W2 (east wall)
    new = head.model_copy(deep=True)
    new.walls = [w for w in new.walls if w.id != "W2"]
    _, rep = carry_over(assign_ids(new), head, [])
    assert {"id": "W2", "field": "height", "value": 4500} in rep["lost_edits"]


def test_ids_never_reused():
    head = head_spec()
    head.meta.id_seq["W"] = 9  # W6-W9 were deleted
    out, _ = carry_over(assign_ids(moved(head, "W5", dx=400)), head, [])
    assert any(w.id == "W10" for w in out.walls)
