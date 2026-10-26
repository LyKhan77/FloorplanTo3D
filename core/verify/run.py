"""Stage 8 verification: glb 1:1, grid check, IoU -> verify.json + iou_mask.png (PRD/06 §6)."""

import json
from pathlib import Path

import cv2
import numpy as np

from core.spec.models import Spec
from core.verify.glb_check import glb_check
from core.verify.iou import diff_image, iou, plan_wall_mask

IOU_OK = 0.85
IOU_WARN = 0.70


def grid_check(spec: Spec, dims: list[tuple[str, str, int]] | None) -> dict:
    """Grid spacing vs dimension text. Skipped until OCR dimensions are available (M5)."""
    if dims is None:
        return {"status": "skipped"}
    by_label = {a.label: a.offset for a in spec.grid.axes}
    errs = [abs(abs(by_label[a] - by_label[b]) - mm) for a, b, mm in dims if a in by_label and b in by_label]
    max_err = max(errs, default=0)
    return {"max_err_mm": max_err, "pass": max_err <= 0.005 * max((mm for *_, mm in dims), default=1)}


def verify_status(glb_pass: bool, iou_value: float | None) -> tuple[str, list[str]]:
    if not glb_pass:
        return "failed", ["glb dimensions differ from the spec by more than 1 mm"]
    if iou_value is None:
        return "succeeded", []
    if iou_value < IOU_WARN:
        return "needs_attention", [f"IoU {iou_value:.3f} below {IOU_WARN}"]
    if iou_value < IOU_OK:
        return "succeeded", [f"IoU {iou_value:.3f} below {IOU_OK}"]
    return "succeeded", []


def run_verify(out_dir: Path, spec: Spec, doc: dict, image_path: Path | None) -> dict:
    out_dir = Path(out_dir)
    glb = glb_check(out_dir / "shell.glb", doc)
    warnings: list[str] = []
    iou_value = None
    render_path = out_dir / "verify_top.png"
    if image_path is None:
        warnings.append("no input image: IoU skipped")
    elif not render_path.exists():
        warnings.append("verification render missing: IoU skipped")
    else:
        render = cv2.imread(str(render_path), cv2.IMREAD_GRAYSCALE)
        render_mask = np.where(render < 128, 255, 0).astype(np.uint8)
        plan_mask = plan_wall_mask(cv2.imread(str(image_path)))
        if plan_mask.shape != render_mask.shape:
            warnings.append(f"render {render_mask.shape} and plan {plan_mask.shape} sizes differ: IoU skipped")
        else:
            iou_value = round(iou(render_mask, plan_mask), 4)
            cv2.imwrite(str(out_dir / "iou_mask.png"), diff_image(render_mask, plan_mask))
    status, status_warnings = verify_status(glb["pass"], iou_value)
    result = {"iou": iou_value, "iou_threshold": IOU_OK, "grid_check": grid_check(spec, None), "glb_check": glb,
              "status": status, "warnings": warnings + status_warnings}
    (out_dir / "verify.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
