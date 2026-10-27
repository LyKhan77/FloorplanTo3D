"""What Strata sees for one element (PRD/05 §3.1-3.2): a 768x768 zoom crop with the element in magenta, a
384x384 context thumbnail with the crop position in red, and the element's numeric features as text."""

import math

import cv2
import numpy as np
from shapely.geometry import LineString, Point, Polygon

from core.spec.derive import _host_walls, wall_footprint
from core.spec.models import Opening, Spec, Wall

CROP_PX = 768
THUMB_PX = 384
MIN_MM, MAX_MM, CROP_FACTOR = 2000, 8000, 1.6
MAGENTA, GREY, RED = (255, 0, 255), (150, 150, 150), (0, 0, 255)
ORTHO_TOL_DEG = 1.5
HATCH_STEP_MM, HATCH_YES = 50, 0.30
TEXT_NEAR_MM = 600


def _find(spec: Spec, eid: str):
    return next(x for x in [*spec.walls, *spec.openings, *spec.rooms] if x.id == eid)


def _door_span(spec: Spec, o: Opening) -> tuple[tuple[float, float], tuple[float, float], Wall]:
    w = next(w for w in spec.walls if w.id == o.wall_id)
    line = LineString([w.a, w.b])
    p, q = line.interpolate(o.offset), line.interpolate(o.offset + o.width)
    return (p.x, p.y), (q.x, q.y), w


def _centre_and_length(spec: Spec, eid: str) -> tuple[tuple[float, float], float]:
    el = _find(spec, eid)
    if isinstance(el, Wall):
        a, b = el.a, el.b
    elif isinstance(el, Opening):
        a, b, _ = _door_span(spec, el)
    else:
        c = Point(el.label_pos) if el.label_pos else Polygon(el.polygon).centroid
        return (c.x, c.y), math.sqrt(max(el.area_m2, 1.0)) * 1000
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), math.dist(a, b)


def _px_per_mm(to_px) -> float:
    (x0, y0), (x1, y1) = to_px(0, 0), to_px(1000, 0)
    return math.hypot(x1 - x0, y1 - y0) / 1000


def crop_box_px(spec: Spec, eid: str, to_px, zoom: float = 1.0) -> tuple[int, int, int, int]:
    """Square box in page px centred on the element: side = clamp(length x 1.6, 2 m, 8 m) / zoom."""
    (cx, cy), length = _centre_and_length(spec, eid)
    side = round(min(MAX_MM, max(MIN_MM, length * CROP_FACTOR)) / zoom * _px_per_mm(to_px))
    px, py = to_px(cx, cy)
    x0, y0 = round(px - side / 2), round(py - side / 2)
    return x0, y0, x0 + side, y0 + side


def _cut(page_gray: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = box
    h, w = page_gray.shape[:2]
    out = np.full((y1 - y0, x1 - x0), 255, np.uint8)  # off-page parts stay white
    sx0, sy0, sx1, sy1 = max(x0, 0), max(y0, 0), min(x1, w), min(y1, h)
    if sx1 > sx0 and sy1 > sy0:
        out[sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = page_gray[sy0:sy1, sx0:sx1]
    return out


def _target_outline(spec: Spec, eid: str):
    el = _find(spec, eid)
    if isinstance(el, Wall):
        return wall_footprint(el, spec)
    if isinstance(el, Opening):
        a, b, w = _door_span(spec, el)
        return LineString([a, b]).buffer(w.thickness / 2 + 150, cap_style="flat")
    return Polygon(el.polygon, el.holes)


def element_crop(page_gray: np.ndarray, spec: Spec, eid: str, to_px, zoom: float = 1.0) -> np.ndarray:
    box = crop_box_px(spec, eid, to_px, zoom)
    side = box[2] - box[0]
    img = cv2.cvtColor(_cut(page_gray, box), cv2.COLOR_GRAY2BGR)
    img = cv2.resize(img, (CROP_PX, CROP_PX), interpolation=cv2.INTER_AREA if side > CROP_PX else cv2.INTER_CUBIC)
    k = CROP_PX / side

    def pts(coords) -> np.ndarray:
        return np.array([[(to_px(x, y)[0] - box[0]) * k, (to_px(x, y)[1] - box[1]) * k] for x, y in coords],
                        np.int32)

    for w in spec.walls:
        if w.id != eid:
            cv2.polylines(img, [pts([w.a, w.b])], False, GREY, 1, cv2.LINE_AA)
    for o in spec.openings:
        if o.id != eid and any(w.id == o.wall_id for w in spec.walls):
            a, b, _ = _door_span(spec, o)
            cv2.polylines(img, [pts([a, b])], False, GREY, 1, cv2.LINE_AA)
    shape = _target_outline(spec, eid)
    for ring in [shape.exterior, *shape.interiors] if not shape.is_empty else []:
        cv2.polylines(img, [pts(ring.coords)], True, MAGENTA, 3)
    cv2.putText(img, eid, (12, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.6, MAGENTA, 3)
    return img


def context_thumb(page_gray: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    h, w = page_gray.shape[:2]
    k = THUMB_PX / max(h, w)
    small = cv2.resize(cv2.cvtColor(page_gray, cv2.COLOR_GRAY2BGR), (max(1, round(w * k)), max(1, round(h * k))),
                       interpolation=cv2.INTER_AREA)
    out = np.full((THUMB_PX, THUMB_PX, 3), 255, np.uint8)
    out[:small.shape[0], :small.shape[1]] = small
    x0, y0, x1, y1 = (round(v * k) for v in box)
    cv2.rectangle(out, (x0, y0), (x1, y1), RED, 2)
    return out


def _orientation(w: Wall) -> str:
    deg = math.degrees(math.atan2(w.b[1] - w.a[1], w.b[0] - w.a[0])) % 180
    if min(deg, 180 - deg) <= ORTHO_TOL_DEG:
        return "horizontal"
    return "vertical" if abs(deg - 90) <= ORTHO_TOL_DEG else "diagonal"


def _hatch_fraction(w: Wall, hatch: np.ndarray | None, to_px) -> float:
    length = math.dist(w.a, w.b)
    if hatch is None or not length:
        return 0.0
    n = max(1, math.ceil(length / HATCH_STEP_MM))
    h, wd = hatch.shape[:2]
    hits = 0
    for i in range(n):
        t = (i + 0.5) / n
        x, y = to_px(w.a[0] + (w.b[0] - w.a[0]) * t, w.a[1] + (w.b[1] - w.a[1]) * t)
        xi, yi = int(x), int(y)
        hits += 0 <= xi < wd and 0 <= yi < h and hatch[yi, xi] > 0
    return hits / n


def wall_evidence(spec: Spec, wid: str, *, mm_per_px: float, hatch: np.ndarray | None, texts: list[dict],
                  to_px) -> str:
    w = next(x for x in spec.walls if x.id == wid)
    ends = {e: next((o.id for o in _host_walls(spec, w, e)), "none") for e in ("a", "b")}
    frac = _hatch_fraction(w, hatch, to_px)
    line = LineString([w.a, w.b])
    near = sorted((line.distance(Point(t["at_mm"])), t["text"], t["cls"]) for t in texts
                  if line.distance(Point(t["at_mm"])) <= TEXT_NEAR_MM)
    near_s = f'"{near[0][1]}" ({near[0][2]} class)' if near else "none"
    partner = "yes" if (w.provenance.evidence.get("pair_overlap") or 0) > 0 else "no"
    return "\n".join([
        f"Element {w.id}",
        (f"- length: {round(line.length)} mm, thickness: {w.thickness} mm "
         f"(stroke {w.thickness / mm_per_px:.1f} px), orientation: {_orientation(w)}"),
        f"- connects to walls at ends: start={ends['a']}, end={ends['b']}",
        f"- passes through dense-hatch area: {'yes' if frac >= HATCH_YES else 'no'} ({round(frac * 100)}% of length)",
        f"- nearest text within {TEXT_NEAR_MM} mm: {near_s}",
        f"- parallel partner line found: {partner}",
        f"- CV confidence: {w.provenance.confidence:.2f}",
    ])


def _image_side(vx: float, vy: float) -> str:
    """Image direction of a vector given in image axes (x right, y down)."""
    if abs(vx) >= abs(vy):
        return "right" if vx > 0 else "left"
    return "bottom" if vy > 0 else "top"


def _door_frame(w: Wall) -> str:
    """hinge/swing (PRD/03: relative to a->b, swing seen from a facing b) in image terms; spec y is up."""
    dx, dy = w.b[0] - w.a[0], -(w.b[1] - w.a[1])
    start, end = _image_side(-dx, -dy), _image_side(dx, dy)
    left, right = _image_side(dy, -dx), _image_side(-dy, dx)
    return (f'- in the image the host wall runs from its start ({start}) to its end ({end}): hinge "start" = the '
            f'{start} end of the opening, "end" = the {end} end; swing "left" = the leaf opens towards the {left}, '
            f'"right" = towards the {right}')


def door_evidence(spec: Spec, did: str) -> str:
    o = next(x for x in spec.openings if x.id == did)
    w = next((x for x in spec.walls if x.id == o.wall_id), None)
    ev = o.provenance.evidence
    yn = lambda k: "yes" if ev.get(k) else "no"
    return "\n".join([
        f"Element {o.id}",
        f"- host wall: {o.wall_id} (thickness {w.thickness if w else '?'} mm, {_orientation(w) if w else '?'})",
        f"- width: {o.width} mm, offset from wall start: {o.offset} mm",
        f"- current door_type: {o.door_type}, hinge: {o.hinge}, swing: {o.swing}",
        *([_door_frame(w)] if w else []),
        f"- swing arc found: {yn('arc')}, gap in wall found: {yn('gap')}",
        f"- CV confidence: {o.provenance.confidence:.2f}",
    ])


def room_evidence(spec: Spec, rid: str, label_text: str) -> str:
    r = next(x for x in spec.rooms if x.id == rid)
    return "\n".join([
        f"Element {r.id}",
        f'- OCR label: "{label_text}"',
        f"- area: {r.area_m2:.1f} m2",
        f"- current type: {r.type}",
        f"- current name: {r.name or '(none)'}",
    ])
