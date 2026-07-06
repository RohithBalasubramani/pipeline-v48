"""Layer 2 per-card emit — {swap_decision, exact_metadata, data_instructions} (contract 5).
Unit (deterministic: producer byte-identity, gates, swap chain, roster-served fields:[]) + live (roster-served
RTM heatmap #5: chrome byte-faithful to the STRIPPED default, roster present, no seed values, conforms)."""
import json

import pytest

from layer2.emit.metadata.producer import produce, _metadata_default
from layer2.gates import gate_exact_metadata, gate_data_instructions
from layer2.swap.decide import gate as swap_gate
from layer2.emit.data.consumer_binding import build as consumer_build, page_endpoint
from grounding.default_assemble import strip_to_placeholders

_HEATMAP = {"heatmap": {"title": "Real Time Monitoring", "metric": "all", "history": [{"x": 1}],
                        "metricTabs": [{"key": "all", "label": "All Metrics"}, {"key": "kw", "label": "kW"}],
                        "statusColors": {"low": "#eee"}, "sectionContracts": {"incomers": 2700}}}
# STORED seedless skeleton the builder (scripts/build_stripped_payloads.py) persists to card_payloads.payload_stripped.
# Runtime stripping is retired: the producer reads THIS directly and never re-strips at request time.
_HEATMAP_STRIPPED = strip_to_placeholders(_HEATMAP)

# /tmp/l2_inputs.json = REAL L1a/L1b outputs {"l1a":…, "l1b":…} dumped by a prior live pipeline run — the swap-chain
# tests need a genuine card-input context (pool, page, asset) and we never fabricate one. Absent artifact → honest
# skip-with-reason (dump it from run.harness / a host /api/run to enable these), never a FileNotFoundError red.
def _l2_inputs():
    try:
        with open("/tmp/l2_inputs.json", errors="replace") as f:
            return json.load(f)
    except FileNotFoundError:
        pytest.skip("/tmp/l2_inputs.json missing — needs real L1a/L1b from a prior live run (not fabricated)")


def test_producer_reads_stored_skeleton_verbatim_no_restrip():
    # the emit skeleton IS the STORED payload_stripped verbatim (deep-copied) — NOT a re-strip of the raw default.
    em, applied, rejected = produce(_HEATMAP, {}, [], _HEATMAP_STRIPPED)
    assert applied == [] and rejected == []
    assert em == _metadata_default(_HEATMAP, _HEATMAP_STRIPPED) == _HEATMAP_STRIPPED   # stored skeleton, byte-for-byte
    # the stored skeleton carries typed placeholders (no seed): series structure kept with value zeroed, numeric → 0.0.
    assert em["heatmap"]["history"] == [{"x": 0.0}]                           # data series: structure kept, value zeroed
    assert em["heatmap"]["sectionContracts"] == {"incomers": 0.0}             # numeric data → typed-zero placeholder
    assert em["heatmap"]["statusColors"] == {"low": "#eee"}                   # chrome kept byte-identical


def test_producer_missing_stored_skeleton_fails_loudly():
    # runtime stripping is retired: a card with NO stored payload_stripped must FAIL LOUDLY (run the builder),
    # NEVER silently strip on the fly.
    import pytest as _pytest
    with _pytest.raises(ValueError):
        produce(_HEATMAP, {}, [], None)


def test_producer_applies_declared_morph_only():
    ai = {"heatmap": {"title": "Voltage — Real Time"}}
    em, applied, rejected = produce(_HEATMAP, ai, ["heatmap.title"], _HEATMAP_STRIPPED)
    assert applied == ["heatmap.title"] and em["heatmap"]["title"] == "Voltage — Real Time"
    assert em["heatmap"]["statusColors"] == {"low": "#eee"}                   # untouched = default


def test_producer_rejects_chrome_morph():
    ai = {"heatmap": {"title": "() => <div/>"}}
    em, applied, rejected = produce(_HEATMAP, ai, ["heatmap.title"], _HEATMAP_STRIPPED)
    assert applied == [] and rejected and em["heatmap"]["title"] == "Real Time Monitoring"


def test_exact_metadata_gate_flags_byte_violation():
    em = _metadata_default(_HEATMAP, _HEATMAP_STRIPPED)
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
    assert c["mfm_id"] == 174 and c["endpoint"] == "real-time-monitoring"
    assert c["window_seconds"] == 30 and c["metrics"] == ["kw"]
    # NO deterministic endpoint guess: with no AI spec the endpoint is an honest None, never a fallback.
    assert consumer_build(cr, {"mfm_id": 174}, "x", ai_spec={})["endpoint"] is None
    assert page_endpoint("individual-feeder-meter-shell/voltage-current") == "voltage-current"


def test_roster_served_card_empty_fields_conforms(monkeypatch):
    """Defect (a): a ROSTER-SERVED card (card_fill_recipe row exists) emitting fields:[] is LEGITIMATE — its DATA
    rides the roster interpreter, not fields[]. The recipe roster must be normalized/backfilled BEFORE the fields
    gate so 'data_instructions.fields is empty' is never recorded as an emit failure (the pages-04/01 cards-26/27/5
    payload_error class). A card WITHOUT a recipe row still fails honestly on empty fields."""
    import layer2.build as B
    from data.db_client import q
    from layer2.catalog import card_fill_recipe

    spec = (card_fill_recipe.read(26).get("roster_spec") or {})
    if not spec.get("slots"):
        pytest.skip("card 26 no longer carries a card_fill_recipe roster_spec")

    def fake_emit(ci, feedback=None):
        return {"swap_decision": {"action": "keep"}, "exact_metadata": {},
                "data_instructions": {"payload_shape": "TablePayload", "fields": []}}   # NO fields, NO roster emitted

    monkeypatch.setattr(B, "emit", fake_emit)
    l1a = {"page_key": "panel-overview-shell/harmonics-pq", "metric": "thd", "intent": "snapshot",
           "story": "Harmonics & PQ", "interdependency_groups": [],
           "cards": [{"card_id": 26, "title": "Feeder PQ Table", "analytical_story": "per-feeder distortion rank"}]}
    l1b = {"asset": {"mfm_id": 320, "name": "PCC-Panel-4", "table": "pcc_panel_4_feedbacks",
                     "class": "Panel", "has_data": True, "has_feeders": True},
           "column_basket": {"tables": ["pcc_panel_4_feedbacks"], "columns": []}}
    out = B.run_card("t26", 26, l1a, l1b)
    assert out["conforms"] is True
    assert out["failure"] is None                       # roster-served: NO 'fields is empty' payload_error
    roster = out["data_instructions"].get("roster") or []
    assert {s.get("slot") for s in spec["slots"]} <= {r.get("slot") for r in roster}   # recipe truth backfilled

    # honesty guard: a card with NO recipe row (picked from the DB, not hardcoded) still fails on empty fields.
    # The fields-optional classes are DB-driven (gates.fields_optional_classes) — a bare card of one of those
    # (panel_aggregate rides its member-aggregation consumer, the specials build chrome server-side) legitimately
    # emits fields:[], so exclude the LIVE set here to pick a genuinely fields-REQUIRED bare card to negative-test.
    from config.gates_vocab import fields_optional_classes as _foc    # the ONE shared accessor [A6a]
    _optional = _foc()
    have = {int(r[0]) for r in q("cmd_catalog", "SELECT card_id FROM card_fill_recipe")}
    rows = q("cmd_catalog", "SELECT card_id, handling_class FROM card_handling ORDER BY card_id")
    bare = next((int(r[0]) for r in rows if int(r[0]) not in have and r[1] not in _optional), None)
    if bare is None:
        pytest.skip("every card now has a recipe row — no bare card to negative-test")
    pk = q("cmd_catalog", f"SELECT DISTINCT page_key FROM page_layout_cards WHERE card_id={bare}")
    l1a2 = dict(l1a, page_key=pk[0][0] if pk else l1a["page_key"],
                cards=[{"card_id": bare, "title": "t", "analytical_story": "a"}])
    out2 = B.run_card("tneg", bare, l1a2, l1b)
    assert out2["conforms"] is False                              # a fields-REQUIRED bare card is NOT given the carve-out
    assert (out2["failure"] or {}).get("detail")                 # ...it fails HONESTLY with a stated reason, never a silent
    #   conform (the exact gate it trips — 'fields is empty' vs an earlier 'no default payload' — depends on the picked
    #   card; the precise empty-fields gate is unit-tested in test_layer2_empty_roster_honest_blank).


@pytest.mark.live
def test_layer2_card5_keep_byteidentical_live():
    """Roster-served card 5 (RTM heatmap, current architecture): exact_metadata CHROME byte-faithful to the
    STRIPPED default (metadata_reference — data leaves are typed placeholders, NEVER harvested seed values),
    data_instructions.roster present (recipe truth, backfilled even when the AI omits slots), and an empty/absent
    fields[] is NOT an emit failure. Supersedes the old strip semantics + liveMode/feeders fields assertions."""
    from layer2.build import run_card
    from layer2.catalog.card_payload import default_for
    from layer2.catalog import card_fill_recipe
    from layer2.emit.metadata.producer import metadata_reference, _get, _has
    from validate.leaf_classify import classify
    d = _l2_inputs()
    out = run_card("t5", 5, d["l1a"], d["l1b"])
    assert out["conforms"] is True
    assert out["failure"] is None                                             # roster-served: no fields-empty error
    assert out["$ctx"] == "panel-overview-shell/real-time-monitoring::g0"     # group atom
    assert out["swap_decision"]["origin"] == "kept"
    # exact_metadata: chrome byte-faithful to the STRIPPED default — every non-morphed leaf byte-identical to
    # metadata_reference(default); declared morphs are the only legitimate deltas (gate re-checked here).
    dp = default_for(5, "panel-overview-shell/real-time-monitoring")
    ref = metadata_reference(dp["payload"], dp["payload_stripped"])   # STORED seedless skeleton (read directly, no re-strip)
    ok, issues = gate_exact_metadata(out["exact_metadata"], ref, morphed=out["_applied_morphs"])
    assert ok, issues
    # NO seed values: every DATA leaf ships either the typed placeholder from the stripped ref (produce strip-at-
    # source) or the split()-elided None (enforce_exact_metadata path — filled live on the frontend) — NEVER the
    # harvested demo number (produce() rejects data-leaf morphs, so this holds whatever the AI declared).
    for leaf in classify(dp["payload"]).get("data_leaves") or []:
        p = leaf["path"]
        if _has(out["exact_metadata"], p) and _has(ref, p):
            got = _get(out["exact_metadata"], p)
            assert got is None or got == _get(ref, p), f"seed value survived at {p}: {got!r}"
    # roster present: the card_fill_recipe truth ships (member-scope slots), even if the AI omitted them
    spec_slots = {s.get("slot") for s in (card_fill_recipe.read(5).get("roster_spec") or {}).get("slots") or []}
    roster = out["data_instructions"].get("roster") or []
    assert spec_slots and spec_slots <= {r.get("slot") for r in roster}


def test_swap_target_reemit(monkeypatch):
    """When the gate ACCEPTS a swap to target T, run_card re-emits for T → final card_id=T, payload authored for T,
    _reemit_of=original. (The first emit was for the shown card's shape; the second is for the final card.)"""
    import layer2.build as B
    from layer2.card_input import build_card_input
    d = _l2_inputs()
    l1a, l1b = d["l1a"], d["l1b"]

    # pick a REAL swap target from #5's CURRENT pool (the pool is restricted to the 9 available pages, so the target
    # must come from the live pool — not a hardcoded id). Force the AI to swap #5 -> target, then keep for target.
    pool = build_card_input("t", 5, l1a, l1b)["swap_candidates"]
    if not pool:
        pytest.skip("no swap candidates in #5's available-pages pool")
    target = pool[0]["card_id"]
    calls = []

    def fake_emit(ci, feedback=None):
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
    import layer2.build as B
    d = _l2_inputs()
    calls = []

    def fake_emit(ci, feedback=None):
        calls.append(ci["card_id"])
        return {"swap_decision": {"action": "keep"}, "exact_metadata": {"heatmap": {}},
                "data_instructions": {"payload_shape": "x", "fields": []}}

    monkeypatch.setattr(B, "emit", fake_emit)
    out = B.run_card("t", 5, d["l1a"], d["l1b"])
    assert out["card_id"] == 5 and out["_reemit_of"] is None and calls == [5]   # KEEP → single emit, no re-emit
