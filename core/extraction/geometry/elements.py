"""elements.json (one stage-3 candidate, spec mm) and its conversion to a partial Spec without rooms.

The partial spec lets the extraction benchmark score walls, doors, stairs and the footprint before stages 4-5 exist.
"""

from datetime import UTC, datetime

from pydantic import ValidationError

from core.spec.models import Column, Grid, GridAxis, Meta, Opening, Provenance, Spec, Stair, Wall

PARTIAL_CREATED_AT = datetime(2026, 1, 1, tzinfo=UTC)  # fixed: the partial spec must be deterministic


def to_mm(px_to_mm: list[float], u: float, v: float) -> tuple[int, int]:
    a, b, c, d, e, f = px_to_mm
    return round(a * u + b * v + c), round(d * u + e * v + f)


def _prov(el: dict) -> Provenance:
    return Provenance(source="cv", confidence=round(float(el.get("confidence", 1.0)), 4),
                      evidence=el.get("evidence") or {})


def elements_to_spec(elements: dict, grid_doc: dict, project_id: str = "extract") -> Spec:
    walls, wall_ids = [], {}
    for i, w in enumerate(elements.get("walls", [])):
        try:
            wall = Wall(id=f"W{len(walls) + 1}", a=tuple(w["a"]), b=tuple(w["b"]), thickness=w["thickness"],
                        kind=w["kind"], provenance=_prov(w))
        except ValidationError:
            continue
        if wall.a == wall.b:
            continue
        wall_ids[i] = wall.id
        walls.append(wall)
    columns = []
    for c in elements.get("columns", []):
        try:
            columns.append(Column(id=f"C{len(columns) + 1}", center=tuple(c["center"]), shape=c["shape"],
                                  size=tuple(c["size"]), rotation=c.get("rotation", 0), kind=c.get("kind", "structural"),
                                  grid_ref=tuple(c["grid_ref"]) if c.get("grid_ref") else None, provenance=_prov(c)))
        except ValidationError:
            continue
    openings = []
    for o in elements.get("openings", []):
        if o["wall"] not in wall_ids:
            continue
        prefix = "D" if o.get("category", "door") == "door" else "N"
        try:
            openings.append(Opening(id=f"{prefix}{len(openings) + 1}", category=o.get("category", "door"),
                                    wall_id=wall_ids[o["wall"]], offset=o["offset"], width=o["width"],
                                    door_type=o.get("door_type"), hinge=o.get("hinge"), swing=o.get("swing"),
                                    provenance=_prov(o)))
        except ValidationError:
            continue
    stairs = []
    for s in elements.get("stairs", []):
        try:
            stairs.append(Stair(id=f"S{len(stairs) + 1}", flights=s["flights"], landings=s.get("landings", []),
                                provenance=_prov(s)))
        except ValidationError:
            continue
    meta = Meta(project_id=project_id, created_at=PARTIAL_CREATED_AT, source="pipeline",
                px_to_mm=grid_doc["px_to_mm_original"], mm_per_px=grid_doc["mm_per_px"],
                scale_source=grid_doc.get("scale_source", "grid_dimensions"))
    axes = [GridAxis(id=a["id"], label=a["label"], orientation=a["orientation"], offset=a["offset"])
            for a in grid_doc.get("axes", [])]
    return Spec(meta=meta, grid=Grid(axes=axes), walls=walls, columns=columns, openings=openings, stairs=stairs)
