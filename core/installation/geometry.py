"""3D geometry of an installation (design §6.6-§6.7) as build_input items: perforated U trays, drops to racks,
hangers or pedestals, the ceiling, the raised floor, and sleeve cutters in the walls the trays cross."""

import math

from shapely.geometry import LineString, MultiPolygon, Point
from shapely.geometry import Polygon as SPolygon
from shapely.ops import unary_union

from core.build_prep.mesh import MeshData, box, merge, prism
from core.build_prep.schema import CutterItem, MeshItem
from core.build_prep.shell import mesh_item
from core.installation.derive import ceiling, drops, mounting, racks, tray_elevation
from core.installation.models import Installation
from core.spec.models import Spec

SHEET_MM = 1.5
ROD_MM = 10  # M10 threaded rod
CHANNEL_MM = 41  # trapeze strut
HANGER_STEP_MM = 1500
SLEEVE_PAD_MM = 50
CEILING_MM = 100
PANEL_MM = 30
PEDESTAL_GRID_MM = 600
DROP_MAX_WIDTH_MM = 300
UV_TILE_MM = 25
COLLECTION = {"data": "TrayData", "power": "TrayPower"}


def _u_section(path, width: float, side: float, z: float) -> tuple[MeshData, MeshData]:
    """Bottom plate and two side plates, mitred at corners; and the coloured lips on the side plates."""
    line = LineString(path)
    plate = prism(line.buffer(width / 2, cap_style="flat", join_style="mitre"), z, z + SHEET_MM)
    sides = [line.offset_curve(s * (width / 2 - SHEET_MM / 2), join_style="mitre").buffer(SHEET_MM / 2, cap_style="flat", join_style="mitre")
             for s in (1, -1)]
    walls = merge(plate, *(prism(p, z, z + side) for p in sides))
    lips = merge(*(prism(p, z + side, z + side + SHEET_MM) for p in sides))
    return walls, lips


def _stations(path) -> list[tuple[float, float, float, float]]:
    """(x, y, heading, turn) every HANGER_STEP_MM from the start, at the end, and at every corner. At a corner the
    heading is the bisector and `turn` the deflection (degrees): the mitred tray is wider there."""
    line = LineString(path)
    ds = sorted({*(d for d in _arange(line.length)), line.length, *(line.project(Point(p)) for p in path[1:-1])})
    out, last = [], None
    for d in ds:
        if last is not None and d - last < 100:
            continue
        last = d
        p, q = line.interpolate(max(0, d - 1)), line.interpolate(min(line.length, d + 1))
        at = line.interpolate(d)
        a, b = line.interpolate(max(0, d - 200)), line.interpolate(min(line.length, d + 200))
        h1 = math.atan2(at.y - a.y, at.x - a.x) if d > 0 else None
        h2 = math.atan2(b.y - at.y, b.x - at.x) if d < line.length else None
        turn = abs(math.degrees((h2 - h1 + math.pi) % (2 * math.pi) - math.pi)) if h1 is not None and h2 is not None else 0.0
        out.append((at.x, at.y, math.degrees(math.atan2(q.y - p.y, q.x - p.x)), turn))
    return out


def _arange(length: float) -> list[float]:
    return [k * HANGER_STEP_MM for k in range(int(length // HANGER_STEP_MM) + 1)]


def _hanger(x: float, y: float, heading: float, width: float, z: float, top: float, turn: float = 0.0) -> MeshData:
    """Trapeze strut under the tray, two rods from the strut up to the ceiling, clear of the (mitred) tray."""
    a = math.radians(heading)
    nx, ny = -math.sin(a), math.cos(a)
    reach = width / (2 * math.cos(math.radians(min(turn, 150)) / 2))  # how far the mitred tray reaches across here
    half = reach + ROD_MM * 2
    strut = box(x, y, z - CHANNEL_MM / 2, CHANNEL_MM, 2 * half + 60, CHANNEL_MM, heading)
    rods = [box(x + s * nx * half, y + s * ny * half, (z - CHANNEL_MM + top) / 2, ROD_MM, ROD_MM, top - (z - CHANNEL_MM), heading)
            for s in (1, -1)]
    return merge(strut, *rods)


def _outline(layout: Spec):
    polys = [SPolygon(p) for p in layout.meta.building_outline] or [SPolygon(r.polygon, r.holes) for r in layout.rooms]
    return unary_union(polys)


def floor_drop(layout: Spec, inst: Installation) -> int:
    """How far the layout floor slab moves down in the installation build: the raised floor's height."""
    return -(inst.meta.raised_floor_height or 0)


def _vertical_u(x: float, y: float, heading: float, width: float, side: float, z0: float, z1: float) -> MeshData:
    """A drop running up or down: the U section stood on end, back plate facing the tray."""
    a = math.radians(heading)
    ux, uy, nx, ny = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    back = box(x, y, (z0 + z1) / 2, SHEET_MM, width, z1 - z0, heading)
    sides = [box(x + ux * side / 2 + s * nx * (width / 2), y + uy * side / 2 + s * ny * (width / 2), (z0 + z1) / 2,
                 side, SHEET_MM, z1 - z0, heading) for s in (1, -1)]
    return merge(back, *sides)


def installation_items(inst: Installation, layout: Spec, templates: dict[str, str]) -> tuple[list[MeshItem], list[CutterItem]]:
    meshes: list[MeshItem] = []
    cutters: list[CutterItem] = []
    top = ceiling(inst.meta, layout)
    slab = -(inst.meta.raised_floor_height or 0)
    trays = {t.id: t for t in inst.cable_trays if len(t.path) >= 2}
    for t in trays.values():
        z = tray_elevation(t, inst.meta, layout)
        body, lips = _u_section(t.path, t.width, t.side_height, z)
        props = {"spec_id": t.id, "spec_type": "tray", "tray_class": t.tray_class}
        meshes.append(mesh_item(f"tray_{t.tray_class}_{t.id}", COLLECTION[t.tray_class], body, "tray_galv", props) | {"uv_box_mm": UV_TILE_MM})
        meshes.append(mesh_item(f"tray_{t.tray_class}_{t.id}_lip", COLLECTION[t.tray_class], lips, f"tray_edge_{t.tray_class}", props))
        overhead = mounting(t, inst.meta) == "overhead"
        for k, (x, y, heading, turn) in enumerate(_stations(t.path)):
            part = _hanger(x, y, heading, t.width, z, top, turn) if overhead else box(x, y, (slab + z) / 2, CHANNEL_MM, CHANNEL_MM, z - slab, heading)
            meshes.append(mesh_item(f"hanger_{t.id}_{k}", "Hangers", part, "hanger", {"spec_id": t.id, "spec_type": "hanger"}))
        if overhead:
            line = LineString(t.path)
            for w in layout.walls:
                if math.dist(w.a, w.b) == 0:
                    continue
                wz = (w.base_z, w.base_z + (w.height or layout.meta.defaults.wall_height))
                wall = LineString([w.a, w.b]).buffer(w.thickness / 2 + 10, cap_style="flat")
                inside = line.intersection(wall)  # only where the tray's axis goes through the wall: a tray alongside cuts nothing
                if inside.is_empty or inside.length == 0:
                    continue
                cut = inside.buffer(t.width / 2 + SLEEVE_PAD_MM, cap_style="square", join_style="mitre").intersection(wall)
                if cut.is_empty or z + t.side_height < wz[0] or z > wz[1] or not isinstance(cut, SPolygon | MultiPolygon):
                    continue
                m = prism(cut, z - SLEEVE_PAD_MM, z + t.side_height + SLEEVE_PAD_MM)
                cutters.append({"target": f"wall_{w.id}", "verts": m["verts"], "faces": m["faces"]})
    by_id = {r.id: r for r in racks(inst, layout, templates)}
    for d in drops(inst, layout, templates):
        t, r = trays[d["tray_id"]], by_id[d["rack_id"]]
        z = tray_elevation(t, inst.meta, layout)
        w = min(t.width, DROP_MAX_WIDTH_MM)
        parts = []
        if d["horizontal"]:
            heading = math.degrees(math.atan2(d["to"][1] - d["at"][1], d["to"][0] - d["at"][0]))
        else:  # straight down from the tray: the back plate runs along the tray
            line = LineString(t.path)
            s0 = line.project(Point(d["at"]))
            p, q = line.interpolate(max(0, s0 - 1)), line.interpolate(min(line.length, s0 + 1))
            heading = math.degrees(math.atan2(q.y - p.y, q.x - p.x)) + 90
        if d["horizontal"] > 0:
            parts.append(_u_section([d["at"], d["to"]], w, t.side_height, z)[0])
        if mounting(t, inst.meta) == "overhead":
            z0, z1 = r.position[2] + r.dims[2], z
        else:
            z0, z1 = z + t.side_height, r.position[2]
        if z1 > z0:
            parts.append(_vertical_u(d["to"][0], d["to"][1], heading, w, t.side_height, z0, z1))
        if parts:
            meshes.append(mesh_item(f"drop_{r.id}_{t.id}", "Drops", merge(*parts), "tray_galv",
                                    {"spec_id": f"{r.id}:{t.id}", "spec_type": "drop", "tray_class": t.tray_class}) | {"uv_box_mm": UV_TILE_MM})
    outline = _outline(layout)
    if not outline.is_empty:
        meshes.append(mesh_item("ceiling", "Ceiling", prism(outline, top, top + CEILING_MM), "ceiling", {"spec_type": "ceiling"}))
        if inst.meta.raised_floor_height:
            meshes.append(mesh_item("raised_floor_panels", "RaisedFloor", prism(outline, -PANEL_MM, 0), "raised_floor", {"spec_type": "raised_floor"}))
            x0, y0, x1, y1 = outline.bounds
            peds = [box(x, y, (slab - PANEL_MM) / 2, CHANNEL_MM, CHANNEL_MM, -PANEL_MM - slab, 0)
                    for x in _grid(x0, x1) for y in _grid(y0, y1) if outline.contains(Point(x, y))]
            if peds:
                meshes.append(mesh_item("raised_floor_pedestals", "RaisedFloor", merge(*peds), "hanger", {"spec_type": "raised_floor"}))
    return meshes, cutters


def _grid(lo: float, hi: float) -> list[float]:
    return [lo + PEDESTAL_GRID_MM / 2 + k * PEDESTAL_GRID_MM for k in range(int((hi - lo) // PEDESTAL_GRID_MM))]
