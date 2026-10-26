"""Stage 3 candidate overlay: walls blue (low confidence orange), doors green, columns orange, stairs purple,
hatch/symbol masks shaded grey. BGR on the working page."""

import cv2
import numpy as np

BLUE, ORANGE_LOW, GREEN, COL, PURPLE = (255, 0, 0), (0, 165, 255), (0, 160, 0), (0, 140, 255), (200, 0, 160)


def render_elements_overlay(page_gray: np.ndarray, elements: dict, s: float) -> np.ndarray:
    img = cv2.cvtColor(page_gray, cv2.COLOR_GRAY2BGR)
    masks = elements.get("_masks", {})
    shade = np.zeros(page_gray.shape, bool)
    for key in ("hatch", "symbol"):
        if key in masks:
            shade |= masks[key] > 0
    img[shade] = (img[shade] * 0.6 + np.array([90, 90, 90]) * 0.4).astype(np.uint8)
    px = elements.get("_px", {})
    walls = px.get("walls", [])
    for w, el in zip(walls, elements.get("walls", []), strict=False):
        colour = BLUE if el["confidence"] >= 0.6 else ORANGE_LOW
        cv2.line(img, (round(w["p0"][0]), round(w["p0"][1])), (round(w["p1"][0]), round(w["p1"][1])), colour,
                 max(2, round(w["thickness_mm"] / s)))
    for d in elements.get("openings", []):
        if d["wall"] >= len(walls):
            continue
        w = walls[d["wall"]]
        lo, hi = w["a"] + d["offset"] / s, w["a"] + (d["offset"] + d["width"]) / s
        p, q = ((lo, w["c"]), (hi, w["c"])) if w["orient"] == "h" else ((w["c"], lo), (w["c"], hi))
        cv2.line(img, (round(p[0]), round(p[1])), (round(q[0]), round(q[1])), GREEN, 5)
    for c in px.get("columns", []):
        hw, hh = c["size_mm"][0] / s / 2, c["size_mm"][1] / s / 2
        x, y = c["center_px"]
        cv2.rectangle(img, (round(x - hw), round(y - hh)), (round(x + hw), round(y + hh)), COL, 2)
    for st in px.get("stairs", []):
        for f in st["flights"]:
            cv2.arrowedLine(img, (round(f["start"][0]), round(f["start"][1])), (round(f["end"][0]), round(f["end"][1])),
                            PURPLE, 3, tipLength=0.08)
    return img
