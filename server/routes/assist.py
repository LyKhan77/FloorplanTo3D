"""/api/projects/{id}/assist: fix a marked area with an instruction, streamed as Server-Sent Events (area-fix design §6.5)."""

import itertools
import json
import uuid

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.assist.session import Session, run_turn, save_log
from core.spec.store import SpecStore
from server.errors import ApiError
from server.projects import latest_stage_file

router = APIRouter(prefix="/api/projects/{pid}/assist")


class AreaBody(BaseModel):
    session_id: str | None = None
    base_version: int
    ops: list[dict] = []
    box: tuple[float, float, float, float]
    selection: list[str] = []
    message: str
    drawn: list[dict] = []  # boxes the user pointed at in the drawing (K1, K2, ...), for generate interior


class DecisionBody(BaseModel):
    accepted: bool


def _sessions(request: Request) -> dict[str, Session]:
    # ponytail: in-memory and never evicted; sessions are small, add a TTL if a server runs for weeks
    if not hasattr(request.app.state, "assist_sessions"):
        request.app.state.assist_sessions = {}
    return request.app.state.assist_sessions


def _client(request: Request):
    factory = getattr(request.app.state, "assist_client_factory", None)
    if factory:
        return factory()
    from core.llm_review.client import StrataClient

    return StrataClient.from_settings(request.app.state.settings)


def _drawing(request: Request, pid: str):
    """The newest run's page, its binary and the px -> mm transform; all None for an imported spec (no run)."""
    import cv2

    storage = request.app.state.storage
    page, binary = latest_stage_file(storage, pid, "01_preprocess/page.png"), latest_stage_file(storage, pid, "01_preprocess/bin.png")
    grid = latest_stage_file(storage, pid, "02_grid/grid.json")
    if not page or not binary or not grid:
        return None, None, None
    return (cv2.imread(str(page), cv2.IMREAD_GRAYSCALE), cv2.imread(str(binary), cv2.IMREAD_GRAYSCALE),
            json.loads(grid.read_text())["px_to_mm"])


def _ceiling(storage, pid: str) -> float | None:
    """The installation's ceiling height when one exists (cameras hang below it), else None (wall height)."""
    from core.installation.store import InstallationStore

    try:
        store = InstallationStore(storage.project_dir(pid) / "installations")
        head = store.head()
        return store.load(head).meta.ceiling_height if head is not None else None
    except (OSError, ValueError):
        return None


def _session(request: Request, pid: str, sid: str) -> Session:
    s = _sessions(request).get(sid)
    if s is None or s.project_id != pid:
        raise ApiError(404, "no_session", "sesi asisten tidak ditemukan, mulai lagi")
    return s


@router.post("/area")
def area(pid: str, body: AreaBody, request: Request):
    storage = request.app.state.storage
    store = SpecStore(storage.project_dir(pid) / "specs")
    try:
        base = store.load(body.base_version)
    except (FileNotFoundError, OSError):
        raise ApiError(404, "spec_not_found", f"spec version {body.base_version} not found") from None
    if body.session_id:
        s = _session(request, pid, body.session_id)
        s.box, s.selection = body.box, body.selection
        first = []
    else:
        s = Session(id=uuid.uuid4().hex[:12], project_id=pid, box=body.box, selection=body.selection)
        _sessions(request)[s.id] = s
        first = [{"event": "session", "session_id": s.id}]
    page, binary, px_to_mm = _drawing(request, pid)
    client = _client(request)
    log_dir = storage.project_dir(pid) / "assist"

    def stream():
        events = run_turn(client, s, body.message, base, body.ops, page, binary, px_to_mm, log_dir,
                          storage.templates_dir, body.drawn, _ceiling(storage, pid))
        for ev in itertools.chain(first, events):
            name = ev.pop("event")
            yield f"event: {name}\ndata: {json.dumps(ev)}\n\n"

    # a sync generator: Starlette runs it in a threadpool, so the blocking Strata call does not stall the loop
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


class DrawnBoxBody(BaseModel):
    at: tuple[float, float] | None = None
    a: tuple[float, float] | None = None
    b: tuple[float, float] | None = None


DRAWN_MAX_MM = 20000  # a pointed box may be a whole row of racks; the Rack tool keeps 3000


@router.post("/drawn-box")
def drawn_box(pid: str, body: DrawnBoxBody, request: Request):
    """A box the user points at in the drawing (click, or Shift-drag fitted to the drawn lines), for generate interior."""
    from core.installation.snap import fit_box, snap_box

    _, binary, px_to_mm = _drawing(request, pid)
    if binary is None:
        raise ApiError(404, "no_run", "belum ada gambar hasil ekstraksi untuk dibaca")
    if body.at is not None:
        found = snap_box(binary, px_to_mm, body.at, max_mm=DRAWN_MAX_MM)
    elif body.a is not None and body.b is not None:
        found = fit_box(binary, px_to_mm, body.a, body.b, max_mm=DRAWN_MAX_MM)
    else:
        raise ApiError(422, "bad_request", "kirim at, atau a dan b")
    if found is None:
        raise ApiError(422, "no_box", "tidak ada kotak di sini")
    store = SpecStore(request.app.state.storage.project_dir(pid) / "specs")
    head = store.head()
    if head is not None and (rid := _room_of_box(store.load(head), found)):
        # a click on an empty room finds the room's own outline: that picks the room, it is no drawn equipment
        raise ApiError(422, "is_room", f"ini ruang {rid}, bukan kotak perangkat")
    return found


def _room_of_box(spec, found: dict) -> str | None:
    """The room whose outline the box is (IoU >= 0.7), or None."""
    from shapely.geometry import Polygon
    from shapely.geometry import box as sbox

    (cx, cy), (short, long_) = found["center"], found["size"]
    sx, sy = (short, long_) if found["rotation"] == 0 else (long_, short)
    b = sbox(cx - sx / 2, cy - sy / 2, cx + sx / 2, cy + sy / 2)
    for r in spec.rooms:
        poly = Polygon(r.polygon, r.holes)
        inter = poly.intersection(b).area
        if inter and inter / poly.union(b).area >= ROOM_IOU:
            return r.id
    return None


ROOM_IOU = 0.7


@router.post("/area/{sid}/decision", status_code=204)
def decision(pid: str, sid: str, body: DecisionBody, request: Request):
    s = _session(request, pid, sid)
    s.decisions.append({"proposal": len(s.proposals) - 1, "accepted": body.accepted})
    s.messages.append({"role": "user", "content": f"(The user {'accepted' if body.accepted else 'rejected'} "
                                                  "your last proposal.)"})
    save_log(s, request.app.state.storage.project_dir(pid) / "assist")
    return Response(status_code=204)
