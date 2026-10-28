from benchmarks.correction_effort import SECONDS, correction_minutes, correction_ops
from core.spec.models import Wall
from tests.spec.fixtures import spec_with_rooms


def test_time_model():
    assert SECONDS == {"delete_wall": 5, "add_wall": 20, "delete_opening": 5, "add_opening": 15, "set_door": 10,
                       "set_room_type": 8, "rename_room": 8, "set_stair": 20}


def test_identical_spec_needs_no_correction():
    gt = spec_with_rooms()
    assert correction_minutes(correction_ops(gt, gt)) == 0.0


def test_ops_count_each_kind():
    gt = spec_with_rooms()
    pred = gt.model_copy(deep=True)
    pred.walls = [w for w in pred.walls if w.id != "W4"] + [Wall(id="W9", a=(2000, 3000), b=(4000, 3000),
                                                                 thickness=100, kind="partition")]
    pred.openings = [o for o in pred.openings if o.id != "D2"]  # W4 hosts no door; D1 stays on W5
    pred.rooms[0].type = "other"
    ops = correction_ops(pred, gt)
    assert {k: v for k, v in ops.items() if v} == {"add_wall": 1, "delete_wall": 1, "add_opening": 1,
                                                    "set_room_type": 1}
    assert correction_minutes(ops) == round((20 + 5 + 15 + 8) / 60, 1)  # 0.8


def test_wrong_door_direction_needs_set_door():
    gt = spec_with_rooms()
    pred = gt.model_copy(deep=True)
    pred.openings[0].hinge = "end"  # D1: start -> end
    assert correction_ops(pred, gt)["set_door"] == 1


def test_stopped_run_costs_a_full_redraw():
    gt = spec_with_rooms()
    ops = correction_ops(None, gt)
    assert ops["add_wall"] == len(gt.walls) and ops["add_opening"] == len(gt.openings)
    assert ops["set_room_type"] == 2 and ops["rename_room"] == 2
    assert correction_minutes(ops) > 0
