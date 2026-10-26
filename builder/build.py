"""Blender headless builder. stdlib + bpy + bmesh only; never import core/.

Usage: blender -b --factory-startup --python-exit-code 1 -P builder/build.py -- <build_input.json> <out_dir>
build_input v0: {"version": 0, "boxes": [{"name", "min_mm": [x,y,z], "size_mm": [w,d,h], "props": {}}]}
Spec units are mm (+X east, +Y north, +Z up); Blender units are meters.
"""

import json
import sys
from pathlib import Path

import bmesh
import bpy

REQUIRED_VERSION = (5, 2)


def progress(pct: int, msg: str) -> None:
    print(f"@@PROGRESS {pct} {msg}", flush=True)


def add_box(spec: dict) -> None:
    size = [v / 1000 for v in spec["size_mm"]]
    center = [(lo + s / 2) / 1000 for lo, s in zip(spec["min_mm"], spec["size_mm"])]
    mesh = bpy.data.meshes.new(spec["name"])
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)  # bake size into mesh so glTF extents are real
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(spec["name"], mesh)
    obj.location = center
    for key, value in spec.get("props", {}).items():
        obj[key] = value
    bpy.context.scene.collection.objects.link(obj)


def main(argv: list[str]) -> None:
    if bpy.app.version[:2] != REQUIRED_VERSION:
        raise SystemExit(f"Blender 5.2 LTS required, got {bpy.app.version_string}")
    inp, out_dir = Path(argv[0]), Path(argv[1])
    data = json.loads(inp.read_text())
    progress(10, "loaded")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    for box in data["boxes"]:
        add_box(box)
    progress(60, "built")

    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(out_dir / "shell.glb"),
        export_format="GLB",
        export_extras=True,
        export_yup=True,
    )
    progress(100, "exported")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
