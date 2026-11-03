def hall(w=10000, h=8000, doors=(), columns=(), objects=(), l_cut=None):
    """A one-room spec: exterior walls 200 mm on the axis rectangle (0,0)-(w,h), rooms rebuilt.

    doors: (wall index 0=S 1=E 2=N 3=W, offset from the wall's start, width); columns: (x, y, size);
    l_cut: (x, y) corner removed from the north-east, making an L.
    """
    from core.spec.models import Column, Opening, PlacedObject, Wall
    from core.spec.rooms import rebuild_rooms
    from tests.spec.fixtures import two_room_spec

    if l_cut:
        cx, cy = l_cut
        pts = [(0, 0), (w, 0), (w, cy), (cx, cy), (cx, h), (0, h)]
    else:
        pts = [(0, 0), (w, 0), (w, h), (0, h)]
    walls = [Wall(id=f"W{i + 1}", a=pts[i], b=pts[(i + 1) % len(pts)], thickness=200, kind="exterior")
             for i in range(len(pts))]
    openings = [Opening(id=f"D{i + 1}", category="door", wall_id=f"W{wi + 1}", offset=off, width=wd,
                        door_type="single_swing", hinge="start", swing="left") for i, (wi, off, wd) in enumerate(doors)]
    cols = [Column(id=f"C{i + 1}", center=(x, y), shape="rect", size=(sz, sz)) for i, (x, y, sz) in enumerate(columns)]
    base = two_room_spec()
    s = base.model_copy(update={"walls": walls, "openings": openings, "columns": cols, "rooms": [],
                                "objects": [PlacedObject(**o) for o in objects]})
    return rebuild_rooms(s)
