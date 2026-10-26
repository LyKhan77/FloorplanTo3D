"""Raw mesh primitives for build_input (verts in mm, faces as vertex-index lists, outward normals)."""

import math
from collections import Counter
from typing import TypedDict

import shapely
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.polygon import orient


class MeshData(TypedDict):
    verts: list[list[float]]
    faces: list[list[int]]


class _Builder:
    def __init__(self) -> None:
        self.verts: list[list[float]] = []
        self.faces: list[list[int]] = []
        self._index: dict[tuple[float, float, float], int] = {}

    def v(self, x: float, y: float, z: float) -> int:
        key = (round(x, 6), round(y, 6), round(z, 6))
        if key not in self._index:
            self._index[key] = len(self.verts)
            self.verts.append([float(x), float(y), float(z)])
        return self._index[key]

    def mesh(self) -> MeshData:
        return {"verts": self.verts, "faces": self.faces}


def _parts(poly: Polygon | MultiPolygon) -> list[Polygon]:
    return list(poly.geoms) if isinstance(poly, MultiPolygon) else [poly]


def _triangles(part: Polygon) -> list[list[tuple[float, float]]]:
    """Counter-clockwise triangles covering the polygon (holes excluded), without Steiner points."""
    out = []
    for tri in shapely.constrained_delaunay_triangles(part).geoms:
        if not part.contains(tri.representative_point()):
            continue
        pts = list(orient(tri, 1.0).exterior.coords)[:3]
        out.append(pts)
    return out


def flat(poly: Polygon | MultiPolygon, z: float) -> MeshData:
    b = _Builder()
    for part in _parts(poly):
        for tri in _triangles(part):
            b.faces.append([b.v(x, y, z) for x, y in tri])
    return b.mesh()


def prism(poly: Polygon | MultiPolygon, z0: float, z1: float) -> MeshData:
    b = _Builder()
    for part in _parts(poly):
        part = orient(part, 1.0)  # exterior CCW, holes CW
        for tri in _triangles(part):
            b.faces.append([b.v(x, y, z1) for x, y in tri])
            b.faces.append([b.v(x, y, z0) for x, y in reversed(tri)])
        for ring in (part.exterior, *part.interiors):
            pts = list(ring.coords)[:-1]
            for (px, py), (qx, qy) in zip(pts, pts[1:] + pts[:1]):
                b.faces.append([b.v(px, py, z0), b.v(qx, qy, z0), b.v(qx, qy, z1), b.v(px, py, z1)])
    return b.mesh()


def box(cx: float, cy: float, cz: float, sx: float, sy: float, sz: float, rot_z_deg: float = 0.0) -> MeshData:
    c, s = math.cos(math.radians(rot_z_deg)), math.sin(math.radians(rot_z_deg))
    b = _Builder()

    def corner(dx: float, dy: float, dz: float) -> int:
        x, y = dx * sx / 2, dy * sy / 2
        return b.v(cx + x * c - y * s, cy + x * s + y * c, cz + dz * sz / 2)

    v = {(dx, dy, dz): corner(dx, dy, dz) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)}
    b.faces += [
        [v[-1, -1, -1], v[-1, 1, -1], v[1, 1, -1], v[1, -1, -1]],  # bottom
        [v[-1, -1, 1], v[1, -1, 1], v[1, 1, 1], v[-1, 1, 1]],  # top
        [v[-1, -1, -1], v[1, -1, -1], v[1, -1, 1], v[-1, -1, 1]],  # -y
        [v[1, 1, -1], v[-1, 1, -1], v[-1, 1, 1], v[1, 1, 1]],  # +y
        [v[-1, 1, -1], v[-1, -1, -1], v[-1, -1, 1], v[-1, 1, 1]],  # -x
        [v[1, -1, -1], v[1, 1, -1], v[1, 1, 1], v[1, -1, 1]],  # +x
    ]
    return b.mesh()


def merge(*meshes: MeshData) -> MeshData:
    out: MeshData = {"verts": [], "faces": []}
    for m in meshes:
        base = len(out["verts"])
        out["verts"] += m["verts"]
        out["faces"] += [[i + base for i in f] for f in m["faces"]]
    return out


def is_closed(m: MeshData) -> bool:
    """Every undirected edge is shared by exactly two faces."""
    edges = Counter()
    for f in m["faces"]:
        for a, b in zip(f, f[1:] + f[:1]):
            edges[(min(a, b), max(a, b))] += 1
    return bool(edges) and all(n == 2 for n in edges.values())
