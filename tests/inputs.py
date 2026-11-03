"""Local, never-committed inputs (floorplan/) that some tests need; they skip when the file is missing."""

from pathlib import Path

import pytest

ANCOL = next(iter(Path("floorplan").glob("*ANCOL*.pdf")), None)
requires_ancol = pytest.mark.skipif(ANCOL is None, reason="Ancol PDF is a local input (floorplan/ is not committed)")
