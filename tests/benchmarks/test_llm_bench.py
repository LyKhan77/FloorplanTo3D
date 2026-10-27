import json

from benchmarks.llm_items import build_items_from_specs, evaluation, score_task, typo_variants
from benchmarks.run_llm_bench import main
from core.spec.models import Opening, Provenance, Wall
from tests.spec.fixtures import spec_with_rooms


def cv(conf: float, **ev) -> Provenance:
    return Provenance(source="cv", confidence=conf, evidence=ev)


def cv_spec():
    """GT = spec_with_rooms. W1 exact, W2 60 mm off (wall), W6 far from any GT wall (annotation), W7 half on W3
    (ambiguous); D1 on the GT door, D9 nowhere near a GT door."""
    s = spec_with_rooms()
    s.walls = [
        Wall(id="W1", a=(0, 0), b=(10000, 0), thickness=200, kind="exterior", provenance=cv(0.7)),
        Wall(id="W2", a=(10060, 0), b=(10060, 6000), thickness=200, kind="exterior", provenance=cv(0.45)),
        Wall(id="W5", a=(5000, 0), b=(5000, 6000), thickness=100, kind="interior", provenance=cv(0.9)),
        Wall(id="W6", a=(1000, 3000), b=(3000, 3000), thickness=100, kind="partition", provenance=cv(0.4, pair_overlap=0.8)),
        Wall(id="W7", a=(8000, 6000), b=(12000, 6000), thickness=200, kind="exterior", provenance=cv(0.5)),
    ]
    s.openings = [
        Opening(id="D1", category="door", wall_id="W5", offset=2000, width=900, door_type="single_swing", hinge="end",
                swing="right", provenance=cv(0.4, arc=True)),
        Opening(id="D9", category="door", wall_id="W1", offset=6500, width=900, door_type="opening",
                provenance=cv(0.3, gap=True)),
    ]
    return s


LABELS = [("PANTRI", (2000, 2000)), ("GUDANG", (7000, 3000)), ("NOWHERE", (50000, 50000)),
          ("PRDPDSED", (3000, 3000))]  # an annotation the OCR classed as a room label: not the room's name


def gt_spec():
    gt = spec_with_rooms()
    gt.rooms[0].name, gt.rooms[1].name = "PANTRY", "GUDANG"
    return gt


def items(balance=True):
    return build_items_from_specs({0: cv_spec()}, gt_spec(), LABELS, balance=balance)


def test_t1_labels_by_centreline_match():
    lab = {i["element"]: i["label"]["verdict"] for i in items(balance=False)["T1"]}
    assert lab["W1"] == "wall" and lab["W2"] == "wall" and lab["W6"] == "annotation"
    assert "W7" not in lab  # half on a GT wall: ambiguous
    w2 = next(i for i in items(balance=False)["T1"] if i["element"] == "W2")
    assert w2["baseline"] == {"verdict": "annotation"} and w2["candidate"] == 0  # CV confidence 0.45 < 0.5


def test_t2_negatives_capped(monkeypatch):
    import benchmarks.llm_items as li

    monkeypatch.setattr(li, "T2_MAX_NEGATIVES", 0)
    assert all(i["label"]["is_door"] for i in items()["T2"])


def test_t1_is_balanced():
    t1 = items()["T1"]
    walls = sum(i["label"]["verdict"] == "wall" for i in t1)
    assert walls == sum(i["label"]["verdict"] == "annotation" for i in t1) == 1  # 3 walls subsampled to 1


def test_t2_labels_from_gt_and_negatives():
    t2 = {i["element"]: i for i in items()["T2"]}
    assert t2["D1"]["label"] == {"is_door": True, "door_type": "single_swing", "hinge": "start", "swing": "left"}
    assert t2["D1"]["baseline"] == {"is_door": True, "door_type": "single_swing", "hinge": "end", "swing": "right"}
    assert t2["D9"]["label"]["is_door"] is False


def test_t3_labels_types_and_typos():
    t3 = items()["T3"]
    base = [i for i in t3 if not i["synthetic"]]
    assert {(i["text"], i["label"]["type"]) for i in base} == {("PANTRI", "office"), ("GUDANG", "storage")}
    assert "PRDPDSED" not in {i["text"] for i in t3}
    assert {i["text"] for i in t3 if i["synthetic"]} >= {"PANRI", "GUDNG"}
    assert all("baseline" in i and "room" in i for i in t3)


def test_typo_variants_deterministic():
    assert typo_variants("PANTRY") == ["PANRY", "PATNRY"]
    assert typo_variants("BATTERY ROOM")[-1] == "BATTERY R0OM"
    assert typo_variants("PANTRY") == typo_variants("PANTRY")


def test_fewshot_items_excluded_from_eval():
    every = items()
    for rows in every.values():
        shots = {i["id"] for i in rows if i["fewshot"]}
        assert not shots & {i["id"] for i in evaluation(rows)}
    assert any(i["fewshot"] for i in every["T3"])


def test_oracle_passes_and_baseline_fails_gate():
    rows = [{"id": f"x{i}", "label": {"verdict": v}, "baseline": {"verdict": v}, "fewshot": False}
            for i, v in enumerate(["wall"] * 10 + ["annotation"] * 10)]
    rows[0]["baseline"] = {"verdict": "annotation"}  # baseline 95%
    oracle = score_task("T1", rows, {r["id"]: r["label"] for r in rows})
    assert oracle["accuracy"] == 1.0 and oracle["delete_precision"] == 1.0 and oracle["passes"] is True
    same = score_task("T1", rows, {r["id"]: r["baseline"] for r in rows})
    assert same["passes"] is False and same["baseline_accuracy"] == 0.95


def test_t1_delete_precision_gate():
    rows = [{"id": f"x{i}", "label": {"verdict": v}, "baseline": {"verdict": "wall"}, "fewshot": False}
            for i, v in enumerate(["wall"] * 10 + ["annotation"] * 10)]
    answers = {r["id"]: {"verdict": "annotation"} for r in rows[8:]}  # 2 real walls called annotation
    answers |= {r["id"]: {"verdict": "wall"} for r in rows[:8]}
    rep = score_task("T1", rows, answers)
    assert rep["accuracy"] == 0.9 and rep["delete_precision"] == 10 / 12 and rep["passes"] is False


def test_invalid_answers_count_wrong():
    rows = [{"id": "a", "label": {"verdict": "wall"}, "baseline": {"verdict": "wall"}, "fewshot": False}]
    rep = score_task("T1", rows, {"a": None})
    assert rep["accuracy"] == 0.0 and rep["invalid_rate"] == 1.0


def test_t2_gate_needs_hinge_and_swing_gain():
    rows = [{"id": f"d{i}", "label": {"is_door": True, "door_type": "single_swing", "hinge": "start", "swing": "left"},
             "baseline": {"is_door": True, "door_type": "single_swing", "hinge": "end", "swing": "left"}, "fewshot": False}
            for i in range(10)]
    rep = score_task("T2", rows, {r["id"]: r["label"] for r in rows})
    assert rep["per_field"]["hinge"] == 1.0 and rep["baseline_per_field"]["hinge"] == 0.0
    assert rep["passes"] is False  # swing equals the baseline: no +10 points


def test_t0_scores_merged_fields():
    rows = [{"id": "p1", "prompt": "tinggi 4.5 m, lantai dua", "expected": {"wall_height": 4500, "floor_name": "Lantai 2"},
             "fewshot": False}]
    rep = score_task("T0", rows, {"p1": {"floor_name": "Lantai 2", "wall_height": 3000}})  # rule wins wall_height
    assert rep["accuracy"] == 1.0 and rep["baseline_accuracy"] == 0.8 and rep["passes"] is True


def test_report_written(tmp_path):
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    rows = [{"id": f"x{i}", "task": "T1", "candidate": 0, "element": "W1", "label": {"verdict": v},
             "baseline": {"verdict": "wall"}, "fewshot": False} for i, v in enumerate(["wall", "annotation"] * 5)]
    (items_dir / "T1.json").write_text(json.dumps(rows))
    rep = main(["--task", "T1", "--items", str(items_dir), "--out-dir", str(tmp_path), "--fake-oracle"])
    assert rep["passes"] is True and rep["n"] == 10
    assert (tmp_path / "llm-T1-v1-ev-fs.md").exists()
    assert json.loads((tmp_path / "llm-T1-v1-ev-fs.json").read_text())["accuracy"] == 1.0
