"""Hot/cold-aisle rack rows for a data hall (design §6.2).

Works in a local frame where rows run along x: the room is turned by -angle, rows are walked across y, and each
placement is turned back. Facing +1 = front towards +y (local rotation 0), -1 = towards -y (180).
"""

import math

import numpy as np
from shapely import affinity
from shapely.geometry import Point
from shapely.geometry import box as sbox
from shapely.ops import unary_union

from core.interior.layout import Layout, Placement
from core.interior.library import Tpl
from core.interior.rules import Rules
from core.interior.space import Space

STRIP_MM = 100
OFFSET_STEP_MM = 100


def _row_lines(y0: float, y1: float, off: float, d: float, front: float, back: float, rules: Rules):
    """(centre y, facing) of each row across [y0, y1]: pairs facing a cold aisle, back to back across hot aisles,
    and one single row at the end when a pair no longer fits."""
    rows, cur = [], y0 + back + off
    while True:
        b_bottom = cur + d + rules.cold_aisle_mm
        if b_bottom + d + back <= y1:
            rows += [(cur + d / 2, 1), (b_bottom + d / 2, -1)]
            cur = b_bottom + d + rules.hot_aisle_mm
            continue
        if cur + d + front <= y1:
            rows.append((cur + d / 2, 1))
        return rows


def _parts(g):
    return [q for q in getattr(g, "geoms", [g]) if not q.is_empty and q.area > 1]


def _intervals(room, blocked, x0: float, x1: float, lo: float, hi: float, ylo: float, yhi: float, end: float):
    """Free x intervals of the band [lo, hi] (rack plus its zones): a full-height strip is free when nothing outside the
    room or blocked overlaps it, so every obstacle forbids its x extent. Outside-room pieces at the rack's own height
    forbid `end` more on each side (row-end clearance to the walls)."""
    band = sbox(x0, lo, x1, hi)
    bad = [(q.bounds[0], q.bounds[2]) for q in _parts(band.difference(room))]
    bad += [(q.bounds[0] - end, q.bounds[2] + end) for q in _parts(sbox(x0 - end, ylo, x1 + end, yhi).difference(room))]
    if not blocked.is_empty:
        bad += [(q.bounds[0], q.bounds[2]) for q in _parts(blocked.intersection(band))]
    out, cur = [], x0
    for a, b in sorted(bad):
        if a > cur:
            out.append((cur, min(a, x1)))
        cur = max(cur, b)
        if cur >= x1:
            break
    if cur < x1:
        out.append((cur, x1))
    return [(a, b) for a, b in out if b > a]


def _sequence(rack: Tpl, pdu: Tpl | None, cooler: Tpl | None, every: int):
    """Item order from the door end, as long as the run asks: [PDU] then racks, a cooler after every `every` racks."""
    if pdu:
        yield pdu
    count = 0
    while True:
        yield rack
        count += 1
        if cooler and count % every == 0:
            yield cooler


def _walk(space: Space, ang: float, off: float, rack: Tpl, pdu, cooler, rules: Rules):
    """Runs (lists of placements, door end first) for one orientation and cross offset."""
    room = affinity.rotate(space.room, -ang, origin=(0, 0)).buffer(1)  # 1 mm tolerance on the room edge
    blocked = unary_union([affinity.rotate(b, -ang, origin=(0, 0)) for b in space.blocked])
    doors = [affinity.rotate(Point(dr.center), -ang, origin=(0, 0)) for dr in space.doors]
    x0, y0, x1, y1 = affinity.rotate(space.room, -ang, origin=(0, 0)).bounds
    d, back, front = rack.d, max(rack.back_clear, rules.wall_clear_mm), rack.front_clear
    grid = rules.grid_mm
    runs = []
    for yc, facing in _row_lines(y0, y1, off, d, front, back, rules):
        lo = yc - d / 2 - (rack.back_clear if facing > 0 else front)
        hi = yc + d / 2 + (front if facing > 0 else rack.back_clear)
        for a, b in _intervals(room, blocked, x0, x1, lo, hi, yc - d / 2, yc + d / 2, rules.row_end_clear_mm):
            if b - a < rack.w:
                continue
            mid = Point((a + b) / 2, yc)
            near = min(doors, key=lambda p: p.distance(mid)) if doors else None
            from_right = near is not None and near.x > (a + b) / 2
            # grid-aligned start at the door end
            if from_right:
                start, step = x0 + math.floor((b - x0) / grid) * grid, -1
            else:
                start, step = x0 + math.ceil((a - x0) / grid) * grid, 1
            seq = _sequence(rack, pdu, cooler, rules.inrow_per_racks)
            run, pos, in_run = [], start, 0
            front_line = yc + facing * d / 2
            for item in seq:
                lo_x, hi_x = (pos, pos + item.w) if step > 0 else (pos - item.w, pos)
                if lo_x < a - 1e-6 or hi_x > b + 1e-6:
                    break
                if item is rack and in_run == rules.max_row_len:  # cross aisle, then a new run
                    runs.append(run)
                    pos += step * rules.row_end_clear_mm
                    run, in_run = [], 0
                    lo_x, hi_x = (pos, pos + item.w) if step > 0 else (pos - item.w, pos)
                    if lo_x < a - 1e-6 or hi_x > b + 1e-6:
                        break
                cx, cy = (lo_x + hi_x) / 2, front_line - facing * item.d / 2
                wx, wy = affinity.rotate(Point(cx, cy), ang, origin=(0, 0)).coords[0]
                run.append(Placement(item.id, item.version, wx, wy, 0.0, (0 if facing > 0 else 180) + ang,
                                     (item.w, item.d, item.h)))
                in_run += item is rack
                pos += step * item.w
            while run and run[-1].template_id != rack.id:  # a run never ends on a cooler
                if pdu and run[-1].template_id == pdu.id and len(run) == 1:
                    break
                run.pop()
            if any(p.template_id == rack.id for p in run):
                runs.append(run)
    return runs


def layout_rows(space: Space, lib: dict[str, Tpl], items: dict[str, int | None], options: dict,
                rules: Rules) -> Layout:
    rack_ids = [t for t in items if t in lib and lib[t].category in ("rack", "network")]
    if not rack_ids:
        return Layout(meta={"runs": []})  # no racks: the other items stand against the walls (devices._leftovers)
    rack = lib[rack_ids[0]]
    notes = [f"{t} dilewati: baris memakai satu jenis rack ({rack.id})" for t in rack_ids[1:]]
    target = items[rack.id]
    pdu = next((lib[t] for t in items if t in lib and t.startswith("pdu")), None)
    cooler = None
    if options.get("cooling") == "inrow":
        cooler = next((tpl for t, tpl in lib.items() if t.startswith("inrow")), None)
    angles = {"ew": [0.0], "ns": [90.0]}.get(options.get("rows") or "auto", [0.0, 90.0])
    module = 2 * rack.d + rules.cold_aisle_mm + rules.hot_aisle_mm
    best = None
    for ang in angles:
        for off in np.arange(0, module, OFFSET_STEP_MM):
            runs = _walk(space, ang, float(off), rack, pdu, cooler, rules)
            n = sum(p.template_id == rack.id for r in runs for p in r)
            key = (n, -len(runs))
            if best is None or key > best[0]:
                best = (key, runs)
    runs = best[1]
    capacity = best[0][0]
    if target is not None and target < capacity:
        runs = _keep_nearest(runs, target, rack.id, space)
    elif target is not None and target > capacity:
        notes.append(f"muat {capacity} dari {target} rack")
    return Layout([p for r in runs for p in r], {rack.id: capacity}, notes, {"runs": runs})


def _keep_nearest(runs: list[list[Placement]], target: int, rack_id: str, space: Space) -> list[list[Placement]]:
    """Fill the target from the runs nearest a door (each run starts at its door end)."""
    if space.doors:
        dist = lambda r: min(math.dist((r[0].x, r[0].y), dr.center) for dr in space.doors)
    else:
        c = space.room.centroid
        dist = lambda r: math.dist((r[0].x, r[0].y), (c.x, c.y))
    out, left = [], target
    for run in sorted(runs, key=dist):
        if left <= 0:
            break
        kept, n = [], 0
        for p in run:
            if p.template_id == rack_id:
                if n == left:
                    break
                n += 1
            kept.append(p)
        while kept and kept[-1].template_id != rack_id:
            kept.pop()
        out.append(kept)
        left -= n
    return out
