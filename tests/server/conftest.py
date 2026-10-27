import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.config import load_settings
from server.app import create_app


def settings_for(data_dir: Path, **env):
    """Strata tasks are off unless a test turns them on: .env may enable them for the live server."""
    return load_settings({**os.environ, "DATA_DIR": str(data_dir), "LLM_TASKS_ENABLED": "", **env})


@pytest.fixture
def data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def client(data_dir):
    with TestClient(create_app(settings_for(data_dir))) as c:
        yield c


@pytest.fixture
def plan_bytes():
    return Path("floorplan/plan.jpeg").read_bytes()


@pytest.fixture
def storage_with_project(data_dir):
    from server.storage import Storage

    st = Storage(data_dir)
    (st.projects_dir / "p-0001").mkdir(parents=True)
    (st.projects_dir / "p-0001" / "project.json").write_text("{}")
    return st, "p-0001"


GT_PATH = Path("benchmarks/gatsu/gt_spec.json")


def create_project(client, plan_bytes, **data) -> str:
    r = client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")},
                    data={"start": "false", **data})
    assert r.status_code == 201, r.text
    return r.json()["project_id"]


def import_gt(client, pid: str) -> None:
    r = client.post(f"/api/projects/{pid}/specs/import", content=GT_PATH.read_bytes(),
                    headers={"content-type": "application/json"})
    assert r.status_code == 201, r.text


@pytest.fixture
def setup_client(data_dir):
    """Fixture data only: no `with`, so no lifespan, no orchestrator and no DATA_DIR lock next to the app under test."""
    return TestClient(create_app(settings_for(data_dir)))


@pytest.fixture
def project_id(setup_client, plan_bytes):
    return create_project(setup_client, plan_bytes)


@pytest.fixture
def project_with_gt(setup_client, project_id):
    import_gt(setup_client, project_id)
    return project_id


@pytest.fixture
def app_factory(data_dir):
    from contextlib import contextmanager

    @contextmanager
    def factory(stage_impls=None, env=None):
        with TestClient(create_app(settings_for(data_dir, **(env or {})), stage_impls=stage_impls)) as c:
            yield c

    return factory


def wait_status(client, pid, rid, statuses, timeout=10.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/projects/{pid}/runs/{rid}").json()
        if run.get("status") in statuses:
            return run
        time.sleep(0.05)
    raise AssertionError(f"run {rid} did not reach {statuses}: {run}")


def wait_stage_running(client, pid, rid, n, timeout=10.0):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/projects/{pid}/runs/{rid}").json()
        if run["stages"][n]["status"] == "running":
            return run
        time.sleep(0.05)
    raise AssertionError(f"stage {n} of {rid} never ran")


def client_events(client, pid):
    import json

    return [json.loads(line) for line in client.get(f"/api/projects/{pid}/events.jsonl").text.splitlines() if line]


def write_fake_run(run_dir, rid, status, stage_running=None, kind="regenerate"):
    import json

    names = ["input", "preprocess", "grid", "extract", "rooms", "validate", "review", "build", "verify", "report",
             "publish"]
    stages = [{"n": n, "name": name, "status": "skipped" if kind == "regenerate" and n < 7 else "pending",
               "started_at": None, "ended_at": None, "duration_ms": None, "progress": None, "metrics": {},
               "warnings": []} for n, name in enumerate(names)]
    if stage_running is not None:
        stages[stage_running]["status"] = "running"
    run = {"run_id": rid, "project_id": run_dir.parent.name, "kind": kind, "from_stage": 7 if kind == "regenerate" else 0,
           "version": 1, "spec_version_in": 1, "spec_version_out": None, "status": status, "stages": stages,
           "code_version": "test", "blender_version": None, "created_at": f"2026-10-26T00:00:0{rid[-1] == 'b' and 1 or 0}+07:00",
           "error": None}
    (run_dir / rid).mkdir(parents=True)
    (run_dir / rid / "run.json").write_text(json.dumps(run))


@pytest.fixture
def client_with_outputs(client, project_id, data_dir):
    out = data_dir / "projects" / project_id / "outputs" / "v1"
    (out / "renders").mkdir(parents=True)
    (out / "shell.glb").write_bytes(b"glTF-binary-placeholder")
    (out / "report.html").write_text("<html>report</html>")
    (out / "renders" / "top.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return client, project_id
