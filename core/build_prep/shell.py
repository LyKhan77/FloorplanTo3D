"""Shell geometry for build_input: walls, columns, floors, slabs, stairs (PRD/06 §4.1, §4.4, §4.5, §4.5b)."""

import math

from shapely import affinity
from shapely.geometry import MultiPolygon, Point
from shapely.geometry import Polygon as SPolygon
from shapely.ops import unary_union

from core.build_prep.mesh import MeshData, box, flat, merge, prism
from core.build_prep.schema import EmptyItem, MeshItem
from core.spec.derive import id_key, stair_metrics, wall_footprint
from core.spec.models import Column, Spec

MIN_PIECE_MM2 = 1.0  # boolean slivers below this are float noise
SLAB_DEPTH = 150


def mesh_item(name: str, collection: str, mesh: MeshData, material: str, props: dict,
              parent: str | None = None, location: list[float] | None = None, rot_z: float = 0.0) -> MeshItem:
    return {"name": name, "collection": collection, "verts": mesh["verts"], "faces": mesh["faces"],
            "material": material, "props": props, "parent": parent,
            "location": location if location is not None else [0, 0, 0], "rot_z": rot_z}


def _clean(geom) -> SPolygon | MultiPolygon:
    parts = [p for p in getattr(geom, "geoms", [geom]) if isinstance(p, SPolygon) and p.area >= MIN_PIECE_MM2]
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def wall_solids(spec: Spec) -> dict[str, SPolygon | MultiPolygon]:
    """One footprint per wall without overlap; a shared corner belongs to the wall with the lower ID."""
    taken = SPolygon()
    out = {}
    for w in sorted(spec.walls, key=lambda w: id_key(w.id)):
        fp = wall_footprint(w, spec)
        out[w.id] = _clean(fp.difference(taken))
        taken = taken.union(fp)
    return out


def _wall_material(kind: str) -> str:
    return {"exterior": "wall_ext", "glass": "glass"}.get(kind, "wall_int")


def wall_items(spec: Spec) -> list[MeshItem]:
    solids = wall_solids(spec)
    items = []
    for w in spec.walls:
        solid = solids[w.id]
        if solid.is_empty:
            continue
        h = w.height if w.height is not None else spec.meta.defaults.wall_height
        items.append(mesh_item(f"wall_{w.id}", "Walls", prism(solid, w.base_z, w.base_z + h), _wall_material(w.kind),
                               {"spec_id": w.id, "spec_type": "wall", "height_mm": h}))
    return items


def column_shape(col: Column) -> SPolygon:
    w, d = col.size
    x, y = col.center
    if col.shape == "circle":
        return Point(x, y).buffer(w / 2, quad_segs=6)  # 24 segments
    if col.shape == "h_section" and col.kind != "pilaster":
        tf, tw = d / 10, w / 10  # flange and web thickness = 1/10 of the size
        flanges = [SPolygon([(x - w / 2, y + s * (d / 2 - tf)), (x + w / 2, y + s * (d / 2 - tf)),
                             (x + w / 2, y + s * d / 2), (x - w / 2, y + s * d / 2)]) for s in (-1, 1)]
        web = SPolygon([(x - tw / 2, y - d / 2 + tf), (x + tw / 2, y - d / 2 + tf),
                        (x + tw / 2, y + d / 2 - tf), (x - tw / 2, y + d / 2 - tf)])
        shape = unary_union([*flanges, web])
    else:
        shape = SPolygon([(x - w / 2, y - d / 2), (x + w / 2, y - d / 2), (x + w / 2, y + d / 2), (x - w / 2, y + d / 2)])
    return affinity.rotate(shape, col.rotation, origin=(x, y)) if col.rotation else shape


def column_items(spec: Spec) -> list[MeshItem]:
    out = []
    for c in spec.columns:
        h = c.height if c.height is not None else spec.meta.defaults.wall_height
        out.append(mesh_item(f"column_{c.id}", "Columns", prism(column_shape(c), 0, h),
                             "wall_ext" if c.kind == "pilaster" else "column",
                             {"spec_id": c.id, "spec_type": "column"}))
    return out


def floor_items(spec: Spec) -> list[MeshItem]:
    out = []
    for r in spec.rooms:
        out.append(mesh_item(f"room_{r.id}", "Floors", flat(SPolygon(r.polygon, r.holes), 0),
                             "floor_data_hall" if r.type == "data_hall" else "floor",
                             {"spec_id": r.id, "spec_type": "room", "area_m2": r.area_m2}))
    for n, outline in enumerate(spec.meta.building_outline, 1):
        out.append(mesh_item(f"slab_{n}", "Floors", prism(SPolygon(outline), -SLAB_DEPTH, 0), "floor",
                             {"spec_id": f"slab_{n}", "spec_type": "slab"}))
    return out


def stair_items(spec: Spec) -> tuple[list[EmptyItem], list[MeshItem]]:
    empties, meshes = [], []
    for st in spec.stairs:
        root = f"stair_{st.id}"
        empties.append({"name": root, "collection": "Stairs", "location": [0, 0, 0], "rot_z": 0.0,
                        "props": {"spec_id": st.id, "spec_type": "stair"}, "parent": None})
        metrics = stair_metrics(st, spec.meta.defaults)
        for i, (f, m) in enumerate(zip(st.flights, metrics), 1):
            length = math.hypot(f.end[0] - f.start[0], f.end[1] - f.start[1])
            ux, uy = (f.end[0] - f.start[0]) / length, (f.end[1] - f.start[1]) / length
            angle = math.degrees(math.atan2(uy, ux))
            steps = []
            for k in range(1, f.risers + 1):  # solid steps: step k rises k risers from the flight's start level
                along = (k - 0.5) * m.tread_mm
                height = k * m.riser_mm
                steps.append(box(f.start[0] + ux * along, f.start[1] + uy * along, m.start_z + height / 2,
                                 m.tread_mm, f.width, height, angle))
            meshes.append(mesh_item(f"{root}_f{i}", "Stairs", merge(*steps), "wall_int",
                                    {"spec_id": st.id, "spec_type": "stair"}, parent=root))
        for j, landing in enumerate(st.landings, 1):
            top = metrics[min(j, len(metrics)) - 1].end_z
            meshes.append(mesh_item(f"{root}_l{j}", "Stairs", prism(SPolygon(landing), st.base_z, top), "wall_int",
                                    {"spec_id": st.id, "spec_type": "stair"}, parent=root))
    return empties, meshes
