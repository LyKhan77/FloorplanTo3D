from pathlib import Path

from benchmarks.tools.gt_author import load_gt
from core.spec.models import Spec
from core.spec.validate import validate

GT = Path("benchmarks/gatsu/gt_spec.json")


def _gt() -> Spec:
    return Spec.model_validate_json(GT.read_text())


def test_gatsu_gt_valid_and_scored():
    r = validate(_gt())
    assert r.passed and r.score >= 0.95, [(i.code, i.element_ids) for i in r.issues]


def test_gatsu_gt_matches_yaml():
    exclude = {"meta": {"created_at"}}
    assert load_gt(Path("benchmarks/gatsu/gt.yaml")).model_dump(exclude=exclude) == _gt().model_dump(exclude=exclude)


def test_gatsu_gt_scope():
    s = _gt()
    names = {r.name for r in s.rooms}
    for n in ("R. MEETING", "GUDANG", "PANTRY", "GALERY", "BATTERY ROOM", "AHU ROOM", "MDF ROOM", "CAPASITOR ROOM"):
        assert n in names
    assert len(s.stairs) >= 1 and any(c.kind == "pilaster" for c in s.columns)
    assert {a.label for a in s.grid.axes} == set("ABCDEF123")
    assert len(s.meta.building_outline) == 2
