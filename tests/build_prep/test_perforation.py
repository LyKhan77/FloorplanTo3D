import cv2

from core.build_prep.perforation import PX_PER_MM, write_perforation_png


def test_perforation_tile_has_one_transparent_slot(tmp_path):
    """One 25 x 25 mm cell with a 7 x 20 mm slot, at 2 px/mm; colour baked in so Base Color reads the texture."""
    img = cv2.imread(str(write_perforation_png(tmp_path / "perf.png", "#B8BCC2")), cv2.IMREAD_UNCHANGED)
    assert img.shape == (25 * PX_PER_MM, 25 * PX_PER_MM, 4)
    alpha = img[..., 3]
    assert (alpha == 0).sum() == (7 * PX_PER_MM) * (20 * PX_PER_MM)
    assert set(alpha.ravel().tolist()) == {0, 255}
    assert tuple(img[0, 0, :3]) == (0xC2, 0xBC, 0xB8)  # BGR of #B8BCC2
