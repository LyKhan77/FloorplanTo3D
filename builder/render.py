"""Verification and document renders (PRD/06 §6 step 1, §7.1). Runs after the exports."""

import math
from pathlib import Path

import bpy

MM = 0.001
SOLID_COLLECTIONS = ("Walls", "Columns")  # black in the verification render
CUTAWAY_COLLECTIONS = ("Walls", "Columns", "Doors", "Windows")  # clipped at cutaway height in iso renders


def _camera(item: dict, cols) -> bpy.types.Object:
    cam = bpy.data.cameras.new(item["name"])
    cam.clip_start, cam.clip_end = 0.01, 2000.0
    if item["kind"] == "ORTHO":
        cam.type = "ORTHO"
        cam.ortho_scale = item["ortho_scale"] * MM
    else:
        cam.type = "PERSP"
        cam.sensor_fit = "HORIZONTAL"
        cam.angle = math.radians(item["fov_deg"])
    obj = bpy.data.objects.new(item["name"], cam)
    obj.location = [c * MM for c in item["location"]]
    obj.rotation_euler = [math.radians(a) for a in item["rotation_deg"]]
    cols.get("Cameras").objects.link(obj)
    return obj


def _solids(cols, names=SOLID_COLLECTIONS) -> list[bpy.types.Object]:
    return [o for name in names for o in cols.objects([name]) if o.type == "MESH"]


def _setup_common(scene: bpy.types.Scene, item: dict, out_dir: Path) -> None:
    scene.render.resolution_x, scene.render.resolution_y = item["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.filepath = str(out_dir / item["output"])
    scene.render.film_transparent = False
    (out_dir / item["output"]).parent.mkdir(parents=True, exist_ok=True)


def _render_verify(scene, cols) -> list:
    """Walls and columns flat black on white, nothing else, no anti-aliasing or colour management."""
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light, shading.color_type = "FLAT", "OBJECT"
    shading.show_shadows = shading.show_cavity = shading.show_object_outline = False
    shading.show_specular_highlight = False
    scene.display.render_aa = "OFF"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure, scene.view_settings.gamma = 0.0, 1.0
    scene.render.dither_intensity = 0.0
    scene.world.color = (1, 1, 1)
    solids = set(_solids(cols))
    hidden = []
    for o in scene.objects:
        if o in solids:
            o.color = (0, 0, 0, 1)
        elif not o.hide_render:
            o.hide_render = True
            hidden.append(o)
    return hidden


def _render_doc(scene, cols, engine: str, item: dict) -> list:
    scene.render.engine = engine
    if engine == "BLENDER_WORKBENCH":
        shading = scene.display.shading
        shading.light, shading.color_type = "STUDIO", "MATERIAL"
        shading.show_shadows, shading.show_cavity = False, True
        scene.display.render_aa = "8"
    scene.view_settings.view_transform = "Standard"
    scene.world.color = (0.95, 0.95, 0.95)
    hidden = []
    if item["name"] != "cam_top":  # annotations (labels, grid) only on the top view
        for o in cols.objects(["Annotations"]):
            if not o.hide_render:
                o.hide_render = True
                hidden.append(o)
    return hidden


def _cutaway(cols, height_mm: float) -> tuple[bpy.types.Object, list]:
    """Temporary INTERSECT booleans that keep walls/columns below `height_mm`; exports are already written."""
    me = bpy.data.meshes.new("_cutaway")
    s, top = 10_000.0, height_mm * MM
    me.from_pydata([(-s, -s, -1), (s, -s, -1), (s, s, -1), (-s, s, -1), (-s, -s, top), (s, -s, top), (s, s, top),
                    (-s, s, top)], [], [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6],
                                        [3, 0, 4, 7]])
    box = bpy.data.objects.new("_cutaway", me)
    bpy.context.scene.collection.objects.link(box)
    box.hide_render = True
    mods = []
    for o in _solids(cols, CUTAWAY_COLLECTIONS):
        mod = o.modifiers.new("_cutaway", "BOOLEAN")
        mod.operation, mod.solver, mod.object = "INTERSECT", "FLOAT", box  # Blender 5: FAST was renamed FLOAT
        mods.append((o, mod))
    return box, mods


def render_all(cameras: list[dict], cfg: dict, out_dir: Path, cols, progress) -> None:
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    engine = cfg.get("engine", "BLENDER_WORKBENCH")
    for i, item in enumerate(cameras):
        scene.camera = _camera(item, cols)
        _setup_common(scene, item, out_dir)
        hidden = _render_verify(scene, cols) if item["mode"] == "verify" else _render_doc(scene, cols, engine, item)
        cut = _cutaway(cols, item["cutaway_mm"]) if item.get("cutaway_mm") else None
        bpy.ops.render.render(write_still=True)
        if cut:
            box, mods = cut
            for o, mod in mods:
                o.modifiers.remove(mod)
            me = box.data
            bpy.data.objects.remove(box)
            bpy.data.meshes.remove(me)
        for o in hidden:
            o.hide_render = False
        progress(70 + int(29 * (i + 1) / len(cameras)), f"rendered {item['name']}")
