"""Command line: run stages 7-9 without the server.

Usage: uv run --env-file .env python -m core.cli build <spec.json> <out_dir> [--image PATH] [--templates DIR]
       [--engine BLENDER_WORKBENCH|BLENDER_EEVEE]
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import cv2

from core.blender_run import parse_progress
from core.pipeline import BuildFailed, stage_build, stage_report, stage_verify
from core.spec.models import Spec
from core.spec.validate import validate

BLENDER_TIMEOUT_S = 300


def _on_line(line: str) -> None:
    p = parse_progress(line)
    if p:
        print(f"  [{p[0]:3d}%] {p[1]}", flush=True)
    elif line.startswith(("WARN", "Error", "Traceback")):
        print(f"  {line}", flush=True)


def _out_dir_problem(out_dir: Path, force: bool) -> str | None:
    """Refuse targets the final rename would destroy: '.', the home folder, or a folder that is not a build output."""
    resolved = out_dir.resolve()
    if not out_dir.name or resolved in (Path.cwd().resolve(), Path.home().resolve()) or resolved.parent == resolved:
        return f"refusing to use {out_dir} as the output folder"
    if resolved.exists() and any(resolved.iterdir()) and not (resolved / "build_input.json").exists() and not force:
        return f"{out_dir} is not empty and is not a previous build output (use --force to replace it)"
    return None


def build(spec_path: Path, out_dir: Path, image: Path | None, templates: Path | None, engine: str,
          force: bool = False) -> int:
    t0 = time.monotonic()
    problem = _out_dir_problem(out_dir, force)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    spec = Spec.model_validate_json(spec_path.read_text())
    result = validate(spec)
    if not result.passed:
        for i in result.issues:
            if i.severity == "error":
                print(f"error {i.code} {','.join(i.element_ids)}: {i.message}", file=sys.stderr)
        return 2
    if image and cv2.imread(str(image)) is None:
        print(f"cannot read image {image}", file=sys.stderr)
        return 2

    tmp = out_dir.parent / f"{out_dir.name}.tmp-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    try:
        doc, warnings = stage_build(spec, tmp, image, templates, engine, _on_line, timeout_s=BLENDER_TIMEOUT_S)
        verify = stage_verify(spec, tmp, doc, image, warnings)
        stage_report(spec, tmp, doc, verify, image, spec.meta.run_id)
        if out_dir.exists():
            shutil.rmtree(out_dir)
        tmp.rename(out_dir)
    except BuildFailed as e:
        failed_log = out_dir.parent / f"{out_dir.name}.failed.log"
        shutil.copy(e.log, failed_log)
        print(f"blender failed (exit {e.exit_code}); log: {failed_log}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001 - any failure must not leave a half-written output folder
        print(f"build failed: {e!r}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for w in verify["warnings"]:  # includes the build warnings
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
    b.add_argument("--force", action="store_true", help="replace a non-empty out_dir that is not a previous build")
    args = ap.parse_args(argv)
    return build(args.spec, args.out_dir, args.image, args.templates, args.engine, args.force)


if __name__ == "__main__":
    sys.exit(main())
