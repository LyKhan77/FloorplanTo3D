"""Placeholder templates for MVP testing (PRD/10 §6), built with the regular Blender builder.

Usage: uv run --env-file .env python -m core.templates.make_placeholders [--out data/templates]
"""

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from core.build_prep.mesh import box
from core.build_prep.schema import BUILD_INPUT_VERSION
from core.config import load_settings

BUILDER = Path(__file__).resolve().parents[2] / "builder" / "build.py"
VERSION = "1.0.0"
# (id, (w, d, h) mm, category, resizable axes) — PRD/10 §6
PLACEHOLDERS = [
    ("rack-42u-600x1200", (600, 1200, 2000), "rack", "dh"),
    ("rack-48u-800x1200", (800, 1200, 2250), "rack", "dh"),
    ("crac-unit-generic", (2500, 900, 1950), "cooling", "w"),
    ("ups-cabinet-generic", (1200, 800, 2000), "power", "w"),
    ("battery-rack-generic", (1500, 750, 1800), "battery", "w"),
    ("pdu-floor-generic", (600, 600, 1800), "power", ""),
    ("fire-cylinder-generic", (400, 400, 1800), "fire", ""),
]
CATEGORY_COLOR = {"rack": "#393939", "cooling": "#4589FF", "power": "#F1C21B", "battery": "#24A148", "fire": "#DA1E28"}


def _round50(v: float) -> int:
    return int(round(v / 50) * 50)


def template_meta(tid: str, dims: tuple[int, int, int], category: str, axes: str) -> dict:
    w, d, h = dims
    resizable = {a: ({"min": _round50(v * 0.75), "max": _round50(v * 1.25), "step": 50} if a in axes else False)
                 for a, v in (("w", w), ("d", d), ("h", h))}
    clearance = {"front": 1200, "back": 1000} if category == "rack" else {}
    return {"id": tid, "version": VERSION, "name": tid.replace("-", " ").title(), "category": category,
            "tags": ["placeholder"], "dims": {"w": w, "d": d, "h": h}, "pivot": "bottom_center", "front": "+y",
            "resizable": resizable, "scale_mode": "stretch" if axes else "fixed",
            "snap": {"grid_mm": 600, "align": "edge"}, "clearance": clearance, "source": {"workflow": "placeholder"}}


def build_doc(dims: tuple[int, int, int], color: str) -> dict:
    w, d, h = dims
    body = box(0, 0, h / 2, w, d, h)
    panel = box(0, d / 2 - 5, h / 2, w * 0.8, 10, h * 0.8)  # dark face on the front (+Y), inside the bbox
    return {
        "version": BUILD_INPUT_VERSION, "spec_version": 0,
        "materials": {"tpl_body": {"color": color, "roughness": 0.6, "alpha": 1.0},
                      "tpl_front": {"color": "#161616", "roughness": 0.4, "alpha": 1.0}},
        "meshes": [
            {"name": "template_root", "collection": "Template", **body, "material": "tpl_body", "props": {},
             "parent": None, "location": [0, 0, 0], "rot_z": 0.0},
            {"name": "front_panel", "collection": "Template", **panel, "material": "tpl_front", "props": {},
             "parent": "template_root", "location": [0, 0, 0], "rot_z": 0.0},
        ],
        "empties": [{"name": "front_marker", "collection": "Template", "location": [0, d / 2, h / 2], "rot_z": 0.0,
                     "props": {}, "parent": "template_root"}],
        "cutters": [], "instances": [], "labels": [], "grid_lines": [], "cameras": [],
        "render": {}, "exports": [{"file": "asset.glb", "collections": ["Template"]}],
    }


def thumbnail(tid: str, color: str) -> np.ndarray:
    img = np.zeros((512, 512, 4), np.uint8)  # transparent
    h = color.lstrip("#")
    bgr = (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))
    cv2.rectangle(img, (96, 96), (416, 416), (*bgr, 255), -1)
    cv2.arrowedLine(img, (256, 360), (256, 140), (255, 255, 255, 255), 14, tipLength=0.3)  # front = up (+Y)
    cv2.putText(img, tid[:22], (40, 470), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (*bgr, 255), 2)
    return img


def make_placeholders(out_root: Path, blender_bin: str) -> list[Path]:
    paths = []
    for tid, dims, category, axes in PLACEHOLDERS:
        folder = Path(out_root) / tid / VERSION
        folder.mkdir(parents=True, exist_ok=True)
        color = CATEGORY_COLOR.get(category, "#8D8D8D")
        inp = folder / "build_input.json"
        inp.write_text(json.dumps(build_doc(dims, color)))
        r = subprocess.run([blender_bin, "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(BUILDER),
                            "--", str(inp), str(folder)], capture_output=True, text=True, timeout=300, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"builder failed for {tid}: {r.stderr[-1000:]}")
        inp.unlink()
        (folder / "template.json").write_text(json.dumps(template_meta(tid, dims, category, axes), indent=2) + "\n")
        cv2.imwrite(str(folder / "thumbnail.png"), thumbnail(tid, color))
        paths.append(folder)
    return paths


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("data/templates"))
    args = ap.parse_args(argv)
    for p in make_placeholders(args.out, load_settings().blender_bin):
        print(p)


if __name__ == "__main__":
    main()
