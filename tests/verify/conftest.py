import json
import os

import pytest

from core.build_prep.assemble import build_input_for
from tests.builder.helpers import BLENDER, build
from tests.spec.fixtures import spec_with_rooms


@pytest.fixture(scope="session")
def built_fixture_dir(tmp_path_factory):
    """Two-room fixture built once (no renders); build_input.json copied next to the outputs."""
    if not os.access(BLENDER, os.X_OK):
        pytest.skip("Blender not found")
    tmp = tmp_path_factory.mktemp("built")
    doc, _ = build_input_for(spec_with_rooms(), None, None)
    doc["cameras"] = []
    assert build(tmp, doc).returncode == 0
    (tmp / "out" / "build_input.json").write_text(json.dumps(doc))
    return tmp / "out"
