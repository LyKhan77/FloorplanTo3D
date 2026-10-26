import json

import pytest

from tests.server.conftest import wait_status

pytestmark = pytest.mark.slow


def fast_build(ctx):
    return {"status": "succeeded"}


def test_upload_runs_extraction_and_manual_scale_rerun(app_factory, plan_bytes):
    with app_factory(stage_impls={n: fast_build for n in range(7, 11)}) as client:
        r = client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")}, data={"name": "e"})
        pid, rid = r.json()["project_id"], r.json()["run_id"]
        run = wait_status(client, pid, rid, {"needs_attention", "failed", "succeeded"}, timeout=180)
        assert [s["status"] for s in run["stages"][:3]] == ["succeeded"] * 3, run
        assert run["stages"][2]["metrics"]["axes_v"] == 6
        assert run["status"] == "succeeded" and run["stages"][5]["metrics"]["version"] == 1
        grid = client.get(f"/api/projects/{pid}/runs/{rid}/artifacts/02_grid/grid.json").json()
        assert grid["scale_source"] == "grid_dimensions"

        # rerun from stage 2 with a manual scale: stages 0-1 are copied from the previous run
        r = client.post(f"/api/projects/{pid}/runs",
                        json={"kind": "from_stage", "from_stage": 2, "params_override": {"mm_per_px": 26.5}})
        rid2 = r.json()["run_id"]
        run = wait_status(client, pid, rid2, {"needs_attention", "failed", "succeeded"}, timeout=180)
        assert [s["status"] for s in run["stages"][:3]] == ["skipped", "skipped", "succeeded"], run
        grid = client.get(f"/api/projects/{pid}/runs/{rid2}/artifacts/02_grid/grid.json").json()
        assert grid["scale_source"] == "manual" and grid["mm_per_px"] == pytest.approx(26.5)
        assert any("berbeda" in w for w in run["stages"][2]["warnings"])
        listed = client.get(f"/api/projects/{pid}/runs/{rid2}/stages/1").json()["artifacts"]
        assert "01_preprocess/page.png" in listed
        assert json.loads(json.dumps(run))["params_override"] == {"mm_per_px": 26.5}
