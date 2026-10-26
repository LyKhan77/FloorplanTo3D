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
