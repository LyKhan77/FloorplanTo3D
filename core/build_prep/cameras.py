"""Cameras for verification and document renders (PRD/06 §6 step 1, §7.1)."""

import math

from shapely.geometry import Polygon as SPolygon
from shapely.ops import unary_union

from core.build_prep.schema import CameraItem
from core.spec.models import Spec

DOC_RES = [1600, 1000]
ROOM_RES = [1280, 800]
HIGH = 50_000  # camera height for top views (mm)
ISO_ELEVATION = 35
ISO_DISTANCE = 100_000
# camera yaw so the view looks from that corner towards the building centre (forward = (-sin yaw, cos yaw))
ISO_YAW = {"ne": 135, "nw": 225, "se": 45, "sw": 315}


def px_to_mm_axis_aligned(spec: Spec) -> bool:
    _, b, _, d, _, _ = spec.meta.px_to_mm
    return abs(b) < 1e-6 and abs(d) < 1e-6


def _bbox(spec: Spec) -> tuple[float, float, float, float]:
    shapes = [SPolygon(o) for o in spec.meta.building_outline] or [SPolygon(r.polygon) for r in spec.rooms]
    if not shapes:
        pts = [p for w in spec.walls for p in (w.a, w.b)] or [(0, 0), (1, 1)]
        xs, ys = zip(*pts)
        return min(xs), min(ys), max(xs), max(ys)
    return unary_union(shapes).bounds


def _cam(name, kind, location, rotation, output, mode, resolution, ortho_scale=None, fov=None, cutaway=None) -> CameraItem:
    return {"name": name, "kind": kind, "location": location, "rotation_deg": rotation, "ortho_scale": ortho_scale,
            "fov_deg": fov, "resolution": resolution, "output": output, "mode": mode, "cutaway_mm": cutaway}


def cameras(spec: Spec, image_size: tuple[int, int] | None) -> list[CameraItem]:
    out: list[CameraItem] = []
    if image_size and px_to_mm_axis_aligned(spec):
        a, _, c, _, e, f = spec.meta.px_to_mm
        w, h = image_size
        cx, cy = a * w / 2 + c, e * h / 2 + f
        out.append(_cam("cam_verify", "ORTHO", [cx, cy, HIGH], [0, 0, 0], "verify_top.png", "verify", [w, h],
                        ortho_scale=max(w * abs(a), h * abs(e))))

    x0, y0, x1, y1 = _bbox(spec)
    bw, bh = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    aspect = DOC_RES[0] / DOC_RES[1]
    out.append(_cam("cam_top", "ORTHO", [cx, cy, HIGH], [0, 0, 0], "renders/top.png", "doc", DOC_RES,
                    ortho_scale=max(bw, bh * aspect) * 1.05))
    diag = math.hypot(bw, bh)
    for corner, yaw in ISO_YAW.items():
        el, yr = math.radians(ISO_ELEVATION), math.radians(yaw)
        forward = (-math.sin(yr) * math.cos(el), math.cos(yr) * math.cos(el), -math.sin(el))
        loc = [cx - forward[0] * ISO_DISTANCE, cy - forward[1] * ISO_DISTANCE, 1500 - forward[2] * ISO_DISTANCE]
        out.append(_cam(f"cam_iso_{corner}", "ORTHO", loc, [90 - ISO_ELEVATION, 0, yaw], f"renders/iso_{corner}.png",
                        "doc", DOC_RES, ortho_scale=diag * 1.1, cutaway=1200))

    for r in spec.rooms:
        if r.area_m2 < 4 or r.type == "outdoor":
            continue
        poly = SPolygon(r.polygon, r.holes)
        p = poly.representative_point()
        ring = list(r.polygon)
        edges = list(zip(ring, ring[1:] + ring[:1]))
        (ax, ay), (bx, by) = max(edges, key=lambda e: math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]))
        dx, dy = (ax + bx) / 2 - p.x, (ay + by) / 2 - p.y
        yaw = math.degrees(math.atan2(dy, dx)) - 90
        out.append(_cam(f"cam_room_{r.id}", "PERSP", [p.x, p.y, 1600], [90, 0, yaw], f"renders/room_{r.id}.png",
                        "doc", ROOM_RES, fov=75))
    return out
