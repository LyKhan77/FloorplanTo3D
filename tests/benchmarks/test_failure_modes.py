import cv2
import numpy as np
import pytest

from benchmarks.failure_modes import (
    classify_false,
    classify_missed,
    classify_rooms,
    ink_profile,
    wall_coverage,
)
from core.extraction.rooms.overlay import px_from_mm
from core.spec.models import Provenance, Room, Wall
from tests.spec.fixtures import spec_with_rooms, two_room_spec

TO_PX = px_from_mm([10, 0, 0, 0, -10, 6000])  # 10 mm per px, y up; page 600 x 600 px


def wall(wid, a, b, t=200, conf=0.9):
    return Wall(id=wid, a=a, b=b, thickness=t, kind="interior", provenance=Provenance(source="cv", confidence=conf))


def line(img, a_mm, b_mm):
    pa, pb = (tuple(round(v) for v in TO_PX(*p)) for p in (a_mm, b_mm))
    cv2.line(img, pa, pb, 255, 2)


def missed_fixture():
    """W1 drawn as two faces, W2 one face, W3 not drawn, W4 drawn but absent after masking."""
    gt = two_room_spec().model_copy(update={"walls": [
        wall("W1", (1000, 5000), (4000, 5000)), wall("W2", (1000, 3000), (4000, 3000)),
        wall("W3", (1000, 1000), (4000, 1000)), wall("W4", (5000, 1000), (5000, 4000))], "openings": [], "columns": []})
    binary = np.zeros((600, 600), np.uint8)
    line(binary, (1000, 4900), (4000, 4900))
    line(binary, (1000, 5100), (4000, 5100))
    line(binary, (1000, 2900), (4000, 2900))
    clean = binary.copy()
    line(binary, (4900, 1000), (4900, 4000))
    line(binary, (5100, 1000), (5100, 4000))
    return gt, binary, clean


def test_ink_profile_reads_each_offset():
    gt, binary, _ = missed_fixture()
    w2 = gt.walls[1]
    left, centre, right = ink_profile(binary, w2, TO_PX, (-100, 0, 100))
    assert centre == 0.0 and max(left, right) == 1.0 and min(left, right) == 0.0


def test_classify_missed_modes():
    gt, binary, clean = missed_fixture()
    pred = gt.model_copy(update={"walls": []})
    modes = {r["id"]: r["mode"] for r in classify_missed(gt, pred, binary, clean, TO_PX)}
    assert modes == {"W1": "double", "W2": "single", "W3": "faint", "W4": "erased"}


def test_found_walls_are_not_missed():
    gt, binary, clean = missed_fixture()
    assert [r["id"] for r in classify_missed(gt, gt, binary, clean, TO_PX)] == []


def test_wall_coverage_partial():
    ref = wall("R", (0, 0), (2000, 0))
    # x 1000-2000 lies along the reference; up to ~2141 is still within 150 mm of its end point (50 mm off)
    assert wall_coverage(wall("X", (1000, 50), (3000, 50)), [ref]) == pytest.approx(1141 / 2000, abs=0.02)
    assert wall_coverage(wall("Y", (0, 400), (2000, 400)), [ref]) == 0.0


def test_classify_false_regions():
    gt = two_room_spec()
    hatch = np.zeros((600, 600), np.uint8)
    hatch[50:150, 50:300] = 255  # x 500-3000 mm, y 4500-5500 mm
    pred = gt.model_copy(update={"walls": [*gt.walls,
                                           wall("W8", (6000, 2000), (8000, 2000), conf=0.4),   # alone in a room
                                           wall("W9", (1000, 5000), (2500, 5000), conf=0.4),   # inside the hatch
                                           wall("W10", (6000, 3500), (8000, 3500), conf=0.4)]})  # next to a label
    masks = {"hatch": hatch, "symbol": np.zeros_like(hatch), "stair": np.zeros_like(hatch)}
    texts = [{"text": "NYY 4x1C", "cls": "annotation", "at_mm": (7000, 3800)}]
    regions = {r["id"]: r["region"] for r in classify_false(pred, gt, masks, texts, TO_PX)}
    assert regions == {"W8": "free_end", "W9": "hatch", "W10": "text"}


def test_classify_rooms_counts_merges():
    gt = spec_with_rooms()
    gt.rooms.append(Room(id="R3", type="outdoor", polygon=[(-1000, 0), (-200, 0), (-200, 6000), (-1000, 6000)]))
    pred = gt.model_copy(update={"rooms": [Room(id="R1", polygon=[(100, 100), (9900, 100), (9900, 5900), (100, 5900)])]})
    out = classify_rooms(gt, pred)
    assert (out["inner_gt"], out["inner_matched"], out["outdoor_gt"], out["outdoor_matched"]) == (2, 0, 1, 0)
    assert out["merged"] == [["R1", "R2"]]
    assert classify_rooms(gt, gt)["inner_matched"] == 2


# --- leaks (M7d) ------------------------------------------------------------------------------------------------

def _rooms(spec):
    from core.spec.rooms import rebuild_rooms

    return rebuild_rooms(spec.model_copy(update={"rooms": []}))


def test_leak_through_an_open_door():
    from benchmarks.failure_modes import classify_leaks

    gt = spec_with_rooms()
    pred = gt.model_copy(deep=True)
    pred.openings = [o for o in pred.openings if o.id != "D1"]
    pred.walls = [w for w in pred.walls if w.id != "W5"] + [wall("W8", (5000, 0), (5000, 2000), t=100),
                                                             wall("W9", (5000, 2900), (5000, 6000), t=100)]
    rows = classify_leaks(gt, _rooms(pred))
    assert [(sorted(r["gt_rooms"]), r["cause"], r["wall"]) for r in rows] == [(["R1", "R2"], "door_gap", "W5")]


def test_leak_through_a_missing_wall():
    from benchmarks.failure_modes import classify_leaks

    gt = spec_with_rooms()
    gt.openings = [o for o in gt.openings if o.id != "D1"]
    pred = gt.model_copy(deep=True)
    pred.walls = [w for w in pred.walls if w.id != "W5"]
    rows = classify_leaks(gt, _rooms(pred))
    assert [(r["cause"], r["wall"]) for r in rows] == [("wall_missing", "W5")]


def test_no_leak_no_rows():
    from benchmarks.failure_modes import classify_leaks

    gt = spec_with_rooms()
    assert classify_leaks(gt, gt) == []
