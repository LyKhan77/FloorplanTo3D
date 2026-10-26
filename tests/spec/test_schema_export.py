import json
from pathlib import Path

from core.spec.export_schema import build_schemas


def test_committed_schemas_match_models():
    for name, schema in build_schemas().items():
        path = Path("schema") / name
        assert path.exists(), f"{name} missing: run uv run python -m core.spec.export_schema"
        assert json.loads(path.read_text()) == schema, f"{name} stale: run uv run python -m core.spec.export_schema"
