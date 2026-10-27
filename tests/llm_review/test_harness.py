import itertools
import json
import math

import numpy as np

from core.extraction.rooms.overlay import px_from_mm
from core.llm_review.harness import ReviewInputs, run_review, select_for_review
from core.spec.models import Provenance, Wall
from core.spec.validate import Issue, ValidationContext
from tests.llm_review.conftest import FakeStrata, element_of
from tests.spec.fixtures import spec_with_rooms

INF = math.inf


def cv(conf: float) -> Provenance:
    return Provenance(source="cv", confidence=conf)


def review_spec():
    """Two rooms; W1 a real wall (0.5), W6 a stray dangling line (0.4, V004); deleting W6 lifts the score."""
    s = spec_with_rooms()
    for w in s.walls:
        w.provenance = cv(0.9)
    for o in s.openings:
        o.provenance = cv(0.5)
    for r in s.rooms:
        r.provenance = cv(1.0)
    s.walls[0].provenance = cv(0.5)
    s.walls.append(Wall(id="W6", a=(1000, 3000), b=(3000, 3000), thickness=100, kind="partition", provenance=cv(0.4)))
    return s


def inputs(labels=()):
    return ReviewInputs(page=np.full((600, 1000), 255, np.uint8), to_px=px_from_mm([10, 0, 0, 0, -10, 6000]),
                        mm_per_px=10, hatch=None, texts=[], labels=list(labels), vctx=ValidationContext())


def t1(answers: dict, doors: dict | None = None):
    """FakeStrata answering T1 by element (a list cycles through votes) and T2 with `doors`."""
    counters = {}

    def script(messages, kw):
        el = element_of(messages)
        n = counters.get(el, 0)
        counters[el] = n + 1
        if kw["schema"].__name__ == "T2Answer":
            return (doors or {}).get(el) or {"id": el, "is_door": True, "door_type": "single_swing", "hinge": "start", "swing": "left"}
        a = answers.get(el, "wall")
        a = a[n % len(a)] if isinstance(a, list) else a
        if isinstance(a, Exception) or a not in ("wall", "annotation", "unsure"):
            return a  # an exception (Strata down) or raw text (invalid output)
        return {"id": el, "verdict": a}

    return FakeStrata(script)


def run(spec, fake, tmp_path, **kw):
    args = {"tasks": {"T1"}, "votes": 3, "max_iter": 0, "deadline": INF, "out": tmp_path, "version": 1} | kw
    return run_review(spec, kw.pop("inputs", inputs()), fake, **{k: v for k, v in args.items() if k != "inputs"})


def decisions(tmp_path) -> dict:
    return {d["element"]: d for d in json.loads((tmp_path / "decisions.json").read_text())}


def test_select_skips_confident_and_human_edited():
    s = review_spec()
    s.walls[3].provenance = Provenance(source="editor", confidence=0.3)  # W4: a person drew it
    s.openings[1].provenance = cv(0.95)  # D2 confident
    assert select_for_review(s, [], {"T1", "T2"}) == [("T1", "W6"), ("T1", "W1"), ("T2", "D1")]
    flagged = [Issue("V005", "warning", ["W2"], "x")]
    assert ("T1", "W2") in select_for_review(s, flagged, {"T1"})  # 0.9 but referenced by a warning
    # W1 and D1 tie at 0.5: (confidence, id) puts D1 first, then the result is ordered T1 before T2
    assert select_for_review(s, [], {"T1", "T2"}, limit=2) == [("T1", "W6"), ("T2", "D1")]
    assert select_for_review(s, [], {"T2"}) == [("T2", "D1")]


def test_phase_a_accepts_majority_delete(tmp_path):
    s = review_spec()
    r = run(s, t1({"W6": "annotation"}), tmp_path)
    assert r.ops == [{"op": "delete_wall", "id": "W6", "reason": "strata: annotation"}]
    assert r.score_after > r.score_before and all(w.id != "W6" for w in r.spec.walls)
    d = decisions(tmp_path)
    assert d["W6"]["decision"] == "accepted" and d["W1"]["decision"] == "no_change"
    assert d["W6"]["score_before"] < d["W6"]["score_after"] and d["W6"]["verdict"] == {"id": "W6", "verdict": "annotation"}


def test_vote3_skipped_when_first_two_agree(tmp_path):
    f = t1({"W6": "annotation"})
    run(review_spec(), f, tmp_path)
    w6 = [c for c in f.calls if c["element"] == "W6"]
    assert [c["temperature"] for c in w6] == [0, 0.4]
    assert all(c["effort"] == "none" for c in w6)


def test_votes_use_zoomed_crops(tmp_path):
    run(review_spec(), t1({"W6": ["annotation", "wall", "annotation"]}), tmp_path)
    crops = tmp_path / "crops"
    assert {"W6_v1.png", "W6_v2.png", "W6_v3.png", "W6_ctx.png"} <= {p.name for p in crops.iterdir()}


def test_no_consensus_changes_nothing(tmp_path):
    s = review_spec()
    r = run(s, t1({"W6": ["annotation", "wall", "unsure"]}), tmp_path)
    assert r.ops == [] and r.spec == s and decisions(tmp_path)["W6"]["decision"] == "no_consensus"


def test_score_drop_rejected(tmp_path):
    r = run(review_spec(), t1({"W1": "annotation"}), tmp_path)
    d = decisions(tmp_path)["W1"]
    assert d["decision"] == "rejected" and d["reason"] == "score_drop" and r.ops == []
    assert d["score_after"] < d["score_before"]


def test_invalid_output_and_dead_strata_continue(tmp_path):
    s = review_spec()
    r = run(s, t1({"W6": "not json at all", "W1": ConnectionError("down")}), tmp_path)
    d = decisions(tmp_path)
    assert d["W6"]["decision"] == "invalid_output" and d["W1"]["decision"] == "invalid_output"
    assert r.spec == s and r.invalid >= 2


def test_deadline_stops_before_next_call(tmp_path):
    f = t1({"W6": "annotation"})
    clock = itertools.chain([0, 0], itertools.repeat(999)).__next__
    r = run(review_spec(), f, tmp_path, deadline=10, clock=clock)
    assert r.timed_out and len(f.calls) == 2 and r.ops == [{"op": "delete_wall", "id": "W6", "reason": "strata: annotation"}]


def test_phase_b_feedback_and_strict_gate(tmp_path):
    replies = iter([{"tool_calls": [{"name": "delete_wall", "arguments": {"id": "W3", "reason": "dim"}}]},
                    {"tool_calls": [{"name": "delete_wall", "arguments": {"id": "W6", "reason": "dim"}}]},
                    {"tool_calls": [{"name": "finish", "arguments": {"summary": "ok"}}]}])
    f = FakeStrata(lambda m, kw: next(replies))
    r = run(review_spec(), f, tmp_path, tasks={"T4"}, max_iter=5)
    assert r.ops == [{"op": "delete_wall", "id": "W6", "reason": "dim"}]
    assert len(f.calls) == 2  # no issue left after W6 went, so no third turn
    assert "rejected: confidence>=0.8:W3" in json.dumps(f.calls[1]["messages"])
    assert f.calls[0]["effort"] == "medium" and f.calls[0]["tools"]
    d = [x for x in json.loads((tmp_path / "decisions.json").read_text()) if x["task"] == "T4"]
    assert [(x["element"], x["decision"], x["reason"]) for x in d] == [
        ("W3", "rejected", "confidence>=0.8:W3"), ("W6", "accepted", None)]


def test_phase_b_finish_ends_loop(tmp_path):
    f = FakeStrata(lambda m, kw: {"tool_calls": [{"name": "finish", "arguments": {"summary": "none"}}]})
    r = run(review_spec(), f, tmp_path, tasks={"T4"}, max_iter=5)
    assert len(f.calls) == 1 and r.ops == []


def test_t3_runs_on_rooms_of_current_spec(tmp_path):
    s = review_spec()
    s.rooms[0].type, s.rooms[0].name = "other", ""
    f = FakeStrata(lambda m, kw: {"id": "R1", "type": "pantry", "name_normalized": "PANTRY"})
    r = run(s, f, tmp_path, tasks={"T3"}, inputs=inputs(labels=[("PANTRI", (2000, 2000))]))
    assert {"op": "set_room_type", "id": "R1", "type": "pantry"} in r.ops
    assert {"op": "rename_room", "id": "R1", "name": "PANTRY"} in r.ops
    assert f.calls[0]["effort"] == "none" and "PANTRI" in json.dumps(f.calls[0]["messages"][-1])
    assert all(c["element"] == "R1" for c in f.calls)  # R2 is named and typed: not asked


def test_transcript_lines_follow_schema(tmp_path):
    run(review_spec(), t1({"W6": "annotation"}), tmp_path)
    line = json.loads((tmp_path / "transcript.jsonl").read_text().splitlines()[0])
    assert {"ts", "task", "element", "prompt_version", "vote", "request", "response", "latency_ms", "tokens"} <= line.keys()
    assert line["prompt_version"] == "v1" and line["request"]["effort"] == "none"
    assert {"raw", "parsed", "valid"} <= line["response"].keys()
    assert (tmp_path / line["request"]["messages_ref"]).exists()


def test_events_emitted(tmp_path):
    events = []
    run(review_spec(), t1({"W6": "annotation"}), tmp_path, emit=lambda t, d: events.append((t, d)))
    assert events and events[0][0] == "llm.decision"
    assert {"element", "task", "verdict", "accepted", "score_before", "score_after"} <= events[0][1].keys()
    assert next(d for t, d in events if d["element"] == "W6")["accepted"] is True


def test_fewshot_only_for_tasks_that_gained_from_it(tmp_path):
    """benchmarks/DECISIONS.md: few-shot raised T1's accuracy but dropped its delete precision to 0.76."""
    import cv2

    for task in ("T1", "T3"):
        d = tmp_path / "shots" / task
        d.mkdir(parents=True)
        cv2.imwrite(str(d / "x.png"), np.zeros((8, 8, 3), np.uint8))
        answer = {"id": "W9", "verdict": "wall"} if task == "T1" else {"id": "R9", "type": "office", "name_normalized": "X"}
        (d / "items.json").write_text(json.dumps([{"element": "W9", "evidence": "Element W9", "label": "X",
                                                   "answer": answer, "image": None, "context": None}]))
    s = review_spec()
    s.rooms[0].type, s.rooms[0].name = "other", ""

    def script(messages, kw):
        el = element_of(messages)
        if kw["schema"].__name__ == "T3Answer":
            return {"id": el, "type": "pantry", "name_normalized": "PANTRY"}
        return {"id": el, "verdict": "wall"}

    f = FakeStrata(script)
    run(s, f, tmp_path / "out", tasks={"T1", "T3"}, fewshot_root=tmp_path / "shots",
        inputs=inputs(labels=[("PANTRI", (2000, 2000))]))
    t1 = next(c for c in f.calls if c["schema"].__name__ == "T1Answer")
    t3 = next(c for c in f.calls if c["schema"].__name__ == "T3Answer")
    assert len(t1["messages"]) == 2 and len(t3["messages"]) == 4  # system + question; T3 adds one example pair


# --- final review fixes ---------------------------------------------------------------------------------------------

def test_malformed_tool_call_is_rejected_not_a_crash(tmp_path):
    replies = iter([{"tool_calls": [{"name": "merge_walls", "arguments": {"ids": [1, 2], "reason": "x"}}]},
                    {"tool_calls": [{"name": "merge_walls", "arguments": {"ids": None, "reason": "x"}}]},
                    {"tool_calls": [{"name": "delete_wall", "arguments": "oops"}]},
                    {"tool_calls": [{"name": "finish", "arguments": {"summary": "ok"}}]}])
    r = run(review_spec(), FakeStrata(lambda m, kw: next(replies)), tmp_path, tasks={"T4"}, max_iter=5)
    t4 = [d for d in r.decisions if d["task"] == "T4"]
    assert [d["decision"] for d in t4] == ["rejected"] * 3 and all(d["reason"].startswith("bad_args") for d in t4)


def test_phase_a_drops_bounded_by_the_stage5_score(tmp_path, monkeypatch):
    """Each delete costs 0.004 (inside the 0.005 tolerance); together they may not fall below stage 5 - 0.005."""
    import core.llm_review.harness as h
    from core.spec.validate import ValidationResult

    s = review_spec()
    s.walls[1].provenance = cv(0.45)  # W2 is reviewed too
    n0 = len(s.walls)
    monkeypatch.setattr(h, "validate", lambda spec, ctx=None: ValidationResult(0.9 - 0.004 * (n0 - len(spec.walls)), True, []))
    r = run(s, t1({"W6": "annotation", "W2": "annotation", "W1": "annotation"}), tmp_path)
    assert len(r.ops) == 1 and r.score_after >= r.score_before - 0.005
    assert sum(d["reason"] == "score_drop" for d in r.decisions) == 2


def test_answer_about_another_element_is_rejected(tmp_path):
    f = FakeStrata(lambda m, kw: {"id": "W1", "verdict": "annotation"} if element_of(m) == "W6" else
                   {"id": element_of(m), "verdict": "wall"})
    r = run(review_spec(), f, tmp_path)
    d = decisions(tmp_path)["W6"]
    assert d["decision"] == "rejected" and d["reason"] == "wrong_id" and r.ops == []


def test_wrong_id_vote_does_not_beat_a_correct_majority(tmp_path):
    votes = iter([{"id": "W1", "verdict": "wall"}, {"id": "W6", "verdict": "annotation"},
                  {"id": "W6", "verdict": "annotation"}])
    f = FakeStrata(lambda m, kw: next(votes) if element_of(m) == "W6" else {"id": element_of(m), "verdict": "wall"})
    run(review_spec(), f, tmp_path)
    assert decisions(tmp_path)["W6"]["decision"] == "accepted"


def test_refused_change_is_rejected_with_reason(tmp_path, monkeypatch):
    """W2 (confidence 0.9) reached review through a validator warning; T1 may not delete it."""
    import core.llm_review.harness as h

    monkeypatch.setattr(h, "select_for_review", lambda spec, issues, tasks, limit=60: [("T1", "W2")])
    r = run(review_spec(), t1({"W2": "annotation"}), tmp_path)
    d = decisions(tmp_path)["W2"]
    assert d["decision"] == "rejected" and d["reason"] == "confidence>=0.8" and r.ops == []


def test_cancel_stops_the_review(tmp_path):
    import threading

    cancel = threading.Event()

    def script(messages, kw):
        cancel.set()  # the user cancels while the first call runs
        return {"id": element_of(messages), "verdict": "annotation"}

    r = run(review_spec(), FakeStrata(script), tmp_path, cancelled=cancel)
    assert r.cancelled and len([d for d in r.decisions if d["element"] == "W1"]) == 0


def test_dead_strata_stops_the_review_after_three_transport_errors(tmp_path):
    s = review_spec()
    s.walls[1].provenance = cv(0.3)
    s.walls[2].provenance = cv(0.35)
    f = FakeStrata(lambda m, kw: ConnectionError("refused"))
    r = run(s, f, tmp_path)
    assert r.aborted and len(f.calls) == 3
