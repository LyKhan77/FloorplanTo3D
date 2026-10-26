import hashlib
import io
import shutil
import zipfile

import pytest


def test_output_file_etag_and_304(client_with_outputs):
    client, pid = client_with_outputs
    r = client.get(f"/api/projects/{pid}/outputs/1/shell.glb")
    assert r.status_code == 200 and r.headers["etag"].strip('"') == hashlib.sha256(r.content).hexdigest()
    # a full or from-stage run republishes v<HEAD>, so browsers must revalidate (cheap 304) instead of trusting a cache
    assert r.headers["cache-control"] == "no-cache"
    again = client.get(f"/api/projects/{pid}/outputs/1/shell.glb", headers={"If-None-Match": r.headers["etag"]})
    assert again.status_code == 304
    listing = client.get(f"/api/projects/{pid}/outputs").json()
    assert listing[0]["version"] == 1 and "top.png" in listing[0]["renders"]
    assert {f["name"] for f in listing[0]["files"]} == {"shell.glb", "report.html"}


def test_output_file_traversal_404(client_with_outputs):
    client, pid = client_with_outputs
    for bad in ("..%2F..%2Fproject.json", "%2Fetc%2Fpasswd", "renders/..%2F..%2F..%2Fproject.json"):
        assert client.get(f"/api/projects/{pid}/outputs/1/{bad}").status_code == 404
    assert client.get(f"/api/projects/{pid}/outputs/9/shell.glb").status_code == 404


def test_bundle_zip_contains_files(client_with_outputs):
    client, pid = client_with_outputs
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/api/projects/{pid}/outputs/1/bundle.zip").content))
    assert {"shell.glb", "report.html", "renders/top.png"} <= set(z.namelist())


@pytest.mark.blender
def test_templates_listing_hides_invalid(app_factory, data_dir, placeholder_root):
    shutil.copytree(placeholder_root, data_dir / "templates")
    (data_dir / "templates" / "pdu-floor-generic" / "1.0.0" / "asset.glb").write_bytes(b"broken")
    with app_factory() as client:
        templates = client.get("/api/templates").json()
        ids = {t["id"] for t in templates}
        assert "rack-42u-600x1200" in ids and "pdu-floor-generic" not in ids
        assert {t["id"] for t in client.get("/api/templates?category=rack").json()} == {"rack-42u-600x1200",
                                                                                         "rack-48u-800x1200"}
        assert client.get("/api/templates/rack-42u-600x1200/1.0.0/thumbnail.png").status_code == 200
        assert client.get("/api/templates/rack-42u-600x1200/1.0.0/asset.glb").content[:4] == b"glTF"
        assert client.get("/api/templates/rack-42u-600x1200/1.0.0").json()["dims"]["h"] == 2000


def test_health_reports_strata_down(app_factory):
    with app_factory(env={"STRATA_BASE_URL": "http://127.0.0.1:9/v1"}) as client:
        h = client.get("/api/health").json()
        assert h["server"] == "ok" and h["strata"]["ok"] is False
        assert set(h["queue"]) >= {"waiting", "running"} and set(h["blender"]) >= {"ok", "version", "busy"}


def test_config_has_no_secrets(client):
    c = client.get("/api/config").json()
    assert c["schema_version"] == "1.0" and c["max_upload_mb"] == 50 and "llm_tasks_enabled" in c


def test_profiles(client):
    assert client.get("/api/profiles").json() == []
    assert client.post("/api/profiles", json={"name": "x", "from_run": "a/b"}).status_code == 404  # unknown run (saving profiles: M5c)


def test_bundle_streams_large_outputs_in_chunks(client_with_outputs, data_dir):
    """Iterating a binary spool yields one chunk per b'\\n' (~80k threadpool hops for 20 MB): seconds per download."""
    import os
    import time

    client, pid = client_with_outputs
    blob = os.urandom(20 << 20)
    (data_dir / "projects" / pid / "outputs" / "v1" / "layout.blend").write_bytes(blob)
    t0 = time.monotonic()
    r = client.get(f"/api/projects/{pid}/outputs/1/bundle.zip")
    elapsed = time.monotonic() - t0
    assert zipfile.ZipFile(io.BytesIO(r.content)).read("layout.blend") == blob
    assert elapsed < 2.0, f"bundle took {elapsed:.1f}s"
