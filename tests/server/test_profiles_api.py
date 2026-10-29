from core.extraction.stages import write_json
from tests.server.conftest import wait_status
from tests.server.test_orchestrator import fake_impls

PARAMS = {"strategy": "S2", "sauvola_k": 0.2, "t_min": 80, "t_max": 450, "l_fix": 0}


def finish_stage5(data_dir, pid: str, rid: str) -> None:
    out = data_dir / "projects" / pid / "runs" / rid / "stages" / "05_validate"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "chosen.json", {"index": 0, "params": PARAMS, "score": 0.9, "version": 1})


def test_profile_round_trip_and_run_with_profile(app_factory, project_id, data_dir):
    seen = {}

    def extract(ctx):
        seen["profile"] = ctx.profile
        return {"status": "succeeded"}

    impls = fake_impls([]) | {3: extract}
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full", "params_override": {"review_pause": False}}).json()["run_id"]
        wait_status(client, project_id, rid, {"succeeded"})
        finish_stage5(data_dir, project_id, rid)
        r = client.post("/api/profiles", json={"name": "Gatsu", "from_run": f"{project_id}/{rid}"})
        assert r.status_code == 201, r.text
        prof = r.json()
        assert prof["params"] == PARAMS and [p["profile_id"] for p in client.get("/api/profiles").json()] == [prof["profile_id"]]
        rid2 = client.post(f"/api/projects/{project_id}/runs",
                           json={"kind": "full", "profile_id": prof["profile_id"],
                                 "params_override": {"review_pause": False}}).json()["run_id"]
        run = wait_status(client, project_id, rid2, {"succeeded"})
        assert run["profile_id"] == prof["profile_id"] and seen["profile"] == prof


def test_profile_errors(app_factory, project_id):
    with app_factory(stage_impls=fake_impls([])) as client:
        assert client.post("/api/profiles", json={"name": "x", "from_run": f"{project_id}/nope"}).status_code == 404
        r = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full", "profile_id": "nope"})
        assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_profile_refuses_run_without_successful_stage5(app_factory, project_id, data_dir):
    impls = fake_impls([]) | {5: lambda ctx: {"status": "needs_attention", "message": "skor rendah"}}
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        wait_status(client, project_id, rid, {"needs_attention"})
        finish_stage5(data_dir, project_id, rid)
        assert client.post("/api/profiles", json={"name": "x", "from_run": f"{project_id}/{rid}"}).status_code == 409
