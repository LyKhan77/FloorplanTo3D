"""Stage 2 overlay: grid axes, bubble labels and the dimension equations used (green) or dropped (red)."""

import cv2
import numpy as np

MAGENTA, GREEN, RED, WHITE, BLACK = (255, 0, 255), (0, 160, 0), (0, 0, 220), (255, 255, 255), (0, 0, 0)


def _dashed(img: np.ndarray, p: tuple[int, int], q: tuple[int, int], colour, dash: int = 24) -> None:
    length = int(np.hypot(q[0] - p[0], q[1] - p[1]))
    for s in range(0, length, 2 * dash):
        a = (p[0] + (q[0] - p[0]) * s // max(length, 1), p[1] + (q[1] - p[1]) * s // max(length, 1))
        e = min(s + dash, length)
        b = (p[0] + (q[0] - p[0]) * e // max(length, 1), p[1] + (q[1] - p[1]) * e // max(length, 1))
        cv2.line(img, a, b, colour, 2)


def _label(img: np.ndarray, text: str, x: int, y: int, scale: float) -> None:
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    cv2.rectangle(img, (x - 4, y - th - 4), (x + tw + 4, y + 4), WHITE, -1)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, BLACK, 2, cv2.LINE_AA)


def render_grid_overlay(page_gray: np.ndarray, grid_doc: dict) -> np.ndarray:
    img = cv2.cvtColor(page_gray, cv2.COLOR_GRAY2BGR)
    h, w = page_gray.shape
    scale = max(0.6, h / 1400)  # label text >= 14 px on the working page
    for a in grid_doc.get("axes", []):
        px = round(a["px"])
        if a["orientation"] == "vertical":
            _dashed(img, (px, 0), (px, h - 1), MAGENTA)
            _label(img, a["label"], px + 6, int(30 * scale), scale)
        else:
            _dashed(img, (0, px), (w - 1, px), MAGENTA)
            _label(img, a["label"], 6, px - 6, scale)
    pos = {(a["orientation"], a["label"]): a["px"] for a in grid_doc.get("axes", [])}
    for colour, eqs in ((GREEN, grid_doc.get("equations_used", [])), (RED, grid_doc.get("equations_dropped", []))):
        for e in eqs:
            x0, y0, x1, y1 = e["text_bbox"]
            name = "vertical" if e["orientation"] == "x" else "horizontal"
            a, b = pos.get((name, e["axis_from"])), pos.get((name, e["axis_to"]))
            if a is None or b is None:
                cv2.rectangle(img, (round(x0), round(y0)), (round(x1), round(y1)), colour, 2)
                continue
            if name == "vertical":
                y = round(y1 + 6)
                cv2.line(img, (round(a), y), (round(b), y), colour, 3)
            else:
                x = round(x1 + 6)
                cv2.line(img, (x, round(a)), (x, round(b)), colour, 3)
            cv2.rectangle(img, (round(x0), round(y0)), (round(x1), round(y1)), colour, 2)
    return img
