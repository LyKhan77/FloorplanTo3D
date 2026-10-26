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
