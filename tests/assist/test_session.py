import json

from core.assist.session import Session, run_turn
from core.llm_review.client import CallResult
from tests.spec.fixtures import spec_with_rooms

BOX = (4000, 1000, 6000, 5000)


class FakeClient:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls: list[list[dict]] = []

    def ask_json(self, messages, schema, **kw):
        self.calls.append(messages)
        a = self.answers.pop(0)
        if isinstance(a, CallResult):
            return a
        return CallResult(raw=json.dumps(a), parsed=schema.model_validate(a).model_dump(), valid=True, error=None,
                          latency_ms=5)


def ask(text):
    return {"question": text, "actions": [], "explanation": ""}


def act(*actions):
    return {"question": None, "actions": list(actions), "explanation": "rapi"}


def turn(client, session, message, tmp_path, ops=()):
    return list(run_turn(client, session, message, spec_with_rooms(), list(ops), None, None, None, tmp_path))


def new(selection=()):
    return Session(id="s1", project_id="p", box=BOX, selection=list(selection))


def kinds(events):
    return [e["event"] for e in events]


def text(messages) -> str:
    out = []
    for m in messages:
        c = m["content"]
        out += [c] if isinstance(c, str) else [p.get("text", "") for p in c]
    return "\n".join(out)


def test_question_then_proposal(tmp_path):
    c = FakeClient(ask("Dinding mana?"), act({"type": "delete_wall", "id": "W5"}))
    s = new()
    ev = turn(c, s, "hapus ini", tmp_path)
    assert kinds(ev)[-2:] == ["question", "done"] and ev[-2]["text"] == "Dinding mana?"
    assert any(e["event"] == "step" and "Strata" in e["text"] for e in ev)
    ev = turn(c, s, "W5", tmp_path)
    p = next(e for e in ev if e["event"] == "proposal")
    assert p["valid"] is True and p["ops"][0]["op"] == "delete_wall" and p["deleted"] == ["W5"]
    assert "hapus ini" in text(c.calls[1]) and "Dinding mana?" in text(c.calls[1])
    log = json.loads((tmp_path / "s1.json").read_text())
    assert len(log["proposals"]) == 1 and log["questions"] == 1


def test_invalid_plan_gets_one_revision(tmp_path):
    c = FakeClient(act({"type": "delete_wall", "id": "W99"}), act({"type": "delete_wall", "id": "W5"}))
    ev = turn(c, new(), "hapus dinding tengah", tmp_path)
    assert len(c.calls) == 2 and "W99" in text(c.calls[1][-1:])
    p = next(e for e in ev if e["event"] == "proposal")
    assert p["valid"] is True and p["deleted"] == ["W5"]


def test_still_invalid_after_revision(tmp_path):
    c = FakeClient(act({"type": "delete_wall", "id": "W99"}), act({"type": "delete_wall", "id": "W98"}))
    ev = turn(c, new(), "hapus", tmp_path)
    p = next(e for e in ev if e["event"] == "proposal")
    assert p["valid"] is False and len(c.calls) == 2


def test_new_validation_error_triggers_revision(tmp_path):
    """A door overlapping D1 is a new validation error: one revision, then invalid."""
    door = {"type": "add_opening", "wall": "W5", "category": "door", "at": [5000, 2400]}
    c = FakeClient(act(door), act(door))
    ev = turn(c, new(), "tambah pintu", tmp_path)
    p = next(e for e in ev if e["event"] == "proposal")
    assert len(c.calls) == 2 and p["valid"] is False and any(i["severity"] == "error" for i in p["issues"])


def test_fourth_question_is_an_error(tmp_path):
    c = FakeClient(*(ask(f"q{i}?") for i in range(4)))
    s = new()
    for i in range(3):
        assert kinds(turn(c, s, f"m{i}", tmp_path))[-2] == "question"
    ev = turn(c, s, "m3", tmp_path)
    assert kinds(ev)[-2:] == ["error", "done"] and "spesifik" in ev[-2]["text"]


def test_strata_down_is_an_error_event(tmp_path):
    down = CallResult(raw="", parsed=None, valid=False, error="timeout", latency_ms=0, transport=True)
    ev = turn(FakeClient(down), new(), "hapus", tmp_path)
    assert kinds(ev)[-2:] == ["error", "done"] and "Strata tidak tersedia" in ev[-2]["text"]


def test_selection_resolves_this(tmp_path):
    c = FakeClient(act({"type": "delete_wall", "id": "W5"}))
    turn(c, new(["W5"]), "hapus dinding ini", tmp_path)
    assert "terpilih: W5" in text(c.calls[0])


def test_local_ops_are_the_base(tmp_path):
    """The area is read from HEAD plus the unsaved local ops: a wall deleted locally is not offered to the LLM."""
    c = FakeClient(*[act({"type": "delete_wall", "id": "W5"})] * 2)
    ev = turn(c, new(), "hapus", tmp_path, ops=[{"op": "delete_wall", "id": "W5", "reason": "x"}])
    assert "W5 a=" not in text(c.calls[0])
    p = next(e for e in ev if e["event"] == "proposal")
    assert p["valid"] is False


def test_an_unexpected_failure_is_an_error_event(tmp_path, monkeypatch):
    import core.assist.session as session

    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(session, "translate", boom)
    ev = turn(FakeClient(act({"type": "delete_wall", "id": "W5"})), new(), "hapus", tmp_path)
    assert kinds(ev)[-2:] == ["error", "done"] and "bug" in ev[-2]["text"]
