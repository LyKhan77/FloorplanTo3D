"""Stages 0-2 as artefact-writing steps (PRD/04): input.json, page.png/bin.png/meta.json, ocr.json/grid.json/overlay.png.

Each stage reads the previous stages' folders next to its own work folder (runs/<id>/stages/NN_name).
"""

import json
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from core.extraction.geometry.candidate import extract_candidate
from core.extraction.geometry.overlay import render_elements_overlay
from core.extraction.geometry.sweep import run_sweep, sweep_params
from core.extraction.grid import detect_grid
from core.extraction.overlay import render_grid_overlay
from core.extraction.params import input_doc, merge_params, parse_prompt
from core.extraction.preprocess import load_raster, preprocess
from core.extraction.rooms.assemble import assemble_spec, leak_issues
from core.extraction.rooms.labels import best_label, labels_from_ocr
from core.extraction.rooms.overlay import px_from_mm, render_rooms_overlay
from core.extraction.rooms.overlay_ids import render_ids_overlay
from core.extraction.scale import compose_original, scale_from
from core.extraction.select import choose, crop_labels, ocr_dimensions_from
from core.extraction.textclass import classify_text, ocr_page
from core.spec.carryover import carry_over
from core.spec.models import Spec
from core.spec.rooms import rebuild_rooms
from core.spec.store import SpecStore, ValidationFailed
from core.spec.validate import ValidationContext, validate

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
    cv2.imwrite(str(out / "wall_mask.png"), el["_masks"]["wall"])
    if index == 0:
        (Path(inputs["work"]) / "masks").mkdir(exist_ok=True)
        for name, mask in el["_masks"].items():
            cv2.imwrite(str(Path(inputs["work"]) / "masks" / f"{name}.png"), mask)
    s = inputs["grid"]["mm_per_px_work"]
    wall_len = sum(((w["p1"][0] - w["p0"][0]) ** 2 + (w["p1"][1] - w["p0"][1]) ** 2) ** 0.5 for w in el["_px"]["walls"]) * s
    return {"index": index, "params": params, "error": None, "wall_len_m": round(wall_len / 1000, 2),
            "line_len_m": el["line_len_m"],
            "counts": {"walls": len(el["walls"]), "doors": len(el["openings"]), "columns": len(el["columns"]),
                       "stairs": len(el["stairs"])},
            "low_conf": sum(w["confidence"] < 0.6 for w in el["walls"])}


def stage_extract(project_dir: Path, work: Path, max_candidates: int = 12, progress: Progress = None,
                  override: dict | None = None, profile: dict | None = None) -> dict:
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
    params = sweep_params(max_candidates, profile)  # a style profile and its neighbours first
    if progress:
        progress(5, f"{len(params)} kandidat")
    results = run_sweep(functools.partial(_candidate_job, inputs), params)
    summary = [r if r.get("index") is not None else {"index": i, "params": p, "error": r.get("error"),
                                                      "counts": None, "wall_len_m": 0, "line_len_m": 0, "low_conf": 0}
               for i, (r, p) in enumerate(zip(results, params, strict=True))]
    write_json(work / "candidates.json", summary)
    best = max((r["wall_len_m"] for r in summary if not r["error"]), default=0)
    metrics = {"candidates": len(summary), "best_wall_len_m": best, "seconds": round(time.monotonic() - t0, 1)}
    if not any(r["counts"] and r["counts"]["walls"] for r in summary):
        return {"status": "failed", "message": "semua kandidat kosong", "metrics": metrics}
    errors = [f"kandidat {r['index']}: {r['error']}" for r in summary if r["error"]]
    return {"status": "succeeded", "metrics": metrics, "warnings": errors}


def meta_info(project_dir: Path, override: dict | None = None) -> dict:
    """Spec meta fields that come from the upload and the run parameters, not from the drawing."""
    up = _upload(project_dir)
    params = run_params(project_dir, override)
    return {"project_id": project_dir.name, "floor_name": params.get("floor_name", ""),
            "site_type": params.get("site_type", "other"),
            "defaults": {k: params[k] for k in ("wall_height", "door_height", "wall_thickness") if k in params},
            "sha256": up["sha256"]}


def stage_rooms(project_dir: Path, work: Path, progress: Progress = None, override: dict | None = None) -> dict:
    """Stage 4 (PRD/04 Tahap 4): every successful candidate -> candidates/<k>/{spec.json, rooms.png, issues.json}."""
    work.mkdir(parents=True, exist_ok=True)
    ext, pre, grid_dir = work.parent / "03_extract", work.parent / "01_preprocess", work.parent / "02_grid"
    grid = json.loads((grid_dir / "grid.json").read_text())
    pmeta = json.loads((pre / "meta.json").read_text())
    page = cv2.imread(str(pre / "page.png"), cv2.IMREAD_GRAYSCALE)
    labels = labels_from_ocr(json.loads((grid_dir / "ocr.json").read_text()), grid["px_to_mm"])
    info = meta_info(project_dir, override)
    w, h = pmeta["original_size"]
    info["image"] = {"sha256": info.pop("sha256"), "width_px": w, "height_px": h}
    to_px = px_from_mm(grid["px_to_mm"])
    rows = []
    cands = [c for c in json.loads((ext / "candidates.json").read_text()) if not c["error"]]
    for i, c in enumerate(cands):
        k = c["index"]
        if progress:
            progress(round(100 * i / max(1, len(cands))), f"kandidat {k}")
        try:
            el = json.loads((ext / "candidates" / str(k) / "elements.json").read_text())
            spec, issues = assemble_spec(el, grid, labels, info)
        except Exception as e:  # noqa: BLE001 - one bad candidate must not sink the stage
            rows.append({"index": k, "error": f"{type(e).__name__}: {e}", "rooms": 0, "labelled": 0, "gross_area_m2": 0})
            continue
        out = work / "candidates" / str(k)
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / "spec.json", spec.model_dump(mode="json"))
        write_json(out / "issues.json", issues)
        cv2.imwrite(str(out / "rooms.png"), render_rooms_overlay(page, spec, to_px))
        rows.append({"index": k, "error": None, "rooms": len(spec.rooms), "labelled": sum(bool(r.name) for r in spec.rooms),
                     "gross_area_m2": spec.meta.gross_area_m2})
    write_json(work / "candidates.json", rows)
    ok = [r for r in rows if not r["error"]]
    if not ok:
        return {"status": "failed", "message": "tidak ada kandidat yang bisa dirakit menjadi spec"}
    return {"status": "succeeded", "metrics": {"candidates": len(ok), "rooms": ok[0]["rooms"]},
            "warnings": [f"kandidat {r['index']}: {r['error']}" for r in rows if r["error"]]}


SCORE_OK, SCORE_MIN = 0.8, 0.6


def _wall_len(spec: Spec) -> float:
    return sum(((w.b[0] - w.a[0]) ** 2 + (w.b[1] - w.a[1]) ** 2) ** 0.5 for w in spec.walls)


def _issue_dicts(result) -> list[dict]:
    return [{"code": i.code, "severity": i.severity, "element_ids": list(i.element_ids), "message": i.message}
            for i in result.issues]


def stage_validate(project_dir: Path, work: Path, run_id: str, progress: Progress = None,
                   override: dict | None = None) -> dict:
    """Stage 5 (PRD/04 Tahap 5): validate every stage-4 candidate, keep the best one without errors, label its
    unnamed rooms from OCR crops, carry HEAD over, save the spec and draw the numbered overlay."""
    work.mkdir(parents=True, exist_ok=True)
    st = work.parent
    rows3 = {c["index"]: c for c in json.loads((st / "03_extract" / "candidates.json").read_text())}
    grid = json.loads((st / "02_grid" / "grid.json").read_text())
    dims = ocr_dimensions_from(grid) or None
    # one estimate of the drawn wall lines for the whole drawing (V018): the most any candidate found
    line_mm = max((c.get("line_len_m") or 0 for c in rows3.values()), default=0) * 1000
    scored, specs = [], {}
    for row in json.loads((st / "04_rooms" / "candidates.json").read_text()):
        if row["error"]:
            continue
        k = row["index"]
        spec = Spec.model_validate_json((st / "04_rooms" / "candidates" / str(k) / "spec.json").read_text())
        res = validate(spec, ValidationContext(ocr_dimensions=dims, thick_line_length_mm=line_mm or None))
        specs[k] = spec
        scored.append({"index": k, "score": round(res.score, 4), "passed": res.passed,
                       "ratios": {c: round(v, 4) for c, v in res.ratios.items()},
                       "errors": sorted({i.code for i in res.issues if i.severity == "error"}),
                       "coverage": round(_wall_len(spec) / line_mm, 4) if line_mm else 0.0})
    write_json(work / "scores.json", scored)
    chosen = choose(scored)
    if chosen is None:
        codes = sorted({c for s in scored for c in s["errors"]})
        return {"status": "needs_attention", "metrics": {"candidates": len(scored)},
                "message": f"semua kandidat punya error validator ({', '.join(codes) or 'tidak ada kandidat'})"}
    k = chosen["index"]
    spec = specs[k]
    ctx = ValidationContext(ocr_dimensions=dims, thick_line_length_mm=line_mm or None)
    page = cv2.imread(str(st / "01_preprocess" / "page.png"), cv2.IMREAD_GRAYSCALE)
    labels = labels_from_ocr(json.loads((st / "02_grid" / "ocr.json").read_text()), grid["px_to_mm"])
    if progress:
        progress(40, "OCR label ruang")
    crops = crop_labels(page, spec, grid["px_to_mm"])
    labels += crops
    if crops:
        spec = rebuild_rooms(spec, labels, pick=best_label, source="cv")
    store = SpecStore(project_dir / "specs")
    head, report = store.head(), None
    if head is not None:
        spec, report = carry_over(spec, store.load(head))
        write_json(work / "carryover.json", report)
    final = validate(spec, ctx)
    try:
        saved = store.save_new(spec, "pipeline", run_id, f"ekstraksi otomatis, kandidat {k}")
    except ValidationFailed as e:
        return {"status": "needs_attention", "metrics": {"candidates": len(scored), "candidate": k},
                "message": "spec terpilih gagal validasi: " + ", ".join(sorted({i.code for i in e.issues}))}
    stage3 = json.loads((st / "03_extract" / "candidates" / str(k) / "elements.json").read_text()).get("issues", [])
    issues = _issue_dicts(final) + leak_issues(saved, labels) + stage3
    write_json(work / "issues.json", issues)
    write_json(work / "chosen.json", {"index": k, "params": rows3.get(k, {}).get("params"),
                                      "score": round(final.score, 4), "version": saved.meta.version})
    composite, layers = render_ids_overlay(page, saved, px_from_mm(grid["px_to_mm"]))
    cv2.imwrite(str(work / "overlay_ids.png"), composite)
    (work / "layers").mkdir(exist_ok=True)
    for name, layer in layers.items():
        cv2.imwrite(str(work / "layers" / f"{name}.png"), layer)
    meta = json.loads((st / "01_preprocess" / "meta.json").read_text())
    mask = cv2.imread(str(st / "03_extract" / "candidates" / str(k) / "wall_mask.png"), cv2.IMREAD_GRAYSCALE)
    to_original = cv2.invertAffineTransform(np.array(meta["work_from_original"], np.float64).reshape(2, 3))
    w0, h0 = meta["original_size"]
    cv2.imwrite(str(work / "wall_mask.png"), cv2.warpAffine(mask, to_original, (w0, h0), flags=cv2.INTER_NEAREST))
    warnings = [f"edit tidak bisa dipindahkan: {e['id']} {e['field']} = {e['value']}" for e in (report or {}).get("lost_edits", [])]
    metrics = {"version": saved.meta.version, "candidate": k, "score": round(final.score, 3), "rooms": len(saved.rooms),
               "issues": len(issues)}
    if final.score < SCORE_MIN:
        return {"status": "needs_attention", "metrics": metrics, "warnings": warnings,
                "message": f"skor validator {final.score:.2f} < {SCORE_MIN}: periksa lalu pilih lanjutkan tetap"}
    if final.score < SCORE_OK:
        warnings.append(f"skor validator {final.score:.2f} < {SCORE_OK}: prioritaskan review")
    return {"status": "succeeded", "metrics": metrics, "warnings": warnings}
