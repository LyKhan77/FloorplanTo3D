from pathlib import Path

import pytest

from tests.builder.helpers import skip_without_blender
from tests.server.conftest import client_events, wait_status


@pytest.mark.blender
@pytest.mark.slow
@skip_without_blender
def test_import_regenerate_download(app_factory, plan_bytes):
    with app_factory() as client:  # real stage implementations and real Blender
        pid = client.post("/api/projects", files={"file": ("plan.jpeg", plan_bytes, "image/jpeg")},
                          data={"name": "Gatsu", "start": "false"}).json()["project_id"]
        r = client.post(f"/api/projects/{pid}/specs/import", content=Path("benchmarks/gatsu/gt_spec.json").read_bytes(),
                        headers={"content-type": "application/json"})
        assert r.status_code == 201
        rid = client.post(f"/api/projects/{pid}/regenerate", json={"version": "HEAD"}).json()["run_id"]
        run = wait_status(client, pid, rid, {"succeeded", "needs_attention", "failed"}, timeout=180)
        # stage 8 is needs_attention: Gatsu IoU 0.45 < 0.70 with the M2 mask (benchmarks/reports/m2-verify.md)
        assert [s["status"] for s in run["stages"][7:]] == ["succeeded", "needs_attention", "succeeded", "succeeded"], run
        outs = client.get(f"/api/projects/{pid}/outputs").json()
        assert outs[0]["version"] == 1 and {"shell.glb", "report.pdf", "layout.blend"} <= {f["name"] for f in outs[0]["files"]}
        assert client.get(f"/api/projects/{pid}/outputs/1/report.html").status_code == 200
        events = [e for e in client_events(client, pid) if e["run_id"] == rid]
        assert any(e["type"] == "stage.progress" for e in events)
        assert any(e["type"] == "output.ready" and e["data"]["version"] == 1 for e in events)
        assert events[-1]["type"] == "run.finished"
        assert client.post(f"/api/projects/{pid}/regenerate", json={"version": 1}).json() == {"run_id": None,
                                                                                              "reused": True}
