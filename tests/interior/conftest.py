import json
from pathlib import Path

import pytest

from core.templates.make_placeholders import PLACEHOLDERS, template_meta


@pytest.fixture(scope="session")
def library_dir(tmp_path_factory) -> Path:
    """The 16 templates' template.json at 1.1.0 (no GLB needed: the engine reads metadata only)."""
    root = tmp_path_factory.mktemp("templates")
    for tid, dims, category, axes in PLACEHOLDERS:
        folder = root / tid / "1.1.0"
        folder.mkdir(parents=True)
        (folder / "template.json").write_text(json.dumps(template_meta(tid, dims, category, axes)))
    return root
