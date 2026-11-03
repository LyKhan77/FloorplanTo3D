"""Cable-tray ladders (MEP, not architecture): masked before walls and columns are read, or every rung becomes a
column and every rail a wall. Templates are drawn from mm dimensions at the run's scale, so no client drawing
is stored. Working px.
"""

import cv2
import numpy as np

# ponytail: two drawn tray styles measured on Ancol p13; another office's tray block needs its own entry here
TRAY_STYLES = {  # mm: rail centre to rail centre, rung pitch, rung width along the run (rungs are filled bars)
    "ladder_wide": {"width": 460, "pitch": 292, "rung": 107},
    "ladder_narrow": {"width": 307, "pitch": 353, "rung": 123},
}
TRAY_MATCH = 0.6  # TM_CCOEFF_NORMED
RUNG_MARGIN = 0.1  # the ladder must beat its own rails alone by this much: a 300 mm double-line wall has no rungs
TRAY_MIN_MM = 2000  # a tray runs for metres; a stair end or leaders crossing a wall match for a rung or two
TEMPLATE_PITCHES = 3


def tray_template(style: dict, s: float, stroke_px: float, rungs: bool = True) -> np.ndarray:
    """A horizontal run of TEMPLATE_PITCHES rungs between two rails, ink = 255, with a stroke of margin around.
    rungs=False: the rails alone, which is what a double-line wall of the same width looks like."""
    t = max(1, round(stroke_px))
    w, pitch, rung = (max(2, round(style[k] / s)) for k in ("width", "pitch", "rung"))
    n = TEMPLATE_PITCHES * pitch
    img = np.zeros((w + 3 * t, n), np.uint8)
    y0, y1 = t, t + w
    cv2.line(img, (0, y0), (n, y0), 255, t)
    cv2.line(img, (0, y1), (n, y1), 255, t)
    for x in range(pitch // 2, n - rung, pitch) if rungs else ():
        cv2.rectangle(img, (x, y0), (x + rung, y1), 255, -1)
    return img


def tray_mask(img: np.ndarray, s: float, stroke_px: float) -> np.ndarray:
    """255 where a tray ladder is drawn (any style, horizontal or vertical)."""
    mask = np.zeros_like(img, np.uint8)
    for style in TRAY_STYLES.values():
        t, rails = tray_template(style, s, stroke_px), tray_template(style, s, stroke_px, rungs=False)
        for tpl, bare in ((t, rails), (np.ascontiguousarray(t.T), np.ascontiguousarray(rails.T))):
            h, w = tpl.shape
            if h > img.shape[0] or w > img.shape[1]:
                continue
            res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
            res_bare = cv2.matchTemplate(img, bare, cv2.TM_CCOEFF_NORMED)
            hits = ((res >= TRAY_MATCH) & (res - res_bare >= RUNG_MARGIN)).astype(np.uint8)
            if hits.any():  # every window whose top-left corner matched
                mask |= cv2.dilate(np.pad(hits, ((0, h - 1), (0, w - 1))), np.ones((h, w), np.uint8),
                                   anchor=(w - 1, h - 1)) * 255
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    short = [i for i in range(1, n) if max(stats[i, 2], stats[i, 3]) * s < TRAY_MIN_MM]
    mask[np.isin(labels, short)] = 0
    return mask
