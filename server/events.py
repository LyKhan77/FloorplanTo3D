"""Event bus: append-only events.jsonl per project + live fan-out to SSE subscribers (PRD/09 §4)."""

import asyncio
import json
import threading
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

from server.storage import Storage


class EventBus:
    def __init__(self, storage: Storage):
        self.storage = storage
        self._seq: dict[str, int] = {}
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self.closed = False

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Subscribers live on this loop; emit() may be called from any thread."""
        self._loop = loop

    def _path(self, pid: str) -> Path:
        return self.storage.projects_dir / pid / "events.jsonl"

    def _last_seq(self, pid: str) -> int:
        path = self._path(pid)
        if not path.exists():
            return 0
        last = 0
        with open(path, "rb") as f:
            for line in f:
                if line.strip():
                    last = json.loads(line)["seq"]
        return last

    def emit(self, pid: str, run_id: str | None, stage: int | None, type: str, *, level: str = "info",
             msg: str = "", data: dict | None = None) -> dict:
        if self.closed:  # a stage thread outliving shutdown must not write next to the next server process
            return {}
        with self._locks[pid]:
            seq = self._seq.get(pid, None)
            seq = (self._last_seq(pid) if seq is None else seq) + 1
            self._seq[pid] = seq
            event = {"seq": seq, "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                     "run_id": run_id, "stage": stage, "type": type, "level": level, "msg": msg, "data": data or {}}
            with open(self._path(pid), "a") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._push(pid, event)  # inside the lock: subscribers get events in seq order
        return event

    def _push(self, pid: str, item: dict | None) -> None:
        for q in list(self._subs[pid]):
            if self._loop is not None:
                self._loop.call_soon_threadsafe(q.put_nowait, item)
            else:
                q.put_nowait(item)

    def close(self) -> None:
        """End every SSE stream (None sentinel) and drop later emits. Uvicorn's graceful shutdown waits for
        open responses, so without this an open dashboard keeps the old process and its runs alive."""
        self.closed = True
        for pid in list(self._subs):
            self._push(pid, None)

    def history(self, pid: str, since: int = 0, run_id: str | None = None) -> list[dict]:
        path = self._path(pid)
        if not path.exists():
            return []
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        return [e for e in events if e["seq"] > since and (run_id is None or e["run_id"] == run_id)]

    def subscribe(self, pid: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs[pid].add(q)
        return q

    def unsubscribe(self, pid: str, q: asyncio.Queue) -> None:
        self._subs[pid].discard(q)


def format_sse(event: dict) -> str:
    return f"id: {event['seq']}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def sse_stream(bus: EventBus, pid: str, since: int, heartbeat_s: float = 15) -> AsyncIterator[str]:
    """Replay events after `since`, then stream live ones. Subscribing first means nothing falls in the gap;
    seq dedup drops live events the replay already sent."""
    q = bus.subscribe(pid)
    if bus.closed:
        q.put_nowait(None)
    try:
        last = since
        for e in bus.history(pid, since):
            last = e["seq"]
            yield format_sse(e)
        while True:
            try:
                e = await asyncio.wait_for(q.get(), heartbeat_s)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if e is None:
                return
            if e["seq"] > last:
                last = e["seq"]
                yield format_sse(e)
    finally:
        bus.unsubscribe(pid, q)
