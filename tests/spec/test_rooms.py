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


def test_neck_split_never_wraps_around_a_thin_partition():
    """Final review C1: a 100 mm partition stopping 200 mm short of the wall; no room may own space on both sides."""
    from core.spec.models import Wall
    from tests.spec.fixtures import two_room_spec

    s = two_room_spec()
    s.walls[4] = Wall(id="W5", a=(4990, 0), b=(4990, 5700), thickness=100, kind="interior")
    rooms, _ = form_rooms(s)
    for r in rooms:
        xs = [x for x, _ in r.exterior.coords]
        assert max(xs) <= 4940 or min(xs) >= 5040, list(r.exterior.coords)  # each room on one side of the faces


def test_inner_rooms_joined_by_a_sliver_stay_one_room():
    """Final review I3 / plan Review Focus 4: only rooms at the outer contour are split at necks."""
    from shapely.geometry import box

    from core.spec.models import Wall
    from tests.spec.fixtures import two_room_spec

    s = two_room_spec()
    # an outer band 1500 mm deep around the two rooms keeps them away from the outline
    s.walls += [Wall(id="W6", a=(-1500, -1500), b=(11500, -1500), thickness=200, kind="exterior"),
                Wall(id="W7", a=(11500, -1500), b=(11500, 7500), thickness=200, kind="exterior"),
                Wall(id="W8", a=(11500, 7500), b=(-1500, 7500), thickness=200, kind="exterior"),
                Wall(id="W9", a=(-1500, 7500), b=(-1500, -1500), thickness=200, kind="exterior")]
    s.walls[4] = Wall(id="W5", a=(4990, 0), b=(4990, 5700), thickness=100, kind="interior")
    rooms, _ = form_rooms(s)
    inner = [r for r in rooms if r.within(box(0, 0, 10000, 6000))]
    assert len(inner) == 1  # the two inner halves joined through the 200 mm gap stay one room


# --- building outline bridges gaps (M7a-2 Task 2) -------------------------------------------------------------------

def _shell(walls, columns=()):
    from tests.spec.fixtures import two_room_spec

    return two_room_spec().model_copy(update={"walls": walls, "columns": list(columns), "openings": [], "rooms": []})


def _w(i, a, b, kind="exterior"):
    from core.spec.models import Wall

    return Wall(id=f"W{i}", a=a, b=b, thickness=200, kind=kind)


def _ring(points):
    return [_w(i + 1, points[i], points[(i + 1) % len(points)]) for i in range(len(points))]


def test_outline_bridges_a_2m_gap_in_the_outer_wall():
    walls = [_w(1, (0, 0), (12000, 0)), _w(2, (12000, 0), (12000, 8000)), _w(3, (12000, 8000), (7000, 8000)),
             _w(4, (5000, 8000), (0, 8000)), _w(5, (0, 8000), (0, 0))]  # 2 m of the top wall missing
    _, outlines = form_rooms(_shell(walls))
    assert len(outlines) == 1 and outlines[0].area == pytest.approx(12_200 * 8_200, rel=0.01)


def test_outline_keeps_a_4m_recess():
    walls = _ring([(0, 0), (4000, 0), (4000, 2000), (8000, 2000), (8000, 0), (12000, 0), (12000, 8000), (0, 8000)])
    _, outlines = form_rooms(_shell(walls))
    assert outlines[0].area == pytest.approx(12_200 * 8_200 - 3_800 * 2_000, rel=0.01)


def test_two_masses_4m_apart_stay_two_outlines():
    a = _ring([(0, 0), (4000, 0), (4000, 4000), (0, 4000)])
    b = [w.model_copy(update={"id": f"W{10 + i}", "a": (w.a[0] + 8000, w.a[1]), "b": (w.b[0] + 8000, w.b[1])})
         for i, w in enumerate(a)]
    _, outlines = form_rooms(_shell(a + b))
    assert len(outlines) == 2


def test_band_with_a_gap_keeps_its_outline_and_only_walled_bays():
    """The outline (gross area) bridges the 2 m gap; rooms come only from space the drawn walls enclose (final
    review I1: a room the closing invents cannot be deleted in the editor)."""
    from core.spec.models import Column

    walls = [_w(1, (0, 0), (6000, 0)), _w(2, (6000, 0), (6000, 1500)), _w(3, (6000, 1500), (4500, 1500)),
             _w(4, (2500, 1500), (0, 1500)), _w(5, (0, 1500), (0, 0))]  # 2 m of the band's top line missing
    fins = [Column(id="C1", center=(2000, 750), shape="rect", size=(400, 1200)),
            Column(id="C2", center=(4000, 750), shape="rect", size=(400, 1200))]
    rooms, outlines = form_rooms(_shell(walls, fins))
    assert outlines[0].area == pytest.approx(6_200 * 1_700, rel=0.01)
    assert rooms == []  # the open band encloses nothing; the editor user closes the gap, then the bays form


def test_annex_1_3m_from_the_building_stays_its_own_outline():
    """Gatsu's capacitor room: a small closed mass 1.3 m off the main wall; closing must not bridge them."""
    main = _ring([(0, 0), (12000, 0), (12000, 8000), (0, 8000)])
    annex = [w.model_copy(update={"id": f"W{20 + i}"}) for i, w in
             enumerate(_ring([(13500, 1000), (16000, 1000), (16000, 3000), (13500, 3000)]))]
    _, outlines = form_rooms(_shell(main + annex))
    assert len(outlines) == 2


def test_closing_never_turns_a_recess_into_a_room():
    """Final review I1: rooms are cut from the drawn walls; the closed shell only sets the outline / gross area."""
    walls = _ring([(0, 0), (4000, 0), (4000, 3000), (6500, 3000), (6500, 0), (12000, 0), (12000, 8000), (0, 8000)])
    rooms, outlines = form_rooms(_shell(walls))  # a 2.5 m x 3 m entrance recess
    assert len(rooms) == 1
    assert outlines[0].area > rooms[0].area  # the outline may still bridge the recess mouth (gross area)


def test_ring_broken_twice_is_still_closed():
    """Final review I2: two 2 m gaps split the ring into open strips; no strip is a mass of its own."""
    walls = [_w(1, (0, 0), (5000, 0)), _w(2, (7000, 0), (12000, 0)), _w(3, (12000, 0), (12000, 8000)),
             _w(4, (12000, 8000), (7000, 8000)), _w(5, (5000, 8000), (0, 8000)), _w(6, (0, 8000), (0, 0))]
    _, outlines = form_rooms(_shell(walls))  # two C halves of ~3.6 m² each: open strips, not masses
    assert len(outlines) == 1 and outlines[0].area == pytest.approx(12_200 * 8_200, rel=0.01)
