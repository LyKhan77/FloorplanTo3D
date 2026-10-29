"""Stage 5 helpers (PRD/04 Tahap 5): validation context, candidate choice, and OCR crops for unnamed rooms."""

import re

from shapely.geometry import Point
from shapely.geometry import Polygon as SPolygon

from core.extraction.geometry.elements import to_mm
from core.extraction.ocr import ocr_crop
from core.extraction.rooms.labels import match_type
from core.extraction.rooms.overlay import px_from_mm
from core.extraction.textclass import classify_text
from core.spec.models import Spec
from core.spec.rooms import RoomLabel

TIE = 0.01  # scores this close are a tie, settled by wall coverage (V018)
MIN_COVERAGE = 0.6  # share of the best candidate's coverage a candidate needs before scores are compared
# more wall than the drawing holds: both faces of a double wall read as two walls (M9: synthetic S1 at 1.21-1.38,
# correct S2 candidates never above 0.96)
MAX_COVERAGE = 1.05
CROP_MIN_M2 = 4  # rooms that V015 counts
CROP_SCALE = 3
TYPED = ("stair", "lift", "outdoor")  # geometry already says what these rooms are


def ocr_dimensions_from(grid_doc: dict) -> list[tuple[str, str, int]]:
    return [(e["axis_from"], e["axis_to"], int(e["value_mm"])) for e in grid_doc.get("equations_used", [])]


def choose(scored: list[dict]) -> dict | None:
    """Best validator score among candidates without errors; ties (<= 0.01) go to higher coverage, then index.

    Candidates that read more wall than the drawing holds (coverage > 1.05) go first, then those below 60% of the
    best remaining coverage: the score only subtracts violations, so an almost empty candidate breaks almost
    nothing (Gatsu S1, one wall: 0.997), and one that draws every double wall twice breaks little more.
    """
    passed = [c for c in scored if c["passed"]]
    if not passed:
        return None
    # drop over-readers only when a remaining candidate is about as complete (0.6 of them): on a plan whose estimate
    # runs low (diagonal or single-line walls) the right candidate itself can pass 1.05, and must not lose to a
    # nearly empty one
    over = [c["coverage"] for c in passed if c["coverage"] > MAX_COVERAGE]
    rest = [c for c in passed if c["coverage"] <= MAX_COVERAGE]
    if over and rest and max(c["coverage"] for c in rest) >= MIN_COVERAGE * max(over):
        passed = rest
    # relative to the best coverage: on a cluttered plan (furniture lines in the estimate) all may sit below 60%
    cut = MIN_COVERAGE * max(c["coverage"] for c in passed)
    valid = [c for c in passed if c["coverage"] >= cut]
    top = max(c["score"] for c in valid)
    return min((c for c in valid if top - c["score"] <= TIE), key=lambda c: (-c["coverage"], c["index"]))


def crop_labels(page_gray, spec: Spec, px_to_mm: list[float]) -> list[RoomLabel]:
    """OCR each unnamed room of >= 4 m² on its own crop (Gatsu: WC, TOILET, LIFT, TANGGA are too small for the
    page-wide pass). A text becomes a label when the lexicon knows it or it has >= 3 letters."""
    to_px = px_from_mm(px_to_mm)
    out = []
    for r in spec.rooms:
        if r.name or r.area_m2 < CROP_MIN_M2 or r.type in TYPED:
            continue
        shape = SPolygon(r.polygon, r.holes)
        pts = [to_px(x, y) for x, y in r.polygon]
        us, vs = [p[0] for p in pts], [p[1] for p in pts]
        box = (min(us) + 2, min(vs) + 2, max(us) - 2, max(vs) - 2)
        for item in sorted(ocr_crop(page_gray, box, CROP_SCALE), key=lambda i: (i.bbox[1], i.bbox[0])):
            if classify_text(item, in_circle=False, in_building=True) != "room_label":
                continue  # stair arrows (NAIK/TURUN), cable annotations, PROPOSED notes are not room names
            name = " ".join(re.findall(r"[A-Z0-9]+", item.text.upper()))
            rtype, _ = match_type(name)
            at = to_mm(px_to_mm, (item.bbox[0] + item.bbox[2]) / 2, (item.bbox[1] + item.bbox[3]) / 2)
            if shape.covers(Point(at)):
                out.append(RoomLabel(at=at, name=name, type=rtype))
    return out
