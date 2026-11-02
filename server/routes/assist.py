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

router = APIRouter(prefix="/api/projects/{pid}/assist/area")


class AreaBody(BaseModel):
    session_id: str | None = None
    base_version: int
    ops: list[dict] = []
    box: tuple[float, float, float, float]
    selection: list[str] = []
    message: str


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


def _session(request: Request, pid: str, sid: str) -> Session:
    s = _sessions(request).get(sid)
    if s is None or s.project_id != pid:
        raise ApiError(404, "no_session", "sesi asisten tidak ditemukan, mulai lagi")
    return s


@router.post("")
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
        events = run_turn(client, s, body.message, base, body.ops, page, binary, px_to_mm, log_dir)
        for ev in itertools.chain(first, events):
            name = ev.pop("event")
            yield f"event: {name}\ndata: {json.dumps(ev)}\n\n"

    # a sync generator: Starlette runs it in a threadpool, so the blocking Strata call does not stall the loop
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/{sid}/decision", status_code=204)
def decision(pid: str, sid: str, body: DecisionBody, request: Request):
    s = _session(request, pid, sid)
    s.decisions.append({"proposal": len(s.proposals) - 1, "accepted": body.accepted})
    s.messages.append({"role": "user", "content": f"(The user {'accepted' if body.accepted else 'rejected'} "
                                                  "your last proposal.)"})
    save_log(s, request.app.state.storage.project_dir(pid) / "assist")
    return Response(status_code=204)
