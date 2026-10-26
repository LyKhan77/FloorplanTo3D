"""Scene assembly from build_input v1: collections, materials, meshes, empties, cutters, instances, annotations."""

import math

import bmesh
import bpy
from mathutils import Matrix

MM = 0.001
SHELL_CHILDREN = ("Walls", "Columns", "Doors", "Windows", "Stairs", "Floors")
MERGE_DIST_M = 0.0001  # 0.1 mm


class Collections:
    """Lazily created collection tree: Shell/{Walls,...}, Objects, Annotations, Cameras, Template, _templates."""

    def __init__(self) -> None:
        self._by_name: dict[str, bpy.types.Collection] = {}

    def get(self, name: str) -> bpy.types.Collection:
        if name not in self._by_name:
            col = bpy.data.collections.new(name)
            parent = self.get("Shell") if name in SHELL_CHILDREN else bpy.context.scene.collection
            parent.children.link(col)
            self._by_name[name] = col
        return self._by_name[name]

    def objects(self, names: list[str]) -> list[bpy.types.Object]:
        """All objects in the named collections (recursive); empty list = every object in the scene."""
        if not names:
            return list(bpy.context.scene.objects)
        out = []
        for n in names:
            if n in self._by_name:
                out += [o for o in self._by_name[n].all_objects if o not in out]
        return out


def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def make_materials(spec: dict) -> dict[str, bpy.types.Material]:
    out = {}
    for name, m in spec.items():
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        h = m["color"].lstrip("#")
        rgb = [_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)]
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Roughness"].default_value = m["roughness"]
        bsdf.inputs["Alpha"].default_value = m["alpha"]
        mat.diffuse_color = (*rgb, m["alpha"])  # used by Workbench MATERIAL color
        if m["alpha"] < 1:
            mat.surface_render_method = "BLENDED"
        out[name] = mat
    return out


def _set_props(obj: bpy.types.Object, props: dict) -> None:
    for k, v in props.items():
        if v is not None:
            obj[k] = v


def make_mesh(item: dict, cols: Collections, mats: dict) -> bpy.types.Object:
    me = bpy.data.meshes.new(item["name"])
    me.from_pydata([[c * MM for c in v] for v in item["verts"]], [], item["faces"])
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DIST_M)
    bm.to_mesh(me)  # normals come oriented from core; no recalculation (open floor meshes would flip)
    bm.free()
    if item.get("material") in mats:
        me.materials.append(mats[item["material"]])
    obj = bpy.data.objects.new(item["name"], me)
    obj.location = [c * MM for c in item.get("location", [0, 0, 0])]
    obj.rotation_euler.z = math.radians(item.get("rot_z", 0.0))
    _set_props(obj, item.get("props", {}))
    cols.get(item["collection"]).objects.link(obj)
    return obj


def make_empty(item: dict, cols: Collections) -> bpy.types.Object:
    obj = bpy.data.objects.new(item["name"], None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.2
    obj.location = [c * MM for c in item["location"]]
    obj.rotation_euler.z = math.radians(item.get("rot_z", 0.0))
    _set_props(obj, item.get("props", {}))
    cols.get(item["collection"]).objects.link(obj)
    return obj


def parent_all(items: list[dict], objects: dict) -> None:
    """Children keep their location/rotation as values in the parent's space (identity parent inverse)."""
    for item in items:
        parent = item.get("parent")
        if parent:
            if parent not in objects:
                print(f"WARN parent missing {parent} for {item['name']}", flush=True)
                continue
            objects[item["name"]].parent = objects[parent]


def apply_cutters(cutters: list[dict], objects: dict) -> None:
    by_target: dict[str, list[dict]] = {}
    for c in cutters:
        by_target.setdefault(c["target"], []).append(c)
    for target, cs in by_target.items():
        obj = objects.get(target)
        if obj is None:
            print(f"WARN cutter target missing {target}", flush=True)
            continue
        tools = []
        for i, c in enumerate(cs):
            me = bpy.data.meshes.new(f"_cut_{target}_{i}")
            me.from_pydata([[v * MM for v in p] for p in c["verts"]], [], c["faces"])
            tool = bpy.data.objects.new(me.name, me)
            bpy.context.scene.collection.objects.link(tool)
            mod = obj.modifiers.new(me.name, "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.solver = "EXACT"
            mod.object = tool
            tools.append(tool)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        cut_mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
        obj.modifiers.clear()
        old = obj.data
        obj.data = cut_mesh
        cut_mesh.name = old.name
        bpy.data.meshes.remove(old)
        for tool in tools:
            me = tool.data
            bpy.data.objects.remove(tool)
            bpy.data.meshes.remove(me)


def _import_template(path: str, key: str, cols: Collections) -> list[bpy.types.Object]:
    """Import an asset.glb once into a hidden _templates/<key> collection."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    imported = [o for o in bpy.data.objects if o not in before]
    lib = cols.get("_templates")
    sub = bpy.data.collections.new(key)
    lib.children.link(sub)
    for o in imported:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        sub.objects.link(o)
    return imported


def make_instances(instances: list[dict], cols: Collections) -> None:
    """Each instance = Empty obj_<id> (pivot, rotation, per-axis scale) + linked duplicates of the template objects."""
    cache: dict[str, list[bpy.types.Object]] = {}
    target = cols.get("Objects")
    for inst in instances:
        key = inst["template_key"]
        if key not in cache:
            try:
                cache[key] = _import_template(inst["asset"], key, cols)
            except Exception as e:  # noqa: BLE001 - a broken asset must not abort the whole build
                print(f"WARN template import failed {key}: {e}", flush=True)
                cache[key] = None
        if cache[key] is None:
            print(f"WARN object skipped {inst['props'].get('spec_id')}: template {key} unavailable", flush=True)
            continue
        root = make_empty({"name": inst["name"], "collection": "Objects", "location": inst["location"],
                           "rot_z": inst["rot_z"], "props": inst["props"]}, cols)
        root.scale = inst["scale"]
        dup_of: dict[bpy.types.Object, bpy.types.Object] = {}
        for src in cache[key]:
            dup = src.copy()  # shares mesh data: a linked duplicate
            target.objects.link(dup)
            dup_of[src] = dup
        for src, dup in dup_of.items():
            dup.parent = dup_of.get(src.parent, root)
            inherited = src.parent in dup_of
            dup.matrix_parent_inverse = src.matrix_parent_inverse.copy() if inherited else Matrix.Identity(4)
    if "_templates" in bpy.context.view_layer.layer_collection.children:
        bpy.context.view_layer.layer_collection.children["_templates"].exclude = True


def make_annotations(labels: list[dict], grid_lines: list[dict], cols: Collections) -> None:
    col = cols.get("Annotations") if labels or grid_lines else None
    for i, lb in enumerate(labels):
        curve = bpy.data.curves.new(f"label_{i}", "FONT")
        curve.body = lb["text"]
        curve.size = lb["size"] * MM
        curve.align_x = "CENTER"
        curve.align_y = "CENTER"
        obj = bpy.data.objects.new(f"label_{i}", curve)
        obj.location = (lb["location"][0] * MM, lb["location"][1] * MM, 0.01)
        col.objects.link(obj)
    for g in grid_lines:
        (ax, ay), (bx, by) = g["a"], g["b"]
        length = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / length, (by - ay) / length
        nx, ny, h = -uy * 10, ux * 10, 5  # 20 mm wide strip, 5 mm above the floor
        verts = [(ax + nx, ay + ny, h), (bx + nx, by + ny, h), (bx - nx, by - ny, h), (ax - nx, ay - ny, h)]
        me = bpy.data.meshes.new(f"grid_{g['label']}")
        me.from_pydata([[c * MM for c in v] for v in verts], [], [[0, 3, 2, 1]])
        obj = bpy.data.objects.new(me.name, me)
        col.objects.link(obj)
