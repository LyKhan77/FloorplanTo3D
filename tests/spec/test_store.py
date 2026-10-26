import os

import pytest

from core.spec.store import SpecStore, ValidationFailed, VersionConflict
from tests.spec.fixtures import spec_with_rooms


def test_save_new_assigns_versions(tmp_path):
    st = SpecStore(tmp_path)
    v1 = st.save_new(spec_with_rooms(), "manual")
    v2 = st.save_new(v1, "manual")
    assert (v1.meta.version, v2.meta.version, v2.meta.parent_version, st.head()) == (1, 2, 1, 2)
    assert st.load("HEAD") == v2 and st.versions() == [1, 2]


def test_empty_store_has_no_head(tmp_path):
    assert SpecStore(tmp_path / "new").head() is None


def test_commit_ops_creates_next_version(tmp_path):
    st = SpecStore(tmp_path)
    st.save_new(spec_with_rooms(), "manual")
    spec, result = st.commit_ops(1, [{"op": "rename_room", "id": "R1", "name": "X"}], "editor", "rename")
    assert spec.meta.version == 2 and spec.meta.source == "editor" and result.passed
    assert next(r for r in st.load(2).rooms if r.id == "R1").name == "X"
    assert any(e.op == "commit" and e.reason == "rename" for e in spec.provenance_log)


def test_stale_base_rejected_no_write(tmp_path):
    st = SpecStore(tmp_path)
    st.save_new(spec_with_rooms(), "manual")
    st.save_new(st.load(1), "manual")
    with pytest.raises(VersionConflict) as e:
        st.commit_ops(1, [{"op": "rename_room", "id": "R1", "name": "X"}], "editor")
    assert (e.value.base, e.value.head) == (1, 2) and st.versions() == [1, 2]


def test_invalid_result_rejected_no_write(tmp_path):
    st = SpecStore(tmp_path)
    st.save_new(spec_with_rooms(), "manual")
    with pytest.raises(ValidationFailed) as e:
        st.commit_ops(1, [{"op": "set_door", "id": "D2", "offset": 9000}], "editor")
    assert any(i.code == "V008" for i in e.value.issues) and st.versions() == [1]


def test_head_written_after_spec(tmp_path, monkeypatch):
    st = SpecStore(tmp_path)
    st.save_new(spec_with_rooms(), "manual")
    real_replace = os.replace

    def boom(src, dst):
        if str(dst).endswith("HEAD"):
            raise OSError("crash before HEAD")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        st.save_new(st.load(1), "manual")
    monkeypatch.undo()
    assert st.head() == 1 and st.load("HEAD").meta.version == 1 and st.versions() == [1]
