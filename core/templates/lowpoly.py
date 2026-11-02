"""Procedural low-poly models of the template library (data-center equipment), built from boxes and prisms.

Local frame: x across the width, y the depth with the front at +y, z up from the floor; the parts span exactly
[-w/2, w/2] x [-d/2, d/2] x [0, h] so the GLB bbox equals template.json dims (core/templates/validate.py).
"""

import math
from dataclasses import dataclass

from shapely.geometry import Point

from core.build_prep.mesh import MeshData, box, merge, prism

MATERIALS = {
    "frame": {"color": "#2A2D31", "roughness": 0.5, "alpha": 1.0, "metallic": 0.6},
    "panel": {"color": "#4A4F57", "roughness": 0.5, "alpha": 1.0, "metallic": 0.4},
    "light": {"color": "#D5D8DD", "roughness": 0.6, "alpha": 1.0},
    "white": {"color": "#EEF0F3", "roughness": 0.6, "alpha": 1.0},
    "vent": {"color": "#121417", "roughness": 0.8, "alpha": 1.0},
    "screen": {"color": "#1D6FE8", "roughness": 0.2, "alpha": 1.0},
    "led": {"color": "#42BE65", "roughness": 0.3, "alpha": 1.0},
    "blue": {"color": "#4589FF", "roughness": 0.5, "alpha": 1.0},
    "yellow": {"color": "#F1C21B", "roughness": 0.5, "alpha": 1.0},
    "red": {"color": "#DA1E28", "roughness": 0.4, "alpha": 1.0},
    "battery": {"color": "#33373D", "roughness": 0.6, "alpha": 1.0},
    "steel": {"color": "#9AA0A6", "roughness": 0.35, "alpha": 1.0, "metallic": 0.8},
}


@dataclass
class Part:
    material: str
    box: tuple[float, float, float, float, float, float]  # x0, x1, y0, y1, z0, z1
    round: bool = False  # a vertical cylinder inscribed in the box (x/y extents)


def B(m: str, x0, x1, y0, y1, z0, z1) -> Part:
    return Part(m, (x0, x1, y0, y1, z0, z1))


def C(m: str, cx, cy, r, z0, z1) -> Part:
    return Part(m, (cx - r, cx + r, cy - r, cy + r, z0, z1), round=True)


def _rack(w, d, h) -> list[Part]:
    t, plinth, top = 40, 80, 40
    x, y = w / 2, d / 2
    ps = [B("frame", sx * x - (t if sx > 0 else 0), sx * x + (t if sx < 0 else 0),
            sy * y - (t if sy > 0 else 0), sy * y + (t if sy < 0 else 0), plinth, h - top)
          for sx in (-1, 1) for sy in (-1, 1)]
    ps += [B("frame", -x + 20, x - 20, -y + 20, y - 20, 0, plinth), B("frame", -x, x, -y, y, h - top, h),
           B("panel", -x, -x + 12, -y + t, y - t, plinth, h - top), B("panel", x - 12, x, -y + t, y - t, plinth, h - top),
           B("frame", -w / 4, w / 4, -y + 100, -y + 300, h - top, h)]  # cable entry on the roof
    for face in (1, -1):  # perforated front and back doors: dark mesh behind horizontal bars
        y0, y1 = (y - 18, y - 4) if face > 0 else (-y + 4, -y + 18)
        b0, b1 = (y - 4, y) if face > 0 else (-y, -y + 4)  # the bars stand proud of the mesh
        ps.append(B("vent", -x + t, x - t, y0, y1, plinth + 30, h - top - 30))
        bars = int((h - plinth - top - 60) // 160)
        for i in range(1, bars):
            z = plinth + 30 + i * 160
            ps.append(B("panel", -x + t, x - t, b0, b1, z, z + 20))
    ps += [B("steel", x - t - 30, x - t - 10, y - 4, y, h / 2 - 150, h / 2 + 150),  # handle
           B("led", -x + t + 30, -x + t + 60, y - 4, y, h - top - 120, h - top - 100)]
    return ps


def _crac(w, d, h) -> list[Part]:
    x, y = w / 2, d / 2
    ps = [B("frame", -x + 30, x - 30, -y + 30, y - 50, 0, 100), B("light", -x, x, -y, y - 22, 100, h),
          B("vent", -x + 20, x - 20, y - 22, y - 20, 120, h - 60), B("vent", -x + 60, x - 60, -y + 60, y - 80, h - 15, h)]
    n = 3
    door = (w - 40 - (n - 1) * 15) / n
    for i in range(n):  # three doors with dark gaps between them
        x0 = -x + 20 + i * (door + 15)
        ps.append(B("white", x0, x0 + door, y - 20, y - 2, 120, h - 60))
        ps.append(B("steel", x0 + door - 60, x0 + door - 40, y - 2, y, h / 2 - 120, h / 2 + 120))
    ps += [B("blue", -x, x, y - 22, y - 2, h - 60, h - 20), B("screen", -150, 150, y - 2, y, h * 0.6, h * 0.6 + 180)]
    return ps


def _ups(w, d, h) -> list[Part]:
    x, y = w / 2, d / 2
    ps = [B("frame", -x + 20, x - 20, -y + 20, y - 40, 0, 80), B("frame", -x, x, -y, y - 20, 80, h)]
    half = (w - 50) / 2
    for i in range(2):
        x0 = -x + 15 + i * (half + 20)
        ps.append(B("panel", x0, x0 + half, y - 20, y - 4, 100, h - 30))
        for k in range(6):  # intake slots on the lower half
            z = 200 + k * 90
            ps.append(B("vent", x0 + 60, x0 + half - 60, y - 4, y - 2, z, z + 40))
    ps += [B("vent", -x + 60, -x + 60 + 360, y - 4, y, h - 520, h - 300), B("screen", -x + 80, -x + 60 + 340, y - 2, y, h - 500, h - 320),
           B("led", -x + 60, -x + 100, y - 2, y, h - 280, h - 260), B("yellow", -x + 15, x - 15, y - 4, y, h - 120, h - 100)]
    return ps


def _battery(w, d, h) -> list[Part]:
    x, y, t = w / 2, d / 2, 50
    ps = [B("frame", sx * x - (t if sx > 0 else 0), sx * x + (t if sx < 0 else 0),
            sy * y - (t if sy > 0 else 0), sy * y + (t if sy < 0 else 0), 0, h) for sx in (-1, 1) for sy in (-1, 1)]
    shelves = 4
    gap = (h - 60) / shelves
    for i in range(shelves):
        z = 30 + i * gap
        ps.append(B("steel", -x + t, x - t, -y + t, y - t, z, z + 30))
        n = max(1, int((w - 2 * t) // 200))
        cell = (w - 2 * t) / n
        bh = min(300, gap - 80)
        for k in range(n):
            x0 = -x + t + k * cell + 10
            ps += [B("battery", x0, x0 + cell - 20, -y + t + 20, y - t - 20, z + 30, z + 30 + bh),
                   B("red", x0 + 20, x0 + 50, y - t - 80, y - t - 40, z + 30 + bh, z + 50 + bh),
                   B("frame", x0 + cell - 70, x0 + cell - 40, y - t - 80, y - t - 40, z + 30 + bh, z + 50 + bh)]
    ps.append(B("frame", -x, x, -y, y, h - 30, h))
    return ps


def _pdu(w, d, h) -> list[Part]:
    x, y = w / 2, d / 2
    ps = [B("frame", -x + 20, x - 20, -y + 20, y - 40, 0, 80), B("light", -x, x, -y, y - 20, 80, h),
          B("panel", -x + 20, x - 20, y - 20, y - 4, 120, h - 40), B("screen", -120, 120, y - 4, y, h - 380, h - 240),
          B("yellow", -x + 20, x - 20, y - 4, y, h - 160, h - 130)]
    for row in range(8):  # breaker rows
        z = 300 + row * 140
        for col in (-1, 1):
            ps.append(B("vent", col * 40 - (180 if col < 0 else 0), col * 40 + (180 if col > 0 else 0), y - 4, y, z, z + 70))
    return ps


def _fire(w, d, h) -> list[Part]:
    x, y = w / 2, d / 2
    r = min(w, d) * 0.375
    body = h - 300
    return [B("frame", -x, x, -y, y, 0, 20), C("red", 0, 0, r, 20, body), C("red", 0, 0, r * 0.7, body, body + 60),
            C("steel", 0, 0, 40, body + 60, body + 140), B("frame", -60, 60, -60, 60, body + 140, body + 240),
            B("steel", -20, 20, -y, y, body + 240, h),  # valve lever across the full depth
            B("frame", -x, x, -y, -y + 20, body * 0.55, body * 0.55 + 60),  # wall strap
            C("white", 70, 0, 30, body + 160, body + 220)]  # pressure gauge


MODELS = {"rack": _rack, "crac": _crac, "ups": _ups, "battery": _battery, "pdu": _pdu, "fire": _fire}


def parts(tid: str, dims: tuple[int, int, int]) -> list[Part]:
    kind = next(k for k in MODELS if tid.startswith(k))
    return MODELS[kind](*dims)


def _mesh(p: Part) -> MeshData:
    x0, x1, y0, y1, z0, z1 = p.box
    if p.round:
        circle = Point((x0 + x1) / 2, (y0 + y1) / 2).buffer((x1 - x0) / 2, quad_segs=4)  # 16 sides
        return prism(circle, z0, z1)
    return box((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, x1 - x0, y1 - y0, z1 - z0)


def meshes(ps: list[Part]) -> dict[str, MeshData]:
    """One merged mesh per material: few objects in the GLB."""
    out: dict[str, list[MeshData]] = {}
    for p in ps:
        out.setdefault(p.material, []).append(_mesh(p))
    return {m: merge(*ms) for m, ms in out.items()}


def front_view(ps: list[Part], size: int = 512):
    """A front elevation (x across, z up) for the thumbnail, painted back to front."""
    import cv2
    import numpy as np

    lo_x, hi_x = min(p.box[0] for p in ps), max(p.box[1] for p in ps)
    hi_z = max(p.box[5] for p in ps)
    scale = (size - 96) / max(hi_x - lo_x, hi_z)
    img = np.zeros((size, size, 4), np.uint8)
    ox, oz = size / 2 - (lo_x + hi_x) / 2 * scale, size - 48
    for p in sorted(ps, key=lambda p: p.box[3]):
        x0, x1, _, _, z0, z1 = p.box
        col = MATERIALS[p.material]["color"].lstrip("#")
        bgr = (int(col[4:6], 16), int(col[2:4], 16), int(col[0:2], 16), 255)
        a = (math.floor(ox + x0 * scale), math.floor(oz - z1 * scale))
        b = (math.ceil(ox + x1 * scale), math.ceil(oz - z0 * scale))
        cv2.rectangle(img, a, b, bgr, -1)
    return img
