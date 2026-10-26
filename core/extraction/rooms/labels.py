"""Room labels from OCR and the room lexicon (PRD/04 Tahap 4 langkah 4-5, §4.3)."""

import re
from functools import cache
from pathlib import Path

import yaml

from core.extraction.geometry.elements import to_mm
from core.spec.rooms import RoomLabel

LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicon.yaml"
GENERIC = {"ROOM", "R", "RUANG"}  # second lines that only complete a name ("CAPASITOR" / "ROOM")
FUZZY_MIN = 5  # Levenshtein <= 1 only for words of >= 5 letters


@cache
def lexicon() -> dict[str, list[str]]:
    return yaml.safe_load(LEXICON_PATH.read_text())


def _letters(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^A-Z0-9]+", text.upper()) if t]


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def match_type(text: str) -> tuple[str, float]:
    """(room type, score): 1.0 for a keyword found (long keywords as a substring, so "BATTERYROOM" matches; short
    ones only as a whole word, so "PAC" does not match inside "CAPACITOR"), 0.8 for one typo in a word of >= 5
    letters, else ("other", 0.0). Ties go to the longest keyword."""
    joined, tokens = _letters(text), _tokens(text)
    best = ("other", 0.0, 0)
    for rtype, words in lexicon().items():
        for word in words:
            key = _letters(word)
            if (len(key) >= FUZZY_MIN and key in joined) or key in tokens:
                score = 1.0
            elif len(key) >= FUZZY_MIN and " " not in word.strip() \
                    and any(len(t) >= FUZZY_MIN and levenshtein(t, key) <= 1 for t in tokens):
                score = 0.8
            else:
                continue
            if (score, len(key)) > (best[1], best[2]):
                best = (rtype, score, len(key))
    return best[0], best[1]


def _overlap(a, b) -> bool:
    return min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])


def _completes(base, generic) -> bool:
    """The generic word sits right below or right of the base text, within 1.5 text heights."""
    h = base[3] - base[1]
    below = 0 <= generic[1] - base[3] <= 1.5 * h and min(base[2], generic[2]) > max(base[0], generic[0])
    right = 0 <= generic[0] - base[2] <= 1.5 * h and min(base[3], generic[3]) > max(base[1], generic[1])
    return below or right


def labels_from_ocr(ocr_items: list[dict], px_to_mm: list[float]) -> list[RoomLabel]:
    items = sorted((i for i in ocr_items if i.get("cls") == "room_label"), key=lambda i: (i["bbox"][1], i["bbox"][0]))
    unique: list[dict] = []
    for it in items:  # the OCR passes repeat a text with an overlapping box
        if not any(u["text"] == it["text"] and _overlap(u["bbox"], it["bbox"]) for u in unique):
            unique.append(it)
    bases = [{"text": " ".join(_tokens(u["text"])) if u["text"].strip() else "", "bbox": list(u["bbox"])}
             for u in unique if _letters(u["text"]) not in GENERIC]
    for g in (u for u in unique if _letters(u["text"]) in GENERIC):
        base = next((b for b in bases if _completes(b["bbox"], g["bbox"])), None)
        if base:
            base["text"] += " " + _letters(g["text"])
            base["bbox"] = [min(base["bbox"][0], g["bbox"][0]), min(base["bbox"][1], g["bbox"][1]),
                            max(base["bbox"][2], g["bbox"][2]), max(base["bbox"][3], g["bbox"][3])]
    out = []
    for b in bases:
        rtype, _ = match_type(b["text"])
        if rtype == "other" and len(re.sub(r"[^A-Z]", "", b["text"])) < 3:
            continue
        x0, y0, x1, y1 = b["bbox"]
        out.append(RoomLabel(at=to_mm(px_to_mm, (x0 + x1) / 2, (y0 + y1) / 2), name=b["text"], type=rtype))
    return out


def best_label(labels: list[RoomLabel]) -> RoomLabel | None:
    return max(labels, key=lambda lb: (match_type(lb.name)[1], len(lb.name)), default=None)
