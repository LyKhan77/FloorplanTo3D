import cv2
import numpy as np
import pytest

from core.extraction.ocr import restore_bbox


def mask_bbox(m):
    ys, xs = np.nonzero(m)
    return (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)


def test_restore_bbox_upscale_only():
    assert restore_bbox((20, 10, 60, 30), upscale=2.0) == pytest.approx((10, 5, 30, 15))


def test_restore_bbox_matches_cv2_rotate_cw():
    img = np.zeros((40, 100), np.uint8)
    img[5:15, 10:30] = 255
    big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    rot = cv2.rotate(big, cv2.ROTATE_90_CLOCKWISE)
    got = restore_bbox(mask_bbox(rot), upscale=2.0, rotated_w=rot.shape[1])
    assert got == pytest.approx((10, 5, 30, 15))
