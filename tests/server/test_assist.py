import json

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
