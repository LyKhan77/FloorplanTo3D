import numpy as np

from core.assist.context import area_context
from tests.spec.fixtures import spec_with_rooms

BOX = (4000, 1000, 6000, 5000)


def test_walls_and_rooms_in_box():
    ctx = area_context(spec_with_rooms(), BOX, [], None, None)
    assert ctx.wall_ids == ["W5"] and ctx.room_ids == ["R1", "R2"]
    assert "W2" not in ctx.text and "D1" in ctx.opening_ids and "D1" in ctx.text
    assert ctx.image is None
    assert "Tidak ada elemen terpilih" in ctx.text


def test_selection_is_called_out_and_included():
    ctx = area_context(spec_with_rooms(), BOX, ["W2"], None, None)
    assert "W2" in ctx.wall_ids and ctx.selection == ["W2"]
    assert "terpilih: W2" in ctx.text


def test_image_has_the_box_and_labels():
    page = np.full((600, 1000), 255, np.uint8)
    ctx = area_context(spec_with_rooms(), BOX, ["W5"], page, [10, 0, 0, 0, -10, 6000])
    img = ctx.image
    assert img is not None and img.ndim == 3 and max(img.shape[:2]) <= 900
    coloured = (np.abs(img[..., 0].astype(int) - img[..., 2]) > 100)
    assert coloured.any()
