"""Electrical rooms (design §6.2): UPS / ATS / MDB lined up on the longest free wall, battery racks in rows facing it."""

import math

from shapely import affinity
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from core.interior.layout import Layout, Placement, clearance
from core.interior.library import Tpl
from core.interior.rows import _intervals
from core.interior.rules import Rules
from core.interior.space import Space

START_MM = 100  # first cabinet's distance from the corner


def _inward(space: Space, edge: LineString) -> tuple[float, float, float]:
    """(angle of the edge with the room on its left, its start x, its start y) in degrees."""
    (ax, ay), (bx, by) = edge.coords[0], edge.coords[-1]
    mx, my = (ax + bx) / 2, (ay + by) / 2
    length = edge.length
    lx, ly = -(by - ay) / length, (bx - ax) / length
    if not space.room.contains(Point(mx + lx * 10, my + ly * 10)):
        ax, ay, bx, by = bx, by, ax, ay
    return math.degrees(math.atan2(by - ay, bx - ax)), ax, ay


def _free(fp, zones, room, blocked, placed) -> bool:
    if not room.covers(fp) or any(not room.covers(z) for z in zones):
        return False
    for g in [fp, *zones]:
        if not blocked.is_empty and g.intersection(blocked).area > 1:
            return False
        if any(g.intersection(q).area > 1 for q in placed):
            return False
    return True


def layout_lineup(space: Space, lib: dict[str, Tpl], items: dict[str, int | None], rules: Rules) -> Layout:
    line = [t for t in items if t in lib and lib[t].category == "power" and not t.startswith("pdu")]
    line_tpls = [lib[t] for t in line for _ in range(items[t] or 1)]
    bat = next((lib[t] for t in items if t in lib and lib[t].category == "battery"), None)
    room = space.room.buffer(1)
    blocked = unary_union(space.blocked)
    notes, best = [], None
    for edge in sorted(space.walls, key=lambda e: -e.length):
        ang, ax, ay = _inward(space, edge)
        for from_end in (False, True):
            placed, pos, ok = [], START_MM, True
            ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            nx, ny = -uy, ux  # into the room
            sign = -1 if from_end else 1  # walk the same wall from its other end
            start = (ax + ux * edge.length, ay + uy * edge.length) if from_end else (ax, ay)
            for tpl in line_tpls:
                along = pos + tpl.w / 2
                sx, sy = start[0] + sign * ux * along, start[1] + sign * uy * along
                p = Placement(tpl.id, tpl.version, sx + nx * (tpl.d / 2 + 1), sy + ny * (tpl.d / 2 + 1), 0.0, ang,
                              (tpl.w, tpl.d, tpl.h))
                if not _free(p.footprint(), p.zones(tpl, rules), room, blocked,
                             [q.footprint() for q in placed]):
                    ok = False
                    break
                placed.append(p)
                pos += tpl.w
            if best is None or len(placed) > len(best[1]):
                best = (ang, placed)  # the whole line-up, or else the longest part that fits
            if ok:
                break
        if best and len(best[1]) == len(line_tpls):
            break
    ang, placed = best if best else (0.0, [])
    if line_tpls and len(placed) < len(line_tpls):
        notes.append(f"line-up: muat {len(placed)} dari {len(line_tpls)} perangkat (UPS/ATS/MDB)")
    lay = Layout(list(placed), {}, notes, {"lineup_angle": ang})
    if bat:
        _battery_rows(space, lay, lib, bat, items[bat.id], ang, rules)
    return lay


def _battery_rows(space: Space, lay: Layout, lib: dict[str, Tpl], bat: Tpl, target: int | None, ang: float,
                  rules: Rules) -> None:
    """Rows parallel to the line-up wall, each facing it, with an aisle of the battery front working space."""
    room = affinity.rotate(space.room, -ang, origin=(0, 0)).buffer(1)
    taken = [affinity.rotate(g, -ang, origin=(0, 0)) for p in lay.placements
             for g in [p.footprint(), *p.zones(lib[p.template_id], rules)]]
    blocked = unary_union([affinity.rotate(b, -ang, origin=(0, 0)) for b in space.blocked] + taken)
    x0, y0, x1, y1 = affinity.rotate(space.room, -ang, origin=(0, 0)).bounds
    front, _ = clearance(bat, rules)
    cur = max([g.bounds[3] for g in taken], default=y0)  # past the line-up and its working space
    count = 0
    while cur + front + bat.d <= y1:
        # the row faces the line-up wall (-y): its working space is the aisle on that side
        lo, hi = cur, cur + front + bat.d
        for a, b in _intervals(room, blocked, x0, x1, lo, hi, cur + front, hi, rules.row_end_clear_mm):
            x = a
            while x + bat.w <= b + 1e-6:
                if target is not None and count >= target:
                    lay.capacity[bat.id] = count
                    return
                c = affinity.rotate(Point(x + bat.w / 2, cur + front + bat.d / 2), ang, origin=(0, 0))
                lay.placements.append(Placement(bat.id, bat.version, c.x, c.y, 0.0, 180 + ang, (bat.w, bat.d, bat.h)))
                count += 1
                x += bat.w
        cur = hi
    lay.capacity[bat.id] = count
    if target is not None and count < target:
        lay.notes.append(f"battery rack: muat {count} dari {target}")

