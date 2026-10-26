"""Exports (PRD/06 §5): glTF binary, FBX, OBJ, and the .blend file."""

from pathlib import Path

import bpy


def _select(objs: list) -> None:
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)


def export_all(exports: list[dict], out_dir: Path, cols) -> Path | None:
    """Write glb/fbx/obj now; return the .blend path, which is saved last (after renders add the cameras)."""
    blend = None
    for item in exports:
        path = out_dir / item["file"]
        if path.suffix == ".blend":
            blend = path
            continue
        _select(cols.objects(item["collections"]))
        if path.suffix == ".glb":
            bpy.ops.export_scene.gltf(filepath=str(path), use_selection=True, export_format="GLB",
                                      export_extras=True, export_apply=True, export_yup=True,
                                      export_cameras=False, export_lights=False)
        elif path.suffix == ".fbx":
            bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, global_scale=1.0, apply_unit_scale=True)
        elif path.suffix == ".obj":
            bpy.ops.wm.obj_export(filepath=str(path), export_selected_objects=True, export_materials=True)
        else:
            raise SystemExit(f"unsupported export {item['file']}")
    return blend


def save_blend(path: Path) -> None:
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=True)
