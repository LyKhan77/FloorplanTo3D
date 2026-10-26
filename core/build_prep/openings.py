"""Opening cutters, parametric doors and windows (PRD/06 §4.1 step 4, §4.2, §4.3).

Door children use door-local axes: x along the wall from the opening start, y across the wall, z up from the sill.
"""

import math

from core.build_prep.mesh import box, merge
from core.build_prep.schema import CutterItem, EmptyItem, MeshItem
from core.build_prep.shell import mesh_item
from core.spec.models import Opening, Spec

FRAME = 50
LEAF_T = 40
CUTTER_EXTRA = 20
TECHNICAL_ROOMS = {"ups_room", "battery_room", "electrical_room", "mdf", "ahu_room", "capacitor_room"}


def opening_frame(spec: Spec, o: Opening) -> tuple[tuple[float, float], float, float, float]:
    """(start point on the centerline, wall angle in degrees, opening height, sill)."""
    w = next(w for w in spec.walls if w.id == o.wall_id)
    length = math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1])
    ux, uy = (w.b[0] - w.a[0]) / length, (w.b[1] - w.a[1]) / length
    d = spec.meta.defaults
    h = o.height if o.height is not None else (d.door_height if o.category == "door" else d.window_height)
    return (w.a[0] + ux * o.offset, w.a[1] + uy * o.offset), math.degrees(math.atan2(uy, ux)), h, o.sill


def _thickness(spec: Spec, o: Opening) -> float:
    return next(w.thickness for w in spec.walls if w.id == o.wall_id)


def _valid(spec: Spec) -> list[Opening]:
    walls = {w.id for w in spec.walls}
    return [o for o in spec.openings if o.wall_id in walls]


def cutters(spec: Spec) -> list[CutterItem]:
    out = []
    for o in _valid(spec):
        (sx, sy), ang, h, sill = opening_frame(spec, o)
        ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        m = box(sx + ux * o.width / 2, sy + uy * o.width / 2, sill + h / 2,
                o.width, _thickness(spec, o) + CUTTER_EXTRA, h, ang)
        out.append({"target": f"wall_{o.wall_id}", "verts": m["verts"], "faces": m["faces"]})
    return out


def _leaf_material(spec: Spec, door_id: str) -> str:
    types = {r.type for r in spec.rooms if door_id in r.doors}
    return "door_leaf_metal" if types & TECHNICAL_ROOMS else "door_leaf"


def door_items(spec: Spec) -> tuple[list[EmptyItem], list[MeshItem]]:
    empties, meshes = [], []
    for o in _valid(spec):
        if o.category != "door":
            continue
        (sx, sy), ang, h, sill = opening_frame(spec, o)
        t, w = _thickness(spec, o), o.width
        root = f"door_{o.id}"
        empties.append({"name": root, "collection": "Doors", "location": [sx, sy, sill], "rot_z": ang,
                        "props": {"spec_id": o.id, "spec_type": "door", "door_type": o.door_type,
                                  "hinge": o.hinge, "swing": o.swing},
                        "parent": None})
        frame = merge(box(FRAME / 2, 0, h / 2, FRAME, t, h), box(w - FRAME / 2, 0, h / 2, FRAME, t, h),
                      box(w / 2, 0, h - FRAME / 2, w, t, FRAME))
        meshes.append(mesh_item(f"frame_{o.id}", "Doors", frame, "door_frame", {"spec_id": o.id, "spec_type": "door"},
                                parent=root))
        leaf_h = h - 10
        side = 1 if o.swing != "right" else -1  # left = +y local
        leaves: list[tuple[str, list[float], dict]] = []
        if o.door_type in (None, "single_swing"):
            if o.hinge == "end":
                leaves.append(("a", [w, 0, 0], box(-w / 2, 0, leaf_h / 2, w, LEAF_T, leaf_h)))
            else:
                leaves.append(("a", [0, 0, 0], box(w / 2, 0, leaf_h / 2, w, LEAF_T, leaf_h)))
        elif o.door_type == "double_swing":
            split = o.leaf_split if o.leaf_split is not None else 0.5
            wa, wb = w * split, w * (1 - split)
            leaves.append(("a", [0, 0, 0], box(wa / 2, 0, leaf_h / 2, wa, LEAF_T, leaf_h)))
            leaves.append(("b", [w, 0, 0], box(-wb / 2, 0, leaf_h / 2, wb, LEAF_T, leaf_h)))
        elif o.door_type == "sliding":
            leaves.append(("a", [0, side * (t / 2 + 20), 0], box(w / 2, 0, leaf_h / 2, w, LEAF_T, leaf_h)))
        elif o.door_type == "rolling":
            leaves.append(("a", [0, side * (t / 2 + 150), 0], box(w / 2, 0, h - 150, w, 300, 300)))
        for suffix, loc, mesh in leaves:  # "opening" has no leaf
            meshes.append(mesh_item(f"leaf_{o.id}_{suffix}", "Doors", mesh, _leaf_material(spec, o.id),
                                    {"spec_id": o.id, "spec_type": "door"}, parent=root, location=loc))
    return empties, meshes


def _window_mesh(start: tuple[float, float], ang: float, sill: float, w: float, h: float):
    ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))

    def at(lx: float, lz: float, sx: float, sy: float, sz: float):
        return box(start[0] + ux * lx, start[1] + uy * lx, sill + lz, sx, sy, sz, ang)

    return merge(at(FRAME / 2, h / 2, FRAME, 60, h), at(w - FRAME / 2, h / 2, FRAME, 60, h),
                 at(w / 2, h - FRAME / 2, w, 60, FRAME), at(w / 2, FRAME / 2, w, 60, FRAME),
                 at(w / 2, h / 2, w - 2 * FRAME, 10, h - 2 * FRAME))


def window_items(spec: Spec) -> list[MeshItem]:
    out = []
    for o in _valid(spec):
        if o.category != "window":
            continue
        start, ang, h, sill = opening_frame(spec, o)
        mesh = _window_mesh(start, ang, sill, o.width, h)
        out.append(mesh_item(f"window_{o.id}", "Windows", mesh, "glass", {"spec_id": o.id, "spec_type": "window"}))
    return out
