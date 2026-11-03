import json
import math
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box as sbox

from core.assist.context import area_context
from core.assist.plan import AreaPlan, translate
from core.spec.models import Spec, Wall
from tests.spec.fixtures import spec_with_rooms

ASK = "rapikan area ini ya"


def plan(*actions) -> AreaPlan:
    return AreaPlan.model_validate({"question": None, "actions": list(actions), "explanation": "x"})


def run(spec, actions, box=(0, 0, 10000, 6000), selection=(), binary=None, px_to_mm=None):
    ctx = area_context(spec, box, list(selection), None, None)
    return translate(plan(*actions), spec, ctx, ASK, binary, px_to_mm)


def with_walls(*walls) -> Spec:
    s = spec_with_rooms()
    return s.model_copy(update={"walls": [*s.walls, *walls]})


def test_delete_and_reason():
    t = run(spec_with_rooms(), [{"type": "delete_wall", "id": "W5"}])
    assert t.ops == [{"op": "delete_wall", "id": "W5", "reason": "asisten: " + ASK[:60]}]
    assert t.deleted == ["W5"] and t.rejected == []


def test_unknown_id_is_rejected():
    t = run(spec_with_rooms(), [{"type": "delete_wall", "id": "W99"}])
    assert t.ops == [] and any("W99" in r for r in t.rejected)
    # a real wall outside the marked area counts as unknown too
    t = run(spec_with_rooms(), [{"type": "delete_wall", "id": "W2"}], box=(4000, 1000, 6000, 5000))
    assert t.ops == [] and any("W2" in r for r in t.rejected)


def test_parallel_merge_becomes_one_midline_wall():
    s = with_walls(Wall(id="W6", a=(2000, 1000), b=(2000, 3000), thickness=150, kind="interior"),
                   Wall(id="W7", a=(2120, 1500), b=(2120, 3000), thickness=100, kind="interior"))
    t = run(s, [{"type": "merge_walls", "ids": ["W6", "W7"]}])
    kinds = [o["op"] for o in t.ops]
    assert kinds == ["delete_wall", "delete_wall", "add_wall"]
    add = t.ops[-1]
    assert add["thickness"] == 150 and {tuple(add["a"]), tuple(add["b"])} == {(2060, 1000), (2060, 3000)}
    assert t.added[0]["snapped"] is False


def test_far_or_skewed_merge_is_rejected():
    far = with_walls(Wall(id="W6", a=(2000, 1000), b=(2000, 3000), thickness=150, kind="interior"),
                     Wall(id="W7", a=(2600, 1000), b=(2600, 3000), thickness=100, kind="interior"))
    assert run(far, [{"type": "merge_walls", "ids": ["W6", "W7"]}]).rejected
    skew = with_walls(Wall(id="W6", a=(2000, 1000), b=(2000, 3000), thickness=150, kind="interior"),
                      Wall(id="W7", a=(2000, 1000), b=(2700, 2930), thickness=100, kind="interior"))
    t = run(skew, [{"type": "merge_walls", "ids": ["W6", "W7"]}])
    assert t.rejected and t.ops == []


def test_collinear_merge_uses_merge_walls():
    s = with_walls(Wall(id="W6", a=(2000, 1000), b=(2000, 2000), thickness=100, kind="interior"),
                   Wall(id="W7", a=(2000, 2000), b=(2000, 3000), thickness=100, kind="interior"))
    t = run(s, [{"type": "merge_walls", "ids": ["W6", "W7"]}])
    assert [o["op"] for o in t.ops] == ["merge_walls"] and t.ops[0]["ids"] == ["W6", "W7"]


@pytest.fixture(scope="module")
def gatsu():
    from core.extraction.preprocess import load_raster, preprocess

    gt = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    a, b, c, d, e, f = json.loads(Path("benchmarks/gatsu/gt_spec.json").read_text())["meta"]["px_to_mm"]
    return gt, preprocess(load_raster(Path("floorplan/plan.jpeg"))).binary, [a / 2, b / 2, c, d / 2, e / 2, f]


def test_add_wall_snaps_to_the_drawing(gatsu):
    gt, binary, t = gatsu
    box = (5000, 6000, 7000, 11700)
    rough = {"type": "add_wall", "a": [5940, 6500], "b": [5940, 11000]}  # W43 runs at x = 5790
    tr = translate(plan(rough), gt, area_context(gt, box, [], None, None), ASK, binary, t)
    add = tr.ops[0]
    assert tr.added[0]["snapped"] is True and abs(add["a"][0] - 5790) <= 60 and abs(add["b"][0] - 5790) <= 60
    blank = np.zeros_like(binary)
    tr = translate(plan(rough), gt, area_context(gt, box, [], None, None), ASK, blank, t)
    assert tr.added[0]["snapped"] is False and tr.ops[0]["thickness"] == gt.meta.defaults.wall_thickness
    assert tr.ops[0]["a"] == [5940, 6500]


def test_order_and_room_ops():
    t = run(spec_with_rooms(), [
        {"type": "set_room_type", "room": "R1", "value": "stair"},
        {"type": "add_wall", "a": [2500, 100], "b": [2500, 5900]},
        {"type": "delete_wall", "id": "W5"},
        {"type": "rename_room", "room": "R2", "name": "Gudang"},
        {"type": "set_room_type", "room": "R2", "value": "kantin"},
    ])
    assert [o["op"] for o in t.ops] == ["delete_wall", "add_wall", "set_room_type_at", "rename_room_at",
                                        "set_room_type_at"]
    at = t.ops[2]["at"]
    assert 100 < at[0] < 4950 and 100 < at[1] < 5900  # inside R1
    assert t.ops[4]["type"] == "other" and any("kantin" in n for n in t.notes)


def test_room_op_uses_the_llm_point_inside_the_area():
    t = run(spec_with_rooms(), [{"type": "set_room_type", "room": "R1", "value": "stair", "at": [1000, 1000]}])
    assert t.ops[0]["at"] == [1000, 1000]


def test_extend_wall_closes_the_corner():
    s = with_walls(Wall(id="W6", a=(2000, 1000), b=(2000, 4600), thickness=100, kind="interior"),
                   Wall(id="W7", a=(1000, 5000), b=(4000, 5000), thickness=100, kind="interior"))
    t = run(s, [{"type": "extend_wall", "id": "W6", "to": "W7"}])
    assert t.ops == [{"op": "move_wall", "id": "W6", "b": [2000, 5000]}]
    assert t.moved == [{"id": "W6", "a": [2000, 1000], "b": [2000, 5000]}]
    par = with_walls(Wall(id="W6", a=(2000, 1000), b=(2000, 4600), thickness=100, kind="interior"))
    assert run(par, [{"type": "extend_wall", "id": "W6", "to": "W5"}]).rejected


def test_split_wall_projects_the_point():
    t = run(spec_with_rooms(), [{"type": "split_wall", "id": "W5", "at": [5040, 4500]}])
    assert t.ops == [{"op": "split_wall", "id": "W5", "at_offset": 4500}]
    assert run(spec_with_rooms(), [{"type": "split_wall", "id": "W5", "at": [5000, 50]}]).rejected
    # D1 spans 2000..2900 on W5
    assert run(spec_with_rooms(), [{"type": "split_wall", "id": "W5", "at": [5000, 2500]}]).rejected


def gap_page():
    """W5 (x = 5000 mm) drawn as a double line with a 1000 mm gap at y 3500..4500 mm; 10 mm per px, y up."""
    img = np.zeros((600, 1000), np.uint8)
    for x in (497, 503):
        img[0:600, x] = 255
    img[600 - 450:600 - 350, 490:510] = 0
    return img


def test_add_opening_snaps_to_the_gap():
    t = run(spec_with_rooms(), [{"type": "add_opening", "wall": "W5", "category": "door", "at": [5000, 4300]}],
            binary=gap_page(), px_to_mm=[10, 0, 0, 0, -10, 6000])
    op = t.ops[0]
    assert op["op"] == "add_opening" and op["wall_id"] == "W5" and op["category"] == "door"
    assert abs(op["offset"] - 3500) <= 30 and abs(op["width"] - 1000) <= 30 and t.openings[0]["snapped"] is True
    t = run(spec_with_rooms(), [{"type": "add_opening", "wall": "W5", "category": "door", "at": [5000, 4300]}])
    assert (t.ops[0]["offset"], t.ops[0]["width"], t.openings[0]["snapped"]) == (3850, 900, False)
    assert run(spec_with_rooms(), [{"type": "add_opening", "wall": "W9", "category": "door", "at": [0, 0]}]).rejected


def test_set_door_keeps_the_centre():
    t = run(spec_with_rooms(), [{"type": "set_door", "id": "D1", "width": 1200, "swing": "right"}])
    assert t.ops == [{"op": "set_door", "id": "D1", "width": 1200, "offset": 1850, "swing": "right"}]


def with_door(*walls, openings=()):
    s = with_walls(*walls)
    return s.model_copy(update={"openings": [*s.openings, *openings]})


def test_merge_flips_hinge_of_a_reversed_wall():
    from core.spec.models import Opening

    s = with_door(Wall(id="W6", a=(2000, 1000), b=(2000, 3000), thickness=150, kind="interior"),
                  Wall(id="W7", a=(2120, 3000), b=(2120, 1000), thickness=100, kind="interior"),
                  openings=[Opening(id="D9", category="door", wall_id="W7", offset=500, width=800,
                                    door_type="single_swing", hinge="start", swing="left")])
    t = run(s, [{"type": "merge_walls", "ids": ["W6", "W7"]}])
    door = t.ops[-1]["openings"][0]
    assert (door["offset"], door["hinge"], door["swing"]) == (700, "end", "right")


def test_merge_drops_an_opening_deleted_in_the_same_plan():
    from core.spec.models import Opening

    s = with_door(Wall(id="W6", a=(2000, 1000), b=(2000, 3000), thickness=150, kind="interior"),
                  Wall(id="W7", a=(2120, 3000), b=(2120, 1000), thickness=100, kind="interior"),
                  openings=[Opening(id="D9", category="door", wall_id="W7", offset=500, width=800)])
    t = run(s, [{"type": "delete_opening", "id": "D9"}, {"type": "merge_walls", "ids": ["W6", "W7"]}])
    assert "openings" not in t.ops[-1]


def test_collinear_merge_keeps_the_lowest_id_over_the_whole_span():
    s = with_walls(Wall(id="W6", a=(2000, 1000), b=(2000, 2000), thickness=100, kind="interior"),
                   Wall(id="W7", a=(2000, 2000), b=(2000, 3000), thickness=100, kind="interior"))
    t = run(s, [{"type": "merge_walls", "ids": ["W7", "W6"]},
                {"type": "add_opening", "wall": "W6", "category": "door", "at": [2000, 2500]},
                {"type": "add_opening", "wall": "W7", "category": "door", "at": [2000, 2500]}])
    assert [o for o in t.ops if o["op"] == "add_opening"] == [
        {"op": "add_opening", "wall_id": "W6", "category": "door", "offset": 1050, "width": 900,
         "door_type": "single_swing", "hinge": "start", "swing": "left"}]
    assert any("W7" in r for r in t.rejected)


def test_actions_on_a_wall_gone_earlier_in_the_plan_are_rejected_not_dropped():
    t = run(spec_with_rooms(), [{"type": "delete_wall", "id": "W5"},
                                {"type": "split_wall", "id": "W5", "at": [5000, 4500]}])
    assert [o["op"] for o in t.ops] == ["delete_wall"] and any("W5" in r for r in t.rejected)


def test_extend_at_the_a_end_keeps_openings_in_place():
    from core.spec.models import Opening

    s = with_door(Wall(id="W6", a=(2000, 400), b=(2000, 4600), thickness=100, kind="interior"),
                  openings=[Opening(id="D9", category="door", wall_id="W6", offset=1000, width=900),
                            Opening(id="N9", category="window", wall_id="W6", offset=2500, width=1000, sill=900)])
    t = run(s, [{"type": "extend_wall", "id": "W6", "to": "W1"}])
    assert {"op": "move_wall", "id": "W6", "a": [2000, 0]} in t.ops
    assert {"op": "set_door", "id": "D9", "offset": 1400} in t.ops
    assert {"op": "delete_opening", "id": "N9", "reason": "asisten: " + ASK} in t.ops
    added = next(o for o in t.ops if o["op"] == "add_opening")
    assert (added["wall_id"], added["category"], added["offset"], added["width"], added["sill"]) == ("W6", "window", 2900, 1000, 900)


def test_add_opening_skips_the_gap_of_an_existing_door():
    img = gap_page()
    img[600 - 290:600 - 200, 490:510] = 0  # D1's own gap, y 2000..2900 mm
    t = run(spec_with_rooms(), [{"type": "add_opening", "wall": "W5", "category": "door", "at": [5000, 3150]}],
            binary=img, px_to_mm=[10, 0, 0, 0, -10, 6000])
    assert abs(t.ops[0]["offset"] - 3500) <= 30 and t.openings[0]["snapped"] is True


STAIR_BOX = (-1400, 5600, 5700, 10100)  # Gatsu stair S1


def test_add_stair_reads_the_drawn_flights(gatsu):
    gt, binary, t = gatsu
    spec = gt.model_copy(update={"stairs": gt.stairs[1:]})  # S1 missed by the extraction
    tr = translate(plan({"type": "add_stair", "at": [3000, 8000]}), spec, area_context(spec, STAIR_BOX, [], None, None),
                   ASK, binary, t)
    op = next(o for o in tr.ops if o["op"] == "add_stair")
    xs = sorted(f["start"][0] for f in op["flights"])
    assert len(xs) == 2 and abs(xs[0] - 1060) <= 100 and abs(xs[1] - 4990) <= 100
    assert all(1300 <= f["width"] <= 1600 for f in op["flights"]) and tr.stairs[0]["snapped"] is True


def test_add_stair_refuses_a_stair_the_spec_already_has(gatsu):
    gt, binary, t = gatsu
    tr = translate(plan({"type": "add_stair", "at": [3000, 8000]}), gt, area_context(gt, STAIR_BOX, [], None, None),
                   ASK, binary, t)
    assert not any(o["op"] == "add_stair" for o in tr.ops) and any("S1" in r for r in tr.rejected)


def _footprint(op):
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    return unary_union([LineString([f["start"], f["end"]]).buffer(f["width"] / 2, cap_style="flat")
                        for f in op["flights"]])


def test_add_stair_designs_a_u_stair_that_fits_the_room():
    from shapely.geometry import Polygon as SPolygon

    s = spec_with_rooms()  # floor to floor 4000: 23 risers, a straight run of 6.4 m does not fit R1 (5.8 m)
    t = run(s, [{"type": "add_stair", "room": "R1", "up": "north"}])
    op = next(o for o in t.ops if o["op"] == "add_stair")
    assert len(op["flights"]) == 2 and sum(f["risers"] for f in op["flights"]) == 23 and op["landings"]
    for f in op["flights"]:
        assert abs(math.dist(f["start"], f["end"]) - f["risers"] * 280) <= 2 and f["width"] == 1200
    assert op["flights"][0]["end"][1] > op["flights"][0]["start"][1]  # the first flight climbs north
    r1 = next(r for r in s.rooms if r.id == "R1")
    assert SPolygon(r1.polygon).buffer(1).covers(_footprint(op)) and t.stairs[0]["snapped"] is False


def test_add_stair_straight_when_it_fits():
    s = spec_with_rooms()
    s = s.model_copy(update={"meta": s.meta.model_copy(update={"defaults": s.meta.defaults.model_copy(
        update={"floor_to_floor": 3000})})})
    t = run(s, [{"type": "add_stair", "room": "R1", "up": "north", "width": 1000}])  # 18 risers: 5.04 m of 5.8 m
    op = next(o for o in t.ops if o["op"] == "add_stair")
    (f,) = op["flights"]
    assert f["risers"] == 18 and f["width"] == 1000 and f["end"][1] > f["start"][1] and f["start"][0] == f["end"][0]


def test_add_stair_that_does_not_fit_is_rejected():
    t = run(spec_with_rooms(), [{"type": "add_stair", "up": "north"}], box=(200, 200, 2200, 2200))
    assert not t.ops and any("tidak muat" in r for r in t.rejected)


def test_add_stair_follows_a_narrow_marked_box_when_no_standard_stair_fits():
    """test-2 R49: a drawn U stair of 2 x ~700 mm flights in a 1.47 x 3.64 m box; a standard stair needs more."""
    t = run(spec_with_rooms(), [{"type": "add_stair", "up": "north"}], box=(1000, 1000, 2470, 4638))
    op = next(o for o in t.ops if o["op"] == "add_stair")
    assert [f["width"] for f in op["flights"]] == [685, 685] and op["landings"]
    assert sum(f["risers"] for f in op["flights"]) == 23
    assert sbox(1000, 1000, 2470, 4638).buffer(1).covers(_footprint(op))
    assert any("injakan" in n for n in t.notes)


def test_add_stair_rejection_says_what_it_needs():
    t = run(spec_with_rooms(), [{"type": "add_stair", "up": "north"}], box=(200, 200, 2200, 2200))
    assert any("butuh" in r and "tidak muat" in r for r in t.rejected)


def test_delete_stair_in_the_area(gatsu):
    gt = gatsu[0]
    ctx = area_context(gt, STAIR_BOX, [], None, None)
    assert "S1" in ctx.stair_ids
    t = translate(plan({"type": "delete_stair", "id": "S1"}), gt, ctx, ASK, None, None)
    assert t.ops == [{"op": "delete_stair", "id": "S1", "reason": "asisten: " + ASK}] and t.deleted == ["S1"]
    t = translate(plan({"type": "delete_stair", "id": "S9"}), gt, ctx, ASK, None, None)
    assert not t.ops and any("S9" in r for r in t.rejected)


def test_a_stair_replaced_in_one_plan_is_read_again_from_the_drawing(gatsu):
    """'Hapus tangga lama, tambahkan sesuai gambar': the deleted S1 no longer blocks the drawn stair."""
    gt, binary, t = gatsu
    tr = translate(plan({"type": "delete_stair", "id": "S1"}, {"type": "add_stair", "at": [3000, 8000]}), gt,
                   area_context(gt, STAIR_BOX, [], None, None), ASK, binary, t)
    assert [o["op"] for o in tr.ops] == ["delete_stair", "add_stair"] and tr.stairs[0]["snapped"] is True


def interior(library_dir, drawn=()):
    from core.assist.plan import Interior
    from core.interior.library import load_library
    from core.interior.rules import load_rules

    return Interior(load_library(library_dir), load_rules(), list(drawn), 3000)


def test_fill_room_emits_add_objects(library_dir):
    s = spec_with_rooms()
    ctx = area_context(s, (0, 0, 10000, 6000), [], None, None)
    # R1 is 4.85 x 5.8 m with two doors' keep-clear zones: 2 racks fit
    tr = translate(plan({"type": "fill_room", "room": "R1", "items": [{"template": "rack-42u-600x1200", "count": 2}]}),
                   s, ctx, ASK, None, None, interior=interior(library_dir))
    adds = [o for o in tr.ops if o["op"] == "add_object"]
    assert len(adds) == 2 and all(o["template_version"] == "1.1.0" for o in adds)
    assert len(tr.objects) == 2 and all(o["snapped"] is False for o in tr.objects)
    assert all(100 <= o["position"][0] <= 4950 for o in adds)  # inside R1


def test_unknown_template_rejected(library_dir):
    s = spec_with_rooms()
    ctx = area_context(s, (0, 0, 10000, 6000), [], None, None)
    tr = translate(plan({"type": "fill_room", "room": "R1", "items": [{"template": "rack-99u", "count": 1}]}), s, ctx,
                   ASK, None, None, interior=interior(library_dir))
    assert not tr.ops and any("rack-99u" in r for r in tr.rejected)


def test_place_drawn_uses_the_box(library_dir):
    s = spec_with_rooms()
    k1 = {"id": "K1", "center": [2500, 3000], "size": [800, 1200], "rotation": 90}
    ctx = area_context(s, (0, 0, 10000, 6000), [], None, None, drawn=[k1])
    assert "K1" in ctx.text
    tr = translate(plan({"type": "place_drawn", "boxes": ["K1"], "template": "ups-cabinet-generic"}), s, ctx, ASK,
                   None, None, interior=interior(library_dir, [k1]))
    (op,) = [o for o in tr.ops if o["op"] == "add_object"]
    assert op["template_id"] == "ups-cabinet-generic" and op["position"][:2] == [2500, 3000]
    assert tr.objects[0]["snapped"] is True
    tr = translate(plan({"type": "place_drawn", "boxes": ["K7"], "template": "ups-cabinet-generic"}), s, ctx, ASK,
                   None, None, interior=interior(library_dir, [k1]))
    assert any("K7" in r for r in tr.rejected)


def test_overlapping_drawn_boxes_are_a_problem(library_dir):
    s = spec_with_rooms()
    ks = [{"id": "K1", "center": [2500, 3000], "size": [800, 1200], "rotation": 90},
          {"id": "K2", "center": [2700, 3000], "size": [800, 1200], "rotation": 90}]
    ctx = area_context(s, (0, 0, 10000, 6000), [], None, None, drawn=ks)
    tr = translate(plan({"type": "place_drawn", "boxes": ["K1", "K2"], "template": "ups-cabinet-generic"}), s, ctx,
                   ASK, None, None, interior=interior(library_dir, ks))
    assert any("tumpang tindih" in r for r in tr.rejected)
