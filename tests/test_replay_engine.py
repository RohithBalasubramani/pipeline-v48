"""tests/test_replay_engine.py — the replay engine's contracts, no live DB/LLM needed:
coding round-trip · tape exact/FIFO/repeat/fuzzy/strict · hooks pass-through/record/inject (all doors) ·
capture bundle persistence · ids resolution · compare severities · report rendering · clock freeze."""
import datetime as dt
import json
import os
from decimal import Decimal

import pytest

from replay import coding, store
from replay.recorder import Recorder, attach
from replay.tape import Tape, TapeMiss, content_key
from replay import hooks


# ── plumbing ─────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def traces_dir(tmp_path, monkeypatch):
    d = str(tmp_path / "traces")
    monkeypatch.setattr("replay.ids.TRACES_DIR", d)
    monkeypatch.setattr("replay.store.TRACES_DIR", d)
    return d


@pytest.fixture()
def session():
    """An active capture session: fresh obs trace + attached recorder. Yields the recorder."""
    from obs import trace as obs_trace
    t = obs_trace.new_trace(kind="test")
    rec = Recorder(t["trace_id"])
    attach(t, rec)
    yield rec
    obs_trace._TRACE.set(None)


def _tape_session(events, **kw):
    from obs import trace as obs_trace
    t = obs_trace.new_trace(kind="test-replay")
    rec = Recorder(t["trace_id"], tape=Tape(events, **kw))
    attach(t, rec)
    return rec


# ── coding ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_coding_roundtrip_types():
    v = [(dt.datetime(2026, 7, 12, 10, 30, tzinfo=dt.timezone.utc), dt.date(2026, 1, 2), Decimal("12.50"),
          b"\x00\x01", None, True, 3, 4.5, "x")]
    back = coding.decode(json.loads(json.dumps(coding.encode(v))))
    assert back == v
    assert isinstance(back[0], tuple) and isinstance(back[0][0], dt.datetime) and isinstance(back[0][2], Decimal)


def test_coding_dict_keys_and_lists():
    v = {"a": [1, {"b": (dt.date(2026, 3, 4),)}]}
    back = coding.decode(json.loads(json.dumps(coding.encode(v))))
    assert back == {"a": [1, {"b": (dt.date(2026, 3, 4),)}]}


# ── tape ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _llm_ev(stage, sysm, user, val, seq=1):
    return {"seq": seq, "kind": "llm", "key": content_key("llm", stage, sysm, user, None, None),
            "stage": stage, "system": sysm, "user": user, "outcome": "return", "value": val}


def test_tape_exact_fifo_and_repeat():
    e1, e2 = _llm_ev("route", "s", "u", {"n": 1}), _llm_ev("route", "s", "u", {"n": 2}, seq=2)
    tape = Tape([e1, e2])
    assert tape.lookup("llm", e1["key"]) == (e1, "hit")
    assert tape.lookup("llm", e1["key"]) == (e2, "hit")
    assert tape.lookup("llm", e1["key"]) == (e2, "repeat")     # drained → repeat last (idempotent reads)


def test_tape_fuzzy_and_unconsumed():
    e1, e2 = _llm_ev("route", "s", "uA", {"n": 1}), _llm_ev("l2_emit", "s", "uB", {"n": 2}, seq=2)
    tape = Tape([e1, e2])
    assert tape.llm_fuzzy("route") is e1                       # prompt drifted → same-stage order fallback
    assert tape.llm_fuzzy("route") is None
    assert [x["stage"] for x in tape.unconsumed_llm()] == ["l2_emit"]


def test_tape_unpinned_group_ignored():
    e = {"seq": 1, "kind": "sql.q", "key": "k", "outcome": "return", "rows": []}
    tape = Tape([e], pins=("llm",))
    assert not tape.pinned("sql")


# ── hooks: pass-through / record / inject ────────────────────────────────────────────────────────────────────────────

def test_hooks_pass_through_without_session():
    from obs import trace as obs_trace
    obs_trace._TRACE.set(None)
    assert hooks.llm(lambda s, u, **k: {"ok": 1}, "s", "u", stage="route") == {"ok": 1}
    assert hooks.db_q(lambda db, sql: [["r"]], "cmd_catalog", "SELECT 1") == [["r"]]
    assert hooks.db_rows(lambda sql, p: [(1,)], "sql.nx", "SELECT x", None) == [(1,)]


def test_hooks_record_llm_return_and_raise(session):
    assert hooks.llm(lambda s, u, **k: {"page": "energy"}, "sys", "usr", stage="route") == {"page": "energy"}
    from llm.client import LlmError
    with pytest.raises(LlmError):
        def _boom(s, u, **k):
            raise LlmError("timeout", "vllm down")
        hooks.llm(_boom, "sys", "usr", stage="route", on_error="raise")
    kinds = [e["kind"] for e in session.events]
    assert kinds == ["llm", "llm"]
    assert session.events[0]["outcome"] == "return" and session.events[1]["outcome"] == "raise"
    assert session.events[1]["error"]["kind"] == "timeout"


def test_hooks_record_db_q_error_and_inject_reraises(session):
    with pytest.raises(RuntimeError):
        def _fail(db, sql):
            raise RuntimeError("DB error (neuract): tunnel down")
        hooks.db_q(_fail, "neuract", "SELECT 1")
    rec2 = _tape_session(session.events)
    with pytest.raises(RuntimeError, match="tunnel down"):     # recorded failure re-raises VERBATIM on replay
        hooks.db_q(lambda db, sql: pytest.fail("live call in pinned replay"), "neuract", "SELECT 1")
    assert rec2.events[-1]["served"] == "hit"


def test_hooks_inject_llm_sql_rows_typed(session):
    ts = dt.datetime(2026, 7, 12, 8, 0, tzinfo=dt.timezone.utc)
    hooks.llm(lambda s, u, **k: {"pick": "a"}, "S", "U", stage="route")
    hooks.db_rows(lambda sql, p: [(ts, Decimal("5.5"))], "sql.nx", "SELECT ts,v", ("p1",))
    hooks.db_q(lambda db, sql: [["1", "x"]], "cmd_catalog", "SELECT a")
    rec2 = _tape_session(session.events)
    dead = lambda *a, **k: pytest.fail("live call in pinned replay")
    assert hooks.llm(dead, "S", "U", stage="route") == {"pick": "a"}
    rows = hooks.db_rows(dead, "sql.nx", "SELECT ts,v", ("p1",))
    assert rows == [(ts, Decimal("5.5"))] and isinstance(rows[0][0], dt.datetime)
    assert hooks.db_q(dead, "cmd_catalog", "SELECT a") == [["1", "x"]]
    assert all(e.get("served") == "hit" for e in rec2.events)


def test_hooks_llm_fuzzy_fallback_and_strict_miss(session):
    hooks.llm(lambda s, u, **k: {"pick": "a"}, "S", "U-original", stage="route")
    rec2 = _tape_session(session.events)
    assert hooks.llm(lambda *a, **k: pytest.fail("live"), "S", "U-DRIFTED", stage="route") == {"pick": "a"}
    assert any(e["kind"] == "tape_fuzzy" for e in rec2.events)
    rec3 = _tape_session(session.events, strict=True)
    with pytest.raises(TapeMiss):
        hooks.llm(lambda *a, **k: None, "S", "U-DRIFTED-2", stage="stories")
    assert any(e["kind"] == "tape_miss" for e in rec3.events)


def test_hooks_frame_probe_roundtrip(session):
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame([["2026-07-12T08:00:00+00:00", 1.5], ["2026-07-12T07:00:00+00:00", None]],
                      columns=["ts", "kw"])
    hooks.frame_probe(lambda t, c, limit: (df, ["kw"], True), "gic_x", ["kw"], 500)
    rec2 = _tape_session(session.events)
    df2, cols, ordered = hooks.frame_probe(lambda *a, **k: pytest.fail("live"), "gic_x", ["kw"], 500)
    assert cols == ["kw"] and ordered is True
    assert list(df2.columns) == ["ts", "kw"] and len(df2) == 2 and df2["kw"][0] == 1.5


def test_hooks_exec_card_records_window_and_payload(session):
    out = hooks.exec_card(lambda **kw: {"v": 42}, cid=7, render_card_id=7, handling_class=None,
                          exact_metadata={}, data_instructions={}, asset_table="gic_x",
                          window={"start": "2026-07-01", "end": "2026-07-08"})
    assert out == {"v": 42}
    e = session.events[-1]
    assert e["kind"] == "exec_card" and e["cid"] == 7 and coding.decode(e["payload"]) == {"v": 42}


def test_hooks_pipeline_out_artifact(session):
    hooks.pipeline_out({"run_id": "r_abc", "layer1a": {"page_key": "p"}})
    assert "pipeline_out_r_abc" in session.artifacts


# ── capture + ids + store ────────────────────────────────────────────────────────────────────────────────────────────

def test_captured_writes_bundle_and_resolve(traces_dir):
    from replay.capture import captured
    from replay.ids import resolve

    def _fn():
        hooks.llm(lambda s, u, **k: {"x": 1}, "S", "U", stage="route")
        hooks.pipeline_out({"run_id": "r_zz", "layer1a": {"page_key": "pg"}})
        return {"ok": True, "run_id": "r_zz", "cards": []}

    resp = captured("run", {"prompt": "demo"}, _fn, path="/api/run")
    assert resp["ok"] is True
    d, m = resolve("last")
    assert m["kind"] == "run" and m["prompt"] == "demo" and "r_zz" in m["run_ids"]
    assert resolve("r_zz")[1]["trace_id"] == m["trace_id"]     # run_id → newest bundle
    b = store.load_bundle(d)
    assert b["request"]["body"] == {"prompt": "demo"}
    assert [e["kind"] for e in b["events"]] == ["llm"]
    assert b["artifacts"]["response"]["run_id"] == "r_zz"
    assert b["artifacts"]["pipeline_out_r_zz"]["layer1a"]["page_key"] == "pg"


def test_captured_persists_on_handler_crash(traces_dir):
    from replay.capture import captured
    with pytest.raises(ValueError):
        captured("run", {"prompt": "boom"}, lambda: (_ for _ in ()).throw(ValueError("x")), path="/api/run")
    from replay.ids import resolve
    _, m = resolve("last")
    assert m["status"] == "error" and "ValueError" in m["error"]


# ── compare + report ─────────────────────────────────────────────────────────────────────────────────────────────────

def _bundle(page, cards, val=1, events=None):
    return {"manifest": {"trace_id": f"t_{page}", "started_at_iso": "2026-07-12T08:00:00+00:00"},
            "request": {"body": {"prompt": "demo"}},
            "events": events or [],
            "artifacts": {"pipeline_out_r_a": {
                "run_id": "r_a", "layer1a": {"page_key": page, "cards": [{"card_id": c} for c in cards]},
                "layer1b": {"asset": {"name": "UPS-01"}, "how": "AI"},
                "layer2": {"5": {"conforms": True, "answerability": "full", "exact_metadata": {"kw": val}}},
                "validation": {"verdict": "pass"}, "notes": {}, "errors": {}},
                "response": {"ok": True, "cards": [
                    {"card_id": c, "title": f"c{c}", "render": {"verdict": "render"},
                     "has_payload": True, "payload": {"v": val}} for c in cards]}}}


def test_compare_identical_and_drift_and_diverged():
    from replay.compare import compare_bundles
    same = compare_bundles(_bundle("energy", [5]), _bundle("energy", [5]))
    assert same["overall"] == "identical"
    drift = compare_bundles(_bundle("energy", [5], val=1), _bundle("energy", [5], val=2))
    assert drift["sections"]["l2_metadata"]["severity"] == "drift"
    div = compare_bundles(_bundle("energy", [5]), _bundle("harmonics", [5, 6]))
    assert div["overall"] == "diverged"
    assert div["sections"]["page_selection"]["severity"] == "diverged"
    assert div["sections"]["page_selection"]["original_page"] == "energy"


def test_compare_ai_calls_prompt_vs_completion_drift():
    from replay.compare import compare_bundles
    o = _bundle("p", [5], events=[_llm_ev("route", "s", "u", {"n": 1})])
    same_prompt_new_val = _bundle("p", [5], events=[_llm_ev("route", "s", "u", {"n": 2})])
    new_prompt = _bundle("p", [5], events=[_llm_ev("route", "s", "u-changed", {"n": 1})])
    assert compare_bundles(o, same_prompt_new_val)["sections"]["ai_calls"]["calls"][0]["status"] == "completion_drift"
    c = compare_bundles(o, new_prompt)["sections"]["ai_calls"]["calls"][0]
    assert c["status"] == "prompt_drift" and c["same_completion_anyway"] is True
    assert "u" in c["prompt_diff"]["user"]["original_excerpt"]


def test_compare_sql_changed_and_unmatched():
    from replay.compare import compare_bundles
    def _sq(key, sql, n, rows):
        return {"seq": 1, "kind": "sql.nx", "key": key, "sql": sql, "n_rows": n, "rows": rows}
    o = _bundle("p", [5], events=[_sq("k1", "SELECT a", 2, [[1], [2]]), _sq("k2", "SELECT gone", 1, [[9]])])
    r = _bundle("p", [5], events=[_sq("k1", "SELECT a", 3, [[1], [2], [3]]), _sq("k3", "SELECT new", 1, [[7]])])
    sec = compare_bundles(o, r)["sections"]["sql"]
    assert sec["severity"] == "diverged"
    assert sec["changed_results"][0]["n_rows"] == [2, 3] and "SELECT a" in sec["changed_results"][0]["sql"]
    assert sec["only_original"][0]["sql"] == "SELECT gone" and sec["only_replay"][0]["sql"] == "SELECT new"


def test_report_renders():
    from replay.compare import compare_bundles
    from replay.report import render_html, terminal_summary
    cmp_ = compare_bundles(_bundle("energy", [5]), _bundle("harmonics", [5]))
    html = render_html(cmp_)
    assert "DIVERGED" in html and "page_selection" in html and "<script" not in html
    assert "page_selection" in terminal_summary(cmp_)


def test_env_snapshot_redacts_credentials(monkeypatch):
    from replay.capture import env_snapshot, ENV_REDACTED
    monkeypatch.setenv("PGPASSWORD", "hunter2")
    monkeypatch.setenv("V48_HOST_PORT", "8770")
    snap = env_snapshot()
    assert snap["PGPASSWORD"] == ENV_REDACTED and snap["V48_HOST_PORT"] == "8770"


# ── clock ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_clock_freeze_unfreeze():
    from replay import clock
    try:
        clock.freeze("2026-07-12T08:00:00+00:00")
        tz = dt.timezone(dt.timedelta(hours=5, minutes=30))
        assert clock.now(tz).isoformat() == "2026-07-12T13:30:00+05:30"
    finally:
        clock.unfreeze()
    assert abs((clock.now(dt.timezone.utc) - dt.datetime.now(dt.timezone.utc)).total_seconds()) < 5
