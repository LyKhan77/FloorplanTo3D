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


def fast_blender(ctx):
    return {"status": "succeeded"}


def test_full_run_extracts_and_saves_a_spec(app_factory, project_id):
    with app_factory(stage_impls={n: fast_blender for n in range(7, 11)}) as client:  # real stages 0-5
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        run = wait_status(client, project_id, rid, {"succeeded", "needs_attention", "needs_review", "failed"}, timeout=180)
        assert [s["status"] for s in run["stages"][:6]] == ["succeeded"] * 6, run["stages"][5]
        assert run["spec_version_out"] == 1 and run["stages"][5]["metrics"]["rooms"] >= 20
        assert client.get(f"/api/projects/{project_id}").json()["head"] == 1


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
    with app_factory(stage_impls={n: fast_blender for n in range(7, 11)}) as client:
        r = client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")},
                        data={"name": "x", "params": '{"review_pause": false}'})  # this test builds through stage 10
        body = r.json()
        assert r.status_code == 201 and body["run_id"] and body["status"] == "queued"
        run = wait_status(client, body["project_id"], body["run_id"], {"succeeded"}, timeout=180)
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
                broken.add((pid, rid))  # run ids are only unique per project (same second + 2 hex)
                raise RuntimeError("boom")
            return await real_part(queue, pid, rid)

        def load_run(pid, rid):
            if (pid, rid) in broken:
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


def test_continue_refused_without_spec(app_factory, project_id):
    impls = fake_impls([])
    impls[5] = lambda ctx: {"status": "needs_attention", "message": "semua kandidat punya error validator (V008)"}
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        wait_status(client, project_id, rid, {"needs_attention"})
        r = client.post(f"/api/projects/{project_id}/runs/{rid}/continue", json={"accept_low_score": True})
        assert r.status_code == 409 and r.json()["error"]["code"] == "no_spec"


def test_stage5_version_becomes_the_run_output(app_factory, project_id):
    impls = fake_impls([])
    impls[5] = lambda ctx: {"status": "needs_attention", "metrics": {"version": 1}, "message": "skor 0.5"}
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        run = wait_status(client, project_id, rid, {"needs_attention"})
        assert run["spec_version_out"] == 1


def test_stage6_version_becomes_the_run_output(app_factory, project_id):
    impls = fake_impls([])
    impls[5] = lambda ctx: {"status": "succeeded", "metrics": {"version": 1}}
    impls[6] = lambda ctx: {"status": "succeeded", "metrics": {"version": 2}}
    seen = []
    impls[7] = lambda ctx: (seen.append(ctx.state.get("version")), {"status": "succeeded"})[1]
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full", "params_override": {"review_pause": False}}).json()["run_id"]
        run = wait_status(client, project_id, rid, {"succeeded"})
        assert run["spec_version_out"] == 2


def test_stage6_emits_llm_decision_events(app_factory, project_id):
    impls = fake_impls([])
    impls[6] = lambda ctx: (ctx.emit_event("llm.decision", {"element": "W1", "accepted": True}), {"status": "succeeded"})[1]
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full", "params_override": {"review_pause": False}}).json()["run_id"]
        wait_status(client, project_id, rid, {"succeeded"})
        events = [e for e in client_events(client, project_id) if e["type"] == "llm.decision"]
        assert events and events[0]["stage"] == 6 and events[0]["data"]["element"] == "W1"


def test_real_stage6_skips_when_disabled(app_factory, project_with_gt):
    impls = {n: fast_blender for n in range(7, 11)} | {n: fake_impls([])[n] for n in range(5)}
    impls[5] = lambda ctx: (ctx.state.update(version=1), {"status": "succeeded", "metrics": {"version": 1}})[1]
    with app_factory(stage_impls=impls) as client:  # stage 6 is the real one; settings_for empties LLM_TASKS_ENABLED
        rid = client.post(f"/api/projects/{project_with_gt}/runs", json={"kind": "full", "params_override": {"review_pause": False}}).json()["run_id"]
        run = wait_status(client, project_with_gt, rid, {"succeeded"})
        assert run["stages"][6]["status"] == "skipped" and run["stages"][6]["metrics"]["reason"] == "disabled"


def test_server_tests_never_reach_live_strata(data_dir):
    from tests.server.conftest import settings_for

    s = settings_for(data_dir)
    assert s.llm_tasks_enabled == () and settings_for(data_dir, LLM_TASKS_ENABLED="T1").llm_tasks_enabled == ("T1",)


def test_rerun_from_stage6_carries_stage_1_to_5_artefacts(app_factory, project_id):
    """Retrying the Strata review (from_stage 6) needs the run's page, OCR and validation context."""
    def write(ctx):
        ctx.work_dir.mkdir(parents=True, exist_ok=True)
        (ctx.work_dir / "done.txt").write_text(str(ctx.stage))
        return {"status": "succeeded", **({"metrics": {"version": 1}} if ctx.stage == 5 else {})}

    seen = []
    impls = fake_impls([]) | {n: write for n in range(6)}
    impls[6] = lambda ctx: (seen.append(sorted(p.name for p in ctx.work_dir.parent.iterdir())), {"status": "succeeded"})[1]
    with app_factory(stage_impls=impls) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full", "params_override": {"review_pause": False}}).json()["run_id"]
        wait_status(client, project_id, rid, {"succeeded"})
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "from_stage", "from_stage": 6}).json()["run_id"]
        run = wait_status(client, project_id, rid, {"succeeded"})
    assert run["from_stage"] == 6
    assert {"00_input", "01_preprocess", "02_grid", "05_validate"} <= set(seen[-1])


# --- M8: pause for human review after stage 5 ---------------------------------------------------------------------

def _spec_impls(calls=None):
    impls = fake_impls(calls if calls is not None else [])
    impls[5] = lambda ctx: {"status": "succeeded", "metrics": {"version": 1}}
    return impls


def test_full_run_pauses_for_review_after_stage_5(app_factory, project_id):
    calls = []
    with app_factory(stage_impls=_spec_impls(calls)) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        run = wait_status(client, project_id, rid, {"needs_review", "succeeded"})
        assert run["status"] == "needs_review"
        assert run["stages"][5]["status"] == "succeeded"
        assert [s["status"] for s in run["stages"][6:]] == ["pending"] * 5
        assert 6 not in calls
        assert client.get(f"/api/projects/{project_id}").json()["status"] == "needs_review"


def test_review_pause_off_runs_through(app_factory, project_id):
    with app_factory(stage_impls=_spec_impls()) as client:
        rid = client.post(f"/api/projects/{project_id}/runs",
                          json={"kind": "full", "params_override": {"review_pause": False}}).json()["run_id"]
        assert wait_status(client, project_id, rid, {"needs_review", "succeeded"})["status"] == "succeeded"


def test_continue_after_review_starts_from_stage_6(app_factory, project_id):
    with app_factory(stage_impls=_spec_impls()) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        wait_status(client, project_id, rid, {"needs_review"})
        r = client.post(f"/api/projects/{project_id}/runs/{rid}/continue", json={})
        assert r.status_code == 202, r.text
        new = wait_status(client, project_id, r.json()["run_id"], {"succeeded"})
        assert new["from_stage"] == 6 and new["stages"][5]["status"] == "skipped"
        assert client.get(f"/api/projects/{project_id}/runs/{rid}").json()["status"] == "succeeded"


def test_continue_twice_is_409(app_factory, project_id):
    with app_factory(stage_impls=_spec_impls()) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        wait_status(client, project_id, rid, {"needs_review"})
        new = client.post(f"/api/projects/{project_id}/runs/{rid}/continue", json={}).json()["run_id"]
        wait_status(client, project_id, new, {"succeeded"})
        r = client.post(f"/api/projects/{project_id}/runs/{rid}/continue", json={})
        assert r.status_code == 409 and r.json()["error"]["code"] == "not_continuable"


def test_recover_keeps_needs_review(app_factory, project_id):
    with app_factory(stage_impls=_spec_impls()) as client:
        rid = client.post(f"/api/projects/{project_id}/runs", json={"kind": "full"}).json()["run_id"]
        wait_status(client, project_id, rid, {"needs_review"})
    with app_factory(stage_impls=_spec_impls()) as client:  # a restart runs recover()
        assert client.get(f"/api/projects/{project_id}/runs/{rid}").json()["status"] == "needs_review"
