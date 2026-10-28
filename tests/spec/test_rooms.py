import pytest

from core.spec.models import Column, Wall
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


def test_island_inside_room_is_not_a_building_outline():
    s = two_room_spec()
    s.columns.append(Column(id="C2", center=(2500, 3000), shape="rect", size=(400, 400)))
    ring = [((6000, 2000), (8000, 2000)), ((8000, 2000), (8000, 4000)), ((8000, 4000), (6000, 4000)),
            ((6000, 4000), (6000, 2000))]  # 2 m x 2 m shaft, interior > 1 m²
    s.walls += [Wall(id=f"W{9 + i}", a=a, b=b, thickness=100, kind="interior") for i, (a, b) in enumerate(ring)]
    rooms, outlines = form_rooms(s)
    assert len(outlines) == 1
    assert len(rooms) == 3  # left (with column hole), right (with ring hole), inside the ring


# --- rooms split at sub-passage necks (M7a Task 5) ------------------------------------------------------------------

def test_split_necks_cuts_a_sliver_join():
    from shapely.geometry import Polygon, box

    from core.spec.rooms import _split_necks

    dumbbell = box(0, 0, 3000, 2000).union(box(3000, 1000, 3500, 1100)).union(box(3500, 0, 6500, 2000))
    parts = _split_necks(Polygon(dumbbell.exterior))
    assert len(parts) == 2 and all(p.area > 5_900_000 for p in parts)
    corridor = box(0, 0, 3000, 2000).union(box(3000, 500, 4000, 1500)).union(box(4000, 0, 7000, 2000))
    assert len(_split_necks(Polygon(corridor.exterior))) == 1  # a 1 m corridor is a passage


def test_band_between_fins_forms_one_room_per_bay():
    from core.spec.models import Column, Wall
    from core.spec.rooms import form_rooms
    from tests.spec.fixtures import two_room_spec

    s = two_room_spec().model_copy(update={"openings": [], "rooms": [], "walls": [
        Wall(id="W1", a=(0, 0), b=(6000, 0), thickness=200, kind="exterior"),
        Wall(id="W2", a=(6000, 0), b=(6000, 1500), thickness=200, kind="exterior"),
        Wall(id="W3", a=(6000, 1500), b=(0, 1500), thickness=200, kind="exterior"),
        Wall(id="W4", a=(0, 1500), b=(0, 0), thickness=200, kind="exterior")],
        "columns": [Column(id="C1", center=(2000, 750), shape="rect", size=(400, 1200)),
                    Column(id="C2", center=(4000, 750), shape="rect", size=(400, 1200))]})
    rooms, _ = form_rooms(s)  # the fins leave 50 mm to the band lines: three bays, not one room
    assert len(rooms) == 3
