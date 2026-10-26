"""Stages 0-2 as artefact-writing steps (PRD/04): input.json, page.png/bin.png/meta.json, ocr.json/grid.json/overlay.png.

Each stage reads the previous stages' folders next to its own work folder (runs/<id>/stages/NN_name).
"""

import json
from collections.abc import Callable
from pathlib import Path

import cv2

from core.extraction.geometry.candidate import extract_candidate
from core.extraction.geometry.overlay import render_elements_overlay
from core.extraction.geometry.sweep import run_sweep, sweep_params
from core.extraction.grid import detect_grid
from core.extraction.overlay import render_grid_overlay
from core.extraction.params import input_doc, merge_params, parse_prompt
from core.extraction.preprocess import load_raster, preprocess
from core.extraction.scale import compose_original, scale_from
from core.extraction.textclass import classify_text, ocr_page

Progress = Callable[[int, str], None] | None


def _round(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_round(x) for x in v]
    return v


def write_json(path: Path, obj) -> None:
    """Deterministic JSON (NFR-RL-06): sorted keys, floats rounded to 4 decimals."""
    path.write_text(json.dumps(_round(obj), indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def _upload(project_dir: Path) -> dict:
    return json.loads((project_dir / "input" / "input.json").read_text())


def run_params(project_dir: Path, override: dict | None = None) -> dict:
    up = _upload(project_dir)
    return merge_params({**(up.get("params") or {}), **(override or {})}, parse_prompt(up.get("prompt") or ""))


def _original(project_dir: Path) -> Path:
    return next(p for p in sorted((project_dir / "input").glob("original.*")))


def stage_input(project_dir: Path, work: Path, override: dict | None = None) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    up = _upload(project_dir)
    doc = input_doc(up) | {"params_final": run_params(project_dir, override)}
    write_json(work / "input.json", doc)
    return {"status": "succeeded", "metrics": {"type": up.get("type"), "page": doc["page"]}}


def stage_preprocess(project_dir: Path, work: Path) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    doc_path = work.parent / "00_input" / "input.json"
    page_no = json.loads(doc_path.read_text())["page"] if doc_path.exists() else (_upload(project_dir).get("page") or 1)
    original = _original(project_dir)
    raster = load_raster(original, page_no)
    if original.suffix == ".pdf":  # later stages, the editor and the report need a raster of the plan
        cv2.imwrite(str(project_dir / "input" / "raster.png"), raster)
    r = preprocess(raster)
    cv2.imwrite(str(work / "page.png"), r.page)
    cv2.imwrite(str(work / "bin.png"), r.binary)
    cv2.imwrite(str(work / "colour.png"), r.colour)
    write_json(work / "meta.json", r.meta)
    return {"status": r.status, "message": r.message, "warnings": r.warnings,
            "metrics": {"deskew_deg": r.meta["deskew_deg"], "upscale": r.meta["upscale"],
                        "work_w": r.meta["work_size"][0], "work_h": r.meta["work_size"][1]}}


def _inside(bbox, box) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def stage_grid(project_dir: Path, work: Path, override: dict | None = None, progress: Progress = None) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    pre = work.parent / "01_preprocess"
    meta = json.loads((pre / "meta.json").read_text())
    page = cv2.imread(str(pre / "page.png"), cv2.IMREAD_GRAYSCALE)
    binary = cv2.imread(str(pre / "bin.png"), cv2.IMREAD_GRAYSCALE)
    params = run_params(project_dir, override)
    ocr = ocr_page(page, meta["upscale"])
    if progress:
        progress(30, "OCR")
    grid = detect_grid(page, binary, ocr)
    if progress:
        progress(60, "grid")
    bubbles = [a["bubble"] for a in grid["vertical"] + grid["horizontal"]]

    def in_circle(item) -> bool:
        cx, cy = (item.bbox[0] + item.bbox[2]) / 2, (item.bbox[1] + item.bbox[3]) / 2
        return any((cx - b["cx"]) ** 2 + (cy - b["cy"]) ** 2 < b["r"] ** 2 for b in bubbles)

    classes = [classify_text(i, in_circle=in_circle(i), in_building=_inside(i.bbox, meta["drawing_bbox"])) for i in ocr]
    write_json(work / "ocr.json", [{"text": i.text, "bbox": list(i.bbox), "angle": i.angle, "conf": i.conf, "cls": c}
                                   for i, c in zip(ocr, classes, strict=True)])
    dims = [i for i, c in zip(ocr, classes, strict=True) if c == "dimension"]
    # the form's manual scale is mm per *original* pixel; the solver works in working pixels
    a, b, _, d, e, _ = meta["work_from_original"]
    work_per_original = abs(a * e - b * d) ** 0.5
    manual = params.get("mm_per_px")
    doc = scale_from(grid, dims, manual / work_per_original if manual else None, unit=work_per_original)
    if progress:
        progress(90, "skala")
    if doc["status"] == "succeeded":
        orig = compose_original(doc["px_to_mm"], meta["work_from_original"])
        doc |= {"px_to_mm_original": orig, "mm_per_px_work": doc["mm_per_px"],
                "mm_per_px": abs(orig[0] * orig[4] - orig[1] * orig[3]) ** 0.5}
    write_json(work / "grid.json", doc)
    cv2.imwrite(str(work / "overlay.png"), render_grid_overlay(page, doc))
    residuals = doc.get("residuals") or [0]
    return {"status": doc["status"], "message": doc.get("message", ""), "warnings": doc.get("warnings", []),
            "metrics": {"axes_v": len(grid["vertical"]), "axes_h": len(grid["horizontal"]),
                        "mm_per_px": round(doc["mm_per_px"], 4) if doc.get("mm_per_px") else None,
                        "scale_source": doc.get("scale_source"), "residual_max_pct": round(100 * max(residuals), 3)}}


def _candidate_job(inputs: dict, index: int, params: dict) -> dict:
    """One sweep candidate (top-level so ProcessPoolExecutor can pickle it). Writes its own artefacts."""
    el = extract_candidate(inputs["page"], inputs["binary"], inputs["colour"], inputs["ocr"], inputs["grid"],
                           inputs["meta"], params, inputs["defaults"])
    out = Path(inputs["work"]) / "candidates" / str(index)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "elements.json", {k: v for k, v in el.items() if not k.startswith("_")})
    cv2.imwrite(str(out / "overlay.png"), render_elements_overlay(inputs["page"], el, inputs["grid"]["mm_per_px_work"]))
    if index == 0:
        (Path(inputs["work"]) / "masks").mkdir(exist_ok=True)
        for name, mask in el["_masks"].items():
            cv2.imwrite(str(Path(inputs["work"]) / "masks" / f"{name}.png"), mask)
    s = inputs["grid"]["mm_per_px_work"]
    wall_len = sum(((w["p1"][0] - w["p0"][0]) ** 2 + (w["p1"][1] - w["p0"][1]) ** 2) ** 0.5 for w in el["_px"]["walls"]) * s
    return {"index": index, "params": params, "error": None, "wall_len_m": round(wall_len / 1000, 2),
            "counts": {"walls": len(el["walls"]), "doors": len(el["openings"]), "columns": len(el["columns"]),
                       "stairs": len(el["stairs"])},
            "low_conf": sum(w["confidence"] < 0.6 for w in el["walls"])}


def stage_extract(project_dir: Path, work: Path, max_candidates: int = 12, progress: Progress = None,
                  override: dict | None = None) -> dict:
    """Stage 3 (PRD/04 §3): K candidates -> candidates/<k>/{elements.json,overlay.png}, candidates.json, masks/."""
    import functools
    import time

    t0 = time.monotonic()
    work.mkdir(parents=True, exist_ok=True)
    pre, grid_dir = work.parent / "01_preprocess", work.parent / "02_grid"
    params_final = run_params(project_dir, override)
    inputs = {
        "page": cv2.imread(str(pre / "page.png"), cv2.IMREAD_GRAYSCALE),
        "binary": cv2.imread(str(pre / "bin.png"), cv2.IMREAD_GRAYSCALE),
        "colour": cv2.imread(str(pre / "colour.png"), cv2.IMREAD_GRAYSCALE),
        "meta": json.loads((pre / "meta.json").read_text()),
        "ocr": json.loads((grid_dir / "ocr.json").read_text()),
        "grid": json.loads((grid_dir / "grid.json").read_text()),
        "defaults": {k: params_final[k] for k in ("wall_thickness",) if k in params_final},
        "work": str(work),
    }
    params = sweep_params(max_candidates)
    if progress:
        progress(5, f"{len(params)} kandidat")
    results = run_sweep(functools.partial(_candidate_job, inputs), params)
    summary = [r if r.get("index") is not None else {"index": i, "params": p, "error": r.get("error"),
                                                      "counts": None, "wall_len_m": 0, "low_conf": 0}
               for i, (r, p) in enumerate(zip(results, params, strict=True))]
    write_json(work / "candidates.json", summary)
    best = max((r["wall_len_m"] for r in summary if not r["error"]), default=0)
    metrics = {"candidates": len(summary), "best_wall_len_m": best, "seconds": round(time.monotonic() - t0, 1)}
    if not any(r["counts"] and r["counts"]["walls"] for r in summary):
        return {"status": "failed", "message": "semua kandidat kosong", "metrics": metrics}
    errors = [f"kandidat {r['index']}: {r['error']}" for r in summary if r["error"]]
    return {"status": "succeeded", "metrics": metrics, "warnings": errors}
