"""Objects on boxes the user pointed at in the drawing (design §6.4): one template per box, or a row of them."""

from typing import TypedDict

from shapely.geometry import box as sbox
from shapely.ops import unary_union

from core.interior.layout import Placement, rotation_for
from core.interior.library import Tpl
from core.interior.rules import Rules
from core.interior.space import Space

MATCH = 0.15  # a box within 15% of the template footprint is that template
ROW_MIN = 1.5  # a box at least this many template widths long (and a template deep) is a row
LOOK_MM = 1500  # how far out each side is sampled to find the open side (the front)
TIE = 0.1


class DrawnBox(TypedDict):
    id: str
    center: list[float]
    size: list[float]  # [short, long]
    rotation: int  # 0: the long side runs along y; 90: along x


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= MATCH * b


def _size(tpl: Tpl, axis: str, want: float) -> float:
    """The box's size on a resizable axis within the template's range, else the template's own."""
    rng = tpl.resizable.get(axis)
    base = {"w": tpl.w, "d": tpl.d}[axis]
    return want if rng and rng[0] <= want <= rng[1] else base


def _open_side(cx, cy, axis, half_depth, length, space: Space | None) -> tuple[int, bool]:
    """(+1 or -1 along `axis`, tie?) — the side with more free room within LOOK_MM of the box."""
    if space is None:
        return 1, False
    room = space.room
    blocked = unary_union(space.blocked) if space.blocked else None
    free = []
    for sign in (1, -1):
        if axis == "x":
            g = sbox(min(cx + sign * half_depth, cx + sign * (half_depth + LOOK_MM)), cy - length / 2,
                     max(cx + sign * half_depth, cx + sign * (half_depth + LOOK_MM)), cy + length / 2)
        else:
            g = sbox(cx - length / 2, min(cy + sign * half_depth, cy + sign * (half_depth + LOOK_MM)),
                     cx + length / 2, max(cy + sign * half_depth, cy + sign * (half_depth + LOOK_MM)))
        area = g.intersection(room).area
        if blocked is not None:
            area -= g.intersection(blocked).area
        free.append(area)
    best = 1 if free[0] >= free[1] else -1
    return best, abs(free[0] - free[1]) <= TIE * max(free[0], free[1], 1)


def place_drawn(boxes: list[DrawnBox], tpl: Tpl, space: Space | None, rules: Rules) -> tuple[list[Placement], list[str]]:
    out, notes = [], []
    for b in boxes:
        (cx, cy), (short, long_) = b["center"], b["size"]
        long_axis = "y" if b["rotation"] == 0 else "x"
        short_axis = "x" if long_axis == "y" else "y"
        t_long, t_short = max(tpl.w, tpl.d), min(tpl.w, tpl.d)
        if _close(long_, t_long) and _close(short, t_short):
            # one object: the template's long dimension on the box's long side
            depth_long = tpl.d >= tpl.w
            front_axis = long_axis if depth_long else short_axis
            w = _size(tpl, "w", short if depth_long else long_)
            d = _size(tpl, "d", long_ if depth_long else short)
            centres = [(cx, cy)]
        elif long_ >= ROW_MIN * tpl.w and _close(short, tpl.d):
            # a row: objects side by side along the long side, each facing across it
            n = max(1, round(long_ / tpl.w))
            front_axis, w, d = short_axis, tpl.w, _size(tpl, "d", short)
            step = long_ / n
            centres = [(cx, cy - long_ / 2 + step * (k + 0.5)) if long_axis == "y" else
                       (cx - long_ / 2 + step * (k + 0.5), cy) for k in range(n)]
        else:
            notes.append(f"{b['id']}: ukuran {round(short)}×{round(long_)} mm beda dari {tpl.id} "
                         f"{round(tpl.w)}×{round(tpl.d)} mm, dipakai ukuran template")
            front_axis, w, d = long_axis if tpl.d >= tpl.w else short_axis, tpl.w, tpl.d
            centres = [(cx, cy)]
        across = d / 2
        span = long_ if front_axis == short_axis else short
        sign, tie = _open_side(cx, cy, front_axis, across, span, space)
        if tie and space is not None:
            notes.append(f"arah depan {b['id']} belum pasti: sebutkan sisinya (utara/selatan/timur/barat)")
        front = (sign, 0) if front_axis == "x" else (0, sign)
        rot = rotation_for(front)
        for x, y in centres:
            out.append(Placement(tpl.id, tpl.version, x, y, 0.0, rot, (w, d, tpl.h), source="drawing"))
    return out, notes
