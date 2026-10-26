import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.config import load_settings
from server.app import create_app


def settings_for(data_dir: Path, **env):
    return load_settings({**os.environ, "DATA_DIR": str(data_dir), **env})


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
def project_id(client, plan_bytes):
    return create_project(client, plan_bytes)


@pytest.fixture
def project_with_gt(client, project_id):
    import_gt(client, project_id)
    return project_id
