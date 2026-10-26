import re

import pytest

from server.errors import ApiError
from server.storage import Storage


def test_safe_join_rejects_escape_and_symlink(tmp_path):
    st = Storage(tmp_path)
    base = tmp_path / "projects" / "p"
    base.mkdir(parents=True)
    (base / "a.txt").write_text("x")
    assert st.safe_join(base, "a.txt") == base / "a.txt"
    for bad in ("../x", "/etc/passwd", "sub/../../x", "%2e%2e/x", ""):
        with pytest.raises(ApiError) as e:
            st.safe_join(base, bad)
        assert e.value.status == 404
    (base / "link").symlink_to(tmp_path)
    with pytest.raises(ApiError):
        st.safe_join(base, "link/anything")


def test_new_ids_shape(tmp_path):
    st = Storage(tmp_path)
    assert re.fullmatch(r"msc-gatsu-lantai-1-[0-9a-f]{4}", st.new_project_id("MSC Gatsu — Lantai 1!"))
    assert re.fullmatch(r"project-[0-9a-f]{4}", st.new_project_id("—"))
    assert re.fullmatch(r"\d{8}T\d{6}-[0-9a-f]{2}", st.new_run_id())


def test_write_json_atomic_roundtrip(tmp_path):
    st = Storage(tmp_path)
    st.write_json_atomic(tmp_path / "x" / "a.json", {"k": 1})
    assert st.read_json(tmp_path / "x" / "a.json") == {"k": 1}
    assert not list((tmp_path / "x").glob("*.tmp"))


def test_unknown_project_is_standard_404(client):
    r = client.get("/api/projects/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "project_not_found"


def test_concurrent_atomic_writes_never_expose_partial_json(tmp_path):
    """Cancel route and worker save the same run.json; a shared temp name made readers see torn JSON."""
    import json
    import threading

    from server.storage import Storage

    path, errors, stop = tmp_path / "run.json", [], threading.Event()
    Storage.write_json_atomic(path, {"n": 0})

    def writer(tag):
        for i in range(300):
            try:
                Storage.write_json_atomic(path, {"n": i, "tag": tag, "pad": "x" * 2000})
            except OSError as e:
                errors.append(repr(e))

    def reader():
        while not stop.is_set():
            try:
                json.loads(path.read_text())
            except (ValueError, OSError) as e:
                errors.append(repr(e))

    r = threading.Thread(target=reader)
    r.start()
    ws = [threading.Thread(target=writer, args=(t,)) for t in "ab"]
    for w in ws:
        w.start()
    for w in ws:
        w.join()
    stop.set()
    r.join()
    assert errors == []
    assert not list(tmp_path.glob(".*tmp*"))


def test_concurrent_touch_keeps_every_field(tmp_path):
    """A spec commit and a finishing run both touch project.json; neither change may be lost."""
    import threading

    from server.projects import touch
    from server.storage import Storage

    st = Storage(tmp_path)
    (st.projects_dir / "p-0001").mkdir(parents=True)
    Storage.write_json_atomic(st.projects_dir / "p-0001" / "project.json", {"project_id": "p-0001"})
    ts = [threading.Thread(target=lambda k=k: [touch(st, "p-0001", **{k: i}) for i in range(200)]) for k in "ab"]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    final = st.read_json(st.projects_dir / "p-0001" / "project.json")
    assert (final["a"], final["b"]) == (199, 199)
