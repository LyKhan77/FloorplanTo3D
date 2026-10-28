"""CAD-style raster of a spec (M7b), after floorplan/plan.jpeg: double-line walls with gaps at openings, door leaves
and swings, columns, stair treads, magenta grid bubbles, cyan dimension chains, room labels, and random MEP notes and
filled panels. The spec comes back with the scale the picture was drawn at, so it is the variant's GT.
"""

import itertools
import math

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from core.spec.derive import column_footprint, wall_footprint
from core.spec.models import Spec

BLACK, MAGENTA, CYAN = (0, 0, 0), (255, 0, 255), (255, 255, 0)  # BGR
LEFT, TOP, RIGHT, BOTTOM = 260, 80, 120, 300  # page margins (px): bubbles and dimension chains sit left and below
BUBBLE_R, LABEL_PX, DIM_PX, ROOM_PX, NOTE_PX = 20, 22, 14, 16, 11
NOTES = ["ROUTE CABLE", "PANEL I/O UPS A", "TO NEW SDP", "NYY 4x1Cx95mm", "NYY 6x1Cx240mm", "PROPOSED",
         "NEW PANEL SDP", "GROUNDING CABLE ROUTE", "BCB TO PANEL UPS", "EXISTING TO NEW PANEL"]


class _Page:
    def __init__(self, spec: Spec, s: float):
        pts = [p for w in spec.walls for p in (w.a, w.b)] + [c.center for c in spec.columns]
        self.x0, self.y1 = min(p[0] for p in pts) - 500, max(p[1] for p in pts) + 500
        x1, y0 = max(p[0] for p in pts) + 500, min(p[1] for p in pts) - 500
        self.s = s
        self.w = int(LEFT + (x1 - self.x0) / s + RIGHT)
        self.h = int(TOP + (self.y1 - y0) / s + BOTTOM)
        self.texts: list[tuple] = []  # (text, x, y, size, vertical) centred at (x, y)

    def px(self, p) -> tuple[float, float]:
        return LEFT + (p[0] - self.x0) / self.s, TOP + (self.y1 - p[1]) / self.s

    def ipx(self, p) -> tuple[int, int]:
        x, y = self.px(p)
        return round(x), round(y)

    def px_to_mm(self) -> list[float]:
        s = self.s
        return [s, 0.0, self.x0 - s * LEFT, 0.0, -s, self.y1 + s * TOP]


def _ring(img, page: _Page, coords, colour=BLACK, t=1):
    cv2.polylines(img, [np.array([page.ipx(p) for p in coords], np.int32)], True, colour, t, cv2.LINE_AA)


def _line(img, page: _Page, a, b, colour=BLACK, t=1):
    cv2.line(img, page.ipx(a), page.ipx(b), colour, t, cv2.LINE_AA)


def _unit(a, b):
    n = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    return (b[0] - a[0]) / n, (b[1] - a[1]) / n


def _walls(img, page: _Page, spec: Spec) -> None:
    walls = {w.id: w for w in spec.walls}
    cuts = []
    for o in spec.openings:
        w = walls[o.wall_id]
        ux, uy = _unit(w.a, w.b)
        seg = LineString([(w.a[0] + ux * o.offset, w.a[1] + uy * o.offset),
                          (w.a[0] + ux * (o.offset + o.width), w.a[1] + uy * (o.offset + o.width))])
        cuts.append(seg.buffer(w.thickness / 2 + page.s, cap_style="flat"))
    body = unary_union([wall_footprint(w, spec) for w in spec.walls]).difference(unary_union(cuts))
    for poly in getattr(body, "geoms", [body]):
        if isinstance(poly, Polygon) and not poly.is_empty:
            for ring in [poly.exterior, *poly.interiors]:
                _ring(img, page, ring.coords)
    for c in spec.columns:
        _ring(img, page, column_footprint(c).exterior.coords)


def _arc(img, page: _Page, hinge, toward, normal, r, steps=24):
    pts = [(hinge[0] + r * (math.cos(t) * toward[0] + math.sin(t) * normal[0]),
            hinge[1] + r * (math.cos(t) * toward[1] + math.sin(t) * normal[1])) for t in np.linspace(0, math.pi / 2, steps)]
    cv2.polylines(img, [np.array([page.ipx(p) for p in pts], np.int32)], False, BLACK, 1, cv2.LINE_AA)


def _openings(img, page: _Page, spec: Spec) -> None:
    walls = {w.id: w for w in spec.walls}
    for o in spec.openings:
        w = walls[o.wall_id]
        u = _unit(w.a, w.b)
        side = 1 if o.swing != "right" else -1
        n = (-u[1] * side, u[0] * side)
        j0 = (w.a[0] + u[0] * o.offset, w.a[1] + u[1] * o.offset)
        j1 = (w.a[0] + u[0] * (o.offset + o.width), w.a[1] + u[1] * (o.offset + o.width))
        back = (-u[0], -u[1])
        if o.category == "window":
            for k in (-1, 0, 1):
                d = k * w.thickness / 3
                _line(img, page, (j0[0] - u[1] * d, j0[1] + u[0] * d), (j1[0] - u[1] * d, j1[1] + u[0] * d))
        elif o.door_type == "double_swing":
            for hinge, toward in ((j0, u), (j1, back)):
                _line(img, page, hinge, (hinge[0] + n[0] * o.width / 2, hinge[1] + n[1] * o.width / 2))
                _arc(img, page, hinge, toward, n, o.width / 2)
        elif o.door_type == "single_swing":
            hinge, toward = (j1, back) if o.hinge == "end" else (j0, u)
            _line(img, page, hinge, (hinge[0] + n[0] * o.width, hinge[1] + n[1] * o.width))
            _arc(img, page, hinge, toward, n, o.width)
        elif o.door_type == "sliding":
            for k, (p, q) in ((-1, (j0, (j0[0] + u[0] * o.width * 0.55, j0[1] + u[1] * o.width * 0.55))),
                              (1, ((j1[0] - u[0] * o.width * 0.55, j1[1] - u[1] * o.width * 0.55), j1))):
                d = k * w.thickness / 4
                _line(img, page, (p[0] - u[1] * d, p[1] + u[0] * d), (q[0] - u[1] * d, q[1] + u[0] * d), t=2)


def _stairs(img, page: _Page, spec: Spec) -> None:
    for st in spec.stairs:
        for ring in st.landings:
            _ring(img, page, ring)
        for f in st.flights:
            d = _unit(f.start, f.end)
            p = (-d[1] * f.width / 2, d[0] * f.width / 2)
            length = math.hypot(f.end[0] - f.start[0], f.end[1] - f.start[1])
            for i in range(f.risers + 1):
                c = (f.start[0] + d[0] * length * i / f.risers, f.start[1] + d[1] * length * i / f.risers)
                _line(img, page, (c[0] - p[0], c[1] - p[1]), (c[0] + p[0], c[1] + p[1]))
            for k in (-1, 1):
                _line(img, page, (f.start[0] + k * p[0], f.start[1] + k * p[1]), (f.end[0] + k * p[0], f.end[1] + k * p[1]))
            cv2.arrowedLine(img, page.ipx(f.start), page.ipx(f.end), BLACK, 1, cv2.LINE_AA, tipLength=0.08)


def _grid(img, page: _Page, spec: Spec) -> None:
    vertical = sorted((a for a in spec.grid.axes if a.orientation == "vertical"), key=lambda a: a.offset)
    horizontal = sorted((a for a in spec.grid.axes if a.orientation == "horizontal"), key=lambda a: a.offset)
    bottom = page.h - BOTTOM + 40  # just under the drawing's lowest margin
    left = LEFT - 40
    # vertical axes: bubbles below, bay chain and total above them
    xs = [page.px((a.offset, 0))[0] for a in vertical]
    by, chain, total = bottom + 170, bottom + 90, bottom + 55
    for a, x in zip(vertical, xs):
        cv2.line(img, (round(x), round(page.px((0, min(a2.offset for a2 in horizontal)))[1])), (round(x), by - BUBBLE_R),
                 MAGENTA, 1, cv2.LINE_AA)
        cv2.circle(img, (round(x), by), BUBBLE_R, MAGENTA, 2, cv2.LINE_AA)
        page.texts.append((a.label, x, by, LABEL_PX, False))
    _chain(img, page, xs, [b.offset - a.offset for a, b in itertools.pairwise(vertical)], chain, total, False)
    # horizontal axes: bubbles left, chains between bubbles and the drawing
    ys = [page.px((0, a.offset))[1] for a in horizontal]
    bx, chain, total = left - 170, left - 90, left - 55
    for a, y in zip(horizontal, ys):
        cv2.line(img, (bx + BUBBLE_R, round(y)), (round(page.px((min(v.offset for v in vertical), 0))[0]), round(y)),
                 MAGENTA, 1, cv2.LINE_AA)
        cv2.circle(img, (bx, round(y)), BUBBLE_R, MAGENTA, 2, cv2.LINE_AA)
        page.texts.append((a.label, bx, y, LABEL_PX, False))
    _chain(img, page, ys, [b.offset - a.offset for a, b in itertools.pairwise(horizontal)], chain, total, True)


def _chain(img, page: _Page, at: list[float], spans: list[int], chain: float, total: float, vertical: bool) -> None:
    """Dimension chain across the axes at px positions `at`: one text per bay, plus the total on its own line."""
    pt = (lambda along, across: (round(across), round(along))) if vertical else (lambda along, across: (round(along), round(across)))
    for line_at, ends in ((chain, at), (total, [at[0], at[-1]])):
        cv2.line(img, pt(min(ends), line_at), pt(max(ends), line_at), CYAN, 1, cv2.LINE_AA)
        for e in ends:
            cv2.line(img, pt(e - 5, line_at + 5), pt(e + 5, line_at - 5), CYAN, 2, cv2.LINE_AA)
    order = sorted(range(len(at)), key=lambda i: at[i])
    for (i, j), mm in zip(itertools.pairwise(order), spans if not vertical else spans[::-1]):
        a, b = at[i], at[j]
        page.texts.append((str(abs(mm)), (a + b) / 2 if not vertical else chain - 12, chain - 12 if not vertical else (a + b) / 2,
                           DIM_PX, vertical))
    page.texts.append((str(sum(abs(m) for m in spans)), (at[0] + at[-1]) / 2 if not vertical else total - 12,
                       total - 12 if not vertical else (at[0] + at[-1]) / 2, DIM_PX, vertical))


def _clutter(img, page: _Page, spec: Spec, rng: np.random.Generator) -> None:
    rooms = [r for r in spec.rooms if Polygon(r.polygon).area > 4e6]
    if not rooms:
        return
    for _ in range(int(rng.integers(2, 6))):  # filled panels, 600 x 300 mm
        p = Polygon(rooms[int(rng.integers(len(rooms)))].polygon).representative_point()
        a, b = page.ipx((p.x - 300, p.y + 150)), page.ipx((p.x + 300, p.y - 150))
        cv2.rectangle(img, a, b, BLACK, -1)
    for _ in range(int(rng.integers(3, 9))):  # MEP notes with a leader into a room
        target = Polygon(rooms[int(rng.integers(len(rooms)))].polygon).representative_point()
        tx, ty = page.px((target.x, target.y))
        x, y = tx + float(rng.uniform(-160, 160)), ty + float(rng.uniform(-120, 120))
        lines = [str(t) for t in rng.choice(NOTES, size=int(rng.integers(1, 4)), replace=False)]
        for k, t in enumerate(lines):
            page.texts.append((t, x, y + k * (NOTE_PX + 3), NOTE_PX, False))
        cv2.line(img, (round(x - 50), round(y - NOTE_PX)), (round(tx), round(ty)), BLACK, 1, cv2.LINE_AA)


def _text(img: np.ndarray, texts: list[tuple]) -> np.ndarray:
    canvas = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(canvas)
    for text, x, y, size, vertical in texts:
        font = ImageFont.load_default(size=size)
        if not vertical:
            draw.text((x, y), text, fill=(0, 0, 0), font=font, anchor="mm")
            continue
        box = font.getbbox(text)
        tile = Image.new("L", (box[2] - box[0] + 4, box[3] - box[1] + 4), 0)
        ImageDraw.Draw(tile).text((2 - box[0], 2 - box[1]), text, fill=255, font=font)
        tile = tile.rotate(90, expand=True)  # reads bottom to top, as dimension text on the Y chain
        canvas.paste((0, 0, 0), (round(x - tile.width / 2), round(y - tile.height / 2)), tile)
    return cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR)


def render(spec: Spec, seed: int, mm_per_px: float = 25.0) -> tuple[np.ndarray, Spec]:
    """(BGR image, the spec with the scale and px_to_mm it was drawn at)."""
    rng = np.random.default_rng(seed)
    page = _Page(spec, mm_per_px)
    img = np.full((page.h, page.w, 3), 255, np.uint8)
    _walls(img, page, spec)
    _openings(img, page, spec)
    _stairs(img, page, spec)
    _grid(img, page, spec)
    _clutter(img, page, spec, rng)
    for r in spec.rooms:
        if r.name and r.label_pos:
            page.texts.append((r.name, *page.px(r.label_pos), ROOM_PX, False))
    img = _text(img, page.texts)
    out = spec.model_copy(deep=True)
    out.meta.mm_per_px = mm_per_px
    out.meta.px_to_mm = page.px_to_mm()
    return img, out
