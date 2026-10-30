import hashlib
import json


def _create(client, plan_bytes, **data):
    return client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")},
                       data={"start": "false", **data})


def test_create_project_stores_original_and_hash(client, data_dir, plan_bytes):
    r = _create(client, plan_bytes, name="MSC Gatsu L1", prompt="data hall", params='{"wall_height": 4500}')
    assert r.status_code == 201
    body = r.json()
    pid = body["project_id"]
    assert body["run_id"] is None and pid.startswith("msc-gatsu-l1-")
    d = data_dir / "projects" / pid
    assert (d / "input" / "original.jpg").read_bytes() == plan_bytes
    meta = json.loads((d / "input" / "input.json").read_text())
    assert meta["sha256"] == hashlib.sha256(plan_bytes).hexdigest() and meta["prompt"] == "data hall"
    detail = client.get(f"/api/projects/{pid}").json()
    assert detail["name"] == "MSC Gatsu L1" and detail["params"] == {"wall_height": 4500} and detail["head"] is None
    items = client.get("/api/projects").json()["items"]
    assert [p["project_id"] for p in items] == [pid] and items[0]["status"] == "new"


def test_upload_rejections_leave_no_project(client, data_dir):
    r = client.post("/api/projects", files={"file": ("x.jpg", b"hello", "image/jpeg")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_type"
    big = b"\xff\xd8\xff" + b"0" * (51 * 1024 * 1024)
    assert client.post("/api/projects", files={"file": ("big.jpg", big, "image/jpeg")}).status_code == 413
    projects = data_dir / "projects"
    assert not projects.exists() or not any(projects.iterdir())


def test_bad_params_json_400(client, plan_bytes):
    assert _create(client, plan_bytes, params="[1,2]").status_code == 400


def test_filename_sanitized(client, data_dir, plan_bytes):
    pid = client.post("/api/projects", files={"file": ("../../evil name.jpeg", plan_bytes, "image/jpeg")},
                      data={"start": "false"}).json()["project_id"]
    meta = json.loads((data_dir / "projects" / pid / "input" / "input.json").read_text())
    assert meta["filename"] == "evil_name.jpeg"


def test_patch_and_delete(client, plan_bytes):
    pid = _create(client, plan_bytes).json()["project_id"]
    assert client.patch(f"/api/projects/{pid}", json={"name": "Baru"}).json()["name"] == "Baru"
    assert client.get(f"/api/projects/{pid}/input").content[:3] == b"\xff\xd8\xff"
    assert client.delete(f"/api/projects/{pid}").status_code == 400
    assert client.delete(f"/api/projects/{pid}?confirm=true").status_code == 200
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_list_shows_drawing_fit_of_latest_output(client, data_dir, plan_bytes):
    """The list's quality column is the drawing fit; outputs from before it still show their IoU."""
    pid = _create(client, plan_bytes, name="fit").json()["project_id"]
    d = data_dir / "projects" / pid
    for v, verify in ((1, {"iou": 0.71}), (2, {"iou": 0.67, "drawing_fit": {"fit": 0.98}})):
        out = d / "outputs" / f"v{v}"
        out.mkdir(parents=True)
        (out / "shell.glb").write_bytes(b"glb")
        (out / "verify.json").write_text(json.dumps(verify))
    item = client.get("/api/projects").json()["items"][0]
    assert (item["fit"], item["iou"]) == (0.98, 0.67)
    (d / "outputs" / "v2" / "shell.glb").unlink()
    item = client.get("/api/projects").json()["items"][0]
    assert (item["fit"], item["iou"]) == (None, 0.71)
