"""Spec -> build_input.json v1 (PRD/03 §13)."""

from pathlib import Path

from shapely.geometry import Polygon as SPolygon

from core.build_prep.cameras import _bbox, cameras, px_to_mm_axis_aligned
from core.build_prep.openings import cutters, door_items, window_items
from core.build_prep.schema import BUILD_INPUT_VERSION, MATERIALS, ExportItem, InstanceItem
from core.build_prep.shell import column_items, floor_items, stair_items, wall_items
from core.spec.models import Spec
from core.templates.registry import load_template
from core.templates.validate import validate_template

EXPORTS: list[ExportItem] = [
    {"file": "shell.glb", "collections": ["Shell"]},
    {"file": "layout_full.glb", "collections": ["Shell", "Objects"]},
    {"file": "layout.blend", "collections": []},
    {"file": "layout.fbx", "collections": ["Shell", "Objects"]},
    {"file": "layout.obj", "collections": ["Shell", "Objects"]},
]
LABEL_SIZE = 300
GRID_OVERHANG = 2000


def _instances(spec: Spec, templates_root: Path | None) -> tuple[list[InstanceItem], list[str]]:
    out, warnings = [], []
    problems_by_key: dict[str, list[str]] = {}
    for o in spec.objects:
        key = f"{o.template_id}@{o.template_version}"
        found = load_template(templates_root, o.template_id, o.template_version) if templates_root else None
        if found is None:
            warnings.append(f"object {o.id}: template {key} not found")
            continue
        meta, glb = found
        if key not in problems_by_key:
            problems_by_key[key] = validate_template(glb.parent)
        if problems_by_key[key]:
            warnings.append(f"object {o.id}: template {key} invalid: {problems_by_key[key][0]}")
            continue
        out.append({"name": f"obj_{o.id}", "asset": str(glb.resolve()),
                    "template_key": f"{o.template_id}@{o.template_version}",
                    "location": list(o.position), "rot_z": o.rotation,
                    "scale": [o.dims[0] / meta.dims.w, o.dims[1] / meta.dims.d, o.dims[2] / meta.dims.h],
                    "props": {"spec_id": o.id, "spec_type": "object", "template_id": o.template_id,
                              "label": o.label}})
    return out, warnings


def build_input_for(spec: Spec, templates_root: Path | None, image_size: tuple[int, int] | None,
                    engine: str = "BLENDER_WORKBENCH") -> tuple[dict, list[str]]:
    warnings: list[str] = []
    door_empties, door_meshes = door_items(spec)
    stair_empties, stair_meshes = stair_items(spec)
    meshes = [*wall_items(spec), *column_items(spec), *floor_items(spec), *window_items(spec), *door_meshes,
              *stair_meshes]
    empties = [*door_empties, *stair_empties]
    instances, inst_warnings = _instances(spec, templates_root)
    warnings += inst_warnings
    for item in (*meshes, *empties, *instances):
        item["props"]["spec_version"] = spec.meta.version

    labels = []
    for r in spec.rooms:
        if r.type == "outdoor":
            continue
        at = r.label_pos or SPolygon(r.polygon, r.holes).representative_point().coords[0]
        labels.append({"text": r.name or r.id, "location": list(at), "size": LABEL_SIZE})
    x0, y0, x1, y1 = _bbox(spec)
    grid_lines = []
    for ax in spec.grid.axes:
        if ax.orientation == "vertical":
            a, b = [ax.offset, y0 - GRID_OVERHANG], [ax.offset, y1 + GRID_OVERHANG]
        else:
            a, b = [x0 - GRID_OVERHANG, ax.offset], [x1 + GRID_OVERHANG, ax.offset]
        grid_lines.append({"a": a, "b": b, "label": ax.label})

    if image_size and not px_to_mm_axis_aligned(spec):
        warnings.append("px_to_mm is rotated: verification render skipped")
    doc = {"version": BUILD_INPUT_VERSION, "spec_version": spec.meta.version, "materials": MATERIALS,
           "meshes": meshes, "empties": empties, "cutters": cutters(spec), "instances": instances,
           "labels": labels, "grid_lines": grid_lines, "cameras": cameras(spec, image_size),
           "render": {"engine": engine}, "exports": EXPORTS}
    return doc, warnings
