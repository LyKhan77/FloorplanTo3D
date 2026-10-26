import asyncio
import re
import threading

from server.events import EventBus, sse_stream


def test_emit_seq_monotonic_and_persisted(storage_with_project):
    st, pid = storage_with_project
    bus = EventBus(st)
    e1 = bus.emit(pid, "r1", 3, "stage.log", msg="a")
    e2 = bus.emit(pid, "r1", 3, "stage.log", msg="b")
    assert (e1["seq"], e2["seq"]) == (1, 2)
    assert set(e1) == {"seq", "ts", "run_id", "stage", "type", "level", "msg", "data"}
    assert EventBus(st).emit(pid, "r1", 3, "stage.log")["seq"] == 3  # a new bus continues from the file
    assert [e["msg"] for e in bus.history(pid, since=1)] == ["b", ""]
    assert bus.history(pid, run_id="nope") == []


def _ids(chunks):
    return [int(re.search(r"^id: (\d+)", c, re.MULTILINE)[1]) for c in chunks]


def test_sse_replays_since_then_live_without_gap(storage_with_project):
    st, pid = storage_with_project

    async def main():
        bus = EventBus(st)
        bus.bind_loop(asyncio.get_running_loop())
        for i in range(3):
            bus.emit(pid, "r1", 7, "stage.log", msg=f"old{i}")
        gen = sse_stream(bus, pid, since=1, heartbeat_s=60)
        first = [await anext(gen), await anext(gen)]
        # emitted from a worker thread, like the orchestrator's stage threads
        threading.Thread(target=bus.emit, args=(pid, "r1", 7, "stage.log"), kwargs={"msg": "live"}).start()
        live = await asyncio.wait_for(anext(gen), 2)
        await gen.aclose()
        return first, live

    first, live = asyncio.run(main())
    assert _ids([*first, live]) == [2, 3, 4]
    assert "event: stage.log" in live and '"msg": "live"' in live


def test_sse_heartbeat(storage_with_project):
    st, pid = storage_with_project

    async def main():
        bus = EventBus(st)
        bus.bind_loop(asyncio.get_running_loop())
        gen = sse_stream(bus, pid, since=0, heartbeat_s=0.05)
        chunk = await asyncio.wait_for(anext(gen), 2)
        await gen.aclose()
        return chunk

    assert asyncio.run(main()) == ": ping\n\n"


def test_sse_stream_ends_when_bus_closes(storage_with_project):
    """Open SSE streams must end on shutdown, or uvicorn waits for them forever (old process keeps running)."""
    st, pid = storage_with_project

    async def main():
        bus = EventBus(st)
        bus.bind_loop(asyncio.get_running_loop())
        gen = sse_stream(bus, pid, since=0, heartbeat_s=60)
        pending = asyncio.ensure_future(anext(gen))
        await asyncio.sleep(0.05)
        bus.close()
        try:
            await asyncio.wait_for(pending, 2)
        except StopAsyncIteration:
            return "ended"
        return "still open"

    assert asyncio.run(main()) == "ended"


def test_emit_after_close_writes_nothing(storage_with_project):
    st, pid = storage_with_project
    bus = EventBus(st)
    bus.emit(pid, "r1", 7, "stage.log", msg="before")
    bus.close()
    bus.emit(pid, "r1", 7, "stage.log", msg="after")  # a stage thread outliving shutdown
    assert [e["msg"] for e in bus.history(pid)] == ["before"]


def test_exit_signal_closes_bus_then_calls_previous_handler(storage_with_project):
    import signal

    from server.app import close_bus_on_exit_signal

    st, _ = storage_with_project
    bus, calls = EventBus(st), []
    original = signal.signal(signal.SIGTERM, lambda s, f: calls.append(s))
    try:
        close_bus_on_exit_signal(bus)
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        assert bus.closed and calls == [signal.SIGTERM]
    finally:
        signal.signal(signal.SIGTERM, original)


def test_live_events_reach_subscribers_in_seq_order(storage_with_project):
    """If seq 6 is pushed before seq 5, the client's seq dedup drops 5 and Last-Event-ID never resends it."""
    import time

    st, pid = storage_with_project
    bus = EventBus(st)
    q = bus.subscribe(pid)
    real_push = bus._push

    def slow_first_push(p, item):
        if item and item["seq"] == 1:
            time.sleep(0.2)  # thread A is pre-empted between writing seq 1 and pushing it
        real_push(p, item)

    bus._push = slow_first_push
    a = threading.Thread(target=bus.emit, args=(pid, "r1", 7, "stage.log"))
    a.start()
    time.sleep(0.05)
    bus.emit(pid, None, None, "spec.created")  # thread B: a route emitting meanwhile
    a.join()
    assert [q.get_nowait()["seq"], q.get_nowait()["seq"]] == [1, 2]
