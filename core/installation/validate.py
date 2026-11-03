"""Installation checks I001-I007 (design §6.5). Errors block Save; warnings and info do not."""

import math

from shapely.geometry import LineString, Polygon

from core.installation.derive import (
    ACCESS_MM,
    DROP_RADIUS_MM,
    ceiling,
    drops,
    mounting,
    racks,
    tray_elevation,
)
from core.installation.models import CableTray, Installation
from core.spec.models import Spec
from core.spec.validate import Issue

MIN_SEGMENT_MM = 100
SEPARATION_MM = 300  # power to data
UNDERFLOOR_TOP_MM = -50  # an underfloor tray's top stays under the floor panels


def _foot(t: CableTray):
    return LineString(t.path).buffer(t.width / 2, cap_style="flat", join_style="mitre")


def _box(cx: float, cy: float, w: float, d: float, rot: float) -> Polygon:
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return Polygon([(cx + x * c - y * s, cy + x * s + y * c) for x, y in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))])


def _gap(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Vertical gap between two z ranges (0 when they overlap)."""
    return max(0, a[0] - b[1], b[0] - a[1])


def validate_installation(inst: Installation, layout: Spec, templates: dict[str, str],
                          layout_head: int | None = None) -> list[Issue]:
    issues: list[Issue] = []
    meta = inst.meta
    ok = []
    for t in inst.cable_trays:
        segs = list(zip(t.path, t.path[1:]))
        if len(t.path) < 2 or len(set(t.path)) < len(t.path) or any(math.dist(a, b) < MIN_SEGMENT_MM for a, b in segs):
            issues.append(Issue("I001", "error", [t.id], f"{t.id}: jalur butuh ≥ 2 titik berbeda dan segmen ≥ {MIN_SEGMENT_MM} mm"))
        else:
            ok.append(t)
    rack_list = racks(inst, layout, templates)
    zr = {}
    for t in ok:
        z = tray_elevation(t, meta, layout)
        zr[t.id] = (z, z + t.side_height)
        if mounting(t, meta) == "overhead":
            top = ceiling(meta, layout)
            line = LineString(t.path)
            near = [r.position[2] + r.dims[2] for r in rack_list
                    if line.distance(_box(r.position[0], r.position[1], r.dims[0], r.dims[1], r.rotation).centroid) <= DROP_RADIUS_MM]
            low = max(near, default=0) + ACCESS_MM if near else 0
            if z + t.side_height > top or z < low:
                issues.append(Issue("I002", "error", [t.id], f"{t.id}: elevasi {z} mm di luar batas overhead ({low}–{top - t.side_height} mm)"))
        elif meta.raised_floor_height is None:
            issues.append(Issue("I002", "error", [t.id], f"{t.id}: tray underfloor butuh raised floor; isi tinggi raised floor instalasi"))
        elif z < -meta.raised_floor_height or z + t.side_height > UNDERFLOOR_TOP_MM:
            issues.append(Issue("I002", "error", [t.id], f"{t.id}: elevasi {z} mm di luar ruang raised floor"))
    default_h = layout.meta.defaults.wall_height
    for t in ok:
        foot = _foot(t)
        for w in layout.walls:
            if math.dist(w.a, w.b) == 0:
                continue
            wall = LineString([w.a, w.b]).buffer(w.thickness / 2, cap_style="flat")
            wz = (w.base_z, w.base_z + (w.height or default_h))
            if foot.intersects(wall) and _gap(zr[t.id], wz) == 0:
                issues.append(Issue("I003", "warning", [t.id, w.id], f"{t.id} menembus dinding {w.id}: sleeve dibuat saat build"))
    data, power = [t for t in ok if t.tray_class == "data"], [t for t in ok if t.tray_class == "power"]
    for p in power:
        for d in data:
            gap = math.hypot(_foot(p).distance(_foot(d)), _gap(zr[p.id], zr[d.id]))
            if gap < SEPARATION_MM:
                issues.append(Issue("I004", "warning", [p.id, d.id], f"tray power {p.id} dan data {d.id} berjarak {round(gap)} mm (< {SEPARATION_MM})"))
    for t in ok:
        if mounting(t, meta) != "overhead":
            continue
        foot = _foot(t)
        blockers = [(r.id, _box(r.position[0], r.position[1], r.dims[0], r.dims[1], r.rotation), r.position[2] + r.dims[2]) for r in rack_list]
        blockers += [(c.id, _box(c.center[0], c.center[1], c.size[0], c.size[1], c.rotation), c.height or default_h) for c in layout.columns]
        for eid, shape, top in blockers:
            if foot.intersects(shape) and zr[t.id][0] < top:
                issues.append(Issue("I005", "warning", [t.id, eid], f"{t.id} menabrak {eid}"))
    reached = {(d["rack_id"], d["tray_class"]) for d in drops(inst, layout, templates)}
    classes = {t.tray_class for t in inst.cable_trays}
    for r in rack_list:
        for cls in sorted(classes):  # only classes the installation has: no power trays, no "not connected to power"
            if (r.id, cls) not in reached:
                issues.append(Issue("I006", "info", [r.id], f"{r.id} tidak terhubung ke tray {cls}"))
    issues += _devices(inst, layout)
    if layout_head is not None and layout_head > meta.layout_version:
        issues.append(Issue("I007", "warning", [], f"instalasi memakai layout v{meta.layout_version}; layout terbaru v{layout_head}: rebase"))
    return issues


OVERHEAD_MM = 2000  # from this height up (containment roofs) a device takes no floor space and stands on the racks


def _devices(inst: Installation, layout: Spec) -> list[Issue]:
    """I009: a device outside every room or in a wall/column; I010: devices overlapping (fit-out design §9)."""
    from shapely.ops import unary_union

    from core.interior.layout import Placement
    from core.spec.derive import column_footprint, wall_footprint

    out: list[Issue] = []
    rooms = unary_union([Polygon(r.polygon, r.holes) for r in layout.rooms]).buffer(1) if layout.rooms else None
    solids = [wall_footprint(w, layout) for w in layout.walls] + [column_footprint(c) for c in layout.columns]
    fps = [(o, Placement(o.template_id, o.template_version, *o.position, o.rotation, tuple(o.dims)).footprint())
           for o in inst.objects]
    for o, fp in fps:
        if o.position[2] >= OVERHEAD_MM:
            continue
        outside = rooms is not None and not rooms.covers(fp)
        if outside or any(fp.intersection(s).area > 1 for s in solids):
            out.append(Issue("I009", "warning", [o.id], f"{o.id} di luar ruang atau menabrak dinding/kolom"))
    for i, (a, fa) in enumerate(fps):
        for b, fb in fps[i + 1:]:
            za, zb = (a.position[2], a.position[2] + a.dims[2]), (b.position[2], b.position[2] + b.dims[2])
            if za[0] < zb[1] and zb[0] < za[1] and fa.intersection(fb).area > 1:
                out.append(Issue("I010", "warning", [a.id, b.id], f"{a.id} dan {b.id} tumpang tindih"))
    return out
