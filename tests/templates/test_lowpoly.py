import pytest

from core.templates.lowpoly import MATERIALS, MODELS, parts
from core.templates.make_placeholders import PLACEHOLDERS


@pytest.mark.parametrize(("tid", "dims"), [(t[0], t[1]) for t in PLACEHOLDERS])
def test_parts_fill_the_template_box_exactly(tid, dims):
    """The validator compares the GLB bbox with template.json dims: the parts must span them, never exceed them."""
    w, d, h = dims
    ps = parts(tid, dims)
    lo = [min(p.box[i] for p in ps) for i in (0, 2, 4)]
    hi = [max(p.box[i] for p in ps) for i in (1, 3, 5)]
    assert lo == pytest.approx([-w / 2, -d / 2, 0]) and hi == pytest.approx([w / 2, d / 2, h])
    assert len(ps) >= 4 and all(p.material in MATERIALS for p in ps)  # more than a plain box


@pytest.mark.parametrize("tid", [t[0] for t in PLACEHOLDERS])
def test_low_poly_budget(tid):
    dims = next(t[1] for t in PLACEHOLDERS if t[0] == tid)
    from core.templates.lowpoly import meshes

    tris = sum(len(f) - 2 for m in meshes(parts(tid, dims)).values() for f in m["faces"])
    assert 40 <= tris <= 3000


def test_every_template_has_a_model_and_the_new_ones_are_there():
    ids = {t[0] for t in PLACEHOLDERS}
    assert ids == set(MODELS)
    assert {"inrow-cooler-300x1200", "panel-mdb-generic", "ats-cabinet-generic", "network-rack-2post",
            "fire-control-panel", "cctv-camera-bullet", "access-reader-generic", "containment-roof-600",
            "containment-door-1200"} <= ids
    cats = {t[0]: t[2] for t in PLACEHOLDERS}
    assert (cats["network-rack-2post"], cats["cctv-camera-bullet"], cats["containment-door-1200"]) == (
        "network", "security", "structure")


def test_containment_glass_is_see_through():
    assert any(p.material == "glass" for p in parts("containment-door-1200", (1200, 100, 2100)))
    assert MATERIALS["glass"]["alpha"] < 0.5


@pytest.mark.parametrize(("tid", "dims"), [(t[0], t[1]) for t in PLACEHOLDERS])
def test_material_budget(tid, dims):
    """core/templates/validate.py refuses an asset with more than 8 materials."""
    assert len({p.material for p in parts(tid, dims)}) <= 8
