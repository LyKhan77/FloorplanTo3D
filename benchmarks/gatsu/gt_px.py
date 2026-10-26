"""MSC Gatsu L1 ground truth, measured in plan.jpeg pixels -> benchmarks/gatsu/gt.yaml (mm).

Every coordinate below is a pixel measurement on floorplan/plan.jpeg (1600x945), read from zoomed crops
(benchmarks/tools/crop_zoom.py) and long-segment extraction. Wall points are centerlines (midpoint of the two
drawn edge lines). Interpretation decisions are recorded in NOTES.md.

Run: uv run python -m benchmarks.gatsu.gt_px && uv run python -m benchmarks.tools.gt_author benchmarks/gatsu/gt.yaml
"""

import itertools
import math
from pathlib import Path

import yaml

# Grid axes in pixels (magenta grid bubble leaders); C has no clean leader, so it is interpolated.
GRID_PX_X = {"A": 198.5, "B": 431.0, "C": 663.0, "D": 818.5, "E": 1050.5, "F": 1283.0}
GRID_PX_Y = {"1": 133.0, "2": 365.0, "3": 598.0}
GRID_MM_X = {"A": 0, "B": 6000, "C": 12000, "D": 16000, "E": 22000, "F": 28000}
GRID_MM_Y = {"3": 0, "2": 6000, "1": 12000}
MM_PER_PX = 25.81  # least-squares over the bubbles; gt_author refits from `calibration`
SNAP_MM = 150

walls: list[dict] = []
columns: list[dict] = []
openings: list[dict] = []
stairs: list[dict] = []
rooms: list[dict] = []
_wall_ends: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {}


def _snap(v: float, axes: list[int]) -> int:
    near = min(axes, key=lambda a: abs(a - v))
    return near if abs(near - v) <= SNAP_MM else round(v / 10) * 10


def mm(x: float, y: float) -> tuple[int, int]:
    return (_snap((x - GRID_PX_X["A"]) * MM_PER_PX, list(GRID_MM_X.values())),
            _snap((GRID_PX_Y["3"] - y) * MM_PER_PX, list(GRID_MM_Y.values())))


def t_mm(px: float) -> int:
    return round(px * MM_PER_PX / 10) * 10


def wall(points: list[tuple[float, float]], t: int, kind: str, **flags) -> list[str]:
    ids = []
    for (x1, y1), (x2, y2) in itertools.pairwise(points):
        wid = f"W{len(walls) + 1}"
        a, b = mm(x1, y1), mm(x2, y2)
        walls.append({"id": wid, "a": list(a), "b": list(b), "t": t, "kind": kind, **flags})
        _wall_ends[wid] = (a, b)
        ids.append(wid)
    return ids


def opening(wid: str, p_from: tuple[float, float], p_to: tuple[float, float], category: str = "door", **kw) -> None:
    """Opening between two pixel points on wall `wid`; offset measured from the wall's `a` end."""
    (ax, ay), (bx, by) = _wall_ends[wid]
    length = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / length, (by - ay) / length
    ts = sorted(((px - ax) * ux + (py - ay) * uy) for px, py in (mm(*p_from), mm(*p_to)))
    prefix = "D" if category == "door" else "N"
    oid = f"{prefix}{sum(1 for o in openings if o['id'][0] == prefix) + 1}"
    openings.append({"id": oid, "wall": wid, "category": category, "offset": round(ts[0]),
                     "width": round(ts[1] - ts[0]), **kw})


def column(x: float, y: float, w_px: float, h_px: float, kind: str = "structural", shape: str = "rect",
           grid: str | None = None) -> None:
    cid = f"C{len(columns) + 1}"
    col = {"id": cid, "at": grid or list(mm(x, y)), "shape": shape, "size": [t_mm(w_px), t_mm(h_px)], "kind": kind}
    if grid:
        col["grid"] = True
    columns.append(col)


def room(x: float, y: float, name: str, type_: str) -> None:
    rooms.append({"at": list(mm(x, y)), "name": name, "type": type_})


# --- outer band ---------------------------------------------------------------------------------------
SKIN, INNER, GLASS = t_mm(4.3), t_mm(6), t_mm(6)
wall([(104.5, 38), (1378, 38)], SKIN, "exterior")                       # north skin
wall([(104.5, 691.5), (1378, 691.5)], SKIN, "exterior")                 # south skin
wall([(104.5, 38), (104.5, 272.5)], SKIN, "exterior")                   # west skin, above entrance gap
wall([(104.5, 456), (104.5, 691.5)], SKIN, "exterior")                  # west skin, below entrance gap
wall([(1378, 38), (1378, 250)], SKIN, "exterior")                       # east skin, above stair exit gap
wall([(1378, 411), (1378, 691.5)], SKIN, "exterior")                    # east skin, below gap
wall([(104.5, 272.5), (176, 272.5)], INNER, "exterior")                 # band closures at the gaps
wall([(104.5, 456), (176, 456)], INNER, "exterior")
wall([(1321.5, 250), (1378, 250)], INNER, "exterior")
wall([(1321.5, 411), (1378, 411)], INNER, "exterior", free_ends=True)  # west end meets the S2 stair stringer
# band inner line (building face); north and south jog around the C-D bays
wall([(159, 94), (662.5, 94)], INNER, "exterior")
wall([(819, 94), (1321.5, 94)], INNER, "exterior")
wall([(159, 641), (656, 641)], INNER, "exterior")
wall([(829, 641), (1366.5, 641)], INNER, "exterior")
wall([(159, 94), (159, 272.5)], INNER, "exterior")
wall([(159, 456), (159, 641)], INNER, "exterior")
wall([(1321.5, 94), (1321.5, 270)], INNER, "exterior")
wall([(1366.5, 411), (1366.5, 641)], t_mm(5), "exterior")
# north bay (C-D) and south bay walls
wall([(662.5, 122), (662.5, 74), (819, 74), (819, 122)], INNER, "exterior")
wall([(656, 641), (656, 655), (829, 655), (829, 641)], INNER, "exterior")
# low rail ring inside the band (planter edge), between skin and band inner line
# height is an assumption (not readable from a plan): 1000 mm, see NOTES.md
RAIL, RAIL_H = t_mm(5), 1000
wall([(126.5, 61), (1355, 61)], RAIL, "low", height=RAIL_H)
wall([(126.5, 668.5), (1355, 668.5)], RAIL, "low", height=RAIL_H)
wall([(126.5, 61), (126.5, 272.5)], RAIL, "low", height=RAIL_H)
wall([(126.5, 456), (126.5, 668.5)], RAIL, "low", height=RAIL_H)
wall([(1355, 61), (1355, 250)], RAIL, "low", height=RAIL_H)
wall([(1355, 411), (1355, 668.5)], RAIL, "low", height=RAIL_H)
# pilaster fins: north and south rows at grid lines and mid-bays, west column of four, one east
FIN_X = (199.3, 315.3, 431.3, 547.5, 663.7, 818.7, 934.8, 1050.7, 1166.7, 1283.7)
for x in FIN_X:
    column(x, 65.5, 20, 51, kind="pilaster")
    column(x, 664, 20, 52, kind="pilaster")
for y in (132.5, 249, 481.5, 598):
    column(132, y, 52, 19.5, kind="pilaster")
column(1350, 132.7, 52, 19.3, kind="pilaster")
# piers between the band inner line and the row-1 / row-3 columns
# (piers overlap their column by ~2 px: the drawing joins them, and a hairline gap would merge rooms)
column(184, 109.5, 50, 31, kind="pilaster")
for x in (431.3, 1050.5, 1283):
    column(x, 109.5, 20.6, 31, kind="pilaster")
for x in (199, 431.3, 1050.5, 1283):
    column(x, 622.5, 20.6, 33, kind="pilaster")

# --- structural columns (H sections on every grid intersection) ----------------------------------------
for gx in "ABCDEF":
    for gy in "123":
        column(0, 0, 20.2, 20.2, shape="h_section", grid=f"{gx}{gy}")

# --- glazing (window walls) ---------------------------------------------------------------------------
# glazing runs between piers/walls; ends are placed on the neighbours' centerlines so the facade is closed
wall([(199, 110), (431.3, 110)], GLASS, "glass")
wall([(431.3, 111), (662.5, 111)], GLASS, "glass")
wall([(819, 111), (1043, 111)], GLASS, "glass")
wall([(199, 622), (431.3, 622)], GLASS, "glass")
wall([(431.3, 622), (656, 622)], GLASS, "glass")
wall([(176, 137), (176, 272.5)], GLASS, "glass")
wall([(176, 456), (176, 592)], GLASS, "glass")
wall([(159, 137), (189, 137)], INNER, "exterior")                       # NW link to column A1
wall([(159, 592), (189, 592)], INNER, "exterior")                       # SW link to column A3

# --- west entrance ------------------------------------------------------------------------------------
(w_entr,) = wall([(141.5, 272.5), (141.5, 456)], t_mm(5.6), "exterior")
opening(w_entr, (141.5, 334), (141.5, 396), door_type="double_swing", hinge="both", swing="left")

# --- stair S1 + lift (between A and B, rows 1-2) ----------------------------------------------------------
wall([(210.8, 145), (210.8, 365)], t_mm(4), "interior", free_ends=True)  # bottom end open to the galery
wall([(210.8, 145), (423, 145)], t_mm(4), "interior")
wall([(423, 145), (423, 365)], INNER, "interior")
wall([(279, 221), (350.8, 221), (350.8, 282.5), (279, 282.5), (279, 221)], t_mm(8), "interior")
wall([(361, 375), (361, 463)], t_mm(4), "interior", free_ends=True)  # top continues as stair stringer
stairs.append({"id": "S1", "flights": [
    {"start": list(mm(392, 375)), "end": list(mm(392, 213.7)), "width": t_mm(58), "risers": 15},
    {"start": list(mm(239.5, 213.7)), "end": list(mm(239.5, 375)), "width": t_mm(55), "risers": 15}],
    "landings": [[list(mm(212, 145)), list(mm(421, 145)), list(mm(421, 213.7)), list(mm(212, 213.7))]]})

# --- row 1-2 rooms -------------------------------------------------------------------------------------
wall([(819, 144), (819, 354)], t_mm(5), "interior")                   # meeting | gudang (between D1 and D2)
wall([(934.7, 111), (934.7, 364.5)], INNER, "interior")               # gudang | store
(w_r2a,) = wall([(423, 364.5), (818.5, 364.5)], t_mm(4), "interior")  # corridor north wall
(w_r2b,) = wall([(818.5, 364.5), (1043, 364.5)], t_mm(4), "interior")
opening(w_r2a, (517, 364.5), (580, 364.5), door_type="double_swing", hinge="both", swing="right")
opening(w_r2b, (855, 364.5), (887, 364.5), door_type="single_swing", hinge="end", swing="right")
opening(w_r2b, (970, 364.5), (1002, 364.5), door_type="single_swing", hinge="end", swing="right")
# toilets (E to E+6.3 m)
wall([(1043, 94), (1043, 367)], INNER, "interior")
(w_toil_e,) = wall([(1205, 94), (1205, 367)], t_mm(5), "interior")
wall([(1043, 367), (1205, 367)], t_mm(4), "interior")
wall([(1132, 94), (1132, 324)], t_mm(6), "partition")
wall([(1095, 94), (1095, 176)], t_mm(4), "partition")
wall([(1168.5, 94), (1168.5, 176)], t_mm(4), "partition")
(w_cub,) = wall([(1043, 176), (1205, 176)], t_mm(5), "partition")
wall([(1104, 324), (1205, 324)], t_mm(7.5), "partition", free_ends=True)  # west end free in the toilet
for x0, x1 in ((1063.7, 1092), (1100, 1128.7), (1137, 1165.3), (1173.7, 1202)):
    opening(w_cub, (x0, 176), (x1, 176), door_type="single_swing", hinge="start", swing="right")
opening(w_toil_e, (1205, 287), (1205, 318.7), door_type="single_swing", hinge="end", swing="right")
opening(w_toil_e, (1205, 328), (1205, 359.7), door_type="single_swing", hinge="end", swing="right")
# pantry and east stair S2
(w_pantry_s,) = wall([(1205, 270), (1321.5, 270)], t_mm(6), "interior")
opening(w_pantry_s, (1226, 270), (1258, 270), door_type="single_swing", hinge="end", swing="left")
wall([(1291, 270), (1291, 461.7)], t_mm(8), "interior")
(w_s2_e,) = wall([(1350, 250), (1350, 411)], t_mm(5), "exterior")
opening(w_s2_e, (1350, 382), (1350, 408), door_type="opening")         # stair exit to outside
(w_se_n,) = wall([(1291, 457), (1366.5, 457)], t_mm(4), "interior")
opening(w_se_n, (1295, 457), (1329.7, 457), door_type="single_swing", hinge="start", swing="left")
stairs.append({"id": "S2", "flights": [
    {"start": list(mm(1322.5, 405)), "end": list(mm(1322.5, 299)), "width": t_mm(55), "risers": 10}]})

# --- row 2-3 rooms -------------------------------------------------------------------------------------
(w_gal_n,) = wall([(361, 463), (656, 463)], t_mm(4.5), "interior")     # galery | corridor box
opening(w_gal_n, (617, 463), (647, 463), door_type="single_swing", hinge="end", swing="right")
wall([(656, 463), (656, 641)], INNER, "interior")                       # galery east wall (to south bay)
(w_south_n,) = wall([(829, 461.7), (1121, 461.7)], t_mm(4.5), "interior")
(w_ahu_n,) = wall([(1121, 461.7), (1216.5, 461.7)], t_mm(4.5), "interior")
(w_mdf_n,) = wall([(1216.5, 461.7), (1291, 461.7)], t_mm(4.5), "interior")
opening(w_south_n, (1006.5, 461.7), (1039, 461.7), door_type="single_swing", hinge="end", swing="right")
opening(w_south_n, (1079, 461.7), (1110, 461.7), door_type="single_swing", hinge="end", swing="right")
opening(w_ahu_n, (1137.8, 461.7), (1200.3, 461.7), door_type="double_swing", hinge="both", swing="left")
opening(w_mdf_n, (1226.5, 461.7), (1256.5, 461.7), door_type="single_swing", hinge="start", swing="right")
wall([(829, 461.7), (829, 641)], INNER, "interior")                     # battery west wall (to south bay)
wall([(1121, 461.7), (1121, 641)], INNER, "interior")                   # ex-mushola | AHU
wall([(1216.5, 461.7), (1216.5, 641)], t_mm(5), "interior")             # AHU | MDF
wall([(1283.5, 461.7), (1283.5, 641)], t_mm(7), "interior")             # MDF | east service room
# The double line at y~598-613 under the south rooms is the cable trench/tray, not a wall (NOTES.md).

# --- capacitor room (separate building east of F) -----------------------------------------------------------
(w_cap_n,) = wall([(1426, 576), (1577, 576)], INNER, "exterior")
wall([(1577, 576), (1577, 678), (1426, 678), (1426, 576)], INNER, "exterior")
opening(w_cap_n, (1511, 576), (1573.5, 576), door_type="double_swing", hinge="both", swing="left")

# --- room labels -----------------------------------------------------------------------------------------
room(620, 270, "R. MEETING", "meeting")
room(880, 270, "GUDANG", "storage")
room(1088, 250, "TOILET", "toilet")
room(1170, 250, "TOILET", "toilet")
for x in (1078, 1114, 1151, 1188):
    room(x, 135, "WC", "toilet")
room(1265, 180, "PANTRY", "pantry")
room(417, 554, "GALERY", "lobby")
room(315, 252, "LIFT", "lift")
room(900, 530, "BATTERY ROOM", "battery_room")
room(1165, 530, "AHU ROOM", "ahu_room")
room(1250, 530, "MDF ROOM", "mdf")
room(1500, 630, "CAPASITOR ROOM", "capacitor_room")
room(1322, 350, "TANGGA", "stair")
# outer band cells between the fins are outdoor space (PRD/04 stage 4 step 2b)
for x0, x1 in itertools.pairwise((104.5, *FIN_X, 1378)):
    room((x0 + x1) / 2, 50, "", "outdoor")
    room((x0 + x1) / 2, 680, "", "outdoor")
for y0, y1 in (*itertools.pairwise((38, 132.5, 249, 272.5)), *itertools.pairwise((456, 481.5, 598, 691.5))):
    room(115, (y0 + y1) / 2, "", "outdoor")
for y0, y1 in itertools.pairwise((38, 132.7, 250)):
    room(1366, (y0 + y1) / 2, "", "outdoor")


def main() -> None:
    calibration = {f"{gx}{gy}": [GRID_PX_X[gx], GRID_PX_Y[gy]] for gx in GRID_PX_X for gy in GRID_PX_Y}
    doc = {
        "project_id": "msc-gatsu-l1",
        "floor_name": "Lantai 1",
        "site_type": "data_center",
        "image": "floorplan/plan.jpeg",
        "grid": {"x": GRID_MM_X, "y": GRID_MM_Y},
        "calibration": calibration,
        "walls": walls,
        "columns": columns,
        "openings": [{**{k: v for k, v in o.items() if k != "door_type"}, "type": o.get("door_type")}
                     for o in openings],
        "stairs": stairs,
        "rooms": rooms,
    }
    out = Path(__file__).with_name("gt.yaml")
    header = "# GENERATED by benchmarks/gatsu/gt_px.py from pixel measurements. Edit gt_px.py, not this file.\n"
    out.write_text(header + yaml.safe_dump(doc, sort_keys=False, default_flow_style=None, width=120))
    print(f"wrote {out}: {len(walls)} walls, {len(columns)} columns, {len(openings)} openings, "
          f"{len(stairs)} stairs, {len(rooms)} room labels")


if __name__ == "__main__":
    main()
