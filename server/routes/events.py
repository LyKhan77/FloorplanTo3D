"""GET /api/projects/{id}/events (SSE) and events.jsonl download (PRD/09 §2.6)."""

import json

from fastapi import APIRouter, Header, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from server.events import sse_stream

router = APIRouter(prefix="/api/projects/{pid}")


@router.get("/events")
async def events(pid: str, request: Request, since: int = 0, last_event_id: str | None = Header(None)):
    request.app.state.storage.project_dir(pid)
    start = int(last_event_id) if last_event_id and last_event_id.isdigit() else since
    return StreamingResponse(sse_stream(request.app.state.bus, pid, start), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/events.jsonl")
def events_jsonl(pid: str, request: Request, run_id: str | None = None):
    request.app.state.storage.project_dir(pid)
    lines = [json.dumps(e, ensure_ascii=False) for e in request.app.state.bus.history(pid, 0, run_id)]
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson",
                             headers={"Content-Disposition": f'attachment; filename="{pid}-events.jsonl"'})
