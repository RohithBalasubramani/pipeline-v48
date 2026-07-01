"""Layer 2 per-card emit — {swap_decision, exact_metadata, data_instructions} (contract 5).
Unit (deterministic: producer byte-identity, gates, swap chain) + live (RTM heatmap #5 keeps + conforms)."""
import json

import pytest

from layer2.emit.metadata.producer import produce, _metadata_default
from layer2.emit.metadata.split import split
from layer2.gates import gate_exact_metadata, gate_data_instructions
from layer2.swap.decide import gate as swap_gate
from layer2.emit.data.consumer_binding import build as consumer_build, page_endpoint

_HEATMAP = {"heatmap": {"title": "Real Time Monitoring", "metric": "all", "history": [{"x": 1}],
                        "metricTabs": [{"key": "all", "label": "All Metrics"}, {"key": "kw", "label": "kW"}],
                        "statusColors": {"low": "#eee"}, "sectionContracts": {"incomers": 2700}}}


def test_producer_byte_identical_when_no_morph():
    em, applied, rejected = produce(_HEATMAP, {}, [])
    assert applied == [] and rejected == []
    assert em == _metadata_default(_HEATMAP)          # defaults verbatim, DATA leaves dropped
    assert "history" not in em["heatmap"] and "metric" not in em["heatmap"]   # DATA elided
    assert em["heatmap"]["sectionContracts"] == {"incomers": 2700}            # numeric metadata kept


def test_producer_applies_declared_morph_only():
    ai = {"heatmap": {"title": "Voltage — Real Time"}}
    em, applied, rejected = produce(_HEATMAP, ai, ["heatmap.title"])
    assert applied == ["heatmap.title"] and em["heatmap"]["title"] == "Voltage — Real Time"
    assert em["heatmap"]["statusColors"] == {"low": "#eee"}                   # untouched = default


def test_producer_rejects_chrome_morph():
    ai = {"heatmap": {"title": "() => <div/>"}}
    em, applied, rejected = produce(_HEATMAP, ai, ["heatmap.title"])
    assert applied == [] and rejected and em["heatmap"]["title"] == "Real Time Monitoring"


def test_exact_metadata_gate_flags_byte_violation():
    em = _metadata_default(_HEATMAP)
    em["heatmap"]["statusColors"]["low"] = "#000000"   # silent drift, not declared morphed
    ok, issues = gate_exact_metadata(em, _HEATMAP, morphed=[])
    assert not ok and any("byte-identical" in i for i in issues)


def test_data_instructions_gate_group_ctx():
    di = {"fields": [{"kind": "raw", "metric": "kw", "column": "kw", "source": "$ctx", "role": "series"}]}
    ok, issues = gate_data_instructions(di, {"columns": []}, is_group_card=True)
    assert ok                                          # $ctx fields need no real column on a group card
    ok2, _ = gate_data_instructions(di, {"columns": []}, is_group_card=False)
    assert not ok2                                     # $ctx on a standalone card is rejected


def test_swap_gate_rejects_vague_and_offpool():
    base = dict(pool_ids=[99], template_card_ids=[], already_chosen=set(), page_card_ids=[], current_card_id=5)
    assert swap_gate({"action": "swap", "confidence": 0.95, "criterion": "better", "swap_to_id": 99}, **base)["origin"] == "kept"
    assert swap_gate({"action": "swap", "confidence": 0.7, "criterion": "sankey flow", "swap_to_id": 99}, **base)["origin"] == "kept"
    assert swap_gate({"action": "swap", "confidence": 0.95, "criterion": "sankey flow", "swap_to_id": 5}, **base)["origin"] == "kept"  # off-pool
    assert swap_gate({"action": "swap", "confidence": 0.95, "criterion": "sankey flow", "swap_to_id": 99}, **base)["origin"] == "swapped"


def test_consumer_binding_drives_ems_backend():
    cr = {"backend_strategy": "consumers/real_time_monitoring/pcc_panel.py", "resolver_scope": "panel"}
    # The AI (Layer 2) authors the endpoint + window — consumer_binding only ASSEMBLES the AI spec with 1b's mfm_id.
    c = consumer_build(cr, {"mfm_id": 174}, "panel-overview-shell/real-time-monitoring",
                       ai_spec={"endpoint": "real-time-monitoring", "window_seconds": 30, "metrics": ["kw"]})
    assert c["source_backend"] == "ems_backend" and c["mfm_id"] == 174 and c["endpoint"] == "real-time-monitoring"
    assert c["window_seconds"] == 30 and c["metrics"] == ["kw"]
    # NO deterministic endpoint guess: with no AI spec the endpoint is an honest None, never a fallback.
    assert consumer_build(cr, {"mfm_id": 174}, "x", ai_spec={})["endpoint"] is None
    assert page_endpoint("individual-feeder-meter-shell/voltage-current") == "voltage-current"


@pytest.mark.live
def test_layer2_card5_keep_byteidentical_live():
    from layer2.build import run_card
    d = json.load(open("/tmp/l2_inputs.json"))
    out = run_card("t5", 5, d["l1a"], d["l1b"])
    assert out["conforms"] is True
    assert out["$ctx"] == "panel-overview-shell/real-time-monitoring::g0"     # group atom
    assert out["swap_decision"]["origin"] == "kept"
    # exact_metadata is byte-identical to the harvested default metadata (no morph for an RTM prompt)
    skel, _ = split(d["l1a"] and {"heatmap": {}} or {})  # noqa  (guard import use)
    from layer2.catalog.card_payload import default_for
    dp = default_for(5, "panel-overview-shell/real-time-monitoring")
    assert out["exact_metadata"] == _metadata_default(dp["payload"])
    fields = out["data_instructions"]["fields"]
    assert any(f.get("source") == "$ctx" for f in fields)                      # group → shared buffer
    # group atom: every field is the shared buffer ($ctx) OR a baked literal (kind=const; const has NO source — source is live-only)
    assert all(f.get("source") == "$ctx" or f.get("kind") == "const" for f in fields)
    assert out["data_instructions"]["consumer"]["source_backend"] == "ems_backend"


def test_swap_target_reemit(monkeypatch):
    """When the gate ACCEPTS a swap to target T, run_card re-emits for T → final card_id=T, payload authored for T,
    _reemit_of=original. (The first emit was for the shown card's shape; the second is for the final card.)"""
    import json
    import layer2.build as B
    from layer2.card_input import build_card_input
    d = json.load(open("/tmp/l2_inputs.json"))
    l1a, l1b = d["l1a"], d["l1b"]

    # pick a REAL swap target from #5's CURRENT pool (the pool is restricted to the 9 available pages, so the target
    # must come from the live pool — not a hardcoded id). Force the AI to swap #5 -> target, then keep for target.
    pool = build_card_input("t", 5, l1a, l1b)["swap_candidates"]
    if not pool:
        pytest.skip("no swap candidates in #5's available-pages pool")
    target = pool[0]["card_id"]
    calls = []

    def fake_emit(ci):
        calls.append(ci["card_id"])
        if ci["card_id"] == 5:
            return {"swap_decision": {"action": "swap", "confidence": 0.95, "criterion": "sankey energy flow",
                                      "swap_to_id": target, "swap_to_title": pool[0].get("title", "X")},
                    "exact_metadata": {"heatmap": {}}, "data_instructions": {"payload_shape": "x", "fields": []}}
        return {"swap_decision": {"action": "keep"},                          # the target settles (no re-swap)
                "exact_metadata": {"any": "thing"}, "data_instructions": {"payload_shape": "y", "fields": []}}

    monkeypatch.setattr(B, "emit", fake_emit)
    out = B.run_card("t", 5, l1a, l1b)
    assert out["swap_decision"]["origin"] == "swapped" and out["swap_decision"]["swap_to_id"] == target
    assert out["card_id"] == target and out["_reemit_of"] == 5  # FINAL card is the target; payload re-emitted for it
    assert calls == [5, target]                                # one emit for the shown card, one for the target


def test_no_reemit_on_keep(monkeypatch):
    import json
    import layer2.build as B
    d = json.load(open("/tmp/l2_inputs.json"))
    calls = []

    def fake_emit(ci):
        calls.append(ci["card_id"])
        return {"swap_decision": {"action": "keep"}, "exact_metadata": {"heatmap": {}},
                "data_instructions": {"payload_shape": "x", "fields": []}}

    monkeypatch.setattr(B, "emit", fake_emit)
    out = B.run_card("t", 5, d["l1a"], d["l1b"])
    assert out["card_id"] == 5 and out["_reemit_of"] is None and calls == [5]   # KEEP → single emit, no re-emit
