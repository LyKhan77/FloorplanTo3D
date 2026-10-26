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
