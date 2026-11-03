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
    """Nothing left to propose: the chat says why instead of showing an empty card with Terima disabled."""
    c = FakeClient(act({"type": "delete_wall", "id": "W99"}), act({"type": "delete_wall", "id": "W98"}))
    ev = turn(c, new(), "hapus", tmp_path)
    assert len(c.calls) == 2 and not any(e["event"] == "proposal" for e in ev)
    assert kinds(ev)[-2:] == ["error", "done"] and "W98" in ev[-2]["text"]


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
    assert kinds(ev)[-2] == "error" and "W5" in ev[-2]["text"]


def test_an_unexpected_failure_is_an_error_event(tmp_path, monkeypatch):
    from core.assist import session

    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(session, "translate", boom)
    ev = turn(FakeClient(act({"type": "delete_wall", "id": "W5"})), new(), "hapus", tmp_path)
    assert kinds(ev)[-2:] == ["error", "done"] and "bug" in ev[-2]["text"]


def test_a_reply_to_an_open_proposal_is_a_revision(tmp_path):
    c = FakeClient(act({"type": "delete_wall", "id": "W5"}), act({"type": "delete_wall", "id": "W5"}))
    s = new()
    turn(c, s, "hapus dinding tengah", tmp_path)
    turn(c, s, "pintunya jangan ikut hilang", tmp_path)
    last = text(c.calls[1][-1:])
    assert "NOT applied" in last and "complete" in last and "W5" in last and "pintunya jangan ikut hilang" in last
    assert s.decisions == [{"proposal": 0, "revised": True}]


def test_after_a_decision_a_message_is_a_new_request(tmp_path):
    c = FakeClient(act({"type": "delete_wall", "id": "W5"}), ask("Apa lagi?"))
    s = new()
    turn(c, s, "hapus dinding tengah", tmp_path)
    s.decisions.append({"proposal": 0, "accepted": False})
    turn(c, s, "sekarang ruang kiri jadi kantor", tmp_path)
    assert "NOT applied" not in text(c.calls[1][-1:])


def test_fill_question_first(tmp_path, library_dir):
    c = FakeClient(ask("Ruang ini data hall 4,8 x 5,8 m. Usul: rack 42U berbaris dengan containment. Berapa rack?"))
    ev = list(run_turn(c, new(), "isi ruang ini", spec_with_rooms(), [], None, None, None, tmp_path,
                       templates_dir=library_dir))
    assert kinds(ev)[-2] == "question"
    assert "rack-42u-600x1200" in text(c.calls[0])  # the library reaches Strata


def test_o001_triggers_revision(tmp_path, library_dir):
    ks = [{"id": "K1", "center": [2500, 3000], "size": [800, 1200], "rotation": 90},
          {"id": "K2", "center": [2700, 3000], "size": [800, 1200], "rotation": 90}]
    bad = act({"type": "place_drawn", "boxes": ["K1", "K2"], "template": "ups-cabinet-generic"})
    good = act({"type": "place_drawn", "boxes": ["K1"], "template": "ups-cabinet-generic"})
    c = FakeClient(bad, good)
    ev = list(run_turn(c, new(), "K1 K2 itu UPS", spec_with_rooms(), [], None, None, None, tmp_path,
                       templates_dir=library_dir, drawn=ks))
    p = next(e for e in ev if e["event"] == "proposal")
    assert len(c.calls) == 2 and p["valid"] and len(p["objects"]) == 1


def test_an_empty_result_still_says_why(tmp_path, monkeypatch):
    from core.assist import session
    from core.assist.plan import Translation

    monkeypatch.setattr(session, "translate", lambda *a, **k: Translation())
    c = FakeClient(act({"type": "delete_wall", "id": "W5"}), act({"type": "delete_wall", "id": "W5"}))
    ev = turn(c, new(), "isi", tmp_path)
    assert kinds(ev)[-2] == "error" and ": ." not in ev[-2]["text"] and len(ev[-2]["text"]) > 40
