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
                                                    "set_room_type": 1, "room_type_groups": 1}
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


def test_minutes_never_exceed_a_full_redraw():
    """Final review I3: a reading worse than nothing costs a redraw, not more."""
    from benchmarks.correction_effort import capped_minutes

    gt = spec_with_rooms()
    junk = gt.model_copy(deep=True)
    junk.walls = [Wall(id=f"W{i}", a=(i * 50, 20000), b=(i * 50 + 3000, 20000), thickness=100, kind="partition")
                  for i in range(1, 200)]  # 199 false walls: 16.6 min of deleting
    redraw = correction_minutes(correction_ops(None, gt))
    assert capped_minutes(junk, gt) == redraw and capped_minutes(None, gt) == redraw
    assert capped_minutes(gt, gt) == 0.0


def test_bulk_model():
    ops = {"delete_wall": 68, "add_wall": 16, "set_room_type": 31, "room_type_groups": 5, "add_opening": 2,
           "delete_opening": 0, "set_door": 0, "rename_room": 0, "set_stair": 0}
    assert correction_minutes(ops, bulk=True) == round((10 + 2 * 68 + 16 * 10 + 10 * 5 + 2 * 31 + 2 * 15) / 60, 1)
    assert correction_minutes({**ops, "delete_wall": 0}, bulk=True) == round((16 * 10 + 10 * 5 + 2 * 31 + 2 * 15) / 60, 1)


def test_room_type_groups_counted():
    gt = spec_with_rooms()
    pred = gt.model_copy(deep=True)
    for r in pred.rooms:
        r.type = "other"
    gt.rooms[1].type = gt.rooms[0].type  # both GT rooms want the same type: one bulk action
    ops = correction_ops(pred, gt)
    assert ops["set_room_type"] == 2 and ops["room_type_groups"] == 1


def test_bulk_minutes_capped_and_reported_beside_one_by_one():
    from benchmarks.correction_effort import capped_minutes

    gt = spec_with_rooms()
    redraw = correction_minutes(correction_ops(None, gt), bulk=True)
    assert capped_minutes(None, gt, bulk=True) == redraw <= capped_minutes(None, gt)
    assert capped_minutes(gt, gt, bulk=True) == 0.0


def test_review_model_prices_gap_walls_lower():
    """M8: a wall the review closes with the two-click gap tool costs 8 s; any other missing wall a guide line, 12 s."""
    ops = {"delete_wall": 68, "add_wall": 16, "gap_closures": 6, "gap_doors": 4, "set_room_type": 31,
           "room_type_groups": 8, "add_opening": 10, "delete_opening": 0, "set_door": 0, "rename_room": 0, "set_stair": 0}
    review = correction_minutes(ops, review=True)
    # 6 gap clicks (8 s) replace 4 door adds (15 s) and 2 wall adds; the other 14 walls are guide lines (12 s)
    assert review == round((10 + 2 * 68 + 8 * 6 + 12 * 14 + 15 * 6 + 10 * 8 + 2 * 31) / 60, 1)
    assert review < correction_minutes(ops, bulk=True)


def test_gap_closures_counted_from_review_tasks():
    gt = spec_with_rooms()
    pred = gt.model_copy(deep=True)
    pred.openings = [o for o in pred.openings if o.id != "D1"]
    pred.walls = [w for w in pred.walls if w.id != "W5"] + [
        Wall(id="W5", a=(5000, 0), b=(5000, 2000), thickness=100, kind="interior"),
        Wall(id="W8", a=(5000, 2900), b=(5000, 6000), thickness=100, kind="interior")]
    ops = correction_ops(pred, gt)
    assert (ops["gap_closures"], ops["gap_doors"]) == (1, 1)  # the gap is where the GT has door D1
    assert correction_ops(gt, gt)["gap_closures"] == 0
