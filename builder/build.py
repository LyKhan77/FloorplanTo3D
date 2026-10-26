"""Blender headless builder. stdlib + bpy + bmesh only; never import core/.

Usage: blender -b --factory-startup --python-exit-code 1 -P builder/build.py -- <build_input.json> <out_dir>
Input: build_input.json v1 (core/build_prep/schema.py). Lengths are mm in spec axes; Blender units are meters.
"""

import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))

import export  # noqa: E402
import scene  # noqa: E402

REQUIRED_VERSION = (5, 2)
SUPPORTED_INPUT = 1


def progress(pct: int, msg: str) -> None:
    print(f"@@PROGRESS {pct} {msg}", flush=True)


def main(argv: list[str]) -> None:
    if bpy.app.version[:2] != REQUIRED_VERSION:
        raise SystemExit(f"Blender 5.2 LTS required, got {bpy.app.version_string}")
    inp, out_dir = Path(argv[0]), Path(argv[1])
    data = json.loads(inp.read_text())
    if data.get("version") != SUPPORTED_INPUT:
        raise SystemExit(f"unsupported build_input version {data.get('version')!r}, expected {SUPPORTED_INPUT}")
    progress(5, "loaded")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    collections = scene.Collections()
    materials = scene.make_materials(data["materials"])
    objects = {}
    for e in data.get("empties", []):
        objects[e["name"]] = scene.make_empty(e, collections)
    for m in data.get("meshes", []):
        objects[m["name"]] = scene.make_mesh(m, collections, materials)
    scene.parent_all([*data.get("empties", []), *data.get("meshes", [])], objects)
    progress(30, f"built {len(objects)} objects")

    scene.apply_cutters(data.get("cutters", []), objects)
    progress(50, f"cut {len(data.get('cutters', []))} openings")

    scene.make_instances(data.get("instances", []), collections)
    scene.make_annotations(data.get("labels", []), data.get("grid_lines", []), collections)
    progress(60, "instances and annotations")

    out_dir.mkdir(parents=True, exist_ok=True)
    export.export_all(data["exports"], out_dir, collections)
    progress(70, "exported")

    cameras = data.get("cameras", [])
    if cameras:
        import render

        render.render_all(cameras, data.get("render", {}), out_dir, collections, progress)
    progress(100, "done")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
