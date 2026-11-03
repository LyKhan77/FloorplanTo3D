import json
from pathlib import Path

import pytest

from core.llm_review.client import CallResult

BOX = [5000, 6000, 7000, 11700]  # around GT wall W43 (x = 5790)


class FakeClient:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def ask_json(self, messages, schema, **kw):
        self.calls.append(messages)
        a = self.answers.pop(0)
        return CallResult(raw=json.dumps(a), parsed=schema.model_validate(a).model_dump(), valid=True, error=None,
                          latency_ms=5)


@pytest.fixture
def fake(setup_client):
    holder = FakeClient([])
    setup_client.app.state.assist_client_factory = lambda: holder
    return holder


def events(r) -> list[tuple[str, dict]]:
    out = []
    for block in r.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def post(client, pid, **body):
    return client.post(f"/api/projects/{pid}/assist/area",
                       json={"base_version": 1, "ops": [], "box": BOX, "selection": [], "message": "hapus W43"} | body)


def test_stream_sends_session_steps_and_proposal(setup_client, project_with_gt, fake):
    fake.answers.append({"question": None, "actions": [{"type": "delete_wall", "id": "W43"}], "explanation": "x"})
    r = post(setup_client, project_with_gt)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = events(r)
    assert ev[0][0] == "session" and ev[-1][0] == "done"
    p = next(d for e, d in ev if e == "proposal")
    assert p["ops"][0] == {"op": "delete_wall", "id": "W43", "reason": "asisten: hapus W43"}


def test_followup_uses_the_session(setup_client, project_with_gt, fake):
    fake.answers += [{"question": "Yang mana?", "actions": [], "explanation": ""},
                     {"question": None, "actions": [{"type": "delete_wall", "id": "W43"}], "explanation": "x"}]
    ev = events(post(setup_client, project_with_gt, message="hapus ini"))
    sid = ev[0][1]["session_id"]
    assert ("question", {"text": "Yang mana?"}) in ev
    ev = events(post(setup_client, project_with_gt, session_id=sid, message="W43"))
    assert ev[0][0] != "session" and any(e == "proposal" for e, _ in ev)
    assert "Yang mana?" in json.dumps(fake.calls[1])
    r = post(setup_client, project_with_gt, session_id="nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_session"


def test_without_run_no_image(setup_client, project_with_gt, fake):
    fake.answers.append({"question": "Apa?", "actions": [], "explanation": ""})
    ev = events(post(setup_client, project_with_gt))
    assert "image_url" not in json.dumps(fake.calls[0])
    assert any(e == "step" and "Tanpa gambar" in d["text"] for e, d in ev)


def test_decision_is_logged(setup_client, project_with_gt, fake, data_dir):
    fake.answers.append({"question": None, "actions": [{"type": "delete_wall", "id": "W43"}], "explanation": "x"})
    sid = events(post(setup_client, project_with_gt))[0][1]["session_id"]
    r = setup_client.post(f"/api/projects/{project_with_gt}/assist/area/{sid}/decision", json={"accepted": True})
    assert r.status_code == 204
    log = next(data_dir.rglob(f"assist/{sid}.json"))
    assert json.loads(log.read_text())["decisions"][-1]["accepted"] is True


def test_drawn_box_needs_a_run(setup_client, project_with_gt):
    r = setup_client.post(f"/api/projects/{project_with_gt}/assist/drawn-box", json={"at": [1000, 1000]})
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_run"


def test_drawn_boxes_reach_the_context(setup_client, project_with_gt, fake):
    fake.answers.append({"question": "UPS atau baterai?", "actions": [], "explanation": ""})
    k1 = {"id": "K1", "center": [6000, 8000], "size": [800, 1200], "rotation": 0}
    events(post(setup_client, project_with_gt, drawn=[k1], message="K1 itu apa"))
    assert "K1" in json.dumps(fake.calls[0])


def test_a_box_that_is_a_whole_room_is_no_drawn_box():
    from core.spec.models import Spec
    from server.routes.assist import _room_of_box

    gt = Spec.model_validate_json(Path("benchmarks/gatsu/gt_spec.json").read_text())
    r = next(r for r in gt.rooms if r.id == "R34")  # AHU ROOM
    from shapely.geometry import Polygon

    x0, y0, x1, y1 = Polygon(r.polygon).bounds
    whole = {"center": [(x0 + x1) / 2, (y0 + y1) / 2], "size": sorted([x1 - x0, y1 - y0]),
             "rotation": 0 if y1 - y0 >= x1 - x0 else 90}
    assert _room_of_box(gt, whole) == "R34"
    small = {**whole, "size": [600, 1200]}
    assert _room_of_box(gt, small) is None


def test_installation_layer_reads_installation_objects(setup_client, project_with_gt, fake, library_dir):
    import shutil

    from core.installation.ops import apply as inst_apply
    from core.installation.store import InstallationStore

    c, pid = setup_client, project_with_gt
    shutil.copytree(library_dir, c.app.state.storage.templates_dir, dirs_exist_ok=True)
    c.post(f"/api/projects/{pid}/installations/start", json={})
    crac = {"op": "add_object", "template_id": "crac-unit-generic", "template_version": "1.1.0",
            "position": [6500, 9000, 0], "rotation": 0, "dims": [2500, 900, 1950]}  # inside BOX
    rack = {"type": "place_drawn", "boxes": ["K1"], "template": "rack-42u-600x1200"}
    fake.answers.append({"question": None, "actions": [rack], "explanation": "x"})
    k1 = {"id": "K1", "center": [12000, 8000], "size": [600, 1200], "rotation": 0}
    ev = events(post(c, pid, layer="installation", base_version=1, ops=[crac], drawn=[k1], message="K1 itu rack"))
    assert "crac-unit-generic" in json.dumps(fake.calls[0])
    p = next((d for e, d in ev if e == "proposal"), None)
    assert p is not None, [e for e in ev if e[0] != "session"][3:]
    inst = InstallationStore(c.app.state.storage.project_dir(pid) / "installations").load("HEAD")
    after = inst_apply(inst, [crac, *p["ops"]], "editor", 2)  # the proposal's ops are installation ops
    assert len(after.objects) == 2
