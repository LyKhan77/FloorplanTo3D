"""One stage-3 candidate: masks → strokes → stairs → walls (S1 or S2) → post-processing → columns → doors →
confidence, converted to spec mm (elements.json)."""

import numpy as np

from core.extraction.geometry.columns import find_columns, find_pilasters
from core.extraction.geometry.confidence import wall_confidence
from core.extraction.geometry.doors import find_doors
from core.extraction.geometry.elements import to_mm
from core.extraction.geometry.masks import build_masks
from core.extraction.geometry.postprocess import postprocess
from core.extraction.geometry.stairs import detect_stairs, find_flights, stair_mask
from core.extraction.geometry.strokes import extract_strokes
from core.extraction.geometry.walls_s1 import solid_walls
from core.extraction.geometry.walls_s2 import s2_walls
from core.extraction.preprocess import binarize

DEFAULT_THICKNESS_MM = 100


def _axes_px(grid_doc: dict) -> dict:
    return {o: [a["px"] for a in grid_doc.get("axes", []) if a["orientation"] == o] for o in ("vertical", "horizontal")}


def extract_candidate(page_gray: np.ndarray, binary: np.ndarray, colour: np.ndarray, ocr_items: list[dict],
                      grid_doc: dict, meta: dict, params: dict, defaults: dict) -> dict:
    s = grid_doc["mm_per_px_work"]
    A = grid_doc["px_to_mm"]
    k = params.get("sauvola_k", 0.2)
    bin_ = binary if k == 0.2 else binarize(page_gray, k=k, window=25 * meta["upscale"])
    m = build_masks(bin_, colour, ocr_items, meta["drawing_bbox"], s)
    l_fix = params.get("l_fix", 0) * meta["upscale"]
    strokes0 = extract_strokes(m["clean"], l_fix, s)
    stair_texts = [t for t in ocr_items if t.get("cls") == "stair_dir"]
    stairs, issues = detect_stairs(strokes0, stair_texts, m["clean"], s)
    clean = np.where(stair_mask(find_flights(strokes0, s), m["clean"].shape, s) > 0, 0, m["clean"]).astype(np.uint8)
    strokes = extract_strokes(clean, l_fix, s)
    thickness = defaults.get("wall_thickness", DEFAULT_THICKNESS_MM)
    if params["strategy"] == "S1":
        raw = solid_walls(clean, m["symbol"], s, params["t_min"])
    else:
        raw = s2_walls(strokes, s, params["t_min"], params["t_max"], thickness)
    axes_px = _axes_px(grid_doc)
    proposed = [t for t in ocr_items if t.get("cls") == "proposed"]
    walls, gaps, post_issues = postprocess(raw, axes_px, m["pointers"], proposed, s)
    columns = find_columns(clean, m["symbol"], grid_doc.get("axes", []), walls, s) + \
        find_pilasters(clean, walls, grid_doc.get("axes", []), s)
    doors = find_doors(clean, strokes, walls, gaps, s)

    def mm_pt(p) -> list[int]:
        return list(to_mm(A, p[0], p[1]))

    el_walls = []
    for w in walls:
        ev = {k: v for k, v in w["evidence"].items() if k != "from"}
        el_walls.append({"a": mm_pt(w["p0"]), "b": mm_pt(w["p1"]), "thickness": max(10, round(w["thickness_mm"])),
                         "kind": w.get("kind", "interior"), "strategy": w["strategy"],
                         "confidence": wall_confidence(w, m["hatch"], ocr_items, axes_px, walls, s), "evidence": ev})
    el_cols = [{"center": mm_pt(c["center_px"]), "size": c["size_mm"], "shape": c["shape"], "rotation": 0,
                "kind": c["kind"], "confidence": c["confidence"], "grid_ref": c["grid_ref"]} for c in columns]
    el_stairs = [{"flights": [{"start": mm_pt(f["start"]), "end": mm_pt(f["end"]), "width": round(f["width_px"] * s),
                               "risers": f["risers"]} for f in st["flights"]],
                  "landings": [[mm_pt(p) for p in poly] for poly in st["landings"]],
                  "confidence": st["confidence"], "direction_source": st["direction_source"]} for st in stairs]
    el_issues = [{**i, "at": mm_pt(i["at"]) if i.get("at") else None} for i in issues + post_issues]
    return {"params": params, "walls": el_walls, "columns": el_cols, "openings": doors, "stairs": el_stairs,
            "issues": el_issues, "_masks": {"stair": stair_mask(find_flights(strokes0, s), clean.shape, s),
                                            "hatch": m["hatch"], "symbol": m["symbol"]},
            "_px": {"walls": walls, "columns": columns, "stairs": stairs}}
