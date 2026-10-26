"""Scale from dimension chains between grid axes (PRD/04 §2.3) and px_to_mm.

A dimension text measures along X (horizontal text, vertical axes) or Y (vertical text, horizontal axes). It is
first read as the span between the two neighbouring axes that bracket it; equations that disagree with the
median scale by > 1% are re-matched to any bracketing axis pair (totals such as 28000 = A..F) or dropped.
"""

import itertools
import re
import statistics

from core.extraction.ocr import OcrItem

MAX_RESIDUAL = 0.01
SCREEN = 0.05  # first pass against the shared median: catches wrong spans (a total read as one bay), not noise
MAX_ANISOTROPY = 0.01
MSG_NO_SCALE = "Skala tidak dapat ditentukan, isi skala manual"


def _value(text: str) -> int | None:
    digits = re.sub(r"[\s.,]", "", text)
    return int(digits) if digits.isdigit() else None


def _axes(grid: dict, orientation: str) -> list[dict]:
    return sorted(grid["vertical" if orientation == "x" else "horizontal"], key=lambda a: a["px"])


def _center(item: OcrItem, orientation: str) -> float:
    return (item.bbox[0] + item.bbox[2]) / 2 if orientation == "x" else (item.bbox[1] + item.bbox[3]) / 2


def _eq(value: int, a: dict, b: dict, orientation: str, item: OcrItem) -> dict:
    return {"value_mm": value, "axis_from": a["label"], "axis_to": b["label"], "px": round(abs(b["px"] - a["px"]), 3),
            "orientation": orientation, "text_bbox": [round(v, 1) for v in item.bbox]}


def dimension_equations(grid: dict, dims: list[OcrItem]) -> list[dict]:
    eqs = []
    for item in dims:
        value = _value(item.text)
        orientation = "x" if item.angle == 0 else "y"
        axes = _axes(grid, orientation)
        c = _center(item, orientation)
        pair = next(((a, b) for a, b in itertools.pairwise(axes) if a["px"] <= c <= b["px"]), None)
        if value and pair:
            eqs.append(_eq(value, *pair, orientation, item) | {"_item": item})
    return eqs


def _rematch(eq: dict, grid: dict, s: float, tol: float = MAX_RESIDUAL) -> dict | None:
    axes = _axes(grid, eq["orientation"])
    c = _center(eq["_item"], eq["orientation"])
    cands = [(abs(b["px"] - a["px"]) * s, a, b) for i, a in enumerate(axes) for b in axes[i + 1:]
             if a["px"] <= c <= b["px"]]
    best = min(cands, key=lambda t: abs(t[0] - eq["value_mm"]), default=None)
    if best and abs(best[0] - eq["value_mm"]) / eq["value_mm"] <= tol:
        return _eq(eq["value_mm"], best[1], best[2], eq["orientation"], eq["_item"]) | {"_item": eq["_item"]}
    return None


def _outermost(eq: dict, grid: dict) -> dict | None:
    """PRD/04 §2.3 fallback 3: a lone dimension is the total between the end axes that bracket it."""
    axes = _axes(grid, eq["orientation"])
    c = _center(eq["_item"], eq["orientation"])
    if len(axes) >= 2 and axes[0]["px"] <= c <= axes[-1]["px"]:
        return _eq(eq["value_mm"], axes[0], axes[-1], eq["orientation"], eq["_item"]) | {"_item": eq["_item"]}
    return None


def _fit(group: list[dict]) -> float:
    return sum(e["value_mm"] * e["px"] for e in group) / sum(e["px"] ** 2 for e in group)


def _residual(e: dict, s: float) -> float:
    return abs(e["value_mm"] - s * e["px"]) / e["value_mm"]


def solve_scale(eqs: list[dict], grid: dict) -> dict:
    eqs = [e for e in eqs if e["px"] > 0]
    if len(eqs) == 1:
        eqs = [m] if (m := _outermost(eqs[0], grid)) else []
    if not eqs:
        return {"sx": None, "sy": None, "isotropic": True, "used": [], "dropped": [], "residuals": []}
    # one starting scale for both directions: a direction with few spans would otherwise anchor on a single
    # noisy span (bubble centres are +/- 2 px, i.e. ~0.5% of a 6 m span at 1600 px)
    s0 = statistics.median(e["value_mm"] / e["px"] for e in eqs)
    used, dropped = [], []
    for e in eqs:
        if _residual(e, s0) <= SCREEN:
            used.append(e)
        elif m := _rematch(e, grid, s0, SCREEN):
            used.append(m)
        else:
            dropped.append(e)
    scale = {}
    for o in ("x", "y"):
        group = [e for e in used if e["orientation"] == o]
        if group:
            s = _fit(group)
            keep = [e for e in group if _residual(e, s) <= MAX_RESIDUAL]
            dropped += [e for e in group if e not in keep]
            used = [e for e in used if e["orientation"] != o or e in keep]
            if keep:
                scale[o] = _fit(keep)
    if not scale:
        return {"sx": None, "sy": None, "isotropic": True, "used": [], "dropped": dropped, "residuals": []}
    sx, sy = scale.get("x", scale.get("y")), scale.get("y", scale.get("x"))
    isotropic = abs(sx - sy) / ((sx + sy) / 2) <= MAX_ANISOTROPY
    if isotropic:
        nx, ny = sum(e["orientation"] == "x" for e in used), sum(e["orientation"] == "y" for e in used)
        sx = sy = (sx * nx + sy * ny) / (nx + ny)
    residuals = [round(_residual(e, sx if e["orientation"] == "x" else sy), 6) for e in used]
    return {"sx": sx, "sy": sy, "isotropic": isotropic, "used": used, "dropped": dropped, "residuals": residuals}


def _adjacent(e: dict, axes: list[dict]) -> tuple[int, int] | None:
    idx = {a["label"]: i for i, a in enumerate(axes)}
    i, j = sorted((idx[e["axis_from"]], idx[e["axis_to"]]))
    return (i, j) if j == i + 1 else None


def axis_offsets(grid: dict, used: list[dict], sx: float, sy: float) -> dict[tuple[str, str], int]:
    """mm offsets: vertical axes from the leftmost, horizontal axes from the bottom one (Y up). A chain of matched
    neighbouring dimensions gives exact values; a gap falls back to the scaled pixel distance rounded to 10 mm."""
    out = {}
    for o, name, s in (("x", "vertical", sx), ("y", "horizontal", sy)):
        axes = _axes(grid, o) if o == "x" else _axes(grid, o)[::-1]
        spans = {}
        for e in used:
            if e["orientation"] == o and (adj := _adjacent(e, sorted(axes, key=lambda a: a["px"]))):
                labels = sorted(axes, key=lambda a: a["px"])
                spans[frozenset((labels[adj[0]]["label"], labels[adj[1]]["label"]))] = e["value_mm"]
        offset = 0
        for k, a in enumerate(axes):
            if k:
                prev = axes[k - 1]
                offset += spans.get(frozenset((prev["label"], a["label"])),
                                    round(abs(a["px"] - prev["px"]) * s / 10) * 10)
            out[(name, a["label"])] = offset
    return out


def _cross_check(used: list[dict], grid: dict) -> list[str]:
    warnings = []
    for o in ("x", "y"):
        axes = _axes(grid, o)
        idx = {a["label"]: i for i, a in enumerate(axes)}
        adj = {tuple(sorted((idx[e["axis_from"]], idx[e["axis_to"]]))): e["value_mm"]
               for e in used if e["orientation"] == o and _adjacent(e, axes)}
        for e in used:
            if e["orientation"] != o or _adjacent(e, axes):
                continue
            i, j = sorted((idx[e["axis_from"]], idx[e["axis_to"]]))
            parts = [adj.get((k, k + 1)) for k in range(i, j)]
            if all(parts) and abs(sum(parts) - e["value_mm"]) / e["value_mm"] > MAX_RESIDUAL:
                warnings.append(f"dimensi total {e['value_mm']} ≠ jumlah bagian {sum(parts)} "
                                f"({e['axis_from']}–{e['axis_to']})")
    return warnings


def compose_original(px_to_mm_work: list[float], work_from_original: list[float]) -> list[float]:
    a, b, c, d, e, f = px_to_mm_work
    p, q, r, s, t, u = work_from_original
    return [a * p + b * s, a * q + b * t, a * r + b * u + c, d * p + e * s, d * q + e * t, d * r + e * u + f]


def _public(e: dict) -> dict:
    return {k: v for k, v in e.items() if not k.startswith("_")}


def scale_from(grid: dict, dims: list[OcrItem], manual_mm_per_px: float | None) -> dict:
    solved = solve_scale(dimension_equations(grid, dims), grid)
    warnings = list(grid.get("warnings", []))
    sx, sy = solved["sx"], solved["sy"]
    computed = (sx * sy) ** 0.5 if sx else None
    if manual_mm_per_px:
        if computed and abs(computed - manual_mm_per_px) / manual_mm_per_px > MAX_RESIDUAL:
            warnings.append(f"skala manual {manual_mm_per_px:.3f} berbeda "
                            f"{abs(computed - manual_mm_per_px) / manual_mm_per_px:.1%} dari skala hasil hitung "
                            f"{computed:.3f} mm/px")
        sx = sy = float(manual_mm_per_px)
        source = "manual"
    elif sx is None:
        return {"status": "needs_attention", "message": MSG_NO_SCALE, "axes": [], "warnings": warnings,
                "equations_used": [], "equations_dropped": [_public(e) for e in solved["dropped"]]}
    else:
        adjacent = any(_adjacent(e, _axes(grid, e["orientation"])) for e in solved["used"])
        source = "grid_dimensions" if adjacent or len(solved["used"]) > 1 else "total_length"
    warnings += _cross_check(solved["used"], grid)
    offsets = axis_offsets(grid, solved["used"], sx, sy)
    x0 = min(a["px"] for a in grid["vertical"]) if grid["vertical"] else 0.0
    y0 = max(a["px"] for a in grid["horizontal"]) if grid["horizontal"] else 0.0
    axes = [{"id": f"G{a['label']}", "label": a["label"], "orientation": name, "offset": offsets[(name, a["label"])],
             "px": round(a["px"], 3)}
            for name in ("vertical", "horizontal") for a in sorted(grid[name], key=lambda a: a["px"])]
    return {
        "status": "succeeded", "message": "", "axes": axes, "sx": sx, "sy": sy, "isotropic": solved["isotropic"],
        "px_to_mm": [sx, 0.0, -sx * x0, 0.0, -sy, sy * y0], "mm_per_px": (sx * sy) ** 0.5, "scale_source": source,
        "residuals": solved["residuals"], "equations_used": [_public(e) for e in solved["used"]],
        "equations_dropped": [_public(e) for e in solved["dropped"]], "warnings": warnings,
    }
