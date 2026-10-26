"""Straight stair flights, landings, up direction, stair mask and lift boxes (PRD/04 §3.4b). Working pixels.

Runs before wall detection: tread lines would otherwise read as closely spaced partitions.
"""

import math
import statistics

import cv2
import numpy as np

MIN_TREADS = 5
LEN_TOL = 0.10
WIDTH_MM = (800, 2500)
SPACING_MM = (220, 350)
MAX_CV = 0.15
UP_WORDS = {"NK", "NAIK", "UP"}
DOWN_WORDS = {"TR", "TURUN", "DN", "DOWN"}


def _runs(lines: list[dict], s: float) -> list[list[dict]]:
    """Split lines (sorted by c) into runs with regular spacing in SPACING_MM."""
    runs, cur = [], [lines[0]]
    for prev, ln in zip(lines, lines[1:], strict=False):
        gap = (ln["c"] - prev["c"]) * s
        if SPACING_MM[0] <= gap <= SPACING_MM[1]:
            cur.append(ln)
        else:
            runs.append(cur)
            cur = [ln]
    runs.append(cur)
    return [r for r in runs if len(r) >= MIN_TREADS]


def _flight(run: list[dict], orient: str, s: float, spacing_px: float | None = None) -> dict | None:
    gaps = [b["c"] - a["c"] for a, b in zip(run, run[1:], strict=False)]
    mean = statistics.fmean(gaps)
    if statistics.pstdev(gaps) / mean > MAX_CV:
        return None
    step = spacing_px or mean
    a, b = statistics.median(x["a"] for x in run), statistics.median(x["b"] for x in run)
    return {"tread_axis": orient, "lines": run, "width_mm": round((b - a) * s), "spacing_px": step,
            "risers": round((run[-1]["c"] - run[0]["c"]) / step) + 2, "rect": [a, run[0]["c"], b, run[-1]["c"]]}


def find_flights(strokes: list[dict], s: float) -> list[dict]:
    flights = []
    for orient in ("h", "v"):
        cand = [x for x in strokes if x["orient"] == orient and WIDTH_MM[0] <= (x["b"] - x["a"]) * s <= WIDTH_MM[1]]
        groups: list[list[dict]] = []
        for x in sorted(cand, key=lambda x: (x["c"], x["a"])):
            for g in groups:
                ref = g[0]
                length = ref["b"] - ref["a"]
                overlap = min(ref["b"], x["b"]) - max(ref["a"], x["a"])
                # a tread Hough broke short (a piece lost at a crossing) still belongs: 70% of the reference
                # ... and one running into the stair wall or lift shaft is longer: up to 130%
                if 0.7 * length <= x["b"] - x["a"] <= 1.3 * length and overlap >= 0.7 * length:
                    g.append(x)
                    break
            else:
                groups.append([x])
        for g in groups:
            g.sort(key=lambda x: x["c"])
            parts = [f for r in _runs(g, s) if (f := _flight(r, orient, s))]
            # runs of one flight split by a break line (Gatsu S1 west flight): same span, gap < 3 treads
            merged: list[dict] = []
            for f in parts:
                last = merged[-1] if merged else None
                if last and f["rect"][1] - last["rect"][3] <= 3.5 * last["spacing_px"]:
                    run = last["lines"] + f["lines"]
                    merged[-1] = {**last, "lines": run, "rect": [last["rect"][0], last["rect"][1], last["rect"][2], f["rect"][3]],
                                  "risers": round((run[-1]["c"] - run[0]["c"]) / last["spacing_px"]) + 2}
                else:
                    merged.append(f)
            flights += merged
    return sorted(flights, key=lambda f: (f["tread_axis"], f["rect"][1], f["rect"][0]))


def stair_mask(flights: list[dict], shape: tuple[int, int], s: float) -> np.ndarray:
    mask = np.zeros(shape, np.uint8)
    for f in flights:
        d = round(f["spacing_px"])
        u0, c0, u1, c1 = f["rect"]
        if f["tread_axis"] == "h":
            x0, y0, x1, y1 = u0, c0, u1, c1
        else:
            x0, y0, x1, y1 = c0, u0, c1, u1
        cv2.rectangle(mask, (round(x0) - d, round(y0) - d), (round(x1) + d, round(y1) + d), 255, -1)
    return mask


def _ends(f: dict) -> tuple[tuple[float, float], tuple[float, float]]:
    """(first-tread end, last-tread end) midpoints in (x, y)."""
    u0, c0, u1, c1 = f["rect"]
    mid = (u0 + u1) / 2
    first, last = (mid, c0 - f["spacing_px"] / 2), (mid, c1 + f["spacing_px"] / 2)
    return (first, last) if f["tread_axis"] == "h" else ((first[1], first[0]), (last[1], last[0]))


def _landing(a: dict, b: dict, s: float) -> tuple[list, int, int] | None:
    """A landing joins two parallel flights whose ends sit side by side. Returns (polygon, end of a, end of b)."""
    if a["tread_axis"] != b["tread_axis"]:
        return None
    w = max(a["width_mm"], b["width_mm"]) / s
    for ia, ea in enumerate(_ends(a)):
        for ib, eb in enumerate(_ends(b)):
            along = abs(ea[1] - eb[1]) if a["tread_axis"] == "h" else abs(ea[0] - eb[0])
            across = abs(ea[0] - eb[0]) if a["tread_axis"] == "h" else abs(ea[1] - eb[1])
            # flights of a U stair run either side of a well or lift shaft (Gatsu S1: ~3.1 flight widths apart)
            if along <= 1.5 * w and across <= 4 * w:
                lo = min(a["rect"][0], b["rect"][0])
                hi = max(a["rect"][2], b["rect"][2])
                edge = ea[1] if a["tread_axis"] == "h" else ea[0]
                out = -w if ia == 0 else w  # the landing lies beyond the shared end
                c0, c1 = sorted((edge, edge + out))
                poly = [[lo, c0], [hi, c0], [hi, c1], [lo, c1]] if a["tread_axis"] == "h" else \
                    [[c0, lo], [c1, lo], [c1, hi], [c0, hi]]
                return poly, ia, ib
    return None


def _text_end(f: dict, texts: list[dict], s: float) -> tuple[int, str] | None:
    w = f["width_mm"] / s
    best = None
    for t in texts:
        word = t["text"].strip().upper()
        if word not in UP_WORDS | DOWN_WORDS:
            continue
        cx, cy = (t["bbox"][0] + t["bbox"][2]) / 2, (t["bbox"][1] + t["bbox"][3]) / 2
        for i, e in enumerate(_ends(f)):
            d = math.hypot(cx - e[0], cy - e[1])
            if d <= 1.5 * w and (best is None or d < best[0]):
                best = (d, i, word)
    return (best[1], best[2]) if best else None


def detect_stairs(strokes: list[dict], stair_texts: list[dict], clean: np.ndarray, s: float) -> tuple[list[dict], list[dict]]:
    """Stairs in working pixels: [{flights: [{start, end, width_px, risers}], landings, confidence, direction_source}]."""
    flights = find_flights(strokes, s)
    links = {}
    for i, a in enumerate(flights):
        for j in range(i + 1, len(flights)):
            if (lk := _landing(a, flights[j], s)) and i not in links and j not in links:
                links[i] = (j, lk[0], lk[1], lk[2])
                links[j] = (i, lk[0], lk[2], lk[1])
    start: dict[int, tuple[int, str, float]] = {}  # flight -> (start end index, source, confidence)
    for i, f in enumerate(flights):
        if te := _text_end(f, stair_texts, s):
            end, word = te
            start[i] = (end if word in UP_WORDS else 1 - end, "text", 0.9)
    for i in list(start):  # the other flight of a landing leaves the landing the first one climbs to
        if i in links:
            j, _, land_i, land_j = links[i]
            if j not in start:
                climbs_to_landing = start[i][0] != land_i
                start[j] = (land_j if climbs_to_landing else 1 - land_j, "text", 0.8)
    issues = []
    for i in range(len(flights)):
        if i in start:
            continue
        if i in links:
            start[i] = (1 - links[i][2], "landing", 0.5)  # towards the landing
        else:
            start[i] = (0, "unknown", 0.3)
            e = _ends(flights[i])[0]
            issues.append({"code": "STAIR_DIR", "severity": "warning", "message": "arah naik tangga tidak jelas",
                           "at": [round(e[0], 1), round(e[1], 1)]})

    def as_flight(i: int) -> dict:
        ends = _ends(flights[i])
        a, b = ends[start[i][0]], ends[1 - start[i][0]]
        return {"start": [round(a[0], 2), round(a[1], 2)], "end": [round(b[0], 2), round(b[1], 2)],
                "width_px": round(flights[i]["width_mm"] / s, 2), "risers": flights[i]["risers"]}

    stairs, done = [], set()
    for i in range(len(flights)):
        if i in done:
            continue
        group = [i]
        landings = []
        if i in links:
            j, poly, _, land_j = links[i]
            first_climbs = start[i][0] != links[i][2]
            group = [i, j] if first_climbs else [j, i]
            landings = [[[round(x, 2), round(y, 2)] for x, y in poly]]
        done.update(group)
        src = min((start[g][1] for g in group), key=["text", "landing", "unknown"].index)
        stairs.append({"flights": [as_flight(g) for g in group], "landings": landings,
                       "confidence": min(start[g][2] for g in group), "direction_source": src})
    return stairs, issues


def _line_dist(p, a: dict) -> float:
    (x1, y1), (x2, y2) = a["p0"], a["p1"]
    length = math.hypot(x2 - x1, y2 - y1) or 1.0
    return abs((p[0] - x1) * (y2 - y1) - (p[1] - y1) * (x2 - x1)) / length


def lift_boxes(strokes: list[dict], s: float) -> list[list[float]]:
    """Box crossed by two diagonals (the lift symbol), 1000-3000 mm per side: [x0, y0, x1, y1].

    A diagonal broken at the crossing comes as several collinear pieces; all pieces on either diagonal count.
    """
    ang = lambda x: math.degrees(math.atan2(x["p1"][1] - x["p0"][1], x["p1"][0] - x["p0"][0])) % 180
    diag = [x for x in strokes if x["orient"] == "o" and 25 <= min(ang(x), 180 - ang(x)) <= 65]
    boxes: list[list[float]] = []
    for i, a in enumerate(diag):
        for b in diag[i + 1:]:
            if abs(abs(ang(a) - ang(b)) - 90) > 20:
                continue
            group = [x for x in diag if max(_line_dist(x["p0"], a), _line_dist(x["p1"], a)) <= 3
                     or max(_line_dist(x["p0"], b), _line_dist(x["p1"], b)) <= 3]
            pts = np.array([p for x in group for p in (x["p0"], x["p1"])], float)
            x0, y0 = pts.min(axis=0)
            x1, y1 = pts.max(axis=0)
            w_mm, h_mm = (x1 - x0) * s, (y1 - y0) * s
            if not (1000 <= w_mm <= 3000 and 1000 <= h_mm <= 3000 and 0.7 <= w_mm / h_mm <= 1.4):
                continue
            box = [round(float(v), 1) for v in (x0, y0, x1, y1)]
            if not any(abs(box[0] - o[0]) < 5 and abs(box[1] - o[1]) < 5 for o in boxes):
                boxes.append(box)
    return sorted(boxes)
