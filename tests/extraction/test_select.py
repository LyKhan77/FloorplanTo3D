import json
import shutil

import cv2
import numpy as np
import pytest

from core.extraction.rooms.assemble import assemble_spec
from core.extraction.rooms.overlay import px_from_mm
from core.extraction.select import choose, crop_labels, ocr_dimensions_from
from core.extraction.stages import stage_validate, write_json
from core.spec.store import SpecStore
from tests.extraction.rooms.test_assemble import GRID, META, box_elements, door, wall


def test_choose_prefers_score_then_coverage():
    a = {"index": 0, "score": 0.82, "passed": True, "coverage": 0.7}
    b = {"index": 1, "score": 0.815, "passed": True, "coverage": 0.9}
    assert choose([a, b])["index"] == 1
    assert choose([a, b | {"score": 0.80}])["index"] == 0
    assert choose([a | {"passed": False}, b | {"score": 0.1}])["index"] == 1
    assert choose([a | {"passed": False}]) is None


def test_ocr_dimensions_from_grid():
    grid = {"equations_used": [{"axis_from": "A", "axis_to": "F", "orientation": "x", "px": 2164.0,
                                "text_bbox": [0, 0, 1, 1], "value_mm": 28000}]}
    assert ocr_dimensions_from(grid) == [("A", "F", 28000)]


def test_unlabelled_room_gets_crop_ocr_label():
    el = box_elements()
    el["walls"] = [wall((0, 0), (3000, 0)), wall((3000, 0), (3000, 3000)), wall((3000, 3000), (0, 3000)),
                   wall((0, 3000), (0, 0))]  # 3000 x 3000 mm room
    el["openings"] = [door(0, 1000)]
    spec, _ = assemble_spec(el, GRID, [], META)
    page = np.full((1000, 1000), 255, np.uint8)
    to_px = px_from_mm(GRID["px_to_mm_original"])
    u, v = (round(t) for t in to_px(900, 1700))
    cv2.putText(page, "TOILET", (u, v), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2, cv2.LINE_AA)
    labels = crop_labels(page, spec, GRID["px_to_mm_original"])
    assert [lb.type for lb in labels] == ["toilet"]


def fake_run(tmp_path, specs: dict[int, object], line_len_m: float = 30):
    """Minimal project + run folders for stage 5 from stage-4 specs (no image work needed)."""
    project = tmp_path / "p"
    (project / "input").mkdir(parents=True)
    (project / "input" / "input.json").write_text(json.dumps({"filename": "x.png", "sha256": "0", "prompt": "",
                                                             "params": {}, "page": None, "type": "png"}))
    st = project / "runs" / "r" / "stages"
    for d in ("01_preprocess", "02_grid", "03_extract", "04_rooms"):
        (st / d).mkdir(parents=True)
    cv2.imwrite(str(st / "01_preprocess" / "page.png"), np.full((1000, 1000), 255, np.uint8))
    write_json(st / "01_preprocess" / "meta.json", {"original_size": [500, 500], "work_from_original": [2, 0, 0, 0, 2, 0],
                                                    "work_size": [1000, 1000], "drawing_bbox": [0, 0, 1000, 1000],
                                                    "upscale": 2, "deskew_deg": 0})
    write_json(st / "02_grid" / "grid.json", GRID | {"px_to_mm": GRID["px_to_mm_original"], "mm_per_px_work": 10,
                                                     "equations_used": []})
    write_json(st / "02_grid" / "ocr.json", [])
    rows3, rows4 = [], []
    for k, spec in specs.items():
        c = st / "03_extract" / "candidates" / str(k)
        c.mkdir(parents=True)
        write_json(c / "elements.json", {"issues": []})
        cv2.imwrite(str(c / "wall_mask.png"), np.zeros((1000, 1000), np.uint8))
        rows3.append({"index": k, "params": {"strategy": "S2", "sauvola_k": 0.2, "t_min": 80, "t_max": 450, "l_fix": 0},
                      "error": None, "line_len_m": line_len_m})
        d = st / "04_rooms" / "candidates" / str(k)
        d.mkdir(parents=True)
        write_json(d / "spec.json", spec.model_dump(mode="json"))
        rows4.append({"index": k, "error": None})
    write_json(st / "03_extract" / "candidates.json", rows3)
    write_json(st / "04_rooms" / "candidates.json", rows4)
    return project, st / "05_validate"


def test_no_valid_candidate_needs_attention_without_spec(tmp_path):
    el = box_elements()
    el["openings"] = [door(0, 7900)]  # runs past the wall end: V008
    spec, _ = assemble_spec(el, GRID, [], META)
    spec.openings[0].offset = 7900
    project, work = fake_run(tmp_path, {0: spec})
    r = stage_validate(project, work, "r")
    assert r["status"] == "needs_attention" and "V008" in r["message"]
    assert SpecStore(project / "specs").head() is None


def test_stage_validate_saves_the_best_candidate(tmp_path):
    good, _ = assemble_spec(box_elements(), GRID, [], META)
    worse, _ = assemble_spec(box_elements(openings=[]), GRID, [], META)  # rooms without doors: V012
    project, work = fake_run(tmp_path, {0: worse, 1: good})
    r = stage_validate(project, work, "r")
    assert r["metrics"]["version"] == 1 and r["metrics"]["candidate"] == 1
    saved = SpecStore(project / "specs").load(1)
    assert saved.meta.source == "pipeline" and saved.meta.run_id == "r"
    for f in ("scores.json", "chosen.json", "issues.json", "overlay_ids.png", "wall_mask.png",
              "layers/walls.png", "layers/doors.png", "layers/columns.png", "layers/rooms.png"):
        assert (work / f).exists(), f
    assert cv2.imread(str(work / "layers" / "rooms.png"), cv2.IMREAD_UNCHANGED).shape == (1000, 1000, 4)
    assert cv2.imread(str(work / "wall_mask.png"), cv2.IMREAD_GRAYSCALE).shape == (500, 500)
    assert json.loads((work / "chosen.json").read_text())["index"] == 1


def test_reextraction_carries_over(tmp_path):
    spec, _ = assemble_spec(box_elements(), GRID, [], META)
    project, work = fake_run(tmp_path, {0: spec})
    stage_validate(project, work, "r")
    store = SpecStore(project / "specs")
    store.commit_ops(1, [{"op": "set_wall_height", "id": "W2", "height": 4500}], "editor")
    shutil.rmtree(work)
    r = stage_validate(project, work, "r")
    v3 = store.load(3)
    assert r["metrics"]["version"] == 3 and next(w for w in v3.walls if w.id == "W2").height == 4500
    assert json.loads((work / "carryover.json").read_text())["matched"]["walls"] == len(v3.walls)


@pytest.mark.slow
def test_stage_validate_gatsu(tmp_path):
    from core.extraction.stages import stage_extract, stage_rooms
    from tests.extraction.geometry.gatsu import gatsu_stages

    src = gatsu_stages()
    project = tmp_path / "p"
    shutil.copytree(src.parents[2] / "input", project / "input")
    stages = project / "runs" / "r" / "stages"
    for d in ("00_input", "01_preprocess", "02_grid"):
        shutil.copytree(src / d, stages / d)
    stage_extract(project, stages / "03_extract", 12)
    stage_rooms(project, stages / "04_rooms")
    r = stage_validate(project, stages / "05_validate", "r")
    assert r["status"] in ("succeeded", "needs_attention") and r["metrics"]["version"] == 1
    assert cv2.imread(str(stages / "05_validate" / "wall_mask.png"), cv2.IMREAD_GRAYSCALE).shape == (945, 1600)


def test_choose_skips_candidates_below_60_percent_coverage():
    """An almost empty candidate breaks almost no rule (Gatsu S1: 1 wall, score 0.997): coverage decides first."""
    empty = {"index": 0, "score": 0.997, "passed": True, "coverage": 0.01}
    real = {"index": 1, "score": 0.82, "passed": True, "coverage": 0.8}
    assert choose([empty, real])["index"] == 1
    assert choose([empty])["index"] == 0  # nothing covers enough: the best of what passed


def test_coverage_uses_one_estimate_for_the_drawing(tmp_path):
    good, _ = assemble_spec(box_elements(), GRID, [], META)  # 31 m of walls
    project, work = fake_run(tmp_path, {0: good})
    rows = json.loads((work.parent / "03_extract" / "candidates.json").read_text())
    rows.append(rows[0] | {"index": 1, "line_len_m": 100})  # another candidate saw 100 m of lines
    write_json(work.parent / "03_extract" / "candidates.json", rows)
    stage_validate(project, work, "r")
    assert json.loads((work / "scores.json").read_text())[0]["coverage"] == pytest.approx(0.31, abs=0.01)


def test_crop_ocr_keeps_only_room_labels_and_skips_typed_rooms():
    el = box_elements()
    el["stairs"] = [{"flights": [{"start": [1000, 1000], "end": [1000, 3500], "width": 1000, "risers": 14}],
                     "landings": [], "confidence": 0.9, "direction_source": "text"}]
    spec, _ = assemble_spec(el, GRID, [], META)  # west room: stair, east room: other
    page = np.full((1000, 1000), 255, np.uint8)
    to_px = px_from_mm(GRID["px_to_mm_original"])
    for text, at in (("NAIK", (1800, 2500)), ("ROUTE CABLE", (5500, 2500))):
        u, v = (round(t) for t in to_px(*at))
        cv2.putText(page, text, (u, v), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2, cv2.LINE_AA)
    assert crop_labels(page, spec, GRID["px_to_mm_original"]) == []


def test_label_of_unknown_type_keeps_the_geometric_room_type():
    from core.spec.rooms import RoomLabel, rebuild_rooms

    el = box_elements()
    el["stairs"] = [{"flights": [{"start": [1000, 1000], "end": [1000, 3500], "width": 1000, "risers": 14}],
                     "landings": [], "confidence": 0.9, "direction_source": "text"}]
    spec, _ = assemble_spec(el, GRID, [], META)
    out = rebuild_rooms(spec, [RoomLabel((2000, 2500), "ANEL", "other")])
    room = next(r for r in out.rooms if r.name == "ANEL")
    assert room.type == "stair"


def test_coverage_cut_is_relative_on_cluttered_plans():
    """Furniture lines inflate the line estimate: every candidate may sit below 60%, the empty one must still lose."""
    empty = {"index": 0, "score": 0.997, "passed": True, "coverage": 0.01}
    real = {"index": 1, "score": 0.82, "passed": True, "coverage": 0.4}
    assert choose([empty, real])["index"] == 1


def test_over_reading_candidate_is_left_out():
    """M9 (synthetic s01): S1 read both faces of every double wall: more wall than the drawing holds (1.26)."""
    s1 = {"index": 8, "score": 0.89, "passed": True, "coverage": 1.26}
    s2 = {"index": 0, "score": 0.878, "passed": True, "coverage": 0.91}
    assert choose([s1, s2])["index"] == 0


def test_all_over_reading_still_chooses():
    a = {"index": 0, "score": 0.8, "passed": True, "coverage": 1.2}
    b = {"index": 1, "score": 0.9, "passed": True, "coverage": 1.3}
    assert choose([a, b])["index"] == 1


def test_coverage_cut_uses_the_remaining_candidates():
    """The 60 % cut is taken from the candidates left after the over-reading one is gone (0.6 x 1.37 would drop 0.45
    and keep the over-reader in play)."""
    over = {"index": 9, "score": 0.89, "passed": True, "coverage": 1.37}
    s2 = {"index": 5, "score": 0.84, "passed": True, "coverage": 0.85}  # synthetic s04's numbers
    weak = {"index": 6, "score": 0.86, "passed": True, "coverage": 0.45}
    assert choose([over, s2, weak])["index"] == 5


def test_an_overflowing_correct_candidate_is_kept_when_only_sparse_ones_remain():
    """M9 final review: on a plan with diagonal or single-line walls the estimate runs low and the right S2 can pass
    1.05; dropping it must not hand the choice to an almost empty S1 (the MIN_COVERAGE failure)."""
    s2 = {"index": 0, "score": 0.86, "passed": True, "coverage": 1.1}
    sparse = {"index": 9, "score": 0.97, "passed": True, "coverage": 0.3}
    assert choose([s2, sparse])["index"] == 0
