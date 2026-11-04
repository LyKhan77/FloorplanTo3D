from benchmarks.run_room_tracing_bench import gate_metrics
from core.spec.models import Wall
from tests.spec.fixtures import spec_with_rooms


def test_identical_specs_score_full():
    s = spec_with_rooms()
    m = gate_metrics(s, s, None)
    assert m["wall_recall"] == 1 and m["wall_precision"] == 1
    assert m["rooms_matched"] == m["rooms_total"] == 2 and m["duplicates"] == 0


def test_duplicate_wall_is_counted():
    gt = spec_with_rooms()
    w = gt.walls[0]
    dup = Wall(id="W99", a=(w.a[0], w.a[1] + 50), b=(w.a[0] + 2000, w.a[1] + 50), thickness=100, kind="interior")
    pred = gt.model_copy(update={"walls": [*gt.walls, dup]})
    assert gate_metrics(pred, gt, None)["duplicates"] == 1


def test_region_filter_ignores_the_top():
    gt = spec_with_rooms()
    top = max(gt.walls, key=lambda w: (w.a[1] + w.b[1]) / 2)
    pred = gt.model_copy(update={"walls": [w for w in gt.walls if w.id != top.id]})
    assert gate_metrics(pred, gt, None)["wall_recall"] < 1
    assert gate_metrics(pred, gt, (top.a[1] + top.b[1]) / 2 - 1)["wall_recall"] == 1
