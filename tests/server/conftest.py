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
