"""One equipment layer (design docs/superpowers/specs/2026-11-03-fitout-layer-design.md): devices in the layout spec
move into the installation once, and the installation follows the layout by itself."""

import fcntl
from contextlib import contextmanager

from shapely.geometry import Polygon

from core.installation.store import InstallationStore
from core.interior.layout import Placement
from core.spec.store import SpecStore
from core.spec.validate import Issue

MOVE_REASON = "dipindah ke Instalasi & Interior"
DUPLICATE_IOU = 0.8
SAME_SPOT_MM = 10


def _footprint(o) -> Polygon:
    return Placement(o.template_id, o.template_version, o.position[0], o.position[1], o.position[2], o.rotation,
                     tuple(o.dims)).footprint()


def _iou(a: Polygon, b: Polygon) -> float:
    inter = a.intersection(b).area
    return inter / a.union(b).area if inter else 0.0


def auto_rebase(specs: SpecStore, store: InstallationStore, templates: dict[str, str]) -> tuple[int | None, list[Issue]]:
    """Onto the newest layout when the installation is behind; (new layout version or None, issues)."""
    head = specs.head()
    inst = store.load("HEAD")
    if head is None or inst.meta.layout_version >= head:
        return None, []
    previous = specs.load(inst.meta.layout_version)
    _, issues = store.rebase(head, specs.load(head), templates, previous=previous)
    return head, issues


@contextmanager
def _one_at_a_time(store: InstallationStore):
    """Two tabs (or React StrictMode) open the mode at once: the second waits, then finds the work done. A file of its
    own: the stores' locks are not re-entrant and ensure takes them."""
    store.dir.mkdir(parents=True, exist_ok=True)
    with open(store.dir / ".ensure.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def ensure(specs: SpecStore, store: InstallationStore, templates: dict[str, str], params: dict,
           review_paused: bool) -> dict:
    """The installation exists, holds every device, and stands on the newest layout."""
    with _one_at_a_time(store):
        return _ensure(specs, store, templates, params, review_paused)


def _ensure(specs: SpecStore, store: InstallationStore, templates: dict[str, str], params: dict,
            review_paused: bool) -> dict:
    notes: list[str] = []
    moved_ids: set[str] = set()
    if store.head() is None:
        store.start(specs.head(), params.get("ceiling_height"), params.get("raised_floor_height"), "overhead")
        notes.append("instalasi & interior dibuat")
    moved, skipped = 0, []
    layout = specs.load("HEAD")
    if layout.objects and not review_paused:
        inst = store.load("HEAD")
        done = {o.provenance.evidence.get("moved_from") for o in inst.objects} - {None}
        have = [(templates.get(o.template_id), o.template_id, o.position, _footprint(o)) for o in inst.objects]
        # where each moved device stood in the layout: a restored layout lists it there again, under a new id
        have += [(templates.get(o.template_id), o.template_id, tuple(o.provenance.evidence["at"]), None)
                 for o in inst.objects if o.provenance.evidence.get("at")]
        adds, dels = [], []
        for o in layout.objects:
            dels.append({"op": "delete_object", "id": o.id})
            if o.id in done:
                continue  # moved before; the layout only still lists it (an older version restored)
            fp, cat = _footprint(o), templates.get(o.template_id)
            dup = next((h for h in have if (h[3] is not None and h[0] == cat and _iou(fp, h[3]) >= DUPLICATE_IOU) or (
                h[1] == o.template_id and abs(h[2][0] - o.position[0]) <= SAME_SPOT_MM
                and abs(h[2][1] - o.position[1]) <= SAME_SPOT_MM)), None)
            if dup is not None:
                skipped.append(o.id)
                continue
            adds.append({"op": "add_object", "template_id": o.template_id, "template_version": o.template_version,
                         "position": list(o.position), "rotation": o.rotation, "dims": list(o.dims),
                         **({"label": o.label} if o.label else {}),
                         "evidence": {"moved_from": o.id, "at": [o.position[0], o.position[1]]}})
            have.append((cat, o.template_id, o.position, fp))
        if adds:
            store.commit_ops(inst.meta.version, adds, "editor", f"{len(adds)} objek dari layout v{layout.meta.version}",
                             specs.load(inst.meta.layout_version), templates, layout_head=specs.head())
            moved = len(adds)
            notes.append(f"{moved} objek dipindah ke Instalasi & Interior")
        if skipped:
            notes.append(f"{len(skipped)} objek layout sudah ada di instalasi, tidak dipindah: {', '.join(skipped)}")
        specs.commit_ops(layout.meta.version, dels, "editor", MOVE_REASON)
        moved_ids = {d["id"] for d in dels}
    elif layout.objects:
        notes.append("objek layout dipindah setelah review disetujui")
    rebased_to, issues = auto_rebase(specs, store, templates)
    # a rack moved out of the layout just now is not "gone from the layout" (I008): it is in the installation
    issues = [i for i in issues if not (i.code == "I008" and set(i.element_ids) <= moved_ids)]
    if rebased_to is not None:
        notes.append(f"instalasi dipindah ke layout v{rebased_to}"
                     + (f": {len(issues)} masalah, cek panel Masalah" if issues else ""))
    return {"installation": store.load("HEAD"), "moved": moved, "skipped": skipped, "rebased_to": rebased_to,
            "issues": issues, "notes": notes}
