"""Derived installation geometry (design §6.2, §6.4): elevations, drops to racks and tray lengths. Never stored:
moving a rack or a tray recomputes it."""

import json
import math
from pathlib import Path
from typing import TypedDict

from shapely.geometry import LineString, Point

from core.installation.models import CableTray, Installation, InstallMeta
from core.spec.models import PlacedObject, Spec

ACCESS_MM = 300  # free space above an overhead tray
UNDERFLOOR_LIFT_MM = 100  # an underfloor tray stands this far above the structural slab
DROP_RADIUS_MM = 1500
DROP_MAX_WIDTH_MM = 300


class Drop(TypedDict):
    rack_id: str
    tray_id: str
    tray_class: str
    at: tuple[int, int]  # on the tray axis
    to: tuple[int, int]  # rack centre
    horizontal: int
    vertical: int


def rack_categories(templates_dir: Path) -> dict[str, str]:
    """{template_id: category} from the registry (template.json files)."""
    out = {}
    for f in sorted(Path(templates_dir).glob("*/*/template.json")):
        try:
            meta = json.loads(f.read_text())
            out[meta["id"]] = meta["category"]
        except (OSError, ValueError, KeyError):
            continue
    return out


def mounting(tray: CableTray, meta: InstallMeta) -> str:
    return tray.mounting or meta.default_mounting


def ceiling(meta: InstallMeta, layout: Spec) -> int:
    return meta.ceiling_height or layout.meta.defaults.wall_height


def tray_elevation(tray: CableTray, meta: InstallMeta, layout: Spec) -> int:
    """Underside of the tray above the finished floor (z = 0)."""
    if tray.elevation is not None:
        return tray.elevation
    if mounting(tray, meta) == "overhead":
        return ceiling(meta, layout) - ACCESS_MM - tray.side_height
    return -(meta.raised_floor_height or 0) + UNDERFLOOR_LIFT_MM


def racks(inst: Installation, layout: Spec, templates: dict[str, str]) -> list[PlacedObject]:
    """Racks placed in the installation, plus rack objects still in the layout (placed before the installation layer)."""
    return [o for o in (*inst.objects, *layout.objects) if templates.get(o.template_id) == "rack"]


def drops(inst: Installation, layout: Spec, templates: dict[str, str]) -> list[Drop]:
    """One drop per rack and class, from the nearest tray of that class within DROP_RADIUS_MM of the rack centre."""
    lines = {t.id: LineString(t.path) for t in inst.cable_trays if len(t.path) >= 2}
    out: list[Drop] = []
    for r in racks(inst, layout, templates):
        c = Point(r.position[0], r.position[1])
        for cls in ("data", "power"):
            near = [(lines[t.id].distance(c), t) for t in inst.cable_trays if t.tray_class == cls and t.id in lines]
            near = [(d, t) for d, t in near if d <= DROP_RADIUS_MM]
            if not near:
                continue
            dist, t = min(near, key=lambda x: (x[0], x[1].id))
            at = lines[t.id].interpolate(lines[t.id].project(c))
            z = tray_elevation(t, inst.meta, layout)
            vertical = z - (r.position[2] + r.dims[2]) if mounting(t, inst.meta) == "overhead" else -z - t.side_height
            out.append(Drop(rack_id=r.id, tray_id=t.id, tray_class=cls, at=(round(at.x), round(at.y)),
                            to=(r.position[0], r.position[1]), horizontal=round(dist), vertical=max(0, round(vertical))))
    return out


def lengths(inst: Installation, layout: Spec, templates: dict[str, str]) -> dict:
    """mm per class: horizontal tray runs, drops (horizontal + vertical), total."""
    out = {cls: {"horizontal": 0, "drops": 0, "total": 0} for cls in ("data", "power")}
    for t in inst.cable_trays:
        out[t.tray_class]["horizontal"] += round(sum(math.dist(a, b) for a, b in zip(t.path, t.path[1:])))
    for d in drops(inst, layout, templates):
        out[d["tray_class"]]["drops"] += d["horizontal"] + d["vertical"]
    for v in out.values():
        v["total"] = v["horizontal"] + v["drops"]
    return out
