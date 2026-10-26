import pytest

from core.spec.models import Column
from core.spec.rooms import RoomLabel, form_rooms, rebuild_rooms
from tests.spec.fixtures import two_room_spec


def test_form_rooms_two_rooms():
    rooms, outlines = form_rooms(two_room_spec())
    assert len(rooms) == 2 and len(outlines) == 1
    assert [round(r.area / 1e6, 2) for r in rooms] == [round(4850 * 5800 / 1e6, 2)] * 2


def test_form_rooms_column_inside_becomes_hole():
    s = two_room_spec()
    s.columns.append(Column(id="C2", center=(2500, 3000), shape="rect", size=(400, 400)))
    rooms, _ = form_rooms(s)
    assert any(len(r.interiors) == 1 for r in rooms)


def test_form_rooms_empty_when_open():
    s = two_room_spec()
    s = s.model_copy(update={"walls": [w for w in s.walls if w.id != "W3"]})
    rooms, _ = form_rooms(s)
    assert rooms == []


def test_rebuild_assigns_labels_and_outline():
    s = rebuild_rooms(two_room_spec(), [RoomLabel(at=(2500, 3000), name="R. MEETING", type="meeting")])
    left = next(r for r in s.rooms if r.name == "R. MEETING")
    assert left.type == "meeting" and s.meta.gross_area_m2 == pytest.approx(10.2 * 6.2, abs=0.005)
    assert [r.id for r in s.rooms] == ["R1", "R2"] and s.meta.id_seq["R"] == 2


def test_reconcile_keeps_names_after_partition_removed():
    s = rebuild_rooms(two_room_spec(), [RoomLabel(at=(2500, 3000), name="A", type="office"),
                                         RoomLabel(at=(7500, 3000), name="B", type="storage")])
    s2 = rebuild_rooms(s.model_copy(update={"walls": [w for w in s.walls if w.id != "W5"]}))
    assert len(s2.rooms) == 1 and (s2.rooms[0].id, s2.rooms[0].name) == ("R1", "A")
