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


def test_snap_route(client, project_with_gt):
    """M8: POST /snap answers from the newest run's binary page; 404 without a run, 422 where there is no line."""
    import json

    import cv2
    import numpy as np

    pid = project_with_gt
    assert client.post(f"/api/projects/{pid}/snap", json={"a": [0, 0], "b": [3000, 0]}).status_code == 404
    st = client.app.state.storage.project_dir(pid) / "runs" / "20261029T000000-aa" / "stages"
    (st / "01_preprocess").mkdir(parents=True)
    (st / "02_grid").mkdir(parents=True)
    img = np.zeros((400, 400), np.uint8)
    for row in (197, 203):  # faces of a 150 mm wall at y = 5000 mm
        cv2.line(img, (40, row), (320, row), 255, 1)
    cv2.imwrite(str(st / "01_preprocess" / "bin.png"), img)
    (st / "02_grid" / "grid.json").write_text(json.dumps({"px_to_mm": [25, 0, 0, 0, -25, 10000]}))
    ok = client.post(f"/api/projects/{pid}/snap", json={"a": [1500, 5100], "b": [7500, 5100]})
    assert ok.status_code == 200 and abs(ok.json()["a"][1] - 5000) <= 15
    r = client.post(f"/api/projects/{pid}/snap", json={"a": [1500, 9000], "b": [7500, 9000]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_line"


def test_backdrop_points_at_the_newest_page(client, project_with_gt):
    """M8 review canvas: the page image of the newest run that has one, and its px -> mm transform."""
    import json

    pid = project_with_gt
    assert client.get(f"/api/projects/{pid}/backdrop").status_code == 404
    st = client.app.state.storage.project_dir(pid) / "runs" / "20261029T000000-aa" / "stages"
    (st / "01_preprocess").mkdir(parents=True)
    (st / "02_grid").mkdir(parents=True)
    (st / "01_preprocess" / "page.png").write_bytes(b"png")
    (st / "02_grid" / "grid.json").write_text(json.dumps({"px_to_mm": [12.9, 0, -5000, 0, -12.9, 15000]}))
    r = client.get(f"/api/projects/{pid}/backdrop").json()
    assert r == {"url": f"/api/projects/{pid}/runs/20261029T000000-aa/artifacts/01_preprocess/page.png",
                 "px_to_mm": [12.9, 0, -5000, 0, -12.9, 15000]}


def test_validate_survives_a_broken_ocr_file(client, project_with_gt):
    """M8 final review I4: unreadable stage-2 files only drop the leak tasks; the dry run still answers."""
    pid = project_with_gt
    st = client.app.state.storage.project_dir(pid) / "runs" / "20261029T000000-aa" / "stages" / "02_grid"
    st.mkdir(parents=True)
    (st / "ocr.json").write_text("{not json")
    (st / "grid.json").write_text("{}")
    r = client.post(f"/api/projects/{pid}/specs/validate", json={"base_version": 1, "ops": []})
    assert r.status_code == 200 and isinstance(r.json()["tasks"], list)


def test_commit_names_a_room_from_the_label_inside_it(client, project_with_gt, monkeypatch):
    from shapely.geometry import Polygon

    from core.spec.rooms import RoomLabel
    from server.routes import specs as routes

    spec = client.get(f"/api/projects/{project_with_gt}/specs/HEAD").json()
    room = spec["rooms"][0]
    p = Polygon(room["polygon"]).representative_point()
    monkeypatch.setattr(routes, "_labels", lambda *_: [RoomLabel((p.x, p.y), "R.CABLEVAULT", "cable_vault")])
    ops = [{"op": "rename_room", "id": room["id"], "name": ""}]
    r = client.post(f"/api/projects/{project_with_gt}/specs", json={"base_version": spec["meta"]["version"], "ops": ops})
    assert r.status_code == 201
    saved = next(x for x in r.json()["spec"]["rooms"] if x["id"] == room["id"])
    assert saved["name"] == "R.CABLEVAULT"


def _plan(client, pid, ops=(), room_ids=("R1", "R22")):
    return client.post(f"/api/projects/{pid}/specs/merge-plan",
                       json={"base_version": 1, "ops": list(ops), "room_ids": list(room_ids)})


def test_merge_plan_returns_ops_and_writes_nothing(client, project_with_gt):
    r = _plan(client, project_with_gt)
    assert r.status_code == 200 and r.json()["ops"][0]["op"] == "set_wall_divides"
    assert len(client.get(f"/api/projects/{project_with_gt}/specs").json()) == 1


def test_merge_plan_sees_unsaved_ops(client, project_with_gt):
    first = _plan(client, project_with_gt).json()["ops"]
    r = _plan(client, project_with_gt, first)  # those ops already joined the two rooms
    assert r.status_code == 400 and r.json()["error"]["code"] == "merge_refused"


def test_merge_plan_refusal_is_400(client, project_with_gt):
    r = _plan(client, project_with_gt, room_ids=["R1", "R999"])
    assert r.status_code == 400 and r.json()["error"]["message"] == "Pilih minimal dua ruangan"


def test_unmerge_plan_gives_the_wall_back(client, project_with_gt):
    pid = project_with_gt
    ops = _plan(client, pid).json()["ops"]
    room = next(r for r in client.post(f"/api/projects/{pid}/specs/validate", json={"base_version": 1, "ops": ops}).json()["rooms"]
                if r["id"] in ("R1", "R22"))
    r = client.post(f"/api/projects/{pid}/specs/unmerge-plan", json={"base_version": 1, "ops": ops, "room_id": room["id"]})
    assert r.status_code == 200 and r.json()["ops"] == [{**ops[0], "divides": True}]
