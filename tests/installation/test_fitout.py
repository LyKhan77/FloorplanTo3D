import pytest

from core.installation.fitout import auto_rebase, ensure
from core.installation.store import InstallationStore
from core.spec.store import SpecStore
from tests.spec.fixtures import spec_with_rooms

TEMPLATES = {"rack-42u-600x1200": "rack", "crac-unit-generic": "cooling"}


def obj(tid, x, y, dims=(600, 1200, 2000)):
    return {"op": "add_object", "template_id": tid, "template_version": "1.1.0", "position": [x, y, 0], "rotation": 0,
            "dims": list(dims)}


@pytest.fixture
def stores(tmp_path):
    specs = SpecStore(tmp_path / "specs")
    specs.save_new(spec_with_rooms(), "manual")
    return specs, InstallationStore(tmp_path / "installations")


def with_objects(specs, *ops):
    specs.commit_ops(specs.head(), list(ops), "editor", "objects")


def moved_from(o):
    return o.provenance.evidence.get("moved_from")


def test_ensure_creates_and_moves(stores):
    specs, store = stores
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000), obj("crac-unit-generic", 7000, 3000, (2500, 900, 1950)))
    out = ensure(specs, store, TEMPLATES, {}, review_paused=False)
    inst = store.load("HEAD")
    assert out["moved"] == 2 and len(inst.objects) == 2
    assert sorted(o.position[0] for o in inst.objects) == [2000, 7000] and all(moved_from(o) for o in inst.objects)
    assert specs.load("HEAD").objects == [] and inst.meta.layout_version == specs.head()


def test_ensure_is_idempotent_after_restore(stores):
    specs, store = stores
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000))
    ensure(specs, store, TEMPLATES, {}, review_paused=False)
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000))  # an older version restored: the same rack again
    out = ensure(specs, store, TEMPLATES, {}, review_paused=False)
    assert out["moved"] == 0 and len(store.load("HEAD").objects) == 1


def test_duplicate_racks_are_skipped(stores):
    specs, store = stores
    ensure(specs, store, TEMPLATES, {}, review_paused=False)
    head = store.head()
    store.commit_ops(head, [obj("rack-42u-600x1200", 2000, 3000)], "editor", "rack", specs.load("HEAD"), TEMPLATES)
    with_objects(specs, obj("rack-42u-600x1200", 2010, 3000), obj("rack-42u-600x1200", 3500, 3000))
    out = ensure(specs, store, TEMPLATES, {}, review_paused=False)
    assert out["moved"] == 1 and len(out["skipped"]) == 1 and len(store.load("HEAD").objects) == 2


def test_no_move_while_review_paused(stores):
    specs, store = stores
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000))
    head = specs.head()
    out = ensure(specs, store, TEMPLATES, {}, review_paused=True)
    assert out["moved"] == 0 and specs.head() == head and len(specs.load("HEAD").objects) == 1


def test_auto_rebase_only_when_newer(stores):
    specs, store = stores
    ensure(specs, store, TEMPLATES, {}, review_paused=False)
    assert auto_rebase(specs, store, TEMPLATES) == (None, [])
    specs.commit_ops(specs.head(), [{"op": "rename_room", "id": "R1", "name": "X"}], "editor", "rename")
    version, _ = auto_rebase(specs, store, TEMPLATES)
    assert version == specs.head() and store.load("HEAD").meta.layout_version == specs.head()


def test_moving_racks_is_no_I008(stores):
    """Review: every moved rack came back as "rack tidak ada lagi di layout" after the move's rebase."""
    specs, store = stores
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000))
    store.start(specs.head(), None, None, "overhead")  # an installation standing on a layout that lists the rack
    out = ensure(specs, store, TEMPLATES, {}, review_paused=False)
    assert out["moved"] == 1 and not [i for i in out["issues"] if i.code == "I008"]


def test_a_moved_device_moved_again_is_not_duplicated_by_a_restore(stores):
    specs, store = stores
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000))
    ensure(specs, store, TEMPLATES, {}, review_paused=False)
    inst = store.load("HEAD")
    rk = inst.objects[0].id
    store.commit_ops(inst.meta.version, [{"op": "update_object", "id": rk, "position": [3500, 4000, 0], "reason": "x"}],
                     "editor", "move", specs.load(inst.meta.layout_version), TEMPLATES)
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000))  # the old layout restored: the rack at its old spot
    out = ensure(specs, store, TEMPLATES, {}, review_paused=False)
    assert out["moved"] == 0 and len(store.load("HEAD").objects) == 1


def test_two_ensures_at_once_move_once(stores):
    import threading

    specs, store = stores
    with_objects(specs, obj("rack-42u-600x1200", 2000, 3000))
    errors = []

    def go():
        try:
            ensure(specs, InstallationStore(store.dir), TEMPLATES, {}, review_paused=False)
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert errors == [] and len(store.load("HEAD").objects) == 1
