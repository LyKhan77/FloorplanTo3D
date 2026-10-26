import os

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
