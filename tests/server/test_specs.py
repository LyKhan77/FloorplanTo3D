from tests.server.conftest import GT_PATH


def test_import_then_ops_then_diff(client, project_id):
    r = client.post(f"/api/projects/{project_id}/specs/import?message=GT", content=GT_PATH.read_bytes(),
                    headers={"content-type": "application/json"})
    assert r.status_code == 201 and r.json()["version"] == 1
    r = client.post(f"/api/projects/{project_id}/specs",
                    json={"base_version": 1, "ops": [{"op": "set_wall_height", "id": "W1", "height": 4500}],
                          "message": "tinggi"}, headers={"X-User": "lee"})
    assert r.status_code == 201 and r.json()["version"] == 2 and r.json()["spec"]["walls"][0]["height"] == 4500
    assert client.get(f"/api/projects/{project_id}/specs/diff?from=1&to=2").json()["walls"]["changed"] == ["W1"]
    versions = client.get(f"/api/projects/{project_id}/specs").json()
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[1]["source"] == "editor" and versions[1]["message"] == "user=lee; tinggi"
    assert versions[0]["has_outputs"] is False
    assert client.get(f"/api/projects/{project_id}/specs/HEAD").json()["meta"]["version"] == 2
    assert client.get(f"/api/projects/{project_id}/specs/9").status_code == 404


def test_stale_ops_409(client, project_with_gt):
    pid = project_with_gt
    ops = {"base_version": 1, "ops": [{"op": "rename_room", "id": "R22", "name": "X"}]}
    assert client.post(f"/api/projects/{pid}/specs", json=ops).status_code == 201
    r = client.post(f"/api/projects/{pid}/specs", json=ops)
    assert r.status_code == 409 and r.json()["error"]["code"] == "spec_conflict"
    assert r.json()["error"]["details"] == {"base": 1, "head": 2}


def test_invalid_ops_422_and_bad_op_400(client, project_with_gt):
    pid = project_with_gt
    r = client.post(f"/api/projects/{pid}/specs",
                    json={"base_version": 1, "ops": [{"op": "set_door", "id": "D1", "offset": 99999}]})
    assert r.status_code == 422 and any(i["code"] == "V008" for i in r.json()["error"]["details"]["issues"])
    r = client.post(f"/api/projects/{pid}/specs", json={"base_version": 1, "ops": [{"op": "nope"}]})
    assert r.status_code == 400 and r.json()["error"]["details"]["index"] == 0


def test_validate_dry_run_does_not_write(client, project_with_gt):
    pid = project_with_gt
    r = client.post(f"/api/projects/{pid}/specs/validate", json={"base_version": 1, "ops": []})
    assert r.json()["passed"] and r.json()["score"] > 0.9
    assert len(client.get(f"/api/projects/{pid}/specs").json()) == 1


def test_import_invalid_spec_422(client, project_id):
    r = client.post(f"/api/projects/{project_id}/specs/import", json={"schema_version": "1.0"})
    assert r.status_code == 422


def test_validate_returns_rooms_and_tasks(client, project_with_gt):
    """M8: the dry run answers with the rooms rebuilt from the ops and the review task list."""
    pid = project_with_gt
    base = client.post(f"/api/projects/{pid}/specs/validate", json={"base_version": 1, "ops": []}).json()
    assert base["rooms"] and isinstance(base["tasks"], list)
    r = client.post(f"/api/projects/{pid}/specs/validate",
                    json={"base_version": 1, "ops": [{"op": "delete_wall", "id": "W59", "reason": "uji"}]}).json()
    assert len(r["rooms"]) < len(base["rooms"])
    assert all({"id", "kind", "message", "at", "element_ids"} <= set(t) for t in r["tasks"])
