"""Stages 7-10 as a library (PRD/06): build, verify, report, publish. Used by the CLI and the server."""

import json
import os
import re
import shutil
from collections.abc import Callable
from pathlib import Path

import cv2

from core.blender_run import run_blender
from core.build_prep.assemble import build_input_for
from core.config import load_settings
from core.report.data import report_data
from core.report.overlay import render_overlay
from core.report.render import write_report
from core.spec.models import Spec
from core.verify.run import run_verify

OUTPUT_FILES = ("layout.blend", "shell.glb", "layout_full.glb", "layout.fbx", "layout.obj", "layout.mtl",
                "report.html", "report.pdf", "report.css", "verify.json", "iou_mask.png", "verify_top.png")
REQUIRED_OUTPUTS = ("shell.glb", "layout.blend", "report.html")


class BuildFailed(Exception):
    def __init__(self, exit_code: int, log: Path):
        super().__init__(f"blender failed (exit {exit_code}); log: {log}")
        self.exit_code, self.log = exit_code, log


def image_size(image: Path | None) -> tuple[int, int] | None:
    if image is None:
        return None
    img = cv2.imread(str(image))
    if img is None:
        raise ValueError(f"cannot read image {image}")
    return img.shape[1], img.shape[0]


def stage_build(spec: Spec, work: Path, image: Path | None, templates: Path | None, engine: str,
                on_line: Callable[[str], None] | None = None, on_start: Callable | None = None,
                timeout_s: int = 300, blender_bin: str | None = None) -> tuple[dict, list[str]]:
    """Stage 7: build_input.json + Blender exports and renders in `work`. Returns (doc, warnings)."""
    work.mkdir(parents=True, exist_ok=True)
    doc, warnings = build_input_for(spec, templates, image_size(image), engine)
    (work / "build_input.json").write_text(json.dumps(doc))
    rc = run_blender(work / "build_input.json", work, blender_bin or load_settings().blender_bin, timeout_s,
                     on_line, on_start)
    if rc != 0:
        raise BuildFailed(rc, work / "blender.log")
    return doc, warnings


def plan_mask_for(project_dir: Path, spec: Spec) -> Path | None:
    """Wall mask of the extraction run behind this spec: its own run, or (after editor commits, which carry no
    run id) the nearest ancestor version that came from a run and left a mask."""
    from core.spec.store import SpecStore

    store, seen = SpecStore(project_dir / "specs"), set()
    while spec is not None and spec.meta.version not in seen:
        seen.add(spec.meta.version)
        if spec.meta.run_id:
            path = project_dir / "runs" / spec.meta.run_id / "stages" / "05_validate" / "wall_mask.png"
            if path.exists():
                return path
        parent = spec.meta.parent_version
        spec = store.load(parent) if parent and (project_dir / "specs" / f"spec.v{parent}.json").exists() else None
    return None


def stage_verify(spec: Spec, work: Path, doc: dict, image: Path | None, warnings: list[str],
                 plan_mask: Path | None = None) -> dict:
    """Stage 8: glb 1:1, grid, IoU -> verify.json (build warnings are persisted with it)."""
    return run_verify(work, spec, doc, image, extra_warnings=warnings, plan_mask_path=plan_mask)


def blender_version(work: Path) -> str:
    log = work / "blender.log"
    m = re.search(r"Blender (\d+\.\d+\.\d+)", log.read_text(errors="replace")) if log.exists() else None
    return m[1] if m else "—"


def stage_report(spec: Spec, work: Path, doc: dict, verify: dict, image: Path | None,
                 run_id: str | None) -> tuple[Path, Path]:
    """Stage 9: plan + overlay renders, then report.html / report.pdf."""
    renders_dir = work / "renders"
    renders_dir.mkdir(exist_ok=True)
    if image:
        shutil.copy(image, renders_dir / f"plan{image.suffix}")
        render_overlay(spec, image, renders_dir / "overlay.png")
    renders = {p.stem: f"renders/{p.name}" for p in sorted(renders_dir.iterdir())}
    placed = {i["props"]["spec_id"] for i in doc["instances"]}
    missing = [o.id for o in spec.objects if o.id not in placed]
    data = report_data(spec, verify, {"run_id": run_id or spec.meta.run_id, "blender_version": blender_version(work)},
                       missing_objects=missing)
    return write_report(work, data, renders)


def outputs_complete(path: Path) -> bool:
    return all((Path(path) / f).exists() for f in REQUIRED_OUTPUTS)


def publish(work: Path, outputs_root: Path, version: int) -> Path:
    """Stage 10: copy the deliverables to outputs/v<N> atomically (tmp folder, then rename)."""
    outputs_root.mkdir(parents=True, exist_ok=True)
    final, tmp = outputs_root / f"v{version}", outputs_root / f"v{version}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for name in OUTPUT_FILES:
        if (work / name).exists():
            shutil.copy2(work / name, tmp / name)
    if (work / "renders").exists():
        shutil.copytree(work / "renders", tmp / "renders")
    if final.exists():
        shutil.rmtree(final)
    os.rename(tmp, final)
    return final
