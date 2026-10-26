"""Command line: run stages 7-9 without the server.

Usage: uv run --env-file .env python -m core.cli build <spec.json> <out_dir> [--image PATH] [--templates DIR]
       [--engine BLENDER_WORKBENCH|BLENDER_EEVEE]
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import cv2

from core.blender_run import parse_progress, run_blender
from core.build_prep.assemble import build_input_for
from core.config import load_settings
from core.report.data import report_data
from core.report.overlay import render_overlay
from core.report.render import write_report
from core.spec.models import Spec
from core.spec.validate import validate
from core.verify.run import run_verify

BLENDER_TIMEOUT_S = 300


def _blender_version(log: Path) -> str:
    m = re.search(r"Blender (\d+\.\d+\.\d+)", log.read_text(errors="replace")) if log.exists() else None
    return m[1] if m else "—"


def _on_line(line: str) -> None:
    p = parse_progress(line)
    if p:
        print(f"  [{p[0]:3d}%] {p[1]}", flush=True)
    elif line.startswith(("WARN", "Error", "Traceback")):
        print(f"  {line}", flush=True)


def build(spec_path: Path, out_dir: Path, image: Path | None, templates: Path | None, engine: str) -> int:
    t0 = time.monotonic()
    spec = Spec.model_validate_json(spec_path.read_text())
    result = validate(spec)
    if not result.passed:
        for i in result.issues:
            if i.severity == "error":
                print(f"error {i.code} {','.join(i.element_ids)}: {i.message}", file=sys.stderr)
        return 2
    img = cv2.imread(str(image)) if image else None
    if image and img is None:
        print(f"cannot read image {image}", file=sys.stderr)
        return 2
    doc, warnings = build_input_for(spec, templates, (img.shape[1], img.shape[0]) if img is not None else None, engine)

    tmp = out_dir.parent / f"{out_dir.name}.tmp-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        (tmp / "build_input.json").write_text(json.dumps(doc))
        rc = run_blender(tmp / "build_input.json", tmp, load_settings().blender_bin, BLENDER_TIMEOUT_S, _on_line)
        if rc != 0:
            failed_log = out_dir.parent / f"{out_dir.name}.failed.log"
            shutil.copy(tmp / "blender.log", failed_log)
            print(f"blender failed (exit {rc}); log: {failed_log}", file=sys.stderr)
            return 1
        verify = run_verify(tmp, spec, doc, image)
        renders_dir = tmp / "renders"
        renders_dir.mkdir(exist_ok=True)
        if image:
            shutil.copy(image, renders_dir / "plan.png" if image.suffix == ".png" else renders_dir / f"plan{image.suffix}")
            render_overlay(spec, image, renders_dir / "overlay.png")
        renders = {p.stem: f"renders/{p.name}" for p in sorted(renders_dir.iterdir())}
        data = report_data(spec, verify, {"run_id": spec.meta.run_id, "blender_version": _blender_version(tmp / "blender.log")})
        write_report(tmp, data, renders)
        if out_dir.exists():
            shutil.rmtree(out_dir)
        tmp.rename(out_dir)
    except Exception as e:  # noqa: BLE001 - any failure must not leave a half-written output folder
        print(f"build failed: {e!r}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for w in [*warnings, *verify["warnings"]]:
        print(f"warning: {w}")
    print(f"done in {time.monotonic() - t0:.1f}s: status {verify['status']}, IoU {verify['iou']}, "
          f"glb max err {verify['glb_check']['max_err_mm']} mm -> {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="core.cli", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="spec -> Blender outputs, verification and report (stages 7-9)")
    b.add_argument("spec", type=Path)
    b.add_argument("out_dir", type=Path)
    b.add_argument("--image", type=Path)
    b.add_argument("--templates", type=Path)
    b.add_argument("--engine", default="BLENDER_WORKBENCH", choices=["BLENDER_WORKBENCH", "BLENDER_EEVEE"])
    args = ap.parse_args(argv)
    return build(args.spec, args.out_dir, args.image, args.templates, args.engine)


if __name__ == "__main__":
    sys.exit(main())
