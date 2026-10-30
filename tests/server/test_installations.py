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


def test_project_without_installation_is_unchanged(setup_client, project_with_gt):
    c, pid = setup_client, project_with_gt
    d = c.get(f"/api/projects/{pid}").json()
    assert d["installation"] is None and d["head"] == 1
    assert c.get(f"{base(pid)}/HEAD").status_code == 404
    assert c.get("/api/projects").json()["items"][0]["installation"] is None
