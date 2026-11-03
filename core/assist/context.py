"""What the LLM sees of a marked area (design §6.1): the elements in it, the user's selection, a labelled crop."""

import math
from dataclasses import dataclass

import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry import box as sbox

from core.extraction.rooms.overlay import px_from_mm
from core.spec.models import Spec

MARGIN = 0.15
IMAGE_PX = 900
COLOURS = [(0, 0, 230), (230, 80, 0), (0, 150, 0), (200, 0, 200)]  # BGR, alternating so neighbours differ


@dataclass
class AreaContext:
    box: tuple[float, float, float, float]  # mm: x0, y0, x1, y1
    wall_ids: list[str]
    opening_ids: list[str]
    room_ids: list[str]
    stair_ids: list[str]
    selection: list[str]
    text: str
    image: np.ndarray | None


def rep_point(room) -> tuple[int, int]:
    if room.label_pos:
        return room.label_pos
    p = Polygon(room.polygon, room.holes).representative_point()
    return (round(p.x), round(p.y))


def area_context(spec: Spec, box, selection: list[str], page: np.ndarray | None,
                 px_to_mm: list[float] | None, library: dict | None = None,
                 drawn: list[dict] | None = None) -> AreaContext:
    x0, y0, x1, y1 = min(box[0], box[2]), min(box[1], box[3]), max(box[0], box[2]), max(box[1], box[3])
    area = sbox(x0, y0, x1, y1)
    selection = list(selection)
    walls = [w for w in spec.walls if w.id in selection or LineString([w.a, w.b]).intersects(area)]
    wall_ids = {w.id for w in walls}
    openings = [o for o in spec.openings if o.wall_id in wall_ids]
    rooms = [r for r in spec.rooms if Polygon(r.polygon, r.holes).intersects(area)]
    stairs = [s for s in spec.stairs if any(LineString([f.start, f.end]).intersects(area) for f in s.flights)]
    columns = [c for c in spec.columns if area.covers(Point(c.center))]

    lines = [f"Area (mm): x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f} (+X east, +Y north)."]
    if selection:
        lines.append(f"Elemen yang dimaksud user, terpilih: {', '.join(selection)}")
    else:
        lines.append("Tidak ada elemen terpilih (no element is selected).")
    lines.append("Walls (id, a, b, thickness mm, length mm, kind):")
    for w in walls:
        length = math.dist(w.a, w.b)
        lines.append(f"- {w.id} a={list(w.a)} b={list(w.b)} t={w.thickness:.0f} len={length:.0f} {w.kind}")
        for o in (o for o in openings if o.wall_id == w.id):
            lines.append(f"  - {o.id} {o.category} offset={o.offset:.0f} width={o.width:.0f}"
                         + (f" {o.door_type}" if o.door_type else ""))
    lines.append("Rooms (id, name, type, area m2, point inside):")
    lines += [f"- {r.id} '{r.name}' {r.type} {r.area_m2:.1f} at={list(rep_point(r))}" for r in rooms]
    if stairs:
        lines.append("Stairs (id, flights start->end, width, risers):")
        lines += [f"- {st.id} " + "; ".join(f"{list(f.start)}->{list(f.end)} w={f.width:.0f} r={f.risers}"
                                            for f in st.flights) for st in stairs]
    if columns:
        lines.append("Columns (context only): " + ", ".join(f"{c.id} at={list(c.center)}" for c in columns))
    if drawn:
        lines.append("Drawn boxes the user pointed at (id, centre, size short x long mm, long side along):")
        lines += [f"- {b['id']} at={[round(v) for v in b['center']]} {round(b['size'][0])}x{round(b['size'][1])} "
                  f"{'y' if b['rotation'] == 0 else 'x'}" for b in drawn]
    if library:
        lines.append("Template library (id, category, w x d x h mm), the only templates you may use:")
        lines += [f"- {t.id} {t.category} {t.w:.0f}x{t.d:.0f}x{t.h:.0f}" for t in library.values()]

    image = None
    if page is not None and px_to_mm is not None:
        image = _crop(page, px_to_mm, (x0, y0, x1, y1), walls, set(selection), drawn or [])
    return AreaContext(box=(x0, y0, x1, y1), wall_ids=[w.id for w in walls], opening_ids=[o.id for o in openings],
                       room_ids=[r.id for r in rooms], stair_ids=[st.id for st in stairs], selection=selection, text="\n".join(lines), image=image)


def _crop(page: np.ndarray, px_to_mm: list[float], box, walls, selected: set[str], drawn=()) -> np.ndarray | None:
    x0, y0, x1, y1 = box
    mx, my = (x1 - x0) * MARGIN, (y1 - y0) * MARGIN
    to_px = px_from_mm(px_to_mm)
    corners = [to_px(x, y) for x in (x0 - mx, x1 + mx) for y in (y0 - my, y1 + my)]
    h, w = page.shape[:2]
    c0 = max(0, int(min(p[0] for p in corners))), max(0, int(min(p[1] for p in corners)))
    c1 = min(w, math.ceil(max(p[0] for p in corners))), min(h, math.ceil(max(p[1] for p in corners)))
    crop = page[c0[1]:c1[1], c0[0]:c1[0]]
    if crop.size == 0:
        return None
    crop = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR) if crop.ndim == 2 else crop.copy()
    scale = IMAGE_PX / max(crop.shape[:2])
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)

    def at(p) -> tuple[int, int]:
        x, y = to_px(*p)
        return round((x - c0[0]) * scale), round((y - c0[1]) * scale)

    for i, wall in enumerate(walls):
        colour = COLOURS[i % len(COLOURS)]
        a, b = at(wall.a), at(wall.b)
        cv2.line(crop, a, b, colour, 4 if wall.id in selected else 2, cv2.LINE_AA)
        mid = ((a[0] + b[0]) // 2 + 4, (a[1] + b[1]) // 2 - 4)
        cv2.putText(crop, wall.id, mid, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(crop, wall.id, mid, cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1, cv2.LINE_AA)
    for b in drawn:  # the boxes the user pointed at, in purple with their K labels
        (cx, cy), (short, long_) = b["center"], b["size"]
        sx, sy = (short, long_) if b["rotation"] == 0 else (long_, short)
        p0, p1 = at((cx - sx / 2, cy + sy / 2)), at((cx + sx / 2, cy - sy / 2))
        cv2.rectangle(crop, p0, p1, (200, 0, 160), 2)
        cv2.putText(crop, b["id"], (p0[0] + 3, p0[1] + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 0, 160), 2, cv2.LINE_AA)
    return crop
