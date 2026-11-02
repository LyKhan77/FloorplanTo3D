import json
from pathlib import Path

import numpy as np
import pytest

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
