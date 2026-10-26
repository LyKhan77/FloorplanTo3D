"""Deterministic IDs for an extracted spec, and carry-over against HEAD on re-extraction (PRD/04 Tahap 5 §4, §4b)."""

import math

from shapely.geometry import Polygon as SPolygon

from core.spec.derive import derive
from core.spec.ids import seed_id_seq, take_id
from core.spec.models import Spec, Wall
from core.spec.rooms import RoomLabel, rebuild_rooms

WALL_DIST_MM = 200
WALL_ANGLE_DEG = 3
WALL_OVERLAP = 0.5
POINT_MATCH_MM = 300
EDITED_SOURCES = ("editor", "manual", "llm")


def _door_centre(spec: Spec, o) -> tuple[float, float] | None:
    w = next((w for w in spec.walls if w.id == o.wall_id), None)
    if w is None:
        return None
    length = math.dist(w.a, w.b) or 1.0
    t = (o.offset + o.width / 2) / length
    return (w.a[0] + (w.b[0] - w.a[0]) * t, w.a[1] + (w.b[1] - w.a[1]) * t)


def _renamed(spec: Spec, walls: dict[str, str], openings: dict[str, str], columns: dict[str, str],
             stairs: dict[str, str], rooms: dict[str, str]) -> Spec:
    s = spec.model_copy(deep=True)
    for w in s.walls:
        w.id = walls[w.id]
    for o in s.openings:
        o.id, o.wall_id = openings[o.id], walls[o.wall_id]
    for c in s.columns:
        c.id = columns[c.id]
    for st in s.stairs:
        st.id = stairs[st.id]
        st.room_id = rooms.get(st.room_id) if st.room_id else None
    for r in s.rooms:
        r.id = rooms[r.id]
        r.bounding_walls = [walls[w] for w in r.bounding_walls if w in walls]
        r.doors = [openings[d] for d in r.doors if d in openings]
    for ob in s.objects:
        ob.room_id = rooms.get(ob.room_id) if ob.room_id else None
    return s


def assign_ids(spec: Spec) -> Spec:
    """Positional IDs: walls by (y, x) of a, columns by centre, openings by (host wall, offset), stairs by the
    first flight's start, rooms by centroid (north first, as rebuild_rooms numbers new rooms)."""
    walls = sorted(spec.walls, key=lambda w: (w.a[1], w.a[0], w.b[1], w.b[0]))
    wmap = {w.id: f"W{i + 1}" for i, w in enumerate(walls)}
    order = {w.id: i for i, w in enumerate(walls)}
    omap, n = {}, {"D": 0, "N": 0}
    for o in sorted(spec.openings, key=lambda o: (order[o.wall_id], o.offset)):
        p = "D" if o.category == "door" else "N"
        n[p] += 1
        omap[o.id] = f"{p}{n[p]}"
    cmap = {c.id: f"C{i + 1}" for i, c in enumerate(sorted(spec.columns, key=lambda c: (c.center[1], c.center[0])))}
    smap = {st.id: f"S{i + 1}" for i, st in
            enumerate(sorted(spec.stairs, key=lambda st: (st.flights[0].start[1], st.flights[0].start[0])))}
    centroid = lambda r: SPolygon(r.polygon).centroid
    rmap = {r.id: f"R{i + 1}" for i, r in
            enumerate(sorted(spec.rooms, key=lambda r: (-centroid(r).y, centroid(r).x)))}
    s = _renamed(spec, wmap, omap, cmap, smap, rmap)
    s.walls.sort(key=lambda w: int(w.id[1:]))
    s.openings.sort(key=lambda o: (o.id[0], int(o.id[1:])))
    s.columns.sort(key=lambda c: int(c.id[1:]))
    s.stairs.sort(key=lambda st: int(st.id[1:]))
    s.rooms.sort(key=lambda r: int(r.id[1:]))
    s.meta.id_seq = {}
    seed_id_seq(s)
    return s


def _wall_match(new: Wall, old: Wall) -> float | None:
    """Max distance of the new wall's ends to the old wall's line, if the walls are parallel (<= 3°) and overlap
    >= 50% of the shorter one; else None."""
    lo, ln = math.dist(old.a, old.b), math.dist(new.a, new.b)
    if not lo or not ln:
        return None
    ux, uy = (old.b[0] - old.a[0]) / lo, (old.b[1] - old.a[1]) / lo
    vx, vy = (new.b[0] - new.a[0]) / ln, (new.b[1] - new.a[1]) / ln
    if abs(ux * vy - uy * vx) > math.sin(math.radians(WALL_ANGLE_DEG)):
        return None
    dist = max(abs((p[0] - old.a[0]) * uy - (p[1] - old.a[1]) * ux) for p in (new.a, new.b))
    if dist > WALL_DIST_MM:
        return None
    ts = sorted((p[0] - old.a[0]) * ux + (p[1] - old.a[1]) * uy for p in (new.a, new.b))
    if min(lo, ts[1]) - max(0.0, ts[0]) < WALL_OVERLAP * min(lo, ln):
        return None
    return dist


def _greedy(pairs: list[tuple[float, str, str]]) -> dict[str, str]:
    """new id -> old id, closest first, each element used once."""
    out, used = {}, set()
    for _, old, new in sorted(pairs):
        if new not in out and old not in used:
            out[new] = old
            used.add(old)
    return out


def _point_pairs(new_pts: dict[str, tuple], old_pts: dict[str, tuple]) -> dict[str, str]:
    return _greedy([(math.dist(p, q), oid, nid) for nid, p in new_pts.items() for oid, q in old_pts.items()
                    if p is not None and q is not None and math.dist(p, q) <= POINT_MATCH_MM])


def carry_over(new: Spec, head: Spec, labels: list[RoomLabel]) -> tuple[Spec, dict]:
    alloc = head.model_copy(deep=True)  # allocates new IDs above everything HEAD ever used
    seed_id_seq(alloc)

    def ids(match: dict[str, str], items, prefix) -> dict[str, str]:
        return {x.id: match.get(x.id) or take_id(alloc, prefix(x) if callable(prefix) else prefix) for x in items}

    wm = _greedy([(d, o.id, w.id) for w in new.walls for o in head.walls if (d := _wall_match(w, o)) is not None])
    wmap = ids(wm, new.walls, "W")
    om = _point_pairs({o.id: _door_centre(new, o) for o in new.openings},
                      {o.id: _door_centre(head, o) for o in head.openings})
    omap = ids(om, new.openings, lambda o: "D" if o.category == "door" else "N")
    cm = _point_pairs({c.id: c.center for c in new.columns}, {c.id: c.center for c in head.columns})
    cmap = ids(cm, new.columns, "C")
    sm = _point_pairs({st.id: st.flights[0].start for st in new.stairs}, {st.id: st.flights[0].start for st in head.stairs})
    smap = ids(sm, new.stairs, "S")

    s = _renamed(new.model_copy(update={"rooms": []}), wmap, omap, cmap, smap, {})
    heights = {w.id: w.height for w in head.walls}
    for w in s.walls:
        if w.id in heights and heights[w.id] is not None:
            w.height = heights[w.id]
    s.meta.defaults = head.meta.defaults.model_copy()
    s.meta.id_seq = dict(alloc.meta.id_seq)
    s.objects = [ob.model_copy() for ob in head.objects]
    s.rooms = [r.model_copy(deep=True) for r in head.rooms]  # rebuild_rooms matches them (IoU >= 0.5 / 90%)
    s = rebuild_rooms(s, labels)
    head_rooms = {r.id: r for r in head.rooms}
    for r in s.rooms:
        old = head_rooms.get(r.id)
        if old and old.provenance.source in EDITED_SOURCES:
            r.name, r.type, r.label_pos, r.provenance = old.name, old.type, old.label_pos, old.provenance
    s = derive(Spec.model_validate(s.model_dump()))

    kept = {"walls": set(wm.values()), "openings": set(om.values()), "columns": set(cm.values()),
            "stairs": set(sm.values()), "rooms": {r.id for r in s.rooms} & set(head_rooms)}
    old_ids = {"walls": [w.id for w in head.walls], "openings": [o.id for o in head.openings],
               "columns": [c.id for c in head.columns], "stairs": [st.id for st in head.stairs],
               "rooms": [r.id for r in head.rooms]}
    new_counts = {"walls": len(new.walls), "openings": len(new.openings), "columns": len(new.columns),
                  "stairs": len(new.stairs), "rooms": len(s.rooms)}
    lost = [{"id": w.id, "field": "height", "value": w.height} for w in head.walls
            if w.height is not None and w.id not in kept["walls"]]
    lost += [{"id": r.id, "field": "name", "value": r.name} for r in head.rooms
             if r.provenance.source in EDITED_SOURCES and r.id not in kept["rooms"]]
    report = {"matched": {k: len(v) for k, v in kept.items()},
              "new": {k: new_counts[k] - len(kept[k]) for k in kept},
              "removed": {k: [i for i in old_ids[k] if i not in kept[k]] for k in kept},
              "lost_edits": lost}
    return s, report
