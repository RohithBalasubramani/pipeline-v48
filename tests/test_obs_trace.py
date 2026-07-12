"""obs trace/span layer — the V48 observability system (obs/trace, obs/span, obs/event, sinks, taps).

Covers the CONTRACT, offline (no Postgres, no vLLM — the pg sink is gated off per test via the knob monkeypatch):
  · trace identity: globally unique trace_id per execution (same prompt ≠ same trace, unlike run_id)
  · span capture: latency / status / inputs / outputs / confidence / degradation / errors (recorded AND re-raised)
  · nesting: parent_span_id through the context, ACROSS run_parallel + executor-style pool threads
  · taps: llm_tap rolls token usage onto the active span; db_tap rolls query counts/rows; both no-op untraced
  · legacy forward: obs.stage.stage() lands in the trace as a legacy event + binds its run_id
  · redact: size bound preserves shape and marks truncation
  · fail-open: a broken sink never raises into the pipeline
"""
import json
import os

import pytest

from obs import bus, event, redact, span, trace


@pytest.fixture(autouse=True)
def _fresh_context(monkeypatch):
    """Isolate: no pg sink (offline), no console noise; fresh trace slot per test."""
    monkeypatch.setattr(bus, "_cfg", lambda k, d: {"obs.sink.pg": "off", "obs.sink.console": "off"}.get(k, d))
    trace._TRACE.set(None)
    trace._SPAN.set(None)
    yield
    trace._TRACE.set(None)
    trace._SPAN.set(None)


def _events_for(trace_id):
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "logs", f"trace_{trace_id}.jsonl")
    if not os.path.isfile(p):
        return []
    with open(p) as f:
        return [json.loads(line) for line in f if line.strip()]


def _cleanup(trace_id):
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "logs", f"trace_{trace_id}.jsonl")
    if os.path.isfile(p):
        os.remove(p)


# ── trace identity ───────────────────────────────────────────────────────────────────────────────────────────────

def test_trace_id_globally_unique_per_execution():
    t1 = trace.new_trace(kind="run", prompt="same prompt")
    id1 = t1["trace_id"]
    trace.end_trace()
    t2 = trace.new_trace(kind="run", prompt="same prompt")
    id2 = t2["trace_id"]
    trace.end_trace()
    assert id1 != id2                                          # unlike run_id (prompt hash), traces never collide
    assert id1.startswith("t_") and len(id1) > 20
    _cleanup(id1); _cleanup(id2)


def test_run_ids_bind_and_dedupe():
    t = trace.new_trace(kind="run", prompt="p")
    trace.bind_run_id("r_abc")
    trace.bind_run_id("r_abc")
    trace.bind_run_id("r_loop2")
    assert t["run_ids"] == ["r_abc", "r_loop2"]
    assert trace.current_run_id() == "r_loop2"
    trace.end_trace(); _cleanup(t["trace_id"])


def test_end_trace_idempotent_and_summarizing():
    t = trace.new_trace(kind="run", prompt="p")
    out1 = trace.end_trace(status="degraded", response_summary={"n_cards": 3})
    out2 = trace.end_trace(status="ok")                        # second close: no-op
    assert out1 is not None and out2 is None
    evs = _events_for(t["trace_id"])
    assert [e for e in evs if e["kind"] == "trace"] and evs[-1]["status"] == "degraded"
    _cleanup(t["trace_id"])


# ── spans ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_span_captures_everything():
    t = trace.new_trace(kind="run", prompt="p")
    with span.stage_span("asset_resolution", inputs={"prompt": "ups load"}) as sp:
        sp.set_outputs(asset="UPS-01", how="AI")
        sp.set_confidence(how="AI", class_prior=0.9)
        sp.set_degradation(no_data=True)
        sp.warn("basket thin")
    evs = _events_for(t["trace_id"])
    e = next(x for x in evs if x.get("stage") == "asset_resolution")
    assert e["kind"] == "stage" and e["trace_id"] == t["trace_id"]
    assert e["inputs"]["prompt"] == "ups load"
    assert e["outputs"]["asset"] == "UPS-01"
    assert e["confidence"]["class_prior"] == 0.9
    assert e["status"] == "degraded" and e["degradation"]["no_data"] is True
    assert e["warnings"] == ["basket thin"]
    assert isinstance(e["latency_ms"], int) and e["ts_end"] >= e["ts_start"]
    trace.end_trace(); _cleanup(t["trace_id"])


def test_span_records_and_reraises_exception():
    t = trace.new_trace(kind="run", prompt="p")
    with pytest.raises(ValueError):
        with span.stage_span("validation"):
            raise ValueError("boom")
    e = next(x for x in _events_for(t["trace_id"]) if x.get("stage") == "validation")
    assert e["status"] == "error" and "ValueError: boom" in e["errors"][0]
    assert t["totals"]["errors"] == 1                          # rolled trace-level too
    trace.end_trace(); _cleanup(t["trace_id"])


def test_span_nesting_and_thread_hop():
    """Child spans opened in run_parallel worker threads must parent under the caller's active span."""
    from run.parallel import run_parallel
    t = trace.new_trace(kind="run", prompt="p")
    with span.stage_span("layer2_card_ai") as parent:
        def _card(cid):
            def _run():
                with span.stage_span("layer2_card_ai.card", card_id=cid):
                    pass
                return cid
            return _run
        run_parallel({f"c{i}": _card(i) for i in (1, 2, 3)})
    evs = _events_for(t["trace_id"])
    parent_ev = next(x for x in evs if x["kind"] == "stage" and x["stage"] == "layer2_card_ai")
    cards = [x for x in evs if x["kind"] == "stage" and x["stage"] == "layer2_card_ai.card"]
    assert len(cards) == 3
    assert all(c["parent_span_id"] == parent_ev["span_id"] for c in cards)
    assert sorted(c["card_id"] for c in cards) == [1, 2, 3]
    trace.end_trace(); _cleanup(t["trace_id"])


def test_span_noop_without_trace():
    with span.stage_span("executor") as sp:                    # no active trace: inert handle, nothing emitted
        sp.set_outputs(cards=1)
    assert trace.current() is None


# ── taps ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_llm_tap_rolls_usage_onto_span_and_emits_call_event():
    from obs import llm_tap
    t = trace.new_trace(kind="run", prompt="p")
    with span.stage_span("page_selection") as sp:
        llm_tap.record(stage="route", system="SYS", user="USR", response_text='{"page_key":"x"}',
                       usage={"prompt_tokens": 3710, "completion_tokens": 32},
                       latency_s=1.5, finish_reason="stop", model="qwen")
        assert sp.d["ai"] == {"n_calls": 1, "tokens_prompt": 3710, "tokens_completion": 32}
    evs = _events_for(t["trace_id"])
    llm_ev = next(x for x in evs if x["kind"] == "llm")
    assert llm_ev["ai"]["tokens_prompt"] == 3710 and llm_ev["ai"]["prompt_user"] == "USR"
    assert llm_ev["stage"] == "route" and llm_ev["status"] == "ok"
    stage_ev = next(x for x in evs if x["kind"] == "stage" and x["stage"] == "page_selection")
    assert stage_ev["ai"]["n_calls"] == 1 and stage_ev["ai"]["tokens_prompt"] == 3710
    assert t["totals"]["llm_calls"] == 1                       # trace totals via span close
    trace.end_trace(); _cleanup(t["trace_id"])


def test_db_tap_rolls_queries_onto_span():
    from obs import db_tap
    t = trace.new_trace(kind="run", prompt="p")
    with span.stage_span("validation") as sp:
        db_tap.record(db="cmd_catalog", sql="SELECT 1", rows_returned=42, latency_s=0.01)
        db_tap.record(db="target_version1", sql="SELECT 2", rows_returned=8, latency_s=0.02, error="timeout")
        assert sp.d["db"] == {"n_queries": 2, "rows_returned": 50}
    evs = _events_for(t["trace_id"])
    dbs = [x for x in evs if x["kind"] == "db"]
    assert len(dbs) == 2
    assert dbs[0]["db"]["database"] == "cmd_catalog" and dbs[0]["db"]["rows_returned"] == 42
    assert dbs[1]["status"] == "error" and dbs[1]["errors"] == ["timeout"]
    trace.end_trace(); _cleanup(t["trace_id"])


def test_taps_noop_untraced():
    from obs import db_tap, llm_tap
    llm_tap.record(stage="route", system="s", user="u", usage={"prompt_tokens": 1}, latency_s=0)
    db_tap.record(db="cmd_catalog", sql="SELECT 1", rows_returned=1, latency_s=0)
    assert trace.current() is None                             # nothing minted, nothing raised


# ── legacy stage forward ─────────────────────────────────────────────────────────────────────────────────────────

def test_legacy_stage_forwards_into_trace_and_binds_run_id():
    from obs.stage import stage
    t = trace.new_trace(kind="run", prompt="p")
    stage("r_test123", "asset_gate", pinned=True, how="AI")
    evs = _events_for(t["trace_id"])
    e = next(x for x in evs if x.get("stage") == "legacy.asset_gate")
    assert e["kind"] == "legacy" and e["outputs"]["pinned"] is True
    assert "r_test123" in t["run_ids"]
    trace.end_trace(); _cleanup(t["trace_id"])
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "outputs", "logs", "pipeline_r_test123.jsonl")
    if os.path.isfile(p):
        os.remove(p)


# ── redact ───────────────────────────────────────────────────────────────────────────────────────────────────────

def test_redact_bounds_preserving_shape():
    big = {"prompt": "x" * 100000, "cards": list(range(500)), "nested": {"k": "v" * 9000}}
    out = redact.bound(big, max_bytes=2048)
    assert set(out.keys()) <= set(big.keys()) | {"_truncated"}
    assert len(json.dumps(out)) < 20000                        # bounded (soft budget, hard-capped well below input)
    assert out["prompt"].endswith("…[truncated]")
    assert redact.bound(None, 10) is None and redact.bound(7, 10) == 7


def test_redact_never_raises():
    class Weird:
        def __repr__(self):
            raise RuntimeError("nope")
    assert redact.bound(Weird(), 100) == "<unloggable>"


# ── fail-open ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_broken_sink_never_raises(monkeypatch):
    from obs import sink_jsonl
    monkeypatch.setattr(sink_jsonl, "write", lambda e: (_ for _ in ()).throw(RuntimeError("disk full")))
    t = trace.new_trace(kind="run", prompt="p")
    with span.stage_span("renderer") as sp:                    # sink explodes at close — span must swallow it
        sp.set_outputs(cards=1)
    trace.end_trace()
    _cleanup(t["trace_id"])


def test_bus_reentrancy_guard():
    calls = {"n": 0}
    orig = bus.emit

    def _reentrant(e):
        calls["n"] += 1
        orig(e)                                                # nested emit inside emit must be dropped, not recurse

    t = trace.new_trace(kind="run", prompt="p")
    tok = bus._IN_BUS.set(True)
    try:
        bus.emit(event.trace_event(t))                         # guarded: no sinks fire
    finally:
        bus._IN_BUS.reset(tok)
    assert _events_for(t["trace_id"]) == []
    trace._TRACE.set(None)
    _cleanup(t["trace_id"])
