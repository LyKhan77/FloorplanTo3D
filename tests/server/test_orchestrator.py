import threading

from tests.server.conftest import client_events, wait_stage_running, wait_status, write_fake_run


def fake_impls(calls, block: threading.Event | None = None):
    def ok(ctx):
        calls.append(ctx.stage)
        ctx.emit_log(f"stage {ctx.stage} ok")
        return {"status": "succeeded"}

    def slow(ctx):
        calls.append(ctx.stage)
        ctx.emit_progress(50, "half")
        if block:
            block.wait(5)
        return {"status": "succeeded"}

    impls = {n: ok for n in range(11)}
    if block:
        impls[7] = slow
    return impls


def test_regenerate_runs_7_to_10_in_blender_queue(app_factory, project_with_gt):
    calls = []
    with app_factory(stage_impls=fake_impls(calls)) as client:
        r = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"})
        assert r.status_code == 202
        run = wait_status(client, project_with_gt, r.json()["run_id"], {"succeeded"})
        assert calls == [7, 8, 9, 10] and [s["status"] for s in run["stages"][:7]] == ["skipped"] * 7
        types = [e["type"] for e in client_events(client, project_with_gt) if e["run_id"] == run["run_id"]]
        assert types[0] == "run.queued" and types[-1] == "run.finished" and types.count("stage.started") == 4
        assert client.get(f"/api/projects/{project_with_gt}").json()["latest_run"]["run_id"] == run["run_id"]


def test_second_run_409(app_factory, project_with_gt):
    block = threading.Event()
    with app_factory(stage_impls=fake_impls([], block)) as client:
        client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"})
        r = client.post(f"/api/projects/{project_with_gt}/runs", json={"kind": "full"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "run_in_progress"
        block.set()


def test_full_run_without_spec_stops_needs_attention(app_factory, project_id):
    with app_factory() as client:  # default stage impls; stage 5 has no spec to use
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        run = wait_status(client, project_id, rid, {"needs_attention"})
        assert run["stages"][0]["status"] == "succeeded" and run["stages"][3]["status"] == "skipped"
        assert run["stages"][5]["status"] == "needs_attention" and run["stages"][7]["status"] == "pending"


def test_cancel_running(app_factory, project_with_gt):
    block = threading.Event()
    with app_factory(stage_impls=fake_impls([], block)) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        wait_stage_running(client, project_with_gt, rid, 7)
        assert client.post(f"/api/projects/{project_with_gt}/runs/{rid}/cancel").status_code == 200
        block.set()
        run = wait_status(client, project_with_gt, rid, {"failed"})
        assert run["error"] == "cancelled" and run["stages"][8]["status"] == "pending"


def test_recovery_marks_running_interrupted_and_requeues(app_factory, project_with_gt, data_dir):
    run_dir = data_dir / "projects" / project_with_gt / "runs"
    write_fake_run(run_dir, "20261026T000000-aa", status="running", stage_running=7)
    write_fake_run(run_dir, "20261026T000001-bb", status="queued", kind="regenerate")
    (data_dir / "projects" / project_with_gt / "outputs" / "v1.tmp").mkdir(parents=True)
    calls = []
    with app_factory(stage_impls=fake_impls(calls)) as client:
        a = client.get(f"/api/projects/{project_with_gt}/runs/20261026T000000-aa").json()
        assert (a["status"], a["error"], a["stages"][7]["status"]) == ("failed", "interrupted", "failed")
        wait_status(client, project_with_gt, "20261026T000001-bb", {"succeeded"})
        assert calls == [7, 8, 9, 10]
        assert not (data_dir / "projects" / project_with_gt / "outputs" / "v1.tmp").exists()


def test_regenerate_reuses_complete_outputs(app_factory, project_with_gt, data_dir):
    out = data_dir / "projects" / project_with_gt / "outputs" / "v1"
    out.mkdir(parents=True)
    for f in ("shell.glb", "layout.blend", "report.html"):
        (out / f).write_text("x")
    with app_factory(stage_impls=fake_impls([])) as client:
        r = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": 1})
        assert r.status_code == 200 and r.json() == {"run_id": None, "reused": True}


def test_regenerate_without_spec_409(app_factory, project_id):
    with app_factory(stage_impls=fake_impls([])) as client:
        r = client.post(f"/api/projects/{project_id}/regenerate", json={"version": "HEAD"})
        assert r.status_code == 409 and r.json()["error"]["code"] == "no_spec"


def test_artifact_listing_and_traversal_404(app_factory, project_with_gt):
    def write_artifact(ctx):
        ctx.work_dir.mkdir(parents=True, exist_ok=True)
        (ctx.work_dir / "note.txt").write_text("hello")
        return {"status": "succeeded"}

    impls = fake_impls([]) | {7: write_artifact}
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        wait_status(client, project_with_gt, rid, {"succeeded"})
        stage = client.get(f"/api/projects/{project_with_gt}/runs/{rid}/stages/7").json()
        assert "07_build/work/note.txt" in stage["artifacts"]
        assert client.get(f"/api/projects/{project_with_gt}/runs/{rid}/artifacts/07_build/work/note.txt").text == "hello"
        bad = f"/api/projects/{project_with_gt}/runs/{rid}/artifacts/..%2F..%2F..%2Fproject.json"
        assert client.get(bad).status_code == 404


def test_stage_exception_fails_run_with_message(app_factory, project_with_gt):
    def boom(ctx):
        raise RuntimeError("kaboom")

    with app_factory(stage_impls=fake_impls([]) | {8: boom}) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        run = wait_status(client, project_with_gt, rid, {"failed"})
        assert run["stages"][8]["status"] == "failed" and "kaboom" in run["error"]
        assert run["stages"][9]["status"] == "pending"


def test_create_project_with_start_queues_full_run(app_factory, plan_bytes):
    with app_factory() as client:
        r = client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")}, data={"name": "x"})
        body = r.json()
        assert r.status_code == 201 and body["run_id"] and body["status"] == "queued"
        run = wait_status(client, body["project_id"], body["run_id"], {"needs_attention"})
        assert run["kind"] == "full"
