import cv2
import numpy as np
import pytest

from core.build_prep.assemble import build_input_for
from tests.builder.helpers import build, skip_without_blender
from tests.spec.fixtures import spec_with_rooms

pytestmark = [pytest.mark.blender, skip_without_blender]


def test_verify_render_is_binary_and_aligned(tmp_path):
    doc, _ = build_input_for(spec_with_rooms(), None, (1000, 600))
    doc["cameras"] = [c for c in doc["cameras"] if c["mode"] == "verify"]
    r = build(tmp_path, doc)
    assert r.returncode == 0, r.stderr[-2000:]
    img = cv2.imread(str(tmp_path / "out" / "verify_top.png"), cv2.IMREAD_GRAYSCALE)
    assert img.shape == (600, 1000) and set(np.unique(img)) <= {0, 255}
    # px_to_mm [10,0,0,0,-10,6000]: W1 (y = -100..100 mm) covers image rows 590..600; R1 interior is white
    assert img[595, 500] == 0 and img[300, 250] == 255
    assert img[300, 500] == 0  # W5 at x = 5000 mm -> column 500


def test_doc_renders_exist(tmp_path):
    doc, _ = build_input_for(spec_with_rooms(), None, None)
    r = build(tmp_path, doc)
    assert r.returncode == 0, r.stderr[-2000:]
    for f in ("top.png", "iso_ne.png", "iso_nw.png", "iso_se.png", "iso_sw.png", "room_R1.png", "room_R2.png"):
        img = cv2.imread(str(tmp_path / "out" / "renders" / f))
        assert img is not None and img.std() > 1, f  # not a blank frame
