"""Drawing fit (stage 8): is every wall on a line of the drawing?"""

import json
from pathlib import Path

import cv2
import pytest

from core.spec.models import Spec
from core.verify.fit import drawing_fit

GT = Path("benchmarks/gatsu/gt_spec.json")
PLAN = Path("floorplan/plan.jpeg")


@pytest.fixture(scope="module")
def gray():
    return cv2.imread(str(PLAN), cv2.IMREAD_GRAYSCALE)


def gt() -> Spec:
    return Spec.model_validate(json.loads(GT.read_text()))


def test_gt_fits_the_drawing(gray):
    r = drawing_fit(gt(), gray)
    assert r["fit"] >= 0.90
    assert set(r["walls_off"]) <= {"W30", "W64"}  # two GT walls with no drawn line under them
    assert r["checked"] > 70 and r["tolerance_mm"] == 50


def test_shifted_model_does_not_fit(gray):
    s = gt()
    for w in s.walls:
        w.a, w.b = (w.a[0] + 300, w.a[1]), (w.b[0] + 300, w.b[1])
    assert drawing_fit(s, gray)["fit"] < 0.90


def test_one_misplaced_wall_is_listed(gray):
    s = gt()
    w = next(x for x in s.walls if x.id == "W1")
    w.a, w.b = (w.a[0], w.a[1] + 1500), (w.b[0], w.b[1] + 1500)
    assert "W1" in drawing_fit(s, gray)["walls_off"]


def test_walls_without_samples_are_skipped(gray):
    s = gt()
    w = s.walls[0]
    s.walls[0].a, s.walls[0].b = (90000, 90000), (91000, 90000)  # off the drawing, but fully spanned by an opening
    s.openings = [o for o in s.openings if o.wall_id != w.id]
    door = next(o for o in gt().openings).model_copy(update={"id": "D999", "wall_id": w.id, "offset": 0, "width": 1000})
    s.openings.append(door)
    r = drawing_fit(s, gray)
    assert w.id not in r["walls_off"]
    assert r["checked"] == drawing_fit(gt(), gray)["checked"] - 1


def test_no_transform_gives_none(gray):
    s = gt()
    s.meta.px_to_mm = []
    assert drawing_fit(s, gray)["fit"] is None
