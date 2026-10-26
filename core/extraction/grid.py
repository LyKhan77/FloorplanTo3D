"""Grid bubbles, labels and axis positions (PRD/04 §2.2). Pixels are working-image pixels."""

import math
import re
import statistics

import cv2
import numpy as np

from core.extraction.ocr import OcrItem, ocr_crop

RING_SAMPLES = 72
RING_MIN = 0.9  # drawn bubbles are closed circles (1.0 on Gatsu); arcs of door swings and symbols stay <= 0.81
INNER_MAX = 0.35
_LETTERS = re.compile(r"^[A-Z]{1,2}$")
_NUMBERS = re.compile(r"^\d{1,2}$")


def _text_height(ocr: list[OcrItem]) -> float:
    single = [i.bbox[3] - i.bbox[1] for i in ocr if len(i.text.strip()) == 1]
    hs = single or [i.bbox[3] - i.bbox[1] for i in ocr]
    return statistics.median(hs) if hs else 30.0


def _ring_fraction(binary: np.ndarray, cx: float, cy: float, r: float) -> float:
    h, w = binary.shape
    hits = 0
    for k in range(RING_SAMPLES):
        t = 2 * math.pi * k / RING_SAMPLES
        for dr in (-2, -1, 0, 1, 2):
            x, y = round(cx + (r + dr) * math.cos(t)), round(cy + (r + dr) * math.sin(t))
            if 0 <= x < w and 0 <= y < h and binary[y, x]:
                hits += 1
                break
    return hits / RING_SAMPLES


def _inner_ink(binary: np.ndarray, cx: float, cy: float, r: float) -> float:
    mask = np.zeros_like(binary)
    cv2.circle(mask, (round(cx), round(cy)), round(0.75 * r), 255, -1)
    return float((binary[mask > 0] > 0).mean())


def _label_text(text: str) -> str:
    t = re.sub(r"[^A-Z0-9]", "", text.upper())
    return t if _LETTERS.match(t) or _NUMBERS.match(t) else ""


def find_bubbles(page_gray: np.ndarray, binary: np.ndarray, ocr: list[OcrItem]) -> list[dict]:
    h_text = _text_height(ocr)
    lo, hi = max(5, int(0.6 * h_text)), int(2.5 * h_text)
    circles = cv2.HoughCircles(cv2.medianBlur(page_gray, 3), cv2.HOUGH_GRADIENT, dp=1, minDist=2 * lo, param1=100,
                               param2=30, minRadius=lo, maxRadius=hi)
    bubbles = []
    for cx, cy, r in ([] if circles is None else circles[0].tolist()):
        if _ring_fraction(binary, cx, cy, r) < RING_MIN or _inner_ink(binary, cx, cy, r) >= INNER_MAX:
            continue
        inside = [i for i in ocr if math.hypot((i.bbox[0] + i.bbox[2]) / 2 - cx, (i.bbox[1] + i.bbox[3]) / 2 - cy) < r]
        label, source = next((_label_text(i.text) for i in inside if _label_text(i.text)), ""), "ocr"
        if not label:
            crop = ocr_crop(page_gray, (cx - 0.75 * r, cy - 0.75 * r, cx + 0.75 * r, cy + 0.75 * r))
            label, source = next((_label_text(i.text) for i in crop if _label_text(i.text)), ""), "crop"
        bubbles.append({"cx": round(cx, 2), "cy": round(cy, 2), "r": round(r, 2), "label": label or None,
                        "label_source": source if label else None})
    return sorted(bubbles, key=lambda b: (b["cy"], b["cx"]))


def _rows(bubbles: list[dict], key: str, other: str) -> list[list[dict]]:
    """Bubbles sharing (within r) the `key` coordinate, with >= 2 members, sorted along `other`."""
    groups: list[list[dict]] = []
    for b in sorted(bubbles, key=lambda b: b[key]):
        if groups and abs(groups[-1][-1][key] - b[key]) <= b["r"]:
            groups[-1].append(b)
        else:
            groups.append([b])
    return [sorted(g, key=lambda b: b[other]) for g in groups if len(g) >= 2]


def _merge_rows(rows: list[list[dict]], pos: str) -> list[dict]:
    """Rows of the same orientation (bubbles at both ends of an axis) merged by position."""
    axes: list[dict] = []
    for b in (b for row in rows for b in row):
        same = next((a for a in axes if abs(a[pos] - b[pos]) <= b["r"]), None)
        if same is None:
            axes.append(dict(b))
        elif not same["label"] and b["label"]:
            same.update(label=b["label"], label_source=b["label_source"])
    return sorted(axes, key=lambda a: a[pos])


def group_axes(bubbles: list[dict]) -> tuple[list[dict], list[dict]]:
    """(vertical axes, horizontal axes): a horizontal row of bubbles marks vertical axes (position cx), a vertical
    column marks horizontal axes (position cy)."""
    vertical = _merge_rows(_rows(bubbles, "cy", "cx"), "cx")
    horizontal = _merge_rows(_rows(bubbles, "cx", "cy"), "cy")
    return vertical, horizontal


def _value(label: str, letters: bool) -> int:
    if letters:
        return sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(label)))
    return int(label)


def _label(v: int, letters: bool) -> str:
    if not letters:
        return str(v)
    s = ""
    while v > 0:
        v, rem = divmod(v - 1, 26)
        s = chr(65 + rem) + s
    return s


def infer_labels(group: list[dict]) -> tuple[list[dict], list[str]]:
    """Fill unread labels and fix misreads from the sequence (letters step by one, numbers by +/-1)."""
    letters = sum(bool(b["label"] and _LETTERS.match(b["label"])) for b in group) >= \
        sum(bool(b["label"] and _NUMBERS.match(b["label"])) for b in group)
    pattern = _LETTERS if letters else _NUMBERS
    read = [(i, _value(b["label"], letters)) for i, b in enumerate(group) if b["label"] and pattern.match(b["label"])]
    warnings: list[str] = []
    # the sequence that explains the most readings: value = v0 + step * index
    best = None
    for step in (1, -1):
        for i, v in read:
            v0 = v - step * i
            fit = sum(vv == v0 + step * ii for ii, vv in read)
            if best is None or fit > best[0]:
                best = (fit, v0, step)
    out = [dict(b) for b in group]
    if best is None or best[0] < 2:
        for b in out:
            if not (b["label"] and pattern.match(b["label"])):
                warnings.append(f"grid bubble at ({b['cx']:.0f}, {b['cy']:.0f}) has no readable label")
        return out, warnings
    _, v0, step = best
    for i, b in enumerate(out):
        want = _label(v0 + step * i, letters)
        if b["label"] != want:
            if b["label"]:
                warnings.append(f"grid label {b['label']!r} read at ({b['cx']:.0f}, {b['cy']:.0f}); sequence says {want!r}")
            b.update(label=want, label_source="inferred")
    return out, warnings


def detect_grid(page_gray: np.ndarray, binary: np.ndarray, ocr: list[OcrItem]) -> dict:
    vertical, horizontal = group_axes(find_bubbles(page_gray, binary, ocr))
    vertical, wv = infer_labels(vertical)
    horizontal, wh = infer_labels(horizontal)
    as_axes = lambda group, pos: [{"label": b["label"], "px": b[pos], "bubble": b} for b in group]
    return {"vertical": as_axes(vertical, "cx"), "horizontal": as_axes(horizontal, "cy"), "warnings": wv + wh}
