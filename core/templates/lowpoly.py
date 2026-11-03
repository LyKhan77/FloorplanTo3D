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
    "glass": {"color": "#BFD7EA", "roughness": 0.1, "alpha": 0.3},
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


def _inrow(w, d, h) -> list[Part]:
    """In-row cooler: a rack-sized cabinet with a perforated front, fans behind the rear grille and a display."""
    ps = _rack(w, d, h)
    x, y = w / 2, d / 2
    for k in range(3):  # fans seen through the rear
        z = 400 + k * 500
        ps.append(B("steel", -x + 60, x - 60, -y + 18, -y + 30, z, z + w - 120))
    ps += [B("screen", -x + 60, x - 60, y - 4, y, h - 420, h - 300), B("blue", -x + 40, x - 40, y - 4, y, h - 80, h - 60)]
    return ps


def _sections(w, d, h, body: str, door: str, n: int) -> list[Part]:
    """A cabinet line-up: plinth, body, n doors with gaps, handles and label plates."""
    x, y = w / 2, d / 2
    ps = [B("frame", -x + 20, x - 20, -y + 20, y - 40, 0, 100), B(body, -x, x, -y, y - 22, 100, h),
          B("vent", -x + 10, x - 10, y - 22, y - 20, 110, h - 20)]
    sec = (w - 20 - (n - 1) * 12) / n
    for i in range(n):
        x0 = -x + 10 + i * (sec + 12)
        ps += [B(door, x0, x0 + sec, y - 20, y - 4, 120, h - 30),
               B("steel", x0 + sec - 70, x0 + sec - 50, y - 4, y, h / 2 - 150, h / 2 + 150),
               B("yellow", x0 + sec / 2 - 100, x0 + sec / 2 + 100, y - 4, y, h - 160, h - 110)]
    return ps


def _mdb(w, d, h) -> list[Part]:
    x, y = w / 2, d / 2
    ps = _sections(w, d, h, "light", "white", max(1, round(w / 800)))
    for k in range(3):  # meters on the first section
        ps.append(B("screen", -x + 60 + k * 120, -x + 160 + k * 120, y - 4, y, h - 500, h - 420))
    return ps


def _ats(w, d, h) -> list[Part]:
    y = d / 2
    ps = _sections(w, d, h, "light", "white", 1)
    ps += [B("screen", -150, 150, y - 4, y, h - 520, h - 380),
           B("frame", -220, -60, y - 4, y, h / 2, h / 2 + 160), B("red", -170, -110, y - 2, y, h / 2 + 40, h / 2 + 120),
           B("frame", 60, 220, y - 4, y, h / 2, h / 2 + 160), B("frame", 110, 170, y - 2, y, h / 2 + 40, h / 2 + 120),
           # source indicators (blue = the screen's material: the validator allows 8 materials per asset)
           B("screen", -200, -170, y - 2, y, h - 340, h - 310), B("red", 170, 200, y - 2, y, h - 340, h - 310)]
    return ps


def _network(w, d, h) -> list[Part]:
    """Two-post network rack: base, uprights, patch panels and vertical cable managers."""
    x, y = w / 2, d / 2
    post = 80
    ps = [B("frame", -x, x, -y, y, 0, 40), B("frame", -x, -x + post, -40, 40, 40, h - 60),
          B("frame", x - post, x, -40, 40, 40, h - 60), B("frame", -x, x, -40, 40, h - 60, h),
          B("panel", -x, -x + post, 40, 140, 300, h - 200), B("panel", x - post, x, 40, 140, 300, h - 200)]
    for k in range(int((h - 600) // 180)):  # patch panels with a port strip
        z = 300 + k * 180
        ps += [B("frame", -x + post, x - post, -30, 60, z, z + 44), B("vent", -x + post + 20, x - post - 20, 60, 62, z + 12, z + 32)]
    ps.append(B("steel", -x + post, x - post, -y + 60, -y + 100, h - 60, h - 20))  # ladder rung to the tray
    return ps


def _fire_panel(w, d, h) -> list[Part]:
    """FM-200 control panel, wall mounted (the object's z places it on the wall)."""
    x, y = w / 2, d / 2
    return [B("frame", -x, x, -y, -y + 15, 0, h), B("light", -x + 10, x - 10, -y + 15, y - 15, 10, h - 10),
            B("red", -x + 20, x - 20, y - 15, y - 2, 20, h - 20), B("screen", -120, 120, y - 2, y, h - 220, h - 120),
            B("led", -120, -90, y - 2, y, h - 280, h - 250), B("yellow", -60, -30, y - 2, y, h - 280, h - 250),
            B("red", 0, 30, y - 2, y, h - 280, h - 250), B("frame", 60, 120, y - 2, y, 120, 180)]  # key switch


def _cctv(w, d, h) -> list[Part]:
    """Bullet camera on a wall plate (back at -y), looking along +y."""
    x, y = w / 2, d / 2
    return [B("frame", -x, x, -y, -y + 20, 0, h), B("frame", -15, 15, -y + 20, -y + 90, h * 0.4, h * 0.6),
            B("white", -50, 50, -y + 90, y, h * 0.27, h * 0.8), B("vent", -30, 30, y - 2, y, h * 0.37, h * 0.7),
            B("white", -x, x, -y + 110, y, h * 0.8, h)]  # sun shield


def _reader(w, d, h) -> list[Part]:
    x, y = w / 2, d / 2
    return [B("frame", -x, x, -y, -y + 10, 0, h), B("panel", -x + 5, x - 5, -y + 10, y, 5, h - 5),
            B("screen", -x + 15, x - 15, y - 2, y, h - 60, h - 20), B("led", -10, 10, y - 2, y, 20, 35)]


def _roof(w, d, h) -> list[Part]:
    """Cold-aisle containment roof module: a steel frame round a glass panel, laid across the aisle."""
    x, y = w / 2, d / 2
    return [B("steel", -x, x, -y, -y + 40, 0, h), B("steel", -x, x, y - 40, y, 0, h),
            B("steel", -x, -x + 30, -y + 40, y - 40, 0, h), B("steel", x - 30, x, -y + 40, y - 40, 0, h),
            B("glass", -x + 30, x - 30, -y + 40, y - 40, h / 2 - 5, h / 2 + 5)]


def _door(w, d, h) -> list[Part]:
    """Aisle end door: frame and two sliding glass leaves with handles."""
    x, y = w / 2, d / 2
    leaf = (w - 120) / 2
    ps = [B("steel", -x, -x + 50, -y, y, 0, h), B("steel", x - 50, x, -y, y, 0, h), B("steel", -x, x, -y, y, h - 120, h)]
    for i, x0 in enumerate((-x + 50, -x + 70 + leaf)):
        ps += [B("steel", x0, x0 + leaf, -20, 20, 0, 40), B("steel", x0, x0 + 40, -20, 20, 40, h - 120),
               B("steel", x0 + leaf - 40, x0 + leaf, -20, 20, 40, h - 120), B("glass", x0 + 40, x0 + leaf - 40, -8, 8, 40, h - 120),
               B("frame", x0 + (leaf - 60 if i == 0 else 20), x0 + (leaf - 40 if i == 0 else 40), 20, 40, h / 2 - 200, h / 2 + 200)]
    return ps


def _ahu(w, d, h) -> list[Part]:
    """Air handling unit: a long casing in sections (filter, coil, fan) with access doors and an intake louvre."""
    x, y = w / 2, d / 2
    ps = [B("frame", -x + 30, x - 30, -y + 30, y - 30, 0, 150), B("light", -x, x, -y, y - 20, 150, h)]
    sections = 3
    sec = (w - 40 - (sections - 1) * 15) / sections
    for i in range(sections):
        x0 = -x + 20 + i * (sec + 15)
        ps += [B("white", x0, x0 + sec, y - 20, y - 4, 200, h - 60),
               B("steel", x0 + sec - 70, x0 + sec - 50, y - 4, y, h / 2 - 120, h / 2 + 120)]
    for k in range(8):  # intake louvre on the first section
        z = 400 + k * 160
        ps.append(B("vent", -x + 60, -x + 20 + sec - 60, y - 4, y, z, z + 70))
    ps.append(B("blue", -x, x, y - 4, y, h - 50, h - 30))
    return ps


def _transformer(w, d, h) -> list[Part]:
    """Dry-type transformer in a louvred enclosure."""
    x, y = w / 2, d / 2
    ps = [B("frame", -x + 20, x - 20, -y + 20, y - 20, 0, 100), B("light", -x, x, -y, y - 20, 100, h)]
    for k in range(int((h - 400) // 120)):
        z = 250 + k * 120
        ps.append(B("vent", -x + 100, x - 100, y - 20, y, z, z + 50))
    ps += [B("yellow", -150, 150, y - 2, y, h - 280, h - 130), B("frame", -x, x, -y, y, h - 40, h)]
    return ps


def _genset(w, d, h) -> list[Part]:
    """Enclosed diesel generator set: base frame, acoustic canopy with louvres and doors, exhaust on the roof."""
    x, y = w / 2, d / 2
    ps = [B("frame", -x, x, -y, y, 0, 150), B("panel", -x + 20, x - 20, -y + 20, y - 20, 150, h - 150)]
    for i in range(3):  # side access doors
        x0 = -x + 200 + i * (w - 400) / 3
        ps.append(B("light", x0, x0 + (w - 400) / 3 - 40, y - 20, y - 4, 300, h - 300))
    for k in range(6):
        z = 450 + k * 180
        ps += [B("vent", -x + 20, -x + 24, -y + 200, y - 200, z, z + 90), B("vent", x - 24, x - 20, -y + 200, y - 200, z, z + 90)]
    ps += [B("frame", -x + 20, x - 20, -y + 20, y - 20, h - 150, h - 100),
           C("steel", x - 400, 0, 120, h - 100, h), B("yellow", -x + 20, x - 20, y - 4, y, 160, 200)]
    return ps


def _sts(w, d, h) -> list[Part]:
    ps = _sections(w, d, h, "frame", "panel", 1)
    y = d / 2
    ps += [B("screen", -150, 150, y - 4, y, h - 520, h - 380), B("led", -150, -110, y - 2, y, h - 340, h - 310),
           B("red", 110, 150, y - 2, y, h - 340, h - 310)]
    return ps


def _battery_cabinet(w, d, h) -> list[Part]:
    """Closed battery cabinet: two doors with vent slots."""
    x, y = w / 2, d / 2
    ps = [B("frame", -x + 20, x - 20, -y + 20, y - 40, 0, 80), B("battery", -x, x, -y, y - 20, 80, h)]
    half = (w - 50) / 2
    for i in range(2):
        x0 = -x + 15 + i * (half + 20)
        ps.append(B("panel", x0, x0 + half, y - 20, y - 4, 100, h - 30))
        for k in range(10):
            z = 250 + k * 140
            ps.append(B("vent", x0 + 60, x0 + half - 60, y - 4, y - 2, z, z + 40))
    ps.append(B("led", -x + 40, -x + 70, y - 2, y, h - 120, h - 100))
    return ps


def _fm200_bank(w, d, h) -> list[Part]:
    """FM-200 cylinder bank: cylinders in a rack frame, joined by a manifold."""
    x, y = w / 2, d / 2
    r = min(d / 2 - 30, 160)
    n = max(1, int((w - 100) // (2 * r + 60)))
    pitch = (w - 100) / n
    body = h - 350
    ps = [B("frame", -x, x, -y, y, 0, 40), B("frame", -x, -x + 50, -y, -y + 50, 0, h), B("frame", x - 50, x, -y, -y + 50, 0, h),
          B("frame", -x, x, -y, -y + 50, body * 0.6, body * 0.6 + 50), B("steel", -x + 50, x - 50, -40, 40, h - 120, h - 40)]
    for k in range(n):
        cx = -x + 50 + pitch * (k + 0.5)
        ps += [C("red", cx, 0, r, 40, body), C("steel", cx, 0, 40, body, body + 120), B("frame", cx - 50, cx + 50, -50, 50, body + 120, h - 120)]
    return ps


def _wall_panel(w, d, h, face: str) -> list[Part]:
    """A small wall-mounted detector / alarm panel (the object's z places it on the wall)."""
    x, y = w / 2, d / 2
    return [B("frame", -x, x, -y, -y + 10, 0, h), B("light", -x + 5, x - 5, -y + 10, y - 10, 5, h - 5),
            B(face, -x + 15, x - 15, y - 10, y - 2, 15, h - 15), B("screen", -x + 40, x - 40, y - 2, y, h - 160, h - 60),
            B("led", -x + 40, -x + 70, y - 2, y, 60, 90), B("yellow", x - 70, x - 40, y - 2, y, 60, 90)]


def _noc_desk(w, d, h) -> list[Part]:
    """NOC operator desk with two monitors."""
    x, y = w / 2, d / 2
    top = 750
    ps = [B("white", -x, x, -y, y, top - 30, top), B("frame", -x, -x + 40, -y, y, 0, top - 30),
          B("frame", x - 40, x, -y, y, 0, top - 30), B("panel", -x + 40, x - 40, -y, -y + 20, 300, top - 30)]
    for cx in (-w / 4, w / 4):
        ps += [B("frame", cx - 40, cx + 40, -y + 100, -y + 180, top, top + 120),
               B("vent", cx - 300, cx + 300, -y + 100, -y + 140, top + 120, h), B("screen", cx - 280, cx + 280, -y + 140, -y + 142, top + 140, h - 20)]
    return ps


def _chair(w, d, h) -> list[Part]:
    x, y = w / 2, d / 2
    return [B("frame", -x, x, -y, y, 0, 60), C("steel", 0, 0, 30, 60, 420), B("panel", -x + 50, x - 50, -y + 50, y - 50, 420, 500),
            B("panel", -x + 60, x - 60, -y, -y + 80, 500, h)]


def _storage(w, d, h) -> list[Part]:
    ps = _sections(w, d, h, "light", "white", 2)
    return ps


MODELS = {
    "rack-42u-600x1200": _rack, "rack-48u-800x1200": _rack, "crac-unit-generic": _crac, "ups-cabinet-generic": _ups,
    "battery-rack-generic": _battery, "pdu-floor-generic": _pdu, "fire-cylinder-generic": _fire,
    "inrow-cooler-300x1200": _inrow, "panel-mdb-generic": _mdb, "ats-cabinet-generic": _ats,
    "network-rack-2post": _network, "fire-control-panel": _fire_panel, "cctv-camera-bullet": _cctv,
    "access-reader-generic": _reader, "containment-roof-600": _roof, "containment-door-1200": _door,
    "ahu-unit-generic": _ahu, "transformer-dry-generic": _transformer, "genset-generic": _genset,
    "sts-cabinet-generic": _sts, "battery-cabinet-generic": _battery_cabinet, "fm200-cylinder-bank": _fm200_bank,
    "vesda-panel": lambda w, d, h: _wall_panel(w, d, h, "red"), "fire-alarm-panel": lambda w, d, h: _wall_panel(w, d, h, "red"),
    "noc-desk-generic": _noc_desk, "office-chair-generic": _chair, "storage-cabinet-generic": _storage,
}


def parts(tid: str, dims: tuple[int, int, int]) -> list[Part]:
    return MODELS[tid](*dims)


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
