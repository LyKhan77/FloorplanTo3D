import pytest

from core.installation.store import InstallationStore
from core.spec.store import ValidationFailed, VersionConflict
from tests.spec.fixtures import spec_with_rooms

TRAY = {"op": "add_tray", "path": [(1000, 3000), (4000, 3000)], "tray_class": "data"}


def test_start_creates_empty_v1_with_layout_version(tmp_path):
    store = InstallationStore(tmp_path)
    inst = store.start(20, None, None, "overhead")
    assert store.head() == 1 and inst.meta.layout_version == 20 and inst.cable_trays == []
    assert store.load("HEAD") == inst
    with pytest.raises(FileExistsError):
        store.start(20, None, None, "overhead")


def test_commit_conflict_and_versions(tmp_path):
    store, layout = InstallationStore(tmp_path), spec_with_rooms()
    store.start(1, None, None, "overhead")
    with pytest.raises(VersionConflict):
        store.commit_ops(2, [TRAY], "editor", "x", layout, {})
    inst, _ = store.commit_ops(1, [TRAY], "editor", "tray koridor", layout, {})
    assert (inst.meta.version, inst.meta.parent_version, inst.meta.message) == (2, 1, "tray koridor") and store.versions() == [1, 2]
    with pytest.raises(ValidationFailed):
        store.commit_ops(2, [{**TRAY, "mounting": "underfloor"}], "editor", "", layout, {})
    assert store.head() == 2


def test_rebase_saves_even_with_errors(tmp_path):
    """Review Focus 5: the new layout version puts a 2500 mm rack under a tray at 2600: rebase still saves."""
    from core.spec.models import PlacedObject

    store, layout = InstallationStore(tmp_path), spec_with_rooms()
    store.start(1, None, None, "overhead")
    store.commit_ops(1, [{**TRAY, "elevation": 2600}], "editor", "", layout, {})
    layout.meta.version = 5
    layout.objects = [PlacedObject(id="O1", template_id="rack-48u", template_version="1", position=(2000, 3000, 0),
                                   dims=(800, 1200, 2500))]
    inst, issues = store.rebase(5, layout, {"rack-48u": "rack"})
    assert inst.meta.layout_version == 5 and store.head() == 3 and inst.cable_trays[0].id == "T1"
    assert any(i.code == "I002" for i in issues)
