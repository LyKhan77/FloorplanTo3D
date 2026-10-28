"""Augmentation set (M7a): ~30 deterministic variants of floorplan/plan.jpeg (resolution, JPEG quality, small
rotation, margin crop/pad, blur, noise). The GT of every variant is the Gatsu GT unchanged: the pipeline's mm
frame is anchored on the grid axes and the scale comes from the dimensions, so the image transform does not move
any mm coordinate."""

import random
import zlib

import cv2
import numpy as np

SEED = 7
IDENTITY = {"id": "a00", "scale": 1.0, "jpeg_q": 95, "rotate_deg": 0.0, "margin_px": 0, "blur": 0.0, "noise": 0.0}


SINGLE_FACTOR = [("scale", (0.6, 0.75, 1.5, 2.0)), ("jpeg_q", (40, 60, 80)),
                 ("rotate_deg", (-2.0, -1.0, -0.5, 0.5, 1.0, 2.0)), ("margin_px", (-40, 80)), ("blur", (0.6, 1.0)),
                 ("noise", (4.0, 8.0))]


def variants_from_seed(seed: int = SEED, n: int = 30) -> list[dict]:
    """a00 identity, then one factor at a time (failures are attributable), then random combinations."""
    out = [dict(IDENTITY)]
    for key, values in SINGLE_FACTOR:
        out += [dict(IDENTITY) | {key: v} for v in values]
    rng = random.Random(seed)
    while len(out) < n:
        out.append({"scale": rng.choice((0.6, 0.75, 1.0, 1.5, 2.0)), "jpeg_q": rng.choice((40, 60, 80, 95)),
                    "rotate_deg": round(rng.uniform(-2, 2), 1), "margin_px": rng.choice((-40, 0, 80)),
                    "blur": rng.choice((0.0, 0.6, 1.0)), "noise": rng.choice((0.0, 4.0, 8.0))})
    return [v | {"id": f"a{i:02d}"} for i, v in enumerate(out)]


VARIANTS = variants_from_seed()


PAPER_KEEP = 5  # px of paper kept between the drawing and a crop edge


def _trim(img: np.ndarray, m: int) -> np.ndarray:
    """Crop up to m px per side, but only paper: a crop never cuts a grid bubble or a dimension off the drawing."""
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ys, xs = np.nonzero(gray < 128)
    h, w = gray.shape
    if not len(xs):
        return img[m:h - m, m:w - m]
    top, left = (min(m, max(0, v - PAPER_KEEP)) for v in (ys.min(), xs.min()))
    bottom, right = (min(m, max(0, v - PAPER_KEEP)) for v in (h - 1 - ys.max(), w - 1 - xs.max()))
    return img[top:h - bottom, left:w - right]


def render_variant(img: np.ndarray, v: dict) -> np.ndarray:
    """rotate (white border) -> margin (pad white / crop inward) -> scale -> blur -> noise -> JPEG round trip."""
    white = (255, 255, 255) if img.ndim == 3 else 255
    out = img
    if v["rotate_deg"]:
        h, w = out.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), v["rotate_deg"], 1.0)
        out = cv2.warpAffine(out, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=white)
    m = v["margin_px"]
    if m > 0:
        out = cv2.copyMakeBorder(out, m, m, m, m, cv2.BORDER_CONSTANT, value=white)
    elif m < 0:
        out = _trim(out, -m)
    if v["scale"] != 1.0:
        out = cv2.resize(out, None, fx=v["scale"], fy=v["scale"],
                         interpolation=cv2.INTER_AREA if v["scale"] < 1 else cv2.INTER_CUBIC)
    if v["blur"]:
        out = cv2.GaussianBlur(out, (0, 0), v["blur"])
    if v["noise"]:
        rng = np.random.default_rng(zlib.crc32(v["id"].encode()))
        out = np.clip(out.astype(np.float32) + rng.normal(0, v["noise"], out.shape), 0, 255).astype(np.uint8)
    _ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, v["jpeg_q"]])
    return cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
