"""M12a: the installation layer API."""

from tests.server.conftest import import_gt

TRAY = {"op": "add_tray", "path": [[1000, 3000], [5000, 3000]], "tray_class": "data"}


def base(pid):
    return f"/api/projects/{pid}/installations"


def test_start_commit_validate_flow(setup_client, project_with_gt):
    c, pid = setup_client, project_with_gt
    r = c.post(f"{base(pid)}/start", json={"default_mounting": "overhead"})
    assert r.status_code == 201 and r.json()["meta"]["layout_version"] == 1
    assert c.post(f"{base(pid)}/start", json={}).status_code == 409
    r = c.post(base(pid), json={"base_version": 1, "ops": [TRAY], "message": "koridor"})
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2 and r.json()["lengths"]["data"]["horizontal"] == 4000
    assert [t["id"] for t in c.get(f"{base(pid)}/HEAD").json()["cable_trays"]] == ["T1"]
    v = c.post(f"{base(pid)}/validate", json={"base_version": 2, "ops": [{**TRAY, "tray_class": "power"}]}).json()
    assert v["lengths"]["power"]["horizontal"] == 4000 and "drops" in v and isinstance(v["issues"], list)
    assert [x["version"] for x in c.get(base(pid)).json()] == [1, 2]


def test_save_refused_on_error(setup_client, project_with_gt):
    c, pid = setup_client, project_with_gt
    c.post(f"{base(pid)}/start", json={})
    r = c.post(base(pid), json={"base_version": 1, "ops": [{**TRAY, "mounting": "underfloor"}], "message": ""})
    assert r.status_code == 422 and any(i["code"] == "I002" for i in r.json()["error"]["details"]["issues"])
    assert c.post(base(pid), json={"base_version": 9, "ops": [TRAY], "message": ""}).status_code == 409


def test_layout_changed_flag_and_rebase(setup_client, project_with_gt):
    c, pid = setup_client, project_with_gt
    c.post(f"{base(pid)}/start", json={})
    assert c.get(f"/api/projects/{pid}").json()["installation"] == {"head": 1, "layout_version": 1, "layout_changed": False}
    import_gt(c, pid)  # layout v2
    assert c.get(f"/api/projects/{pid}").json()["installation"]["layout_changed"] is True
    r = c.post(f"{base(pid)}/rebase")
    assert r.status_code == 200 and r.json()["version"] == 2
    assert c.get(f"/api/projects/{pid}").json()["installation"]["layout_changed"] is False


def test_start_takes_heights_from_the_prompt(setup_client, plan_bytes):
    from tests.server.conftest import create_project
    pid = create_project(setup_client, plan_bytes, prompt="tinggi plafon 3.2 m, raised floor 600 mm")
    import_gt(setup_client, pid)
    meta = setup_client.post(f"{base(pid)}/start", json={}).json()["meta"]
    assert (meta["ceiling_height"], meta["raised_floor_height"]) == (3200, 600)


def test_start_without_layout_is_409(setup_client, project_id):
    assert setup_client.post(f"{base(project_id)}/start", json={}).json()["error"]["code"] == "no_layout"


def test_snap_without_run_is_404(setup_client, project_with_gt):
    """Review Focus 1: an imported spec has no extraction run to snap to."""
    c, pid = setup_client, project_with_gt
    assert c.post(f"{base(pid)}/snap-tray", json={"points": [[0, 0], [3000, 0]]}).json()["error"]["code"] == "no_run"
    assert c.post(f"{base(pid)}/snap-box", json={"at": [1000, 1000]}).json()["error"]["code"] == "no_run"
    assert c.post(f"{base(pid)}/fit-box", json={"a": [0, 0], "b": [3000, 3000]}).json()["error"]["code"] == "no_run"


def test_project_without_installation_is_unchanged(setup_client, project_with_gt):
    c, pid = setup_client, project_with_gt
    d = c.get(f"/api/projects/{pid}").json()
    assert d["installation"] is None and d["head"] == 1
    assert c.get(f"{base(pid)}/HEAD").status_code == 404
    assert c.get("/api/projects").json()["items"][0]["installation"] is None


def test_ensure_route_moves_and_rebases(setup_client, project_with_gt):
    c, pid = setup_client, project_with_gt
    spec = c.get(f"/api/projects/{pid}/specs/HEAD").json()
    v = spec["meta"]["version"]
    add = {"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.1.0",
           "position": [2000, 2000, 0], "rotation": 0, "dims": [600, 1200, 2000]}
    assert c.post(f"/api/projects/{pid}/specs", json={"base_version": v, "ops": [add]}).status_code == 201
    r = c.post(f"{base(pid)}/ensure").json()
    assert r["moved"] == 1 and r["installation"]["meta"]["layout_version"] == v + 2
    assert c.get(f"/api/projects/{pid}/specs/HEAD").json()["objects"] == []


def test_build_rebases_first(setup_client, project_with_gt, monkeypatch):
    c, pid = setup_client, project_with_gt
    c.post(f"{base(pid)}/start", json={})
    import_gt(c, pid)  # layout v2: the installation is behind
    monkeypatch.setattr(c.app.state.orchestrator, "start_run", lambda *a, **k: {"run_id": "r1", "status": "queued"})
    assert c.post(f"{base(pid)}/build", json={"version": "HEAD"}).status_code == 202
    assert c.get(f"{base(pid)}/HEAD").json()["meta"]["layout_version"] == 2


def test_ensure_refused_cleanly_when_the_installation_has_errors(setup_client, project_with_gt, monkeypatch):
    from core.installation.store import InstallationStore
    from core.spec.store import ValidationFailed
    from core.spec.validate import Issue

    c, pid = setup_client, project_with_gt
    v = c.get(f"/api/projects/{pid}/specs/HEAD").json()["meta"]["version"]
    add = {"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.1.0",
           "position": [2000, 2000, 0], "rotation": 0, "dims": [600, 1200, 2000]}
    c.post(f"/api/projects/{pid}/specs", json={"base_version": v, "ops": [add]})

    def refuse(*a, **k):
        raise ValidationFailed([Issue("I001", "error", ["T1"], "T1 rusak")])
    monkeypatch.setattr(InstallationStore, "commit_ops", refuse)
    r = c.post(f"{base(pid)}/ensure")
    assert r.status_code == 409 and "belum dipindah" in r.json()["error"]["message"]


def test_a_device_moved_in_2d_saves(setup_client, project_with_gt):
    """Review C1: the web's move / turn ops must pass the server's 'moving needs a reason' rule."""
    c, pid = setup_client, project_with_gt
    c.post(f"{base(pid)}/start", json={})
    add = {"op": "add_object", "template_id": "rack-42u-600x1200", "template_version": "1.1.0",
           "position": [11000, 8000, 0], "rotation": 0, "dims": [600, 1200, 2000]}
    r = c.post(base(pid), json={"base_version": 1, "ops": [add]})
    rid = r.json()["installation"]["objects"][0]["id"]
    from tests.server.web_ops import (
        moved,  # the exact op the web editor sends (web/src/install/deviceOps.ts)
    )
    r = c.post(base(pid), json={"base_version": 2, "ops": [moved(rid, [11500, 8000, 0])]})
    assert r.status_code == 201, r.text
