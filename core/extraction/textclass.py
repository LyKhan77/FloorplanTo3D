"""Rule-based text classes (PRD/04 §2.1). Order matters: existing-condition markers beat MEP annotation."""

import re

import numpy as np

from core.extraction.ocr import OcrItem, run_ocr
from core.extraction.rooms.labels import lexicon

TEXT_CLASSES = ("grid_label", "dimension", "room_label", "annotation", "proposed", "dismantle", "stair_dir", "other")
ROOM_WORDS = tuple(w for words in lexicon().values() for w in words)  # PRD/04 §4.3 (lexicon.yaml)
_GRID = re.compile(r"^(?:[A-Z]{1,2}|\d{1,2})$")
_PROPOSED = re.compile(r"\b(?:PROPOSED|NEW|RENCANA|USULAN)\b")
_DISMANTLE = re.compile(r"\b(?:DISMANTLE|BONGKAR|DEMOLISH)")
_ANNOTATION = re.compile(r"NYY|\dX\d+C|ROUTE|CABLE|PANEL|SDP|UPS|MM²|MM2")
_DIMENSION = re.compile(r"^\d{3,6}$")
_STAIR = re.compile(r"\b(?:NK|NAIK|UP|TR|TURUN|DN|DOWN)\b")
_ROOM = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in ROOM_WORDS) + r")\b")


def classify_text(item: OcrItem, *, in_circle: bool, in_building: bool) -> str:
    t = item.text.strip().upper()
    if in_circle and _GRID.match(t):
        return "grid_label"
    if _PROPOSED.search(t):
        return "proposed"
    if _DISMANTLE.search(t):
        return "dismantle"
    if _ANNOTATION.search(t):
        return "annotation"
    if _DIMENSION.match(re.sub(r"[\s.,]", "", t)):
        return "dimension"
    if _STAIR.search(t):
        return "stair_dir"
    if _ROOM.search(t) or (in_building and len(re.sub(r"[^A-Z]", "", t)) >= 4 and t == item.text.strip()):
        return "room_label"
    return "other"


def ocr_page(page_gray: np.ndarray, upscale_done: float) -> list[OcrItem]:
    """Global OCR on the working page; an image already upscaled by preprocess is not enlarged twice."""
    return run_ocr(page_gray, upscale=max(1.0, 2.0 / upscale_done))
