"""CRAC units, cold-aisle containment, wall devices and fire cylinders (design §6.2), and `fill`, the engine's entry."""

import math
from dataclasses import replace

from shapely import affinity
from shapely.geometry import Point, Polygon

from core.interior.layout import Layout, Placement
from core.interior.library import Tpl
from core.interior.lineup import _inward, layout_lineup
from core.interior.rows import layout_rows
from core.interior.rules import Rules
from core.interior.space import Space

CRAC, ROOF, DOOR = "crac-unit-generic", "containment-roof-600", "containment-door-1200"
PANEL, READER, CCTV, CYL = "fire-control-panel", "access-reader-generic", "cctv-camera-bullet", "fire-cylinder-generic"
BESIDE_DOOR_MM = 300  # panel / reader distance from the door jamb
CCTV_FROM_CORNER_MM = 300


def _rot_for(front: tuple[float, float]) -> float:
    """Rotation (degrees) whose front (-sin, cos) is `front`."""
    return math.degrees(math.atan2(-front[0], front[1]))


def _taken(lay: Layout, lib: dict[str, Tpl], rules: Rules) -> list[Polygon]:
    out = []
    for p in lay.placements:
        if p.z == 0:  # roofs and wall devices up high do not take floor space
            out.append(p.footprint())
            if p.template_id in lib:
                out += p.zones(lib[p.template_id], rules)
    return out


def _fits(fp: Polygon, space: Space, taken: list[Polygon]) -> bool:
    room = space.room.buffer(1)
    if not room.covers(fp):
        return False
    return all(fp.intersection(b).area <= 1 for b in [*space.blocked, *taken])


def _on_wall(tpl: Tpl, space: Space, taken, edges, z: float, prefer=None, step: float = 200) -> Placement | None:
    """The first free spot with the back against one of `edges`, facing into the room; nearest `prefer` first."""
    spots = []
    for edge in edges:
        ang, ax, ay = _inward(space, edge)
        ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        nx, ny = -uy, ux
        along = tpl.w / 2 + 1
        while along <= edge.length - tpl.w / 2 - 1:
            x, y = ax + ux * along + nx * (tpl.d / 2 + 1), ay + uy * along + ny * (tpl.d / 2 + 1)
            spots.append((math.dist((x, y), prefer) if prefer else 0, x, y, ang))
            along += step
    for _, x, y, ang in sorted(spots):
        p = Placement(tpl.id, tpl.version, x, y, z, ang, (tpl.w, tpl.d, tpl.h))
        if _fits(p.footprint(), space, taken):
            return p
    return None


def _cracs(space: Space, lib, n: int, row_ang: float, rules: Rules) -> list[Placement]:
    """CRACs on the walls across the rows' ends, facing along the rows; their airflow zone keeps rows away."""
    tpl = lib[CRAC]
    ux, uy = math.cos(math.radians(row_ang)), math.sin(math.radians(row_ang))
    ends = [e for e in space.walls if abs(((e.coords[1][0] - e.coords[0][0]) * ux + (e.coords[1][1] - e.coords[0][1]) * uy)
                                         / e.length) < 0.1]
    ends.sort(key=lambda e: -e.length)
    out: list[Placement] = []
    taken: list[Polygon] = []
    for i in range(n):
        if not ends:
            break
        edge = ends[i % len(ends)]
        mid = edge.interpolate(0.5, normalized=True)
        p = _on_wall(tpl, space, taken, [edge], 0.0, prefer=(mid.x, mid.y))
        if p is None:
            break
        out.append(p)
        f = p.front()
        zone = affinity.translate(p.footprint(), f[0] * rules.row_end_clear_mm, f[1] * rules.row_end_clear_mm)
        taken += [p.footprint(), p.footprint().union(zone).convex_hull]
    return out


def _airflow(p: Placement, rules: Rules) -> Polygon:
    f = p.front()
    return p.footprint().union(affinity.translate(p.footprint(), f[0] * rules.row_end_clear_mm,
                                                  f[1] * rules.row_end_clear_mm)).convex_hull


def _containment(lay: Layout, lib, rules: Rules) -> None:
    """Roof modules over each cold aisle (on top of the racks) and a door at both aisle ends."""
    roof, door = lib.get(ROOF), lib.get(DOOR)
    racks = [p for r in lay.meta.get("runs", []) for p in r if lib[p.template_id].category in ("rack", "network")]
    if not roof or not door or not racks:
        return
    h = max(p.dims[2] for p in racks)
    lines: dict[tuple, list[Placement]] = {}
    for p in racks:
        ang = round(p.rotation) % 180
        local = affinity.rotate(Point(p.x, p.y), -ang, origin=(0, 0))
        facing = 1 if round(p.rotation - ang) % 360 == 0 else -1
        lines.setdefault((ang, round(local.y + facing * p.dims[1] / 2), facing), []).append((local.x, p))
    for (ang, front_y, facing), members in lines.items():
        if facing != 1:
            continue
        other = lines.get((ang, front_y + rules.cold_aisle_mm, -1))
        if not other:
            continue
        xs_a = [x for x, _ in members]
        xs_b = [x for x, _ in other]
        w = members[0][1].dims[0]
        lo, hi = max(min(xs_a), min(xs_b)) - w / 2, min(max(xs_a), max(xs_b)) + w / 2
        y = front_y + rules.cold_aisle_mm / 2
        n = int((hi - lo) // roof.w)
        start = lo + ((hi - lo) - n * roof.w) / 2
        for k in range(n):
            c = affinity.rotate(Point(start + (k + 0.5) * roof.w, y), ang, origin=(0, 0))
            lay.placements.append(Placement(ROOF, roof.version, c.x, c.y, h, ang, (roof.w, rules.cold_aisle_mm, roof.h)))
        for x in (lo - door.d / 2, hi + door.d / 2):
            c = affinity.rotate(Point(x, y), ang, origin=(0, 0))
            lay.placements.append(Placement(DOOR, door.version, c.x, c.y, 0.0, ang + 90,
                                            (rules.cold_aisle_mm, door.d, door.h)))


def _door_devices(lay: Layout, space: Space, lib, items, rules: Rules) -> None:
    """FM-200 panel and access reader on the wall beside the widest door, on either side of it."""
    if not space.doors:
        if PANEL in items or READER in items:
            lay.notes.append("tidak ada pintu: panel FM-200 / reader tidak dipasang")
        return
    dr = max(space.doors, key=lambda d: d.width)
    zc = dr.zone.centroid
    nx, ny = -dr.along[1], dr.along[0]
    if (zc.x - dr.center[0]) * nx + (zc.y - dr.center[1]) * ny < 0:
        nx, ny = -nx, -ny  # into the room
    for tid, side, z in ((PANEL, 1, rules.fm200_z_mm), (READER, -1, rules.reader_z_mm)):
        if tid not in items or tid not in lib:
            continue
        tpl = lib[tid]
        off = dr.width / 2 + BESIDE_DOOR_MM + tpl.w / 2
        x = dr.center[0] + side * dr.along[0] * off + nx * (dr.half + tpl.d / 2 + 1)
        y = dr.center[1] + side * dr.along[1] * off + ny * (dr.half + tpl.d / 2 + 1)
        lay.placements.append(Placement(tid, tpl.version, x, y, z, _rot_for((nx, ny)), (tpl.w, tpl.d, tpl.h)))


def _cameras(lay: Layout, space: Space, lib, n: int, rules: Rules) -> None:
    """Cameras near the room corners farthest apart, on the wall, looking into the room."""
    tpl = lib[CCTV]
    ring = list(space.room.exterior.coords)[:-1]
    c = space.room.centroid
    corners = sorted(ring, key=lambda p: -math.dist(p, (c.x, c.y)))
    placed = 0
    for corner in corners:
        if placed >= n:
            break
        # of the corner's two walls, the one whose inward normal points closest to the room centre (within 45°)
        def facing(e, corner=corner):  # minus the cosine between the wall's inward normal and the way to the centre
            ang = math.radians(_inward(space, e)[0])
            return math.sin(ang) * (c.x - corner[0]) - math.cos(ang) * (c.y - corner[1])
        edges = sorted((e for e in space.walls if Point(corner).distance(e) < 1), key=facing)
        for e in edges[:1]:
            ang, ax, ay = _inward(space, e)
            ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            from_a = math.dist(corner, (ax, ay)) < 1
            along = CCTV_FROM_CORNER_MM + tpl.w / 2 if from_a else e.length - CCTV_FROM_CORNER_MM - tpl.w / 2
            nx, ny = -uy, ux
            x, y = ax + ux * along + nx * (tpl.d / 2 + 1), ay + uy * along + ny * (tpl.d / 2 + 1)
            z = space.ceiling - rules.cctv_below_ceiling_mm - tpl.h
            lay.placements.append(Placement(CCTV, tpl.version, x, y, z, ang, (tpl.w, tpl.d, tpl.h)))
            placed += 1


def _cylinders(lay: Layout, space: Space, lib, n: int, rules: Rules) -> None:
    tpl = lib[CYL]
    taken = _taken(lay, lib, rules)
    placed = 0
    corners = list(space.room.exterior.coords)[:-1]
    for k in range(n):
        prefer = corners[k % len(corners)] if corners else None
        p = _on_wall(tpl, space, taken, space.walls, 0.0, prefer=prefer)
        if p is None:
            break
        lay.placements.append(p)
        taken.append(p.footprint())
        placed += 1
    if placed < n:
        lay.notes.append(f"tabung pemadam: muat {placed} dari {n}")


def fill(space: Space, lib: dict[str, Tpl], items: dict[str, int | None], options: dict, kind: str,
         rules: Rules) -> Layout:
    """The whole room: rows or line-up, then CRACs, containment and devices. `items` maps template id -> count (None =
    as many as fit / the rule default)."""
    options = {"containment": False, "cooling": None, "rows": "auto", **(options or {})}
    want_crac = options.get("cooling") == "crac" or CRAC in items
    if kind == "rows":
        best = None
        for row_opt, ang in (("ew", 0.0), ("ns", 90.0)):
            if options["rows"] not in ("auto", row_opt):
                continue
            pre: list[Placement] = []
            s2 = space
            if want_crac and CRAC in lib:
                racks_guess = sum((c or 0) for t, c in items.items() if t in lib and lib[t].category == "rack") or 20
                n = items.get(CRAC) or max(2, math.ceil(racks_guess / rules.crac_per_racks))
                pre = _cracs(space, lib, n, ang, rules)
                s2 = replace(space, blocked=[*space.blocked, *[_airflow(p, rules) for p in pre]])
            lay = layout_rows(s2, lib, items, {**options, "rows": row_opt}, rules)
            lay.placements = pre + lay.placements
            n_racks = sum(lay.capacity.values())
            if best is None or n_racks > best[0]:
                best = (n_racks, lay)
        lay = best[1]
    else:
        lay = layout_lineup(space, lib, items, rules)
    if options.get("containment"):
        _containment(lay, lib, rules)
    _door_devices(lay, space, lib, items, rules)
    if CCTV in items and CCTV in lib:
        _cameras(lay, space, lib, items[CCTV] or 2, rules)
    if CYL in items and CYL in lib:
        _cylinders(lay, space, lib, items[CYL] or max(1, math.ceil(space.room.area / 1e6 / rules.fire_cylinder_per_m2)),
                   rules)
    return lay

