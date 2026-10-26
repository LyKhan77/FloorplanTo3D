"""One stage-3 candidate: masks → strokes → stairs → walls (S1 or S2) → post-processing → columns → doors →
confidence, converted to spec mm (elements.json)."""

import numpy as np

from core.extraction.geometry.columns import drop_at_columns, find_columns, find_pilasters
from core.extraction.geometry.confidence import wall_confidence
from core.extraction.geometry.doors import find_doors, fit_to_walls
from core.extraction.geometry.elements import to_mm
from core.extraction.geometry.masks import build_masks
from core.extraction.geometry.postprocess import postprocess
from core.extraction.geometry.stairs import detect_stairs, find_flights, lift_boxes, stair_mask
from core.extraction.geometry.strokes import extract_strokes
from core.extraction.geometry.walls_s1 import solid_walls
from core.extraction.geometry.walls_s2 import s2_walls
from core.extraction.preprocess import binarize

DEFAULT_THICKNESS_MM = 100


def _axes_px(grid_doc: dict) -> dict:
    return {o: [a["px"] for a in grid_doc.get("axes", []) if a["orientation"] == o] for o in ("vertical", "horizontal")}


def _wall_mask(raw: list[dict], shape: tuple[int, int], bbox, s: float) -> np.ndarray:
    """Plan wall mask for stage-8 IoU (PRD/06 §6.2): each raw wall filled between its two lines (S2) or over its
    stroke width (S1), clipped to the drawing area."""
    mask = np.zeros(shape, np.uint8)
    for w in raw:
        if w["orient"] == "o":
            continue
        half = w["thickness_mm"] / s / 2
        a, b, c0, c1 = round(w["a"]), round(w["b"]), round(w["c"] - half), round(w["c"] + half)
        if w["orient"] == "h":
            mask[max(0, c0):c1 + 1, max(0, a):b + 1] = 255
        else:
            mask[max(0, a):b + 1, max(0, c0):c1 + 1] = 255
    margin = round(300 / s)
    x0, y0, x1, y1 = bbox
    keep = np.zeros(shape, bool)
    keep[max(0, y0 - margin):y1 + margin, max(0, x0 - margin):x1 + margin] = True
    mask[~keep] = 0
    return mask


def extract_candidate(page_gray: np.ndarray, binary: np.ndarray, colour: np.ndarray, ocr_items: list[dict],
                      grid_doc: dict, meta: dict, params: dict, defaults: dict) -> dict:
    s = grid_doc["mm_per_px_work"]
    A = grid_doc["px_to_mm"]
    k = params.get("sauvola_k", 0.2)
    bin_ = binary if k == 0.2 else binarize(page_gray, k=k, window=25 * meta["upscale"])
    m = build_masks(bin_, colour, ocr_items, meta["drawing_bbox"], s, grid_doc.get("axes", []))
    l_fix = params.get("l_fix", 0) * meta["upscale"]
    strokes0 = extract_strokes(m["thin"], l_fix, s)  # treads are thin lines; thick stair walls and rails cut them
    stair_texts = [t for t in ocr_items if t.get("cls") == "stair_dir"]
    stairs, issues = detect_stairs(strokes0, stair_texts, m["clean"], s)
    clean = np.where(stair_mask(find_flights(strokes0, s), m["clean"].shape, s) > 0, 0, m["clean"]).astype(np.uint8)
    strokes = extract_strokes(clean, l_fix, s)
    thickness = defaults.get("wall_thickness", DEFAULT_THICKNESS_MM)
    if params["strategy"] == "S1":
        raw = solid_walls(clean, m["symbol"], s, params["t_min"])
    else:
        raw = s2_walls(strokes, s, params["t_min"], params["t_max"], thickness)
    if params["strategy"] == "S1":
        line_len = sum(w["b"] - w["a"] for w in raw if w["orient"] != "o") * s
    else:  # two drawn lines per wall
        line_len = sum(x["b"] - x["a"] for x in strokes if x["orient"] != "o" and (x["b"] - x["a"]) * s >= 300) * s / 2
    axes_px = _axes_px(grid_doc)
    proposed = [t for t in ocr_items if t.get("cls") == "proposed"]
    walls, gaps, post_issues = postprocess(raw, axes_px, m["pointers"], proposed, s)
    columns = find_columns(clean, m["symbol"], grid_doc.get("axes", []), walls, s) + \
        find_pilasters(clean, walls, grid_doc.get("axes", []), s)
    thin = np.where(clean > 0, m["thin"], 0).astype(np.uint8)
    doors = find_doors(thin, extract_strokes(thin, l_fix, s), walls, gaps, s)
    walls, doors = drop_at_columns(walls, doors, columns, s)
    doors, walls = fit_to_walls(doors, walls, s)

    def mm_pt(p) -> list[int]:
        return list(to_mm(A, p[0], p[1]))

    el_walls = []
    for w in walls:
        ev = {k: v for k, v in w["evidence"].items() if k != "from"}
        el_walls.append({"a": mm_pt(w["p0"]), "b": mm_pt(w["p1"]), "thickness": max(10, round(w["thickness_mm"])),
                         "kind": w.get("kind", "interior"), "strategy": w["strategy"],
                         "confidence": wall_confidence(w, m["hatch"], ocr_items, axes_px, walls, s, strokes),
                         "evidence": ev})
    el_cols = [{"center": mm_pt(c["center_px"]), "size": c["size_mm"], "shape": c["shape"], "rotation": 0,
                "kind": c["kind"], "confidence": c["confidence"], "grid_ref": c["grid_ref"]} for c in columns]
    el_stairs = [{"flights": [{"start": mm_pt(f["start"]), "end": mm_pt(f["end"]), "width": round(f["width_px"] * s),
                               "risers": f["risers"]} for f in st["flights"]],
                  "landings": [[mm_pt(p) for p in poly] for poly in st["landings"]],
                  "confidence": st["confidence"], "direction_source": st["direction_source"]} for st in stairs]
    el_issues = [{**i, "at": mm_pt(i["at"]) if i.get("at") else None} for i in issues + post_issues]
    el_lifts = []
    for x0, y0, x1, y1 in lift_boxes(strokes, s):
        (ax, ay), (bx, by) = mm_pt((x0, y0)), mm_pt((x1, y1))
        el_lifts.append([min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)])
    return {"params": params, "walls": el_walls, "columns": el_cols, "openings": doors, "stairs": el_stairs,
            "lifts": el_lifts, "line_len_m": round(line_len / 1000, 2), "issues": el_issues,
            "_masks": {"stair": stair_mask(find_flights(strokes0, s), clean.shape, s), "hatch": m["hatch"],
                       "symbol": m["symbol"], "wall": _wall_mask(raw, clean.shape, meta["drawing_bbox"], s)},
            "_px": {"walls": walls, "columns": columns, "stairs": stairs}}
