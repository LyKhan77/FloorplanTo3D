"""Guide-line snap (M8 review): a rough line a person drew over a missed wall lands on the drawing's wall line.

Along the rough line, every SAMPLE_MM a profile across it (±search_mm) lists the ink runs. The wall is the pair of
runs 60-400 mm apart (its two faces) that the most samples agree on, by vote, not the pair nearest the rough line
in one sample (Gatsu: a door leaf or a fin line next to a wall would win that). No agreed pair: the single line most
samples agree on, with the default thickness (Gatsu draws some walls as one face line). The agreed offsets are fitted
along the line, so a slightly askew rough line still lands straight.
"""

import math

import numpy as np

from core.extraction.rooms.overlay import px_from_mm

SAMPLE_MM = 100
FACE_MIN_MM, FACE_MAX_MM = 60, 400
INLIER_MM = 40
ASKEW = math.tan(math.radians(2))
MIN_AGREE = 0.6


def _runs(ink: np.ndarray, offsets: np.ndarray) -> list[float]:
    """Centre offset of every run of ink along the profile."""
    out, start = [], None
    for i, v in enumerate(ink):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append(float(offsets[start:i].mean()))
            start = None
    if start is not None:
        out.append(float(offsets[start:].mean()))
    return out


def _vote(samples: list[tuple[float, list[tuple]]], need: float) -> list[tuple[float, tuple]] | None:
    """Per sample, the candidate closest to the one most samples share (ties: nearest the rough line). The offset
    window widens along the line by ASKEW, so a rough line up to 2 degrees off the wall still agrees with itself."""
    cands = [(t, c) for t, cs in samples for c in cs]
    if not cands:
        return None
    def near(tc, c, td, d) -> bool:
        return abs(c[0] - d[0]) <= INLIER_MM + ASKEW * abs(td - tc) and all(abs(x - y) <= INLIER_MM for x, y in zip(c[1:], d[1:]))
    tb, best = max(cands, key=lambda tc: (sum(any(near(*tc, t, d) for d in cs) for t, cs in samples), -abs(tc[1][0])))
    picked = []
    for t, cs in samples:
        ok = [d for d in cs if near(tb, best, t, d)]
        if ok:
            picked.append((t, min(ok, key=lambda d: abs(d[0] - best[0]))))
    return picked if len(picked) >= need else None


def snap_wall(binary: np.ndarray, px_to_mm: list[float], a, b, search_mm: float = 250,
              default_mm: int = 150) -> dict | None:
    """{"a", "b", "thickness", "source": "double" | "single"} in mm, or None when no wall line runs along a-b."""
    length = math.dist(a, b)
    if length < SAMPLE_MM:
        return None
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    nx, ny = -uy, ux
    to_px = px_from_mm(px_to_mm)
    step = abs(px_to_mm[0]) / 2 or 1.0  # half a pixel along the profile
    offsets = np.arange(-search_mm, search_mm + step, step)
    h, w = binary.shape[:2]
    n = max(2, int(length // SAMPLE_MM))
    pairs, lines = [], []
    for k in range(n + 1):
        t = length * k / n
        c = (a[0] + ux * t, a[1] + uy * t)
        ink = np.zeros(len(offsets), bool)
        for i, o in enumerate(offsets):
            x, y = to_px(c[0] + nx * o, c[1] + ny * o)
            xi, yi = round(x), round(y)
            ink[i] = 0 <= xi < w and 0 <= yi < h and binary[yi, xi] > 0
        runs = _runs(ink, offsets)
        pairs.append((t, [((p + q) / 2, q - p) for i, p in enumerate(runs) for q in runs[i + 1:]
                          if FACE_MIN_MM <= q - p <= FACE_MAX_MM]))
        lines.append((t, [(r,) for r in runs]))
    need = MIN_AGREE * (n + 1)
    picked, source = _vote(pairs, need), "double"
    if picked is None:
        picked, source = _vote(lines, need), "single"
    if picked is None:
        return None
    ts = np.array([t for t, _ in picked])
    mids = np.array([c[0] for _, c in picked])
    beta, alpha = np.polyfit(ts, mids, 1) if len(ts) > 2 else (0.0, float(np.median(mids)))
    end = lambda t: (a[0] + ux * t + nx * (alpha + beta * t), a[1] + uy * t + ny * (alpha + beta * t))
    thickness = int(round(float(np.median([c[1] for _, c in picked])) / 10) * 10) if source == "double" else default_mm
    return {"a": [round(v) for v in end(0.0)], "b": [round(v) for v in end(length)], "thickness": thickness,
            "source": source}
