"""★ PER-LEAF PAYLOAD_ERROR PARTITION — a single malformed/unbindable FIELD (or a NO-OP rejected morph) that already
HONEST-BLANKS at fill must NOT stamp a card-level payload_error (conforms=False). The mandate: degrade PER-LEAF,
verdicts are TELEMETRY, never a card gate.

Before this fix, 6-7 cards (62/72/77/59/54 = derived-without-fn / bucketed-no-column; 42 = rejected non-leaf morphs)
shipped conforms=False even though they RENDERED partial/honest_blank correctly — the audit PASSED them as honest
degradation, so the payload_error was a telemetry mislabel. build.py now partitions:
  (a) FIELD-LEVEL gate issues (shaped 'fields[…]') → di._per_leaf_gaps + a data_note, NOT a failure; ok_d recomputed
      over only the CARD-STRUCTURAL issues so conforms stays True when only per-leaf field issues remain;
  (b) a NO-OP rejected morph ('… is not a real metadata leaf' / 'declared morphed but no value') → di._noop_morphs,
      NOT a failure (the byte-identical default shipped, it never rendered).
A GENUINE card failure is untouched: a fields-REQUIRED card with EMPTY fields still conforms=False (card-structural),
and an llm_err card still fails.

Non-live: pure in-memory emit via monkeypatch (no LLM, no :5433). Reads only cmd_catalog structure (reachable offline).
"""
import pytest

from layer2.gates import gate_data_instructions


# ── card + inputs: a real SINGLE-ASSET, fields-REQUIRED card (harvested default present, not a roster/fields-optional
#    class) so the field gate genuinely fires and the partition is exercised end-to-end through _finalize.
_CARD = 36
_PAGE = "individual-feeder-meter-shell/real-time-monitoring"


def _l1a():
    return {"page_key": _PAGE, "metric": "kw", "intent": "snapshot", "story": "Real Time Monitoring",
            "interdependency_groups": [],
            "cards": [{"card_id": _CARD, "title": "Live Readings", "analytical_story": "live per-meter readings"}]}


def _l1b():
    # a real single feeder meter asset (its own device table); a small real basket so a valid raw field can bind.
    return {"asset": {"mfm_id": 174, "name": "Feeder-1", "table": "gic_174", "class": "Feeder",
                      "has_data": True, "has_feeders": False},
            "column_basket": {"tables": ["gic_174"],
                              "columns": [{"column": "active_power_total_kw", "metric": "kw"}]}}


def _run(monkeypatch, di, *, exact_metadata=None, morphs=None, llm_error=None):
    """Drive the full run_card/_finalize path for card 36 with a synthetic emit (no swap → single emit)."""
    import layer2.build as B

    def fake_emit(ci, feedback=None):
        raw = {"swap_decision": {"action": "keep"}, "answerability": "full",
               "data_instructions": dict(di)}
        if llm_error is not None:
            return {"_llm_error": llm_error, "_llm_error_detail": "synthetic transport failure"}
        if morphs is not None:                       # morph-map contract emit ({"morphs": {...}})
            raw["morphs"] = dict(morphs)
        else:
            raw["exact_metadata"] = dict(exact_metadata or {})
        return raw

    monkeypatch.setattr(B, "emit", fake_emit)
    return B.run_card(f"t_{_CARD}", _CARD, _l1a(), _l1b())


def _has_default():
    from layer2.catalog.card_payload import default_for
    dp = default_for(_CARD, _PAGE)
    return bool(dp and dp.get("payload_stripped"))


# ── (0) sanity: the gate DOES emit the per-leaf field issue we partition on (guards against a silent gate change) ─────
def test_gate_emits_field_level_issue_for_derived_without_fn():
    di = {"payload_shape": "x", "orientation": "v",
          "fields": [{"slot": "data.readings.activePower.value", "kind": "derived", "base_columns": []}]}  # no fn
    ok, issues = gate_data_instructions(di, {"columns": []})
    assert not ok
    assert any(i.startswith("fields[") and "kind=derived without fn" in i for i in issues), issues


# ── (1) ONE malformed field (derived-without-fn) + a valid field → conforms True, NO payload_error, per-leaf recorded ─
def test_one_bad_field_still_conforms_and_honest_blanks(monkeypatch):
    if not _has_default():
        pytest.skip(f"card {_CARD} has no harvested payload_stripped — cannot exercise _finalize")
    di = {"payload_shape": "x", "orientation": "v", "fields": [
        # the MALFORMED leaf: a derived field with NO fn — it honest-blanks at fill (fn None → nothing derives)
        {"slot": "data.readings.reactivePower.value", "kind": "derived", "base_columns": ["active_power_total_kw"]},
        # a VALID sibling that still fills — proves per-leaf, not per-card, degradation
        {"slot": "data.readings.activePower.value", "kind": "raw", "source": "live",
         "column": "active_power_total_kw", "metric": "kw"},
    ]}
    out = _run(monkeypatch, di, exact_metadata={})
    assert out["conforms"] is True, out.get("failure")
    assert out["failure"] is None, "a single honest-blanking field must NOT be a card-blocking payload_error"
    # the per-leaf gate issue is recorded as TELEMETRY, not dropped
    gaps = out["data_instructions"].get("_per_leaf_gaps") or []
    assert any("kind=derived without fn" in g for g in gaps), gaps
    # the malformed derived leaf still SHIPS (fn None) so the executor honest-blanks it at fill — never removed here
    slots = {f.get("slot") for f in out["data_instructions"].get("fields") or []}
    assert "data.readings.reactivePower.value" in slots
    # the sibling still binds its real column — the card renders its real component with a live leaf
    live = [f for f in out["data_instructions"]["fields"] if f.get("slot") == "data.readings.activePower.value"]
    assert live and live[0].get("column") == "active_power_total_kw"
    # per-leaf degradation → a user-facing note + softened answerability, but never a gap/re-route
    assert out["data_note"]
    assert out["answerability"] in ("partial", "none")
    assert out["gap"] is False


# ── (2) a rejected NON-LEAF morph → conforms True, the byte-identical default metadata ships, recorded as no-op ───────
def test_rejected_nonleaf_morph_still_conforms(monkeypatch):
    if not _has_default():
        pytest.skip(f"card {_CARD} has no harvested payload_stripped — cannot exercise the morph path")
    # a morph on a path that is NOT a real metadata leaf → produce()/morphmap_apply reject it as a no-op (the default
    # ships). Emit ONE valid field so the DATA gate is clean and only the morph rejection is in play.
    di = {"payload_shape": "x", "orientation": "v", "fields": [
        {"slot": "data.readings.activePower.value", "kind": "raw", "source": "live",
         "column": "active_power_total_kw", "metric": "kw"}]}
    out = _run(monkeypatch, di, morphs={"this.path.is.not.a.real.metadata.leaf.at.all": "x"})
    assert out["conforms"] is True, out.get("failure")
    assert out["failure"] is None, "a no-op non-leaf morph (default shipped, never rendered) must not be a payload_error"
    # the default metadata still ships (the component mounts)
    assert out["exact_metadata"]
    # the rejection is recorded as no-op telemetry, and never leaked into a failure
    noop = out["data_instructions"].get("_noop_morphs") or []
    assert any("not a real metadata leaf" in n for n in noop), noop


# ── (3) a genuinely fields-REQUIRED card with EMPTY fields → STILL conforms False (card-structural, NOT partitioned) ──
def test_empty_fields_required_card_still_fails():
    """The card-STRUCTURAL 'data_instructions.fields is empty' does NOT carry the 'fields[' prefix, so it is NEVER
    partitioned — a fields-required card with no fields still fails honestly. Unit-level: assert directly that the
    partition key ('fields[') does not match this structural issue (build.py keeps ok_d False for it)."""
    di = {"payload_shape": "x", "orientation": "v", "fields": []}
    ok, issues = gate_data_instructions(di, {"columns": [{"column": "active_power_total_kw"}]}, fields_optional=False)
    assert not ok and any("fields is empty" in i for i in issues)
    # the partition keys on the 'fields[' PREFIX — the structural issue has no such prefix, so it stays a failure
    struct = [i for i in issues if not str(i).startswith("fields[")]
    assert any("fields is empty" in i for i in struct), struct
    assert struct, "the card-structural issue must remain in the non-partitioned (failure) bucket"


def test_empty_fields_required_card_still_fails_end_to_end(monkeypatch):
    """End-to-end: a fields-REQUIRED card 36 emitting fields:[] (no roster, non-empty basket) still conforms=False —
    the empty-fields structural error survives the partition and blocks the card honestly."""
    if not _has_default():
        pytest.skip(f"card {_CARD} has no harvested payload_stripped")
    out = _run(monkeypatch, {"payload_shape": "x", "orientation": "v", "fields": []}, exact_metadata={})
    assert out["conforms"] is False
    assert (out["failure"] or {}).get("detail"), "must fail HONESTLY with a stated reason"
    assert "fields is empty" in (out["failure"] or {}).get("detail", "")


# ── (4) an llm_err card → CONFORMING SKELETON (infra family; audit 04 F1/F6) ────────────────────────────────────────
def test_llm_error_card_degrades_to_conforming_skeleton(monkeypatch):
    """The INFRA family (llm timeout/transport) no longer hard-fails the card: it ships a conforming skeleton —
    real component, per-leaf 'emit_failed' reasons — so no hard_fail count and no wasted page reroute. The
    telemetry keeps the whole story (_emit_failed carries the classified failure)."""
    out = _run(monkeypatch, {"payload_shape": "x", "orientation": "v", "fields": []}, llm_error="timeout")
    assert out["conforms"] is True
    assert out["failure"] is None
    assert out["answerability"] == "partial" and out["gap"] is False
    ef = out.get("_emit_failed") or {}
    assert ef.get("stage") == "llm" and "timeout" in (ef.get("reason") or ""), ef
    gaps = (out.get("data_instructions") or {}).get("_emit_gaps") or []
    assert gaps and all(g.get("cause") == "emit_failed" for g in gaps)   # per-leaf reasons, restamped
    # the exec-side skip predicate (host/exec_cards) must accept this card: no exception, real metadata
    assert "exception" not in out and out.get("exact_metadata") is not None


def test_llm_error_rollback_knob_off_restores_conforms_false(monkeypatch):
    """The pre-2026-07-15 contract, byte-preserved under layer2.emit_failed_skeleton=off (the rollback lane)."""
    import layer2.emit_failed as EF
    monkeypatch.setattr(EF, "enabled", lambda: False)
    out = _run(monkeypatch, {"payload_shape": "x", "orientation": "v", "fields": []}, llm_error="timeout")
    assert out["conforms"] is False
    f = out["failure"] or {}
    assert f.get("stage") == "llm" and "timeout" in (f.get("reason") or ""), f
