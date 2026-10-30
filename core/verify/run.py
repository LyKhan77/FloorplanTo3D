"""Stage 8 verification: glb 1:1, drawing fit, grid check, IoU (info) -> verify.json + iou_mask.png (PRD/06 §6)."""

import json
from pathlib import Path

import cv2
import numpy as np

from core.spec.models import Spec
from core.verify.fit import drawing_fit
from core.verify.glb_check import glb_check
from core.verify.iou import diff_image, iou, plan_wall_mask

IOU_OK = 0.85  # reported only: after a review the extractor's mask is no longer the truth
FIT_OK = 0.90  # below: scale or offset off, or many walls where nothing is drawn (core/verify/fit.py)


def grid_check(spec: Spec, dims: list[tuple[str, str, int]] | None) -> dict:
    """Grid spacing vs dimension text. Skipped until OCR dimensions are available (M5)."""
    if dims is None:
        return {"status": "skipped"}
    by_label = {a.label: a.offset for a in spec.grid.axes}
    errs = [abs(abs(by_label[a] - by_label[b]) - mm) for a, b, mm in dims if a in by_label and b in by_label]
    max_err = max(errs, default=0)
    return {"max_err_mm": max_err, "pass": max_err <= 0.005 * max((mm for *_, mm in dims), default=1)}


def verify_status(glb_pass: bool, fit: float | None) -> tuple[str, list[str]]:
    if not glb_pass:
        return "failed", ["glb dimensions differ from the spec by more than 1 mm"]
    if fit is not None and fit < FIT_OK:
        return "needs_attention", [f"kecocokan gambar {fit:.3f} di bawah {FIT_OK}: cek skala atau posisi model"]
    return "succeeded", []


def run_verify(out_dir: Path, spec: Spec, doc: dict, image_path: Path | None,
               extra_warnings: list[str] | None = None, plan_mask_path: Path | None = None) -> dict:
    """extra_warnings: build-time warnings (e.g. skipped objects) persisted with the verification result.

    plan_mask_path: the chosen extraction candidate's wall mask in original pixels (PRD/06 §6.2). Without it the
    M2 heuristic mask is used and the result says so."""
    out_dir = Path(out_dir)
    glb = glb_check(out_dir / "shell.glb", doc)
    warnings: list[str] = list(extra_warnings or [])
    iou_value = None
    mask_source = "candidate" if plan_mask_path is not None and Path(plan_mask_path).exists() else "m2"
    render_path = out_dir / "verify_top.png"
    fit = {"fit": None, "walls_off": [], "checked": 0}
    if image_path is not None:
        fit = drawing_fit(spec, cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE))
        if fit["walls_off"]:
            warnings.append(f"{len(fit['walls_off'])} dinding tidak di atas garis gambar: {', '.join(fit['walls_off'])}")
    if image_path is None:
        warnings.append("no input image: IoU skipped")
    elif not render_path.exists():
        warnings.append("verification render missing: IoU skipped")
    else:
        render = cv2.imread(str(render_path), cv2.IMREAD_GRAYSCALE)
        render_mask = np.where(render < 128, 255, 0).astype(np.uint8)
        if mask_source == "candidate":
            plan_mask = np.where(cv2.imread(str(plan_mask_path), cv2.IMREAD_GRAYSCALE) > 0, 255, 0).astype(np.uint8)
        else:
            plan_mask = plan_wall_mask(cv2.imread(str(image_path)))
            warnings.append("IoU memakai mask M2 (tanpa mask kandidat ekstraksi)")
        if plan_mask.shape != render_mask.shape:
            warnings.append(f"render {render_mask.shape} and plan {plan_mask.shape} sizes differ: IoU skipped")
        else:
            iou_value = round(iou(render_mask, plan_mask), 4)
            cv2.imwrite(str(out_dir / "iou_mask.png"), diff_image(render_mask, plan_mask))
    status, status_warnings = verify_status(glb["pass"], fit["fit"])
    result = {"drawing_fit": fit, "fit_threshold": FIT_OK, "iou": iou_value, "iou_threshold": IOU_OK,
              "grid_check": grid_check(spec, None), "glb_check": glb,
              "status": status, "warnings": warnings + status_warnings, "mask_source": mask_source}
    (out_dir / "verify.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
