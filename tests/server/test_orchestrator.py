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
        # stages 0-3 run the extraction (M5a/M5b); stage 4 (rooms) arrives in M5c
        assert run["stages"][0]["status"] == "succeeded" and run["stages"][3]["status"] == "succeeded"
        assert run["stages"][4]["status"] == "skipped"
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
        events = [e for e in client.app.state.bus.history(project_with_gt) if e["run_id"] == "20261026T000000-aa"]
        assert [(e["type"], e["stage"], e["data"]["status"]) for e in events] == [
            ("stage.finished", 7, "failed"), ("run.finished", None, "failed")]  # the log closes the stage too
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


def test_shutdown_kills_blender_and_stops_the_run(app_factory, project_with_gt):
    """Stopping the server must not leave the stage subprocess or later stages running."""
    import subprocess

    procs, calls = [], []

    def slow_build(ctx):
        p = subprocess.Popen(["sleep", "30"])
        procs.append(p)
        ctx.register_process(p)
        p.wait()
        return {"status": "failed" if p.returncode else "succeeded"}

    impls = fake_impls(calls) | {7: slow_build}
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={}).json()["run_id"]
        wait_stage_running(client, project_with_gt, rid, 7)
    assert procs and procs[0].wait(timeout=5) is not None
    assert not [n for n in calls if n > 7]


def test_from_stage_after_build_restarts_at_build(app_factory, project_with_gt):
    """Stages 8-10 read the spec and Blender output that stage 7 of the same run produces."""
    calls = []
    with app_factory(stage_impls=fake_impls(calls)) as client:
        r = client.post(f"/api/projects/{project_with_gt}/runs", json={"kind": "from_stage", "from_stage": 9})
        wait_status(client, project_with_gt, r.json()["run_id"], {"succeeded"})
    assert calls == [7, 8, 9, 10]


def test_second_server_on_same_data_dir_refuses_to_start(app_factory, project_with_gt):
    """uvicorn runs lifespan (and recovery) before binding the port, so a second process would mark the first
    one's live run interrupted before failing with 'address in use'."""
    import pytest

    block = threading.Event()
    with app_factory(stage_impls=fake_impls([], block)) as client:
        rid = client.post(f"/api/projects/{project_with_gt}/regenerate", json={}).json()["run_id"]
        wait_stage_running(client, project_with_gt, rid, 7)
        with pytest.raises(RuntimeError, match="already serving"), app_factory():
            pass
        assert client.get(f"/api/projects/{project_with_gt}/runs/{rid}").json()["status"] == "running"
        block.set()


def test_worker_survives_a_failing_error_handler(app_factory, project_with_gt, plan_bytes):
    """A run whose run.json cannot be read (torn write, deleted project) must not stop the queue for everyone."""
    from tests.server.conftest import create_project, import_gt

    calls = []
    with app_factory(stage_impls=fake_impls(calls)) as client:
        orch = client.app.state.orchestrator
        real_part, real_load = orch._run_part, orch.load_run
        broken = set()

        async def run_part(queue, pid, rid):
            if pid == project_with_gt:
                broken.add(rid)
                raise RuntimeError("boom")
            return await real_part(queue, pid, rid)

        def load_run(pid, rid):
            if rid in broken:
                raise ValueError("torn run.json")
            return real_load(pid, rid)

        orch._run_part, orch.load_run = run_part, load_run
        client.post(f"/api/projects/{project_with_gt}/regenerate", json={})
        other = create_project(client, plan_bytes)
        import_gt(client, other)
        rid = client.post(f"/api/projects/{other}/regenerate", json={}).json()["run_id"]
        wait_status(client, other, rid, {"succeeded"})
        orch._run_part = real_part
        assert client.post(f"/api/projects/{project_with_gt}/regenerate", json={}).status_code == 202
