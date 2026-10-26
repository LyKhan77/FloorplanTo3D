import pytest

from core.spec.derive import derive
from core.spec.models import Flight, PlacedObject, Stair, Wall
from core.spec.validate import WEIGHTS, TemplateLimits, ValidationContext, validate
from tests.spec.fixtures import spec_with_rooms

CTX = ValidationContext(
    ocr_dimensions=[("A", "B", 10000)],
    thick_line_length_mm=40000,
    templates={"rack@1.0.0": TemplateLimits(min=(600, 1000, 1800), max=(800, 1400, 2400))},
)


def test_valid_fixture_scores_one():
    r = validate(spec_with_rooms())
    assert r.passed and r.score == pytest.approx(1.0) and r.issues == []


def test_valid_fixture_scores_one_with_ctx():
    r = validate(spec_with_rooms(), CTX)
    assert r.passed and r.score == pytest.approx(1.0) and r.issues == []


def test_weights_sum_to_one():
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


def _edit(fn):
    def mutate(s):
        s = s.model_copy(deep=True)
        fn(s)
        return derive(s)
    return mutate


def _door(s, did):
    return next(o for o in s.openings if o.id == did)


def _rack(pos, dims=(600, 1200, 2000)):
    return PlacedObject(id="O1", template_id="rack", template_version="1.0.0", position=pos, dims=dims)


CASES = [
    ("V001", _edit(lambda s: setattr(s.meta, "px_to_mm", [0, 0, 0, 0, 0, 0])), "error"),
    ("V002", _edit(lambda s: setattr(s.openings[0], "wall_id", "W99")), "error"),
    ("V003", _edit(lambda s: s.walls.append(Wall(id="W9", a=(2000, 3000), b=(2050, 3000), thickness=100,
                                                   kind="partition", free_ends=True))), "warning"),
    ("V004", _edit(lambda s: s.walls.append(Wall(id="W9", a=(2000, 2000), b=(3000, 2000), thickness=100,
                                                   kind="partition"))), "warning"),
    ("V005", _edit(lambda s: setattr(s.walls[0], "thickness", 700)), "warning"),
    ("V006", _edit(lambda s: setattr(s.walls[4], "b", (5200, 6000))), "warning"),
    ("V007", _edit(lambda s: s.walls.append(s.walls[4].model_copy(update={"id": "W9"}))), "warning"),
    ("V008", _edit(lambda s: setattr(_door(s, "D2"), "offset", 9000)), "error"),
    ("V009", _edit(lambda s: s.openings.append(_door(s, "D1").model_copy(update={"id": "D9", "offset": 2400}))), "error"),
    ("V010", _edit(lambda s: setattr(_door(s, "D1"), "width", 500)), "warning"),
    ("V011", _edit(lambda s: setattr(s.rooms[0], "polygon", [(0, 0), (1000, 1000), (1000, 0), (0, 1000)])), "error"),
    ("V012", _edit(lambda s: setattr(s, "openings", [])), "warning"),
    ("V013", lambda s: s, "warning"),
    ("V014", _edit(lambda s: setattr(s.columns[0], "center", (300, 0))), "warning"),
    ("V015", _edit(lambda s: [setattr(r, "name", "") for r in s.rooms]), "warning"),
    ("V016", _edit(lambda s: s.objects.append(_rack((2000, 2000, 0), (600, 1200, 3000)))), "warning"),
    ("V017", _edit(lambda s: s.objects.append(_rack((5000, 3000, 0)))), "info"),
    ("V018", lambda s: s, "warning"),
    ("V019", _edit(lambda s: s.stairs.append(Stair(id="S1", flights=[
        Flight(start=(1000, 1000), end=(1000, 2000), width=1000, risers=4)]))), "warning"),
]
CTX_OVERRIDE = {
    "V013": ValidationContext(ocr_dimensions=[("A", "B", 9000)]),
    "V018": ValidationContext(thick_line_length_mm=200000),
}


@pytest.mark.parametrize("code,mutate,severity", CASES, ids=[c[0] for c in CASES])
def test_rule_flags_violation(code, mutate, severity):
    r = validate(mutate(spec_with_rooms()), CTX_OVERRIDE.get(code, CTX))
    assert any(i.code == code and i.severity == severity for i in r.issues), r.issues
    assert r.passed == (severity != "error")
    if code in WEIGHTS:
        assert r.ratios[code] > 0 and r.score < 1.0


