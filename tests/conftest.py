import json
import os
from pathlib import Path

import pytest

from core.config import load_settings


@pytest.fixture(scope="session")
def placeholder_root(tmp_path_factory):
    """The 7 placeholder templates, generated once per test session (needs Blender)."""
    blender = load_settings().blender_bin
    if not os.access(blender, os.X_OK):
        pytest.skip("Blender not found")
    from core.templates.make_placeholders import make_placeholders

    root = tmp_path_factory.mktemp("templates")
    make_placeholders(root, blender)
    return root


@pytest.fixture(scope="session")
def library_dir(tmp_path_factory) -> Path:
    """The 16 templates' template.json at 1.1.0 (no GLB needed: the engine reads metadata only)."""
    from core.templates.make_placeholders import PLACEHOLDERS, template_meta

    root = tmp_path_factory.mktemp("templates")
    for tid, dims, category, axes in PLACEHOLDERS:
        folder = root / tid / "1.1.0"
        folder.mkdir(parents=True)
        (folder / "template.json").write_text(json.dumps(template_meta(tid, dims, category, axes)))
    return root

