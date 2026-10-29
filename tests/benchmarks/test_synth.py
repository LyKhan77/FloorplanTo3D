import math

import numpy as np
import pytest
from shapely.geometry import LineString

from benchmarks.synth.perturb import load_base, no_ops, perturb
from core.spec.derive import column_footprint, endpoint_connected
from core.spec.validate import validate


@pytest.fixture(scope="module")
def base():
    return load_base()


def _offsets(spec, orientation):
    return sorted(a.offset for a in spec.grid.axes if a.orientation == orientation)


def _length(w):
    return math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1])


def test_no_ops_keeps_geometry(base):
    s, _ = perturb(base, 0, no_ops(base))
    assert [w.model_dump() for w in s.walls] == [w.model_dump() for w in base.walls]
    assert [o.model_dump() for o in s.openings] == [o.model_dump() for o in base.openings]
    assert [c.center for c in s.columns] == [c.center for c in base.columns]
    assert len(s.rooms) == 48


def test_same_seed_same_spec(base):
    a, ops_a = perturb(base, 7)
    b, ops_b = perturb(base, 7)
    assert ops_a == ops_b and a.model_dump() == b.model_dump()


def test_bays_move_axes_and_walls_on_them(base):
    ops = no_ops(base) | {"bays": [5000] * 5 + [7000] * 2}
    s, _ = perturb(base, 0, ops)
    assert _offsets(s, "vertical") == [0, 5000, 10000, 15000, 20000, 25000]
    assert _offsets(s, "horizontal") == [0, 7000, 14000]
    on_b = [i for i, w in enumerate(base.walls) if w.a[0] == 6000]
    assert on_b and all(s.walls[i].a[0] == 5000 for i in on_b)


def test_mirror_flips_swing_keeps_frame(base):
    s, _ = perturb(base, 0, no_ops(base) | {"mirror": True})
    span = max(_offsets(base, "vertical"))
    assert _offsets(s, "vertical") == sorted(span - o for o in _offsets(base, "vertical"))
    left = min(s.grid.axes, key=lambda a: (a.orientation != "vertical", a.offset))
    assert left.label == "A" and left.offset == 0
    for g, p in zip(base.walls, s.walls):
        assert p.a == (span - g.a[0], g.a[1]) and p.b == (span - g.b[0], g.b[1])
    flip = {"left": "right", "right": "left", None: None}
    for g, p in zip(base.openings, s.openings):
        assert p.swing == flip[g.swing] and p.hinge == g.hinge


def test_dropped_partitions_host_no_openings(base):
    s, _ = perturb(base, 0, no_ops(base) | {"drop_partitions": 3})
    gone = {w.id for w in base.walls} - {w.id for w in s.walls}
    assert len(gone) == 3
    assert not any(o.wall_id in gone for o in base.openings)
    assert all(w.kind in ("partition", "interior") for w in base.walls if w.id in gone)


def test_added_partition_splits_a_room(base):
    s, _ = perturb(base, 0, no_ops(base) | {"add_partitions": 1})
    new = [w for w in s.walls if w.id not in {g.id for g in base.walls}]
    assert len(new) == 1 and new[0].kind == "partition" and new[0].thickness == 100
    w = new[0]
    assert endpoint_connected(s, w, "a") and endpoint_connected(s, w, "b")
    line = LineString([w.a, w.b])
    walls = {x.id: x for x in s.walls}
    for o in s.openings:
        h = walls[o.wall_id]
        ux, uy = (h.b[0] - h.a[0]) / _length(h), (h.b[1] - h.a[1]) / _length(h)
        seg = LineString([(h.a[0] + ux * o.offset, h.a[1] + uy * o.offset),
                          (h.a[0] + ux * (o.offset + o.width), h.a[1] + uy * (o.offset + o.width))])
        assert not line.intersects(seg.buffer(h.thickness / 2))
    assert not any(line.intersects(column_footprint(c)) for c in s.columns)
    assert not any(line.intersects(LineString([f.start, f.end]).buffer(f.width / 2)) for st in s.stairs for f in st.flights)
    assert len(s.rooms) == 49


@pytest.mark.parametrize("seed", range(20))
def test_openings_stay_on_their_walls(base, seed):
    s, _ = perturb(base, seed)
    walls = {w.id: w for w in s.walls}
    for o in s.openings:
        assert o.offset >= 0 and o.offset + o.width <= _length(walls[o.wall_id]) + 1


@pytest.mark.parametrize("seed", range(20))
def test_variants_validate_without_errors(base, seed):
    s, _ = perturb(base, seed)
    assert [i.code for i in validate(s).issues if i.severity == "error"] == []


# --- render -----------------------------------------------------------------------------------------------------

def _px(spec, p):
    """mm -> image px through the render's px_to_mm affine (a 0 c / 0 e f)."""
    a, _, c, _, e, f = spec.meta.px_to_mm
    return (p[0] - c) / a, (p[1] - f) / e


def _ink(img, x, y):
    """Black ink only: stage 1 masks coloured pixels (grid, dimensions) out of the geometry."""
    return img[round(y), round(x)].max() < 128


@pytest.fixture(scope="module")
def rendered(base):
    from benchmarks.synth.render import render

    s, _ = perturb(base, 0, no_ops(base))
    return render(s, 0)


def test_render_draws_double_lines_and_door_gaps(rendered):
    img, s = rendered
    assert s.meta.mm_per_px == 25.0
    hosts = {o.wall_id for o in s.openings}
    thick = [w for w in s.walls if w.thickness >= 180 and w.id not in hosts and _length(w) >= 1000]
    ok = 0
    for w in thick:
        mx, my = (w.a[0] + w.b[0]) / 2, (w.a[1] + w.b[1]) / 2
        nx, ny = -(w.b[1] - w.a[1]) / _length(w), (w.b[0] - w.a[0]) / _length(w)
        faces = [_px(s, (mx + k * nx * w.thickness / 2, my + k * ny * w.thickness / 2)) for k in (-1, 1)]
        near = lambda q: any(_ink(img, q[0] + dx, q[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        ok += not _ink(img, *_px(s, (mx, my))) and all(near(q) for q in faces)
    assert thick and ok >= 0.8 * len(thick)
    walls = {w.id: w for w in s.walls}
    d1 = next(o for o in s.openings if o.id == "D1")
    w = walls[d1.wall_id]
    ux, uy = (w.b[0] - w.a[0]) / _length(w), (w.b[1] - w.a[1]) / _length(w)
    clear = []
    for k in (-1, 1):
        pts = [(w.a[0] + ux * (d1.offset + t * d1.width) - k * uy * w.thickness / 2,
                w.a[1] + uy * (d1.offset + t * d1.width) + k * ux * w.thickness / 2) for t in np.linspace(0.2, 0.8, 9)]
        clear.append(not any(_ink(img, *_px(s, q)) for q in pts))
    assert any(clear)


@pytest.fixture(scope="module")
def stage2(rendered, tmp_path_factory):
    import json

    import cv2

    from benchmarks.llm_items import run_stages

    stop = lambda *_a, **_k: {"status": "failed", "message": "stop after stage 2"}
    root = tmp_path_factory.mktemp("synth")
    data = cv2.imencode(".png", rendered[0])[1].tobytes()
    st, _ = run_stages(root, data, "s00.png", {"03_extract": stop})
    return json.loads((st / "02_grid" / "grid.json").read_text()), json.loads((st / "02_grid" / "ocr.json").read_text())


@pytest.mark.slow
def test_render_text_reads_upright(stage2):
    texts = {t["text"] for t in stage2[1]}
    assert {"28000", "12000"} <= texts


@pytest.mark.slow
def test_stage2_reads_the_rendered_grid(stage2):
    grid = stage2[0]
    axes = lambda o: [a["label"] for a in sorted((a for a in grid["axes"] if a["orientation"] == o), key=lambda a: a["px"])]
    assert axes("vertical") == list("ABCDEF")
    assert sorted(axes("horizontal")) == ["1", "2", "3"]
    assert abs(grid["mm_per_px"] / 25.0 - 1) <= 0.005


# --- runner -----------------------------------------------------------------------------------------------------

def test_target_pass_uses_80_percent_of_nfr():
    from benchmarks.run_synth_bench import target_pass

    ok = {"wall_recall": 0.76, "wall_precision": 0.76, "wall_iou": 0.68, "door_recall": 0.72, "room_match": 0.72,
          "gross_area_err": 0.0125}
    assert target_pass(ok) == (True, [])
    assert target_pass({**ok, "room_match": 0.71}) == (False, ["room_match"])
    assert target_pass({**ok, "gross_area_err": 0.013})[1] == ["gross_area_err"]
    assert target_pass({k: v for k, v in ok.items() if k != "door_recall"}) == (False, ["door_recall"])


def test_variants_start_with_the_unchanged_render(base):
    from benchmarks.run_synth_bench import variants

    vs = variants(3)
    assert [v["id"] for v in vs] == ["s00", "s01", "s02", "s03"]
    assert vs[0]["ops"] == no_ops(base)
    assert vs[1]["ops"] != no_ops(base)


def test_stopped_variant_fails_with_reason(base, tmp_path):
    from benchmarks.correction_effort import capped_minutes
    from benchmarks.run_synth_bench import run_variant, variants

    def boom(project, work, *a, **kw):
        raise ValueError("x")

    v = variants(1)[1]
    row = run_variant(v, tmp_path, {"02_grid": boom})
    gt, _ = perturb(base, v["seed"], v["ops"])
    assert row["passed"] is False and "stage 2 failed" in row["reason"]
    assert row["correction_min"] == capped_minutes(None, gt)
    assert (tmp_path / "s01" / "input.png").exists()


# --- final review fixes -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(1, 6))
def test_seed_alone_gives_the_benchmarked_variant(base, seed):
    """Final review I1: tests that call perturb(base, seed) check the same GT the runner scores."""
    from benchmarks.synth.perturb import draw_ops

    a, _ = perturb(base, seed)
    b, _ = perturb(base, seed, draw_ops(base, np.random.default_rng(seed)))
    assert a.model_dump() == b.model_dump()


@pytest.mark.parametrize("seed", range(20))
def test_redrawn_door_types_fit_the_width(base, seed):
    """Final review I2: leaves stay within PRD/04 §3.4's 500-1300 mm arc radius."""
    s, _ = perturb(base, seed)
    for o in s.openings:
        if o.door_type == "double_swing":
            assert o.width / 2 >= 500, o
        if o.door_type == "single_swing":
            assert o.width <= 1300, o


def _stair_in_walls(spec):
    from shapely.ops import unary_union

    from core.spec.derive import wall_footprint

    walls = unary_union([wall_footprint(w, spec) for w in spec.walls])
    flights = unary_union([LineString([f.start, f.end]).buffer(f.width / 2, cap_style="flat")
                           for st in spec.stairs for f in st.flights])
    return flights.intersection(walls).area


@pytest.mark.parametrize("seed", range(20))
def test_stair_shift_never_pushes_treads_into_walls(base, seed):
    """Final review I3: the stair shift never pushes treads further into walls, and no added partition crosses it."""
    from benchmarks.synth.perturb import draw_ops

    ops = draw_ops(base, np.random.default_rng(seed))
    s, _ = perturb(base, seed, ops)
    unshifted, _ = perturb(base, seed, ops | {"stair_shift": (0, 0)})
    assert _stair_in_walls(s) <= _stair_in_walls(unshifted) + 1  # the shift itself adds no overlap
    assert _stair_in_walls(s) <= 1.25 * _stair_in_walls(base)  # bays stretch flights a little, no more
    flights = [LineString([f.start, f.end]).buffer(f.width / 2) for st in s.stairs for f in st.flights]
    new = [w for w in s.walls if w.id not in {g.id for g in base.walls}]
    assert not any(LineString([w.a, w.b]).intersects(f) for w in new for f in flights)


def test_scoring_uses_the_known_frame(base):
    """Final review I6: the variant's frame is known, so a 100 mm offset is scored, and the best shift is only
    reported."""
    from benchmarks.run_augment_bench import translate
    from benchmarks.run_synth_bench import score

    gt, _ = perturb(base, 0, no_ops(base))
    out = score(translate(gt, 0, 100), gt)
    assert out["metrics"]["wall_pos_median_mm"] >= 90
    assert out["shift_mm"] == [0, -100]


def test_synth_rows_attribute_leaks(base):
    """M7d final review I-2: synthetic leak counts come from the runner's own rows."""
    from benchmarks.run_synth_bench import score

    gt, _ = perturb(base, 0, no_ops(base))
    pred = gt.model_copy(deep=True)
    pred.walls = [w for w in pred.walls if w.kind != "partition"]
    from core.spec.rooms import rebuild_rooms

    out = score(rebuild_rooms(pred.model_copy(update={"rooms": []})), gt)
    assert out["leaks"] and set(out["leaks"]) <= {"door_gap", "wall_missing", "other"}
