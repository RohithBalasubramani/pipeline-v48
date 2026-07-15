"""tests/test_layer3_narrate.py — Layer 3, the AI page narrator (layer3/narrate.py).

Pins the AI-layer contract: the digest is GROUNDED (real labeled readings only), the AI's summary is returned when
it succeeds, and ANY failure honest-degrades to the deterministic fallback (never fabricates, never raises). Non-live
(call_qwen monkeypatched)."""
from __future__ import annotations

import pytest

import layer3.narrate as N


@pytest.fixture(autouse=True)
def _fresh_cache():
    N._CACHE.clear()          # every test drives the SAME digest; the content-hash cache must not bleed across them
    yield
    N._CACHE.clear()


def _resp():
    return {
        "run_id": "t_l3", "prompt": "real-time power and current for Transformer 01",
        "page": {"page_title": "Real Time Monitoring"},
        "asset": {"asset": {"name": "GIC-15-N3-PCC-01 (Transformer-01)"}},
        "validation": {"verdict": "warn", "data_summary": {"n_pass": 57, "n_columns": 63}},
        "cards": [
            {"title": "Power & Energy", "has_payload": True,
             "story": {"analytical_story": "Primary real-time snapshot of active/reactive power."},
             "payload": {"data": {"readings": {
                 "activePower": {"label": "Active Power", "displayValue": "731.3", "unit": "kW", "value": 731.25},
                 "activeEnergy": {"label": "Active Energy", "displayValue": "20491", "unit": "kWh", "value": 20491.2}}}}},
            {"title": "Current Monitor", "has_payload": True, "story": "Live three-phase current trends.",
             "payload": {"data": {"metrics": [{"label": "R Phase", "value": 39.75, "unit": "A"}]}}},
        ],
    }


def test_digest_is_grounded():
    d = N._digest(_resp())
    assert d["asset"] == "GIC-15-N3-PCC-01 (Transformer-01)"
    assert d["page"] == "Real Time Monitoring"
    assert d["validation"] == "warn · 57/63 cols"
    assert d["cards"][0]["readings"][0] == "Active Power · 731.3 kW"
    assert d["cards"][0]["story"].startswith("Primary real-time")
    # the digest NEVER invents a reading — only labeled values from the payload appear
    flat = " ".join(r for c in d["cards"] for r in c["readings"])
    assert "731.3" in flat and "39.75" in flat


def test_narrate_returns_ai_summary(monkeypatch):
    monkeypatch.setattr(N, "call_qwen", lambda system, user, **k: {"summary": "Transformer 01 draws 731.3 kW."})
    out = N.narrate(_resp())
    assert out["degraded"] is False
    assert out["summary"] == "Transformer 01 draws 731.3 kW."


def test_llm_failure_honest_degrades_to_fallback(monkeypatch):
    monkeypatch.setattr(N, "call_qwen", lambda system, user, **k: (_ for _ in ()).throw(RuntimeError("vllm down")))
    out = N.narrate(_resp())
    assert out["degraded"] is True
    assert "Real Time Monitoring" in out["summary"] and "Active Power · 731.3 kW" in out["summary"]


def test_empty_reply_honest_degrades(monkeypatch):
    monkeypatch.setattr(N, "call_qwen", lambda system, user, **k: {})   # on_error='empty' shape
    out = N.narrate(_resp())
    assert out["degraded"] is True and out["summary"]                    # the deterministic line, never blank here


def test_no_cards_is_empty():
    out = N.narrate({"run_id": "t_x", "cards": []})
    assert out == {"summary": "", "degraded": True}


def test_cache_hits_second_call(monkeypatch):
    calls = []
    monkeypatch.setattr(N, "call_qwen", lambda system, user, **k: calls.append(1) or {"summary": "cached story."})
    N._CACHE.clear()
    a = N.narrate(_resp())
    b = N.narrate(_resp())
    assert a["summary"] == b["summary"] == "cached story."
    assert len(calls) == 1                                               # second call served from the content-hash cache
