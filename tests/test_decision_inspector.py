"""AI Decision Inspector — the decision-capture + read path (obs/llm_tap decision context, obs/decision_view,
host/inspector_api), offline (no Postgres, no vLLM):
  · set_decision context rides the llm event (candidates/params) and is cleared by call_qwen
  · candidate lists are size-bounded with an explicit truncation marker (never silently cut)
  · decision_view extracts selected/rejected/reasoning/confidence per stage (route, asset, basket, l2_emit, knowledge)
  · the insight narrator's direct :8200 POST reports its own tap record
  · inspector_api serves a full trace from the per-trace jsonl when pg is unreachable
"""
import io
import json
import os

import pytest

from obs import bus, llm_tap, span, trace

from obs.paths import logs_dir as _paths_logs_dir
_LOGS = _paths_logs_dir()   # writers resolve through the door


@pytest.fixture(autouse=True)
def _fresh_context(monkeypatch):
    """Isolate: no pg sink (offline), no console noise; fresh trace + decision slots per test."""
    monkeypatch.setattr(bus, "_cfg", lambda k, d: {"obs.sink.pg": "off", "obs.sink.console": "off"}.get(k, d))
    trace._TRACE.set(None)
    trace._SPAN.set(None)
    llm_tap.clear_decision()
    yield
    trace._TRACE.set(None)
    trace._SPAN.set(None)
    llm_tap.clear_decision()


def _events_for(trace_id):
    p = os.path.join(_LOGS, f"trace_{trace_id}.jsonl")
    if not os.path.isfile(p):
        return []
    with open(p) as f:
        return [json.loads(line) for line in f if line.strip()]


def _cleanup(trace_id):
    p = os.path.join(_LOGS, f"trace_{trace_id}.jsonl")
    if os.path.isfile(p):
        os.remove(p)


# ── capture: decision context + params ride the llm event ────────────────────────────────────────────────────────

def test_set_decision_and_params_ride_llm_event():
    t = trace.new_trace(kind="run", prompt="p")
    llm_tap.set_decision(kind="selection", candidate_kind="page_key",
                         candidates=[{"page_key": "a", "title": "A"}, {"page_key": "b", "title": "B"}])
    llm_tap.record(stage="route", system="S", user="U", response_text='{"page_key":"a"}',
                   usage={"prompt_tokens": 10, "completion_tokens": 2}, latency_s=0.5,
                   finish_reason="stop", model="m",
                   params={"temperature": 0, "seed": 42, "response_format": "json_object"})
    trace.end_trace()
    llm = [e for e in _events_for(t["trace_id"]) if e["kind"] == "llm"]
    assert len(llm) == 1
    ai = llm[0]["ai"]
    assert ai["params"]["seed"] == 42 and ai["params"]["temperature"] == 0
    assert ai["decision"]["candidate_kind"] == "page_key"
    assert [c["page_key"] for c in ai["decision"]["candidates"]] == ["a", "b"]
    assert llm[0]["latency_ms"] == 500
    _cleanup(t["trace_id"])


def test_call_qwen_clears_decision_context(monkeypatch):
    from llm import client as llm_client

    class _FakeProvider:
        @staticmethod
        def complete(system, user, **kw):
            return {"text": '{"ok": 1}', "finish_reason": "stop", "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    monkeypatch.setattr(llm_client._providers, "resolve", lambda: _FakeProvider)
    t = trace.new_trace(kind="run", prompt="p")
    llm_tap.set_decision(kind="selection", candidate_kind="x", candidates=["a", "b"])
    out = llm_client.call_qwen("S", "U", stage="route")
    assert out == {"ok": 1}
    assert llm_tap.current_decision() is None                  # cleared by the call_qwen finally
    trace.end_trace()
    llm = [e for e in _events_for(t["trace_id"]) if e["kind"] == "llm"]
    assert llm and llm[0]["ai"]["decision"]["candidates"] == ["a", "b"]
    assert llm[0]["ai"]["params"]["response_format"] == "json_object"
    _cleanup(t["trace_id"])


def test_bound_decision_truncates_with_marker():
    d = {"kind": "selection", "candidates": [{"name": f"asset-{i:04d}", "class": "DG"} for i in range(600)]}
    out = llm_tap._bound_decision(d, 4096)
    assert len(json.dumps(out, default=str)) <= 4096
    assert out["candidates_total"] == 600
    assert any(isinstance(c, str) and "more option" in c for c in out["candidates"])


# ── decision_view: per-stage extraction ──────────────────────────────────────────────────────────────────────────

def test_view_route_selected_and_rejected():
    from obs import decision_view
    v = decision_view.view("route", '{"page_key":"pv","metric":"power","intent":"trend","window":"none"}',
                           decision={"kind": "selection", "candidate_kind": "page_key",
                                     "candidates": [{"page_key": "pv"}, {"page_key": "other"}]})
    assert v["selected"]["page_key"] == "pv" and v["rejected"] == ["other"]


def test_view_asset_resolve_branches():
    from obs import decision_view
    cands = {"candidates": [{"name": "DG-01"}, {"name": "DG-02"}, {"name": "UPS-01"}]}
    pin = decision_view.view("asset_resolve", '{"names":["DG-01"],"confident":true}', decision=cands)
    assert pin["selected"]["branch"] == "confident_pin" and pin["confidence"] is True
    assert set(pin["rejected"]) == {"DG-02", "UPS-01"}
    amb = decision_view.view("asset_resolve", '{"confident":false,"candidates":["DG-01","DG-02"]}', decision=cands)
    assert amb["selected"]["branch"] == "ambiguous" and amb["rejected"] == ["UPS-01"]
    assert amb["confidence"] is False


def test_view_basket_confidence_and_reasoning():
    from obs import decision_view
    v = decision_view.view("basket",
                           json.dumps({"feasible": ["c1"], "probable": [
                               {"column": "c2", "confidence": 0.7, "why": "closest stand-in"}]}),
                           decision={"candidates": [{"column": "c1"}, {"column": "c2"}, {"column": "c3"}]})
    assert v["selected"]["feasible"] == ["c1"] and v["rejected"] == ["c3"]
    assert v["confidence"] == 0.7 and "closest stand-in" in v["reasoning"]


def test_view_l2_emit_swap_and_keep():
    from obs import decision_view
    pool = {"candidates": [{"card_id": 51, "title": "A"}, {"card_id": 52, "title": "B"}]}
    swap = decision_view.view("l2_emit", json.dumps({
        "swap_decision": {"action": "swap", "swap_to_id": 51, "confidence": 0.95,
                          "criterion": "trend", "reason": "asked trend"},
        "answerability": "full", "data_instructions": {"fetch": {"endpoint": "compare"}}}), decision=pool)
    assert swap["selected"]["swap_to_id"] == 51 and swap["rejected"] == [52]
    assert swap["confidence"] == 0.95 and "trend" in swap["reasoning"]
    keep = decision_view.view("l2_emit", json.dumps({"swap_decision": {"action": "keep"}}), decision=pool)
    assert keep["selected"]["action"] == "keep" and set(keep["rejected"]) == {51, 52}


def test_view_knowledge_and_error_and_unknown_stage():
    from obs import decision_view
    k = decision_view.view("knowledge_ems", '{"kind":"knowledge","answer":"…"}',
                           decision={"candidates": ["dashboard", "knowledge", "off_scope"], "candidate_kind": "kind"})
    assert k["selected"]["kind"] == "knowledge" and set(k["rejected"]) == {"dashboard", "off_scope"}
    err = decision_view.view("route", None, decision={"candidates": []}, error_kind="timeout")
    assert err["error"] == "timeout" and err["selected"] is None
    gen = decision_view.view("brand_new_stage", '{"choice":"x","reasoning":"because","confidence":0.4}', decision={})
    assert gen["reasoning"] == "because" and gen["confidence"] == 0.4


# ── the insight narrator's direct POST reports its own tap record ─────────────────────────────────────────────────

def test_insight_narrator_tap(monkeypatch):
    import urllib.request
    from ems_exec.renderers import _insight

    body = json.dumps({"choices": [{"message": {"content": '{"text": "All healthy."}'},
                                    "finish_reason": "stop"}],
                       "usage": {"prompt_tokens": 100, "completion_tokens": 8}}).encode()

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: _Resp(body))
    t = trace.new_trace(kind="run", prompt="p")
    with span.stage_span("executor.card", card_id=8):
        out = _insight._narrate_sync_raw({"fact": 1}, ["text"], 5)
    assert out == {"text": "All healthy."}
    trace.end_trace()
    llm = [e for e in _events_for(t["trace_id"]) if e["kind"] == "llm"]
    assert len(llm) == 1 and llm[0]["stage"] == "insight_narrator" and llm[0]["card_id"] == 8
    assert llm[0]["ai"]["tokens_prompt"] == 100 and llm[0]["ai"]["decision"]["kind"] == "generative"
    _cleanup(t["trace_id"])


# ── inspector_api: full trace served from jsonl when pg is unreachable ───────────────────────────────────────────

def test_inspector_api_jsonl_fallback(monkeypatch):
    t = trace.new_trace(kind="run", prompt="ups 2 current")
    with span.stage_span("page_selection"):
        llm_tap.set_decision(kind="selection", candidate_kind="page_key",
                             candidates=[{"page_key": "pv"}, {"page_key": "other"}])
        llm_tap.record(stage="route", system="S", user="U",
                       response_text='{"page_key":"pv","metric":"current","intent":"trend","window":"none"}',
                       usage={"prompt_tokens": 5, "completion_tokens": 2}, latency_s=0.1, model="m",
                       params={"temperature": 0, "seed": 42})
        llm_tap.clear_decision()
    trace.end_trace(status="ok", response_summary={"ok": True})
    tid = t["trace_id"]

    import obs.query as query
    monkeypatch.setattr(query, "_rows", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("pg down")))
    from host import inspector_api
    det = inspector_api.trace_detail(tid)
    assert det["trace"]["trace_id"] == tid and det["trace"]["source"] == "jsonl"
    assert len(det["decisions"]) == 1
    d = det["decisions"][0]
    assert d["stage"] == "route" and d["params"]["seed"] == 42
    assert d["decision"]["selected"]["page_key"] == "pv" and d["decision"]["rejected"] == ["other"]
    assert [s["stage"] for s in det["stages"]] == ["page_selection"]
    json.dumps(det)                                            # host _send uses bare json.dumps — must never raise
    _cleanup(tid)
