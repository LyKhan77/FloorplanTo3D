"""Test helpers for raw meshes (verts in mm, faces as index lists)."""

import numpy as np


def normal(m, f):
    p = np.array([m["verts"][i] for i in f], float)
    return np.cross(p[1] - p[0], p[2] - p[0])


def faces_at(m, z):
    return [f for f in m["faces"] if all(abs(m["verts"][i][2] - z) < 1e-6 for i in f)]


def face_area(m, f):
    p = np.array([m["verts"][i] for i in f], float)
    total = np.zeros(3)
    for i in range(1, len(p) - 1):
        total += np.cross(p[i] - p[0], p[i + 1] - p[0])
    return float(np.linalg.norm(total) / 2)


def area_up(m):
    """Area of all faces whose normal points up (+Z)."""
    return sum(face_area(m, f) for f in m["faces"] if normal(m, f)[2] > 1e-9)


def area_at(m, z):
    return sum(face_area(m, f) for f in faces_at(m, z))
