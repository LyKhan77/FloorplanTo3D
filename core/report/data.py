"""Data for the 3D map document (PRD/06 §7.2)."""

import math
import subprocess
from collections import Counter, defaultdict
from datetime import datetime

from core.spec.derive import id_key, stair_metrics
from core.spec.models import Spec
from core.spec.validate import validate

COMPASS = ["T", "TL", "U", "BL", "B", "BD", "S", "TG"]  # Indonesian 8-point compass, counter-clockwise from east


def _git_version() -> str:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)
    return r.stdout.strip() or "—"


def _compass(dx: float, dy: float) -> str:
    """Direction of travel; +Y is north (U = utara)."""
    angle = math.degrees(math.atan2(dy, dx)) % 360
    return COMPASS[int((angle + 22.5) // 45) % 8]


def report_data(spec: Spec, verify: dict | None, run: dict, missing_objects: list[str] | None = None) -> dict:
    """missing_objects: object IDs that were not placed in the model (template missing or invalid)."""
    missing = set(missing_objects or [])
    rooms = [r for r in sorted(spec.rooms, key=lambda r: id_key(r.id)) if r.type != "outdoor"]
    label = {r.id: r.name or r.id for r in spec.rooms}
    walls = {w.id: w for w in spec.walls}
    default_h = spec.meta.defaults.wall_height

    room_rows = [{"id": r.id, "name": r.name or "—", "type": r.type, "area_m2": r.area_m2,
                  "perimeter_m": r.perimeter_m, "n_doors": len(r.doors),
                  "wall_height": max((walls[w].height or default_h for w in r.bounding_walls if w in walls),
                                     default=default_h)} for r in rooms]

    door_rows = []
    for o in sorted((o for o in spec.openings if o.category == "door"), key=lambda o: id_key(o.id)):
        sides = [label[r.id] for r in sorted(spec.rooms, key=lambda r: id_key(r.id)) if o.id in r.doors]
        rooms_txt = " ↔ ".join(sides) if len(sides) > 1 else (f"{sides[0]} ↔ luar" if sides else "—")
        door_rows.append({"id": o.id, "rooms": rooms_txt, "type": o.door_type or "—",
                          "size": f"{o.width} × {o.height or spec.meta.defaults.door_height}",
                          "hinge": o.hinge or "—", "swing": o.swing or "—"})

    stair_rows = []
    for st in spec.stairs:
        m = stair_metrics(st, spec.meta.defaults)
        f = st.flights[0]
        stair_rows.append({"id": st.id, "room": label.get(st.room_id, "—") if st.room_id else "—",
                           "flights": len(st.flights), "risers": sum(x.risers for x in st.flights),
                           "riser_mm": round(m[0].riser_mm), "tread_mm": round(m[0].tread_mm),
                           "direction": _compass(f.end[0] - f.start[0], f.end[1] - f.start[1])})

    by_kind, by_t = defaultdict(float), defaultdict(float)
    for w in spec.walls:
        length = math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]) / 1000
        by_kind[w.kind] += length
        by_t[w.thickness] += length
    placed = [o for o in spec.objects if o.id not in missing]
    obj_by_tpl = Counter((o.template_id, o.template_version, tuple(o.dims)) for o in placed)
    obj_by_room = Counter(label.get(o.room_id, "—") if o.room_id else "—" for o in placed)

    issues = [f"{i.severity} {i.code} {', '.join(i.element_ids)}: {i.message}" for i in validate(spec).issues]
    issues += [f"verify: {w}" for w in (verify or {}).get("warnings", [])]
    issues += [f"objek {oid} tidak dimodelkan (template hilang atau tidak valid)" for oid in sorted(missing, key=id_key)]
    elements = [*spec.walls, *spec.columns, *spec.openings, *spec.rooms, *spec.stairs, *spec.objects]
    provenance = Counter(e.provenance.source for e in elements if e.provenance.source in ("editor", "manual", "llm"))

    return {
        "title": spec.meta.project_id, "floor": spec.meta.floor_name or "—", "spec_version": spec.meta.version,
        "date": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
        "status": (verify or {}).get("status", "—"),
        "summary": {"gross_area_m2": spec.meta.gross_area_m2,
                    "net_area_m2": round(sum(r.area_m2 for r in rooms), 2),
                    "n_rooms": len(rooms), "n_doors": len(door_rows), "n_columns": len(spec.columns),
                    "wall_height": default_h, "mm_per_px": round(spec.meta.mm_per_px, 3),
                    "scale_source": spec.meta.scale_source, "iou": (verify or {}).get("iou")},
        "rooms": room_rows, "doors": door_rows, "stairs": stair_rows,
        "walls": {"by_kind": [{"kind": k, "length_m": round(v, 2)} for k, v in sorted(by_kind.items())],
                  "by_thickness": [{"thickness": t, "length_m": round(v, 2)} for t, v in sorted(by_t.items())]},
        "objects": {"by_template": [{"template": f"{t}@{v}", "dims": " × ".join(map(str, d)), "count": n}
                                    for (t, v, d), n in sorted(obj_by_tpl.items())],
                    "by_room": [{"room": r, "count": n} for r, n in sorted(obj_by_room.items())]},
        "issues": issues,
        "provenance": dict(provenance),
        "metadata": {"input_sha256": spec.meta.image.sha256 if spec.meta.image else "—",
                     "run_id": run.get("run_id") or spec.meta.run_id or "—", "code_version": _git_version(),
                     "blender_version": run.get("blender_version", "—"), "prompt_version": "—"},
    }
