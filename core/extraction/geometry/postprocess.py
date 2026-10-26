"""Wall post-processing (PRD/04 §3.2 "Pasca-proses") and the existing-condition rules (§3.1.6). Working pixels.

Gaps 600-3000 mm between clean wall ends are closed and kept as evidence["gaps"] (px along the wall); after the
last step they become gap openings with offsets in mm from the wall's a end.
"""

import math

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from core.extraction.geometry.walls_s2 import _wall

CLOSE_GAP_MM = 600
OPENING_GAP_MM = 3000
SNAP_MM = 150
MIN_MM = 300
INTERIOR_MIN_MM = 120
POINTER_TOL_MM = 100
PROPOSED_NEAR_MM = 1000


def _t(w: dict, s: float) -> float:
    return w["thickness_mm"] / s


def _end_xy(w: dict, which: str) -> tuple[float, float]:
    v = w["a"] if which == "a" else w["b"]
    return (v, w["c"]) if w["orient"] == "h" else (w["c"], v)


def _touches(w: dict, which: str, walls: list[dict], s: float) -> bool:
    """The end meets a perpendicular wall's footprint (within half thicknesses)."""
    x, y = _end_xy(w, which)
    for o in walls:
        if o is w or o["orient"] == w["orient"] or o["orient"] == "o":
            continue
        along, across = (x, y) if o["orient"] == "h" else (y, x)
        tol = _t(o, s) / 2 + _t(w, s) / 2 + 1
        if abs(across - o["c"]) <= tol and o["a"] - tol <= along <= o["b"] + tol:
            return True
    return False


def _rebuild(w: dict, **changes) -> dict:
    n = {**w, **changes}
    out = _wall(n["orient"], n["c"], n["a"], n["b"], n["thickness_mm"], n["evidence"])
    out["strategy"] = n["strategy"]
    if "kind" in n:
        out["kind"] = n["kind"]
    return out


def merge_collinear(walls: list[dict], s: float, max_gap_mm: float = CLOSE_GAP_MM) -> tuple[list[dict], list[dict]]:
    """(walls, []) — closed openings are recorded in evidence["gaps"]; the list is filled by postprocess()."""
    out: list[dict] = []
    straight = [w for w in walls if w["orient"] != "o"]
    for w in sorted(straight, key=lambda w: (w["orient"], round(w["c"]), w["a"])):
        last = out[-1] if out else None
        if last and last["orient"] == w["orient"] and abs(last["c"] - w["c"]) <= 2 \
                and abs(last["thickness_mm"] - w["thickness_mm"]) <= 0.25 * max(last["thickness_mm"], w["thickness_mm"]):
            gap_mm = (w["a"] - last["b"]) * s
            opening = max_gap_mm < gap_mm <= OPENING_GAP_MM and not _touches(last, "b", walls, s) \
                and not _touches(w, "a", walls, s)
            if gap_mm <= max_gap_mm or opening:
                la, lb = last["b"] - last["a"], w["b"] - w["a"]
                gaps = last["evidence"].get("gaps", []) + w["evidence"].get("gaps", []) + \
                    ([[last["b"], w["a"]]] if opening else [])
                ev = last["evidence"] | {"gaps": gaps,
                                         "partial_mm": max(last["evidence"].get("partial_mm", 0), w["evidence"].get("partial_mm", 0))}
                out[-1] = _rebuild(last, c=(last["c"] * la + w["c"] * lb) / max(la + lb, 1e-9), b=max(last["b"], w["b"]),
                                   thickness_mm=(last["thickness_mm"] * la + w["thickness_mm"] * lb) / max(la + lb, 1e-9),
                                   evidence=ev)
                continue
        out.append(w)
    return out + [w for w in walls if w["orient"] == "o"], []


def _snap(v: float, axes: list[float], tol: float) -> float:
    near = min(axes, key=lambda a: abs(a - v), default=None)
    return near if near is not None and abs(near - v) <= tol else v


def snap_to_grid(walls: list[dict], axes_px: dict, s: float, tol_mm: float = SNAP_MM) -> list[dict]:
    tol = tol_mm / s
    out = []
    for w in walls:
        if w["orient"] == "o":
            out.append(w)
            continue
        across, along = (axes_px["horizontal"], axes_px["vertical"]) if w["orient"] == "h" else \
            (axes_px["vertical"], axes_px["horizontal"])
        out.append(_rebuild(w, c=_snap(w["c"], across, tol), a=_snap(w["a"], along, tol), b=_snap(w["b"], along, tol)))
    return out


def join_ends(walls: list[dict], s: float) -> list[dict]:
    """Extend or trim each end onto the centreline of the nearest perpendicular wall within its thickness (L/T)."""
    out = []
    for w in walls:
        if w["orient"] == "o":
            out.append(w)
            continue
        ends = {}
        for which in ("a", "b"):
            v = w[which]
            best = None
            for o in walls:
                if o is w or o["orient"] in (w["orient"], "o"):
                    continue
                t = _t(o, s)
                if abs(v - o["c"]) <= t and o["a"] - t <= w["c"] <= o["b"] + t:
                    if best is None or abs(v - o["c"]) < abs(v - best):
                        best = o["c"]
            ends[which] = v if best is None else best
        if ends["b"] - ends["a"] > 0:
            out.append(_rebuild(w, a=ends["a"], b=ends["b"]))
        else:
            out.append(w)
    return out


def drop_short(walls: list[dict], s: float, min_mm: float = MIN_MM) -> list[dict]:
    return [w for w in walls if w["orient"] == "o" or (w["b"] - w["a"]) * s >= min_mm
            or _touches(w, "a", walls, s) or _touches(w, "b", walls, s)]


def _line(w: dict) -> LineString:
    return LineString([w["p0"], w["p1"]])


def classify_kind(walls: list[dict], s: float) -> list[dict]:
    if not walls:
        return []
    union = unary_union([_line(w).buffer(_t(w, s) / 2, cap_style="flat") for w in walls])
    rings = [p.exterior for p in getattr(union, "geoms", [union])]
    out = []
    for w in walls:
        mid = _line(w).interpolate(0.5, normalized=True)
        exterior = any(r.distance(mid) <= _t(w, s) / 2 + 1.5 for r in rings)
        kind = "exterior" if exterior else "interior" if w["thickness_mm"] >= INTERIOR_MIN_MM else "partition"
        out.append(_rebuild(w, kind=kind))
    return out


def apply_existing(walls: list[dict], pointers: list[dict], proposed_texts: list[dict], s: float) -> tuple[list[dict], list[dict]]:
    issues, out = [], []
    led = {tuple(p["text_bbox"]) for p in pointers}
    lone = [t for t in proposed_texts if t.get("cls") == "proposed" and tuple(t["bbox"]) not in led]
    for w in walls:
        line, tol = _line(w), _t(w, s) / 2 + POINTER_TOL_MM / s
        hits = [p for p in pointers if line.distance(Point(p["point"])) <= tol]
        near = [t for t in lone if all(box(*t["bbox"]).distance(Point(p)) <= PROPOSED_NEAR_MM / s for p in (w["p0"], w["p1"]))]
        if any(p["cls"] == "proposed" for p in hits) or near:
            mid = line.interpolate(0.5, normalized=True)
            issues.append({"code": "EXISTING_PROPOSED", "severity": "info",
                           "message": "dinding ditandai PROPOSED tidak dimodelkan (kondisi existing)",
                           "at": [round(mid.x, 1), round(mid.y, 1)]})
            continue
        if any(p["cls"] == "dismantle" for p in hits):
            w = _rebuild(w, evidence=w["evidence"] | {"note": "to_be_dismantled"})
        out.append(w)
    return out, issues


def postprocess(raw: list[dict], axes_px: dict, pointers: list[dict], proposed_texts: list[dict],
                s: float) -> tuple[list[dict], list[dict], list[dict]]:
    walls, _ = merge_collinear(raw, s)
    walls = snap_to_grid(walls, axes_px, s)
    walls = join_ends(walls, s)
    walls = drop_short(walls, s)
    walls = classify_kind(walls, s)
    walls, issues = apply_existing(walls, pointers, proposed_texts, s)
    walls = sorted(walls, key=lambda w: (w["orient"], w["c"], w["a"]))
    gaps = []
    for i, w in enumerate(walls):
        for ga, gb in w["evidence"].get("gaps", []):
            if w["a"] <= ga < gb <= w["b"]:
                gaps.append({"wall_index": i, "offset_mm": round((ga - w["a"]) * s), "width_mm": round((gb - ga) * s)})
    return walls, gaps, issues


def length_mm(w: dict, s: float) -> float:
    return math.dist(w["p0"], w["p1"]) * s
