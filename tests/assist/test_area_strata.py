"""Area assist against the real Strata (design §7). Run: uv run --env-file .env pytest -q tests/assist/test_area_strata.py -m strata"""

import json
import math
from pathlib import Path

import pytest

from core.assist.session import Session, run_turn
from core.config import load_settings
from core.llm_review.client import StrataClient
from core.spec.models import Spec, Wall

pytestmark = pytest.mark.strata


@pytest.fixture(scope="module")
def strata() -> StrataClient:
    client = StrataClient.from_settings(load_settings())
    if not client.health():
        pytest.skip("Strata not reachable")
    return client


@pytest.fixture(scope="module")
def drawing():
    from core.extraction.preprocess import load_raster, preprocess

    gt = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    a, b, c, d, e, f = gt.meta.px_to_mm
    r = preprocess(load_raster(Path("floorplan/plan.jpeg")))
    return gt, r.page, r.binary, [a / 2, b / 2, c, d / 2, e / 2, f]


def with_walls(spec: Spec, *walls: Wall) -> Spec:
    return spec.model_copy(update={"walls": [*spec.walls, *walls]})


def ask(strata, drawing, spec, box, message, selection=(), tmp_path=None, answer=None):
    """One turn; with `answer`, a question from Strata gets that reply in the same session (the real chat flow)."""
    _, page, binary, t = drawing
    s = Session(id="t", project_id="p", box=box, selection=list(selection))
    events = list(run_turn(strata, s, message, spec, [], page, binary, t, tmp_path))
    if answer and any(e["event"] == "question" for e in events):
        events = list(run_turn(strata, s, answer, spec, [], page, binary, t, tmp_path))
    print(json.dumps([e for e in events if e["event"] != "step"], indent=1)[:3000])
    return events


def proposal(events) -> dict:
    p = next((e for e in events if e["event"] == "proposal"), None)
    assert p is not None, [e for e in events if e["event"] != "step"]
    return p


def test_duplicate_walls_merge_onto_the_drawn_line(strata, drawing, tmp_path):
    gt = drawing[0]
    spec = with_walls(gt, Wall(id="W900", a=(5910, 11690), b=(5910, 6000), thickness=150, kind="interior"))
    p = proposal(ask(strata, drawing, spec, (5300, 6500, 6500, 11000), "dua dinding dobel, satukan", tmp_path=tmp_path))
    assert p["valid"] and {"W43", "W900"} <= set(p["deleted"])
    assert len(p["added"]) == 1 and all(abs(pt[0] - 5790) <= 80 for pt in (p["added"][0]["a"], p["added"][0]["b"]))


STRAY = Wall(id="W901", a=(11000, 8000), b=(12500, 8000), thickness=100, kind="partition")


def test_delete_this_with_a_selection(strata, drawing, tmp_path):
    spec = with_walls(drawing[0], STRAY)
    p = proposal(ask(strata, drawing, spec, (9500, 6200, 14500, 10500), "hapus dinding ini", ["W901"], tmp_path))
    assert p["valid"] and p["deleted"] == ["W901"]


def test_delete_this_without_a_selection_asks(strata, drawing, tmp_path):
    spec = with_walls(drawing[0], STRAY)
    events = ask(strata, drawing, spec, (5500, 5500, 16500, 12000), "hapus dinding ini", tmp_path=tmp_path)
    assert any(e["event"] == "question" for e in events)


def test_stair_area_keeps_the_exterior(strata, drawing, tmp_path):
    gt = drawing[0]
    square = [((2000, 7000), (3000, 7000)), ((3000, 7000), (3000, 8000)), ((3000, 8000), (2000, 8000)),
              ((2000, 8000), (2000, 7000))]
    spec = with_walls(gt, *(Wall(id=f"W{910 + i}", a=a, b=b, thickness=100, kind="partition")
                            for i, (a, b) in enumerate(square)))
    p = proposal(ask(strata, drawing, spec, (-1400, 5600, 5700, 10100), "rapikan area ini, jadikan ruang tangga",
                     tmp_path=tmp_path, answer="ruang tempat tangga S1; hapus kotak kecil W910-W913 di dalamnya"))
    exterior = {w.id for w in gt.walls if w.kind == "exterior"}
    assert not exterior & set(p["deleted"])
    assert {"W910", "W911", "W912", "W913"} <= set(p["deleted"])


def test_missing_door_is_added_at_the_gap(strata, drawing, tmp_path):
    gt = drawing[0]
    spec = gt.model_copy(update={"openings": [o for o in gt.openings if o.id != "D2"]})
    p = proposal(ask(strata, drawing, spec, (8000, 5300, 10000, 6700), "tambah pintu di sini", ["W51"], tmp_path))
    door = next(o for o in p["openings"] if o["category"] == "door")
    centre = ((door["a"][0] + door["b"][0]) / 2, (door["a"][1] + door["b"][1]) / 2)
    assert p["valid"] and math.dist(centre, (9035, 6000)) <= 300
