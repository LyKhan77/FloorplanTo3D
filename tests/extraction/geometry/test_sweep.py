import shutil

import pytest

from core.extraction.geometry.sweep import run_sweep, sweep_params


def boom_on_one(index: int, params: dict) -> dict:
    if index == 1:
        raise ValueError("bad candidate")
    return {"index": index, "walls": [1] * (index + 1)}


def test_sweep_params_order_and_cap():
    p = sweep_params(12)
    assert len(p) == 12 and p[0] == {"strategy": "S2", "sauvola_k": 0.2, "t_min": 80, "t_max": 450, "l_fix": 0}
    assert len({tuple(sorted(x.items())) for x in p}) == 12
    assert len(sweep_params(50)) == 16
    assert [x["strategy"] for x in sweep_params(16)][:8] == ["S2"] * 8


def test_failing_candidate_does_not_stop_others():
    out = run_sweep(boom_on_one, [{}, {}, {}], workers=2)
    assert [r.get("index") for r in out] == [0, None, 2]
    assert "bad candidate" in out[1]["error"]


@pytest.mark.slow
def test_stage_extract_writes_candidates_and_is_deterministic(tmp_path):
    import json

    from core.extraction.stages import stage_extract
    from tests.extraction.geometry.gatsu import gatsu_stages

    src = gatsu_stages()
    project = src.parents[2]
    runs = []
    for name in ("r1", "r2"):
        stages = tmp_path / name / "stages"
        for d in ("00_input", "01_preprocess", "02_grid"):
            shutil.copytree(src / d, stages / d)
        res = stage_extract(project, stages / "03_extract", 4)
        assert res["status"] == "succeeded" and res["metrics"]["candidates"] == 4
        runs.append(stages / "03_extract")
    a, b = runs
    assert (a / "candidates.json").read_bytes() == (b / "candidates.json").read_bytes()
    for k in range(4):
        assert (a / f"candidates/{k}/elements.json").read_bytes() == (b / f"candidates/{k}/elements.json").read_bytes()
        assert (a / f"candidates/{k}/overlay.png").is_file()
    summary = json.loads((a / "candidates.json").read_text())
    assert summary[0]["params"]["strategy"] == "S2" and summary[0]["counts"]["walls"] > 0
    assert (a / "masks/stair.png").is_file() and (a / "masks/hatch.png").is_file()
