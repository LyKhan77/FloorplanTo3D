"""M12b: an installation run builds, reports and publishes to installation_outputs (Blender faked)."""

import json

from pygltflib import GLTF2, Node, Scene

from tests.server.conftest import wait_status

TRAY = {"op": "add_tray", "path": [[1000, 3000], [5000, 3000]], "tray_class": "data"}


def fake_blender(build_input, out_dir, blender_bin, timeout_s=300, on_line=None, on_start=None):
    doc = json.loads(build_input.read_text())
    trays = [m["name"] for m in doc["meshes"] if m["name"].startswith("tray_") and not m["name"].endswith("_lip")]
    g = GLTF2(scenes=[Scene(nodes=list(range(len(trays))))], nodes=[Node(name=n) for n in trays])
    for f in ("installation.glb", "layout_installation.glb"):
        g.save(str(out_dir / f))
    (out_dir / "renders").mkdir(exist_ok=True)
    return 0


def test_build_runs_stages_7_to_10_and_publishes(app_factory, project_with_gt, data_dir, monkeypatch):
    import core.installation.build as build_mod

    monkeypatch.setattr(build_mod, "run_blender", fake_blender)
    pid, base = project_with_gt, f"/api/projects/{project_with_gt}/installations"
    with app_factory() as c:
        c.post(f"{base}/start", json={})
        c.post(base, json={"base_version": 1, "ops": [TRAY], "message": ""})
        r = c.post(f"{base}/build", json={})
        assert r.status_code == 202, r.text
        run = wait_status(c, pid, r.json()["run_id"], {"succeeded", "failed", "needs_attention"})
        assert run["status"] == "succeeded", run
        assert run["kind"] == "installation"
        # review I3: the run names the layout version it built on; the installation version has its own field
        assert (run["version"], run["installation_version"]) == (1, 2)
        listing = c.get(f"{base}/outputs").json()[0]
        assert listing["version"] == 2 and listing["built_at"] > 0  # the viewer reloads a rebuilt model by this
        out = data_dir / "projects" / pid / "installation_outputs" / "v2"
        assert json.loads((out / "installation.json").read_text())["lengths"]["data"]["horizontal"] == 4000
        assert json.loads((out / "verify.json").read_text())["glb_ok"] is True
        assert (out / "installation_report.html").exists()
        assert c.get(f"{base}/outputs").json()[0]["version"] == 2
        assert c.get(f"{base}/outputs/2/installation.json").status_code == 200
        assert c.get(f"{base}/outputs/2/..%2Fv2%2Finstallation.json").status_code == 404
        assert not (data_dir / "projects" / pid / "outputs").exists() or not any((data_dir / "projects" / pid / "outputs").iterdir())


def test_build_refused_with_errors(app_factory, project_with_gt, data_dir):
    """Review Focus 5: errors left (here written straight to disk, as a rebase can leave them) refuse the build."""
    pid, base = project_with_gt, f"/api/projects/{project_with_gt}/installations"
    with app_factory() as c:
        c.post(f"{base}/start", json={})
        f = data_dir / "projects" / pid / "installations" / "installation.v1.json"
        doc = json.loads(f.read_text())
        doc["cable_trays"] = [{"id": "T1", "path": [[1000, 3000], [5000, 3000]], "tray_class": "data", "mounting": "underfloor"}]
        f.write_text(json.dumps(doc))
        r = c.post(f"{base}/build", json={})
        assert r.status_code == 409 and r.json()["error"]["code"] == "installation_invalid"
        assert any(i["code"] == "I002" for i in r.json()["error"]["details"]["issues"])
