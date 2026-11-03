"""The template library's data-center equipment as procedural low-poly models (core/templates/lowpoly.py), built with
the regular Blender builder. 1.0.0 were plain boxes; placed objects keep their version, new ones get the newest.

Usage: uv run --env-file .env python -m core.templates.make_placeholders [--out data/templates]
"""

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from core.build_prep.schema import BUILD_INPUT_VERSION
from core.config import load_settings
from core.templates.lowpoly import MATERIALS, front_view, meshes, parts

BUILDER = Path(__file__).resolve().parents[2] / "builder" / "build.py"
VERSION = "1.1.0"
# (id, (w, d, h) mm, category, resizable axes) — PRD/10 §6
PLACEHOLDERS = [
    ("rack-42u-600x1200", (600, 1200, 2000), "rack", "dh"),
    ("rack-48u-800x1200", (800, 1200, 2250), "rack", "dh"),
    ("crac-unit-generic", (2500, 900, 1950), "cooling", "w"),
    ("ups-cabinet-generic", (1200, 800, 2000), "power", "w"),
    ("battery-rack-generic", (1500, 750, 1800), "battery", "w"),
    ("pdu-floor-generic", (600, 600, 1800), "power", ""),
    ("fire-cylinder-generic", (400, 400, 1800), "fire", ""),
    ("inrow-cooler-300x1200", (300, 1200, 2000), "cooling", ""),
    ("panel-mdb-generic", (1600, 600, 2100), "power", "w"),
    ("ats-cabinet-generic", (800, 600, 2000), "power", ""),
    ("network-rack-2post", (600, 600, 2100), "network", "h"),
    ("fire-control-panel", (500, 150, 700), "fire", ""),  # wall mounted: placed with z on the wall
    ("cctv-camera-bullet", (120, 300, 150), "security", ""),
    ("access-reader-generic", (90, 40, 140), "security", ""),
    ("containment-roof-600", (600, 1200, 60), "structure", "d"),  # across the aisle, on top of the racks
    ("containment-door-1200", (1200, 100, 2100), "structure", "w"),
    ("ahu-unit-generic", (3000, 1200, 2200), "cooling", "w"),
    ("transformer-dry-generic", (1800, 1200, 2200), "power", ""),
    ("genset-generic", (4000, 1500, 2200), "power", "w"),
    ("sts-cabinet-generic", (800, 800, 2000), "power", ""),
    ("battery-cabinet-generic", (1200, 800, 2000), "battery", "w"),
    ("fm200-cylinder-bank", (1500, 500, 1800), "fire", "w"),
    ("vesda-panel", (350, 120, 450), "fire", ""),  # wall mounted
    ("fire-alarm-panel", (600, 150, 800), "fire", ""),  # wall mounted
    ("noc-desk-generic", (1800, 800, 1250), "furniture", "w"),
    ("office-chair-generic", (600, 600, 1100), "furniture", ""),
    ("storage-cabinet-generic", (1000, 500, 2000), "other", "w"),
]
CATEGORY_COLOR = {"rack": "#393939", "cooling": "#4589FF", "power": "#F1C21B", "battery": "#24A148", "fire": "#DA1E28",
                  "network": "#8A3FFC", "security": "#007D79", "structure": "#6F6F6F", "furniture": "#8A6A4F",
                  "other": "#8D8D8D"}


def _round50(v: float) -> int:
    return int(round(v / 50) * 50)


def template_meta(tid: str, dims: tuple[int, int, int], category: str, axes: str) -> dict:
    w, d, h = dims
    resizable = {a: ({"min": _round50(v * 0.75), "max": _round50(v * 1.25), "step": 50} if a in axes else False)
                 for a, v in (("w", w), ("d", d), ("h", h))}
    clearance = {"front": 1200, "back": 1000} if category == "rack" else {}
    return {"id": tid, "version": VERSION, "name": tid.replace("-", " ").title(), "category": category,
            "tags": ["lowpoly"], "dims": {"w": w, "d": d, "h": h}, "pivot": "bottom_center", "front": "+y",
            "resizable": resizable, "scale_mode": "stretch" if axes else "fixed",
            "snap": {"grid_mm": 600, "align": "edge"}, "clearance": clearance,
            "source": {"workflow": "procedural", "script": "core/templates/lowpoly.py", "license": "project-owned"}}


def build_doc(tid: str, dims: tuple[int, int, int]) -> dict:
    _, d, h = dims
    by_material = meshes(parts(tid, dims))
    first, *rest = by_material  # the first material's mesh is the root the others hang from
    return {
        "version": BUILD_INPUT_VERSION, "spec_version": 0,
        # tpl_ names: the asset is imported into layout scenes, whose own materials must not merge with these
        "materials": {f"tpl_{m}": MATERIALS[m] for m in by_material},
        "meshes": [{"name": "template_root" if m == first else f"part_{m}", "collection": "Template", **by_material[m],
                    "material": f"tpl_{m}", "props": {}, "parent": None if m == first else "template_root",
                    "location": [0, 0, 0], "rot_z": 0.0} for m in [first, *rest]],
        "empties": [{"name": "front_marker", "collection": "Template", "location": [0, d / 2, h / 2], "rot_z": 0.0,
                     "props": {}, "parent": "template_root"}],
        "cutters": [], "instances": [], "labels": [], "grid_lines": [], "cameras": [],
        "render": {}, "exports": [{"file": "asset.glb", "collections": ["Template"]}],
    }


def thumbnail(tid: str, dims: tuple[int, int, int], color: str) -> np.ndarray:
    """Front elevation of the model on a transparent background, with its id."""
    img = front_view(parts(tid, dims))
    h = color.lstrip("#")
    cv2.putText(img, tid[:26], (24, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16), 255), 2)
    return img


def make_placeholders(out_root: Path, blender_bin: str) -> list[Path]:
    paths = []
    for tid, dims, category, axes in PLACEHOLDERS:
        folder = Path(out_root) / tid / VERSION
        folder.mkdir(parents=True, exist_ok=True)
        color = CATEGORY_COLOR.get(category, "#8D8D8D")
        inp = folder / "build_input.json"
        inp.write_text(json.dumps(build_doc(tid, dims)))
        r = subprocess.run([blender_bin, "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(BUILDER),
                            "--", str(inp), str(folder)], capture_output=True, text=True, timeout=300, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"builder failed for {tid}: {r.stderr[-1000:]}")
        inp.unlink()
        (folder / "template.json").write_text(json.dumps(template_meta(tid, dims, category, axes), indent=2) + "\n")
        cv2.imwrite(str(folder / "thumbnail.png"), thumbnail(tid, dims, color))
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
