"""Synthetic variants of the Gatsu GT (M7b): the GT changed at random, so every variant's GT is known exactly.

Changes, in this order: bay widths (points between two axes move linearly, points beyond the outer axes move with
them), a left-right mirror, dropped partitions, added partitions, re-drawn door types, a stair shift. Rooms are
then formed again from the walls with the GT room labels carried along (core.spec.rooms.rebuild_rooms).
"""

import math
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from core.spec.derive import column_footprint, endpoint_connected, wall_footprint
from core.spec.ids import take_id
from core.spec.models import Spec, Wall
from core.spec.rooms import RoomLabel, rebuild_rooms

GT_PATH = Path("benchmarks/gatsu/gt_spec.json")
SWING_TYPES = ("single_swing", "double_swing", "sliding")
NEW_WALL_MM = 100
LEAF_MIN_MM, LEAF_MAX_MM = 500, 1300
END_MARGIN_MM = 50  # V008: an opening keeps 50 mm from each wall end
MIN_SPLIT_ROOM_MM2 = 15_000_000


def load_base() -> Spec:
    return Spec.model_validate_json(GT_PATH.read_text())


def _offsets(spec: Spec, orientation: str) -> list[int]:
    return sorted(a.offset for a in spec.grid.axes if a.orientation == orientation)


def _bays(spec: Spec) -> list[int]:
    return [int(b - a) for o in ("vertical", "horizontal") for a, b in zip(_offsets(spec, o), _offsets(spec, o)[1:])]


def no_ops(base: Spec) -> dict:
    return {"bays": _bays(base), "mirror": False, "drop_partitions": 0, "add_partitions": 0, "door_types": 0,
            "stair_shift": (0, 0)}


def draw_ops(base: Spec, rng: np.random.Generator) -> dict:
    return {"bays": [int(round(b * rng.uniform(0.75, 1.25) / 500) * 500) for b in _bays(base)],
            "mirror": bool(rng.random() < 0.5), "drop_partitions": int(rng.integers(0, 4)),
            "add_partitions": int(rng.integers(0, 3)), "door_types": int(rng.integers(0, 6)),
            "stair_shift": (int(rng.integers(-6, 7)) * 50, int(rng.integers(-6, 7)) * 50)}


def _length(w: Wall) -> float:
    return math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1])


def _remap(s: Spec, labels: list[RoomLabel], fn) -> list[RoomLabel]:
    """Move every absolute point with fn; openings keep their centre on the moved wall, pushed inside if needed."""
    p = lambda q: tuple(round(v) for v in fn(q))
    old = {w.id: w.model_copy() for w in s.walls}
    for w in s.walls:
        w.a, w.b = p(w.a), p(w.b)
    walls = {w.id: w for w in s.walls}
    kept = []
    for o in s.openings:
        w0, w = old[o.wall_id], walls[o.wall_id]
        t = (o.offset + o.width / 2) / (_length(w0) or 1)
        cx, cy = fn((w0.a[0] + t * (w0.b[0] - w0.a[0]), w0.a[1] + t * (w0.b[1] - w0.a[1])))
        length = _length(w)
        if length < o.width + 2 * END_MARGIN_MM:
            continue  # the wall became too short for its opening
        ux, uy = (w.b[0] - w.a[0]) / length, (w.b[1] - w.a[1]) / length
        along = (cx - w.a[0]) * ux + (cy - w.a[1]) * uy
        o.offset = round(min(max(along - o.width / 2, END_MARGIN_MM), length - o.width - END_MARGIN_MM))
        # two openings pushed onto each other by a shorter wall: the GT keeps the first
        if not any(k.wall_id == o.wall_id and o.offset < k.offset + k.width and k.offset < o.offset + o.width for k in kept):
            kept.append(o)
    s.openings = kept
    for c in s.columns:
        c.center = p(c.center)
    for st in s.stairs:
        for f in st.flights:
            f.start, f.end = p(f.start), p(f.end)
        st.landings = [[p(q) for q in ring] for ring in st.landings]
    return [RoomLabel(at=p(lb.at), name=lb.name, type=lb.type) for lb in labels]


def _bay_fn(old: list[int], new: list[int]):
    def f(v: float) -> float:
        if v <= old[0]:
            return v - old[0] + new[0]
        if v >= old[-1]:
            return v - old[-1] + new[-1]
        return float(np.interp(v, old, new))
    return f


def _apply_bays(s: Spec, labels: list[RoomLabel], bays: list[int]) -> list[RoomLabel]:
    ov, oh = _offsets(s, "vertical"), _offsets(s, "horizontal")
    nv = [0, *np.cumsum(bays[:len(ov) - 1]).tolist()]
    nh = [0, *np.cumsum(bays[len(ov) - 1:]).tolist()]
    fx, fy = _bay_fn(ov, nv), _bay_fn(oh, nh)
    move = {**{("vertical", o): n for o, n in zip(ov, nv)}, **{("horizontal", o): n for o, n in zip(oh, nh)}}
    for a in s.grid.axes:
        a.offset = int(move[(a.orientation, a.offset)])
    # a narrower bay narrows the stair across its flights too, or the treads run into the walls around them
    for st in s.stairs:
        for f in st.flights:
            mid = ((f.start[0] + f.end[0]) / 2, (f.start[1] + f.end[1]) / 2)
            across, fn = (0, fx) if abs(f.end[1] - f.start[1]) >= abs(f.end[0] - f.start[0]) else (1, fy)
            half = f.width / 2
            lo, hi = list(mid), list(mid)
            lo[across] -= half
            hi[across] += half
            f.width = round(min(f.width, fn(hi[across]) - fn(lo[across])))
    return _remap(s, labels, lambda q: (fx(q[0]), fy(q[1])))


def _mirror(s: Spec, labels: list[RoomLabel]) -> list[RoomLabel]:
    span = max(_offsets(s, "vertical"))
    labels = _remap(s, labels, lambda q: (span - q[0], q[1]))
    for o in s.openings:
        o.swing = {"left": "right", "right": "left"}.get(o.swing)
    vertical = sorted((a for a in s.grid.axes if a.orientation == "vertical"), key=lambda a: a.offset)
    names = [a.label for a in vertical]
    for a in vertical:
        a.offset = span - a.offset
    for a, name in zip(sorted(vertical, key=lambda a: a.offset), names):
        a.label, a.id = name, f"G{name}"  # A stays the leftmost axis, at offset 0
    for w in s.walls:
        w.grid_ref = []
    for c in s.columns:
        c.grid_ref = None
    return labels


def _drop_partitions(s: Spec, n: int, rng: np.random.Generator) -> None:
    hosts = {o.wall_id for o in s.openings}
    free = [w.id for w in s.walls if w.kind in ("partition", "interior") and w.id not in hosts]
    gone = set(rng.choice(free, size=min(n, len(free)), replace=False).tolist()) if n and free else set()
    s.walls = [w for w in s.walls if w.id not in gone]


def _door_segments(s: Spec) -> list:
    walls = {w.id: w for w in s.walls}
    out = []
    for o in s.openings:
        w = walls[o.wall_id]
        length = _length(w) or 1
        ux, uy = (w.b[0] - w.a[0]) / length, (w.b[1] - w.a[1]) / length
        out.append(LineString([(w.a[0] + ux * o.offset, w.a[1] + uy * o.offset),
                               (w.a[0] + ux * (o.offset + o.width), w.a[1] + uy * (o.offset + o.width))])
                   .buffer(w.thickness / 2))
    return out


def _split_line(s: Spec, poly: Polygon) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """A wall across the room's short side through its centre, each end reaching its host wall's centreline."""
    x0, y0, x1, y1 = poly.bounds
    c = poly.centroid if poly.contains(poly.centroid) else poly.representative_point()
    line = (LineString([(c.x, y0 - 1), (c.x, y1 + 1)]) if x1 - x0 >= y1 - y0
            else LineString([(x0 - 1, c.y), (x1 + 1, c.y)]))
    cut = line.intersection(poly)
    parts = list(getattr(cut, "geoms", [cut]))
    piece = min((g for g in parts if isinstance(g, LineString) and g.length), key=lambda g: g.distance(c), default=None)
    if piece is None or piece.length < 1000:
        return None
    (ax, ay), (bx, by) = piece.coords[0], piece.coords[-1]
    ux, uy = (bx - ax) / piece.length, (by - ay) / piece.length
    ends = []
    for (px, py), sign in (((ax, ay), -1), ((bx, by), 1)):
        host = min(s.walls, key=lambda w: LineString([w.a, w.b]).distance(Point(px, py)))
        reach = LineString([host.a, host.b]).distance(Point(px, py))  # the room edge is the host's face
        ends.append((round(px + sign * ux * reach), round(py + sign * uy * reach)))
    return ends[0], ends[1]


def _add_partitions(s: Spec, labels: list[RoomLabel], n: int, rng: np.random.Generator) -> Spec:
    for _ in range(n):
        s = rebuild_rooms(s.model_copy(update={"rooms": []}), labels)
        stairs = [LineString([f.start, f.end]).buffer(f.width / 2) for st in s.stairs for f in st.flights]
        blocked = _door_segments(s) + [column_footprint(c) for c in s.columns] + stairs
        before = len(s.rooms)
        for i in rng.permutation(len(s.rooms)):
            r = s.rooms[int(i)]
            poly = Polygon(r.polygon)
            if r.holes or poly.area < MIN_SPLIT_ROOM_MM2 or any(poly.intersects(b) for b in stairs):
                continue
            ends = _split_line(s, poly)
            if ends is None or any(LineString(ends).intersects(b) for b in blocked):
                continue
            w = Wall(id=take_id(s, "W"), a=ends[0], b=ends[1], thickness=NEW_WALL_MM, kind="partition")
            trial = s.model_copy(deep=True)
            trial.walls.append(w)
            if not (endpoint_connected(trial, w, "a") and endpoint_connected(trial, w, "b")):
                continue
            if len(rebuild_rooms(trial.model_copy(update={"rooms": []}), labels).rooms) == before + 1:
                s = trial
                break
    return s


def _door_types(s: Spec, n: int, rng: np.random.Generator) -> None:
    doors = [o for o in s.openings if o.category == "door" and o.door_type in SWING_TYPES]
    for i in rng.permutation(len(doors))[:n]:
        o = doors[int(i)]
        # a type the width allows: swing leaves of 500-1300 mm (PRD/04 §3.4)
        fits = [t for t, ok in (("single_swing", o.width <= LEAF_MAX_MM), ("double_swing", o.width / 2 >= LEAF_MIN_MM),
                                ("sliding", True)) if ok]
        o.door_type = str(rng.choice(fits))
        if o.door_type == "double_swing":
            o.hinge, o.swing = "both", o.swing or "left"
        elif o.door_type == "single_swing":
            o.hinge, o.swing = str(rng.choice(["start", "end"])), o.swing or "left"
        else:
            o.hinge, o.swing = None, None


def _stair_in_walls(s: Spec) -> float:
    walls = unary_union([wall_footprint(w, s) for w in s.walls])
    flights = unary_union([LineString([f.start, f.end]).buffer(f.width / 2, cap_style="flat")
                           for st in s.stairs for f in st.flights])
    return flights.intersection(walls).area


def _shift_stairs_clear(s: Spec, dx: int, dy: int) -> tuple[int, int]:
    """The largest of the shift, half of it, a quarter of it, or none, that does not push treads further into walls."""
    before = _stair_in_walls(s)
    for k in (1, 0.5, 0.25):
        step = (round(dx * k / 50) * 50, round(dy * k / 50) * 50)
        trial = s.model_copy(deep=True)
        _shift_stairs(trial, *step)
        if _stair_in_walls(trial) <= before + 1:
            _shift_stairs(s, *step)
            return step
    return 0, 0


def _shift_stairs(s: Spec, dx: int, dy: int) -> None:
    for st in s.stairs:
        for f in st.flights:
            f.start, f.end = (f.start[0] + dx, f.start[1] + dy), (f.end[0] + dx, f.end[1] + dy)
        st.landings = [[(q[0] + dx, q[1] + dy) for q in ring] for ring in st.landings]


def perturb(base: Spec, seed: int, ops: dict | None = None) -> tuple[Spec, dict]:
    ops = ops or draw_ops(base, np.random.default_rng(seed))
    rng = np.random.default_rng(seed)  # the same choices whether the ops were passed in or drawn here
    s = base.model_copy(deep=True)
    labels = [RoomLabel(at=tuple(r.label_pos), name=r.name, type=r.type) for r in s.rooms if r.label_pos]
    if ops["bays"] != _bays(base):
        labels = _apply_bays(s, labels, ops["bays"])
    if ops["mirror"]:
        labels = _mirror(s, labels)
    _drop_partitions(s, ops["drop_partitions"], rng)
    shifted = _shift_stairs_clear(s, *ops["stair_shift"])  # before partitions, which must not cross the stair
    s.meta.id_seq["R"] = 0
    s = _add_partitions(s, labels, ops["add_partitions"], rng)
    _door_types(s, ops["door_types"], rng)
    s.meta.id_seq["R"] = 0
    added = sum(w.id not in {b.id for b in base.walls} for w in s.walls)  # a room may have had no clean split
    return (rebuild_rooms(s.model_copy(update={"rooms": []}), labels),
            ops | {"added_partitions": added, "stair_shifted": shifted})
