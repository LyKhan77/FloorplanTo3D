"""Spec validator V001-V019 and score (PRD/03 §12). score = 1 - Σ(weight × violation_ratio), clipped to [0, 1]."""

import itertools
import math
import statistics
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from shapely import affinity
from shapely.geometry import LineString
from shapely.geometry import Polygon as SPolygon

from core.spec.derive import column_footprint, endpoint_connected, stair_metrics, wall_footprint
from core.spec.models import PlacedObject, Spec, Wall

WEIGHTS: dict[str, float] = {
    "V003": 0.02, "V004": 0.15, "V005": 0.08, "V006": 0.08, "V007": 0.08, "V010": 0.05, "V012": 0.12,
    "V013": 0.12, "V014": 0.05, "V015": 0.05, "V016": 0.05, "V017": 0.05, "V018": 0.10,
}
ORTHO_TOL_DEG = 1.5


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Literal["error", "warning", "info"]
    element_ids: list[str]
    message: str


@dataclass(frozen=True)
class TemplateLimits:
    min: tuple[int, int, int]
    max: tuple[int, int, int]


@dataclass(frozen=True)
class ValidationContext:
    ocr_dimensions: list[tuple[str, str, int]] | None = None  # (axis label, axis label, mm)
    thick_line_length_mm: float | None = None
    templates: dict[str, TemplateLimits] | None = None  # key "<template_id>@<version>"


@dataclass
class ValidationResult:
    score: float
    passed: bool
    issues: list[Issue]
    ratios: dict[str, float] = field(default_factory=dict)


RuleResult = tuple[list[Issue], float]


def _length(w: Wall) -> float:
    return math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1])


def _ratio(n_bad: int, n_total: int) -> float:
    return n_bad / n_total if n_total else 0.0


def _per_element(code: str, sev, items: list, bad: Callable[[object], str | None]) -> RuleResult:
    issues = [Issue(code, sev, [it.id], msg) for it in items if (msg := bad(it))]
    return issues, _ratio(len(issues), len(items))


def _big_rooms(spec: Spec):
    return [r for r in spec.rooms if r.area_m2 >= 4]


def v001(spec: Spec, ctx: ValidationContext) -> RuleResult:
    m = spec.meta.px_to_mm
    if len(m) != 6 or m[0] * m[4] - m[1] * m[3] == 0:
        return [Issue("V001", "error", [], "px_to_mm missing or singular")], 0.0
    return [], 0.0


def v002(spec: Spec, ctx: ValidationContext) -> RuleResult:
    issues = [Issue("V002", "error", [i], "duplicate id") for i, n in Counter(spec.all_ids()).items() if n > 1]
    walls = {w.id for w in spec.walls}
    axes = {a.id for a in spec.grid.axes}
    rooms = {r.id for r in spec.rooms}
    doors = {o.id for o in spec.openings}
    refs = [(o.id, [o.wall_id], walls) for o in spec.openings]
    refs += [(w.id, w.grid_ref, axes) for w in spec.walls]
    refs += [(c.id, list(c.grid_ref or []), axes) for c in spec.columns]
    refs += [(r.id, r.bounding_walls, walls) for r in spec.rooms] + [(r.id, r.doors, doors) for r in spec.rooms]
    refs += [(e.id, [e.room_id], rooms) for e in [*spec.objects, *spec.stairs] if e.room_id]
    for eid, targets, valid in refs:
        for t in targets:
            if t not in valid:
                issues.append(Issue("V002", "error", [eid], f"unknown reference {t}"))
    return issues, 0.0


def v003(spec: Spec, ctx: ValidationContext) -> RuleResult:
    return _per_element("V003", "warning", spec.walls, lambda w: "wall < 100 mm" if _length(w) < 100 else None)


def v004(spec: Spec, ctx: ValidationContext) -> RuleResult:
    def bad(w):
        if w.free_ends:
            return None
        loose = [e for e in ("a", "b") if not endpoint_connected(spec, w, e)]
        return f"unconnected end(s) {','.join(loose)}" if loose else None
    return _per_element("V004", "warning", spec.walls, bad)


def v005(spec: Spec, ctx: ValidationContext) -> RuleResult:
    medians = {k: statistics.median(w.thickness for w in spec.walls if w.kind == k) for k in {w.kind for w in spec.walls}}

    def bad(w):
        if not 50 <= w.thickness <= 600:
            return f"thickness {w.thickness} outside [50, 600]"
        if abs(w.thickness - medians[w.kind]) > 0.3 * medians[w.kind]:
            return f"thickness {w.thickness} deviates > 30% from {w.kind} median {medians[w.kind]}"
        return None
    return _per_element("V005", "warning", spec.walls, bad)


def v006(spec: Spec, ctx: ValidationContext) -> RuleResult:
    def bad(w):
        if w.allow_skew or _length(w) == 0:
            return None
        ang = math.degrees(math.atan2(w.b[1] - w.a[1], w.b[0] - w.a[0])) % 90
        dev = min(ang, 90 - ang)
        return f"not orthogonal ({dev:.1f}°)" if dev > ORTHO_TOL_DEG else None
    return _per_element("V006", "warning", spec.walls, bad)


def v007(spec: Spec, ctx: ValidationContext) -> RuleResult:
    issues, involved = [], set()
    walls = [w for w in spec.walls if _length(w) > 0]
    for i, w in enumerate(walls):
        ux, uy = (w.b[0] - w.a[0]) / _length(w), (w.b[1] - w.a[1]) / _length(w)
        for o in walls[i + 1:]:
            ox, oy = (o.b[0] - o.a[0]) / _length(o), (o.b[1] - o.a[1]) / _length(o)
            if abs(ux * oy - uy * ox) > math.sin(math.radians(ORTHO_TOL_DEG)):
                continue
            if abs((o.a[0] - w.a[0]) * uy - (o.a[1] - w.a[1]) * ux) >= max(w.thickness, o.thickness) / 2:
                continue  # parallel but on a different line
            ts = sorted((p[0] - w.a[0]) * ux + (p[1] - w.a[1]) * uy for p in (o.a, o.b))
            overlap = min(_length(w), ts[1]) - max(0.0, ts[0])
            if overlap > 0.5 * min(_length(w), _length(o)):
                issues.append(Issue("V007", "warning", [w.id, o.id], f"overlap {overlap:.0f} mm"))
                involved |= {w.id, o.id}
    return issues, _ratio(len(involved), len(spec.walls))


def v008(spec: Spec, ctx: ValidationContext) -> RuleResult:
    walls = {w.id: w for w in spec.walls}
    issues = []
    for o in spec.openings:
        w = walls.get(o.wall_id)
        if w and not (o.offset >= 50 and o.offset + o.width <= _length(w) - 50):
            issues.append(Issue("V008", "error", [o.id], f"opening outside wall {w.id} (50 mm margin)"))
    return issues, 0.0


def v009(spec: Spec, ctx: ValidationContext) -> RuleResult:
    issues = []
    for wid in {o.wall_id for o in spec.openings}:
        ops = sorted((o for o in spec.openings if o.wall_id == wid), key=lambda o: o.offset)
        for a, b in itertools.pairwise(ops):
            if b.offset < a.offset + a.width:
                issues.append(Issue("V009", "error", [a.id, b.id], f"openings overlap on {wid}"))
    return issues, 0.0


def v010(spec: Spec, ctx: ValidationContext) -> RuleResult:
    def bad(o):
        hi = 6000 if o.door_type == "rolling" else 3000
        return f"door width {o.width} outside [600, {hi}]" if not 600 <= o.width <= hi else None
    return _per_element("V010", "warning", [o for o in spec.openings if o.category == "door"], bad)


def v011(spec: Spec, ctx: ValidationContext) -> RuleResult:
    issues = []
    for r in spec.rooms:
        shape = SPolygon(r.polygon, r.holes)
        if not shape.is_valid or shape.area < 1_000_000:
            issues.append(Issue("V011", "error", [r.id], "room polygon invalid or < 1 m²"))
    return issues, 0.0


def v012(spec: Spec, ctx: ValidationContext) -> RuleResult:
    return _per_element("V012", "warning", _big_rooms(spec), lambda r: None if r.doors else "room without door")


def v013(spec: Spec, ctx: ValidationContext) -> RuleResult:
    if ctx.ocr_dimensions is None:
        return [], 0.0
    by_label = {a.label: a for a in spec.grid.axes}
    issues = []
    for la, lb, mm in ctx.ocr_dimensions:
        a, b = by_label.get(la), by_label.get(lb)
        if not a or not b or a.orientation != b.orientation:
            issues.append(Issue("V013", "warning", [], f"dimension {la}-{lb} does not match grid axes"))
        elif abs(abs(a.offset - b.offset) - mm) > 0.005 * mm:
            issues.append(Issue("V013", "warning", [a.id, b.id],
                                f"grid {la}-{lb} = {abs(a.offset - b.offset)} mm, dimension text {mm} mm"))
    return issues, _ratio(len(issues), len(ctx.ocr_dimensions))


def v014(spec: Spec, ctx: ValidationContext) -> RuleResult:
    axes = {a.id: a for a in spec.grid.axes}

    def bad(c):
        refs = [axes.get(i) for i in c.grid_ref]
        if None in refs:
            return None  # V002 reports unknown axes
        x = next(a.offset for a in refs if a.orientation == "vertical")
        y = next(a.offset for a in refs if a.orientation == "horizontal")
        d = math.hypot(c.center[0] - x, c.center[1] - y)
        return f"column {d:.0f} mm from grid intersection" if d > 150 else None
    return _per_element("V014", "warning", [c for c in spec.columns if c.grid_ref], bad)


def v015(spec: Spec, ctx: ValidationContext) -> RuleResult:
    rooms = _big_rooms(spec)
    if not rooms:
        return [], 0.0
    named = sum(1 for r in rooms if r.name.strip()) / len(rooms)
    if named >= 0.7:
        return [], 0.0
    unnamed = [r.id for r in rooms if not r.name.strip()]
    return [Issue("V015", "warning", unnamed, f"only {named:.0%} of rooms ≥ 4 m² are named")], (0.7 - named) / 0.7


def _object_footprint(o: PlacedObject) -> SPolygon:
    w, d = o.dims[0], o.dims[1]
    x, y = o.position[0], o.position[1]
    box = SPolygon([(x - w / 2, y - d / 2), (x + w / 2, y - d / 2), (x + w / 2, y + d / 2), (x - w / 2, y + d / 2)])
    return affinity.rotate(box, o.rotation, origin=(x, y)) if o.rotation else box


def v016(spec: Spec, ctx: ValidationContext) -> RuleResult:
    def bad(o):
        if o.room_id is None:
            return "object outside any room"
        lim = (ctx.templates or {}).get(f"{o.template_id}@{o.template_version}")
        if lim and not all(lo <= v <= hi for v, lo, hi in zip(o.dims, lim.min, lim.max)):
            return f"dims {o.dims} outside template limits"
        return None
    return _per_element("V016", "warning", spec.objects, bad)


def v017(spec: Spec, ctx: ValidationContext) -> RuleResult:
    solids = [wall_footprint(w, spec) for w in spec.walls] + [column_footprint(c) for c in spec.columns]

    def bad(o):
        fp = _object_footprint(o)
        return "object collides with wall/column" if any(fp.intersection(s).area > 0 for s in solids) else None
    return _per_element("V017", "info", spec.objects, bad)


def v018(spec: Spec, ctx: ValidationContext) -> RuleResult:
    if ctx.thick_line_length_mm is None:
        return [], 0.0
    total = sum(_length(w) for w in spec.walls)
    if total < 0.6 * ctx.thick_line_length_mm:
        return [Issue("V018", "warning", [], f"wall length {total:.0f} mm < 60% of {ctx.thick_line_length_mm:.0f}")], 1.0
    return [], 0.0


def v019(spec: Spec, ctx: ValidationContext) -> RuleResult:
    rooms = [SPolygon(r.polygon, r.holes).buffer(1) for r in spec.rooms]
    issues = []
    for st in spec.stairs:
        for f, m in zip(st.flights, stair_metrics(st, spec.meta.defaults)):
            run = LineString([f.start, f.end]).buffer(f.width / 2, cap_style="flat")
            if not 150 <= m.riser_mm <= 200 or m.tread_mm < 250:
                issues.append(Issue("V019", "warning", [st.id],
                                    f"riser {m.riser_mm:.0f} mm / tread {m.tread_mm:.0f} mm out of range"))
            elif not any(r.covers(run) for r in rooms):
                issues.append(Issue("V019", "warning", [st.id], "flight not inside one room"))
    return issues, 0.0


RULES: list[tuple[str, Callable[[Spec, ValidationContext], RuleResult]]] = [
    ("V001", v001), ("V002", v002), ("V003", v003), ("V004", v004), ("V005", v005), ("V006", v006),
    ("V007", v007), ("V008", v008), ("V009", v009), ("V010", v010), ("V011", v011), ("V012", v012),
    ("V013", v013), ("V014", v014), ("V015", v015), ("V016", v016), ("V017", v017), ("V018", v018),
    ("V019", v019),
]


def validate(spec: Spec, ctx: ValidationContext | None = None) -> ValidationResult:
    ctx = ctx or ValidationContext()
    issues, ratios = [], {}
    for code, rule in RULES:
        found, ratio = rule(spec, ctx)
        issues += found
        if code in WEIGHTS:
            ratios[code] = ratio
    score = max(0.0, min(1.0, 1 - sum(WEIGHTS[c] * r for c, r in ratios.items())))
    return ValidationResult(score=score, passed=not any(i.severity == "error" for i in issues),
                            issues=issues, ratios=ratios)
