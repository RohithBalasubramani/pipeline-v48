"""ZERO-SKELETON EMITS [cards 19/25 — fullsweep_20260706_004334 v18_04/v18_05]: an emit whose exact_metadata is the
bare skeleton with NOTHING bound (fields [] and no roster) and NO data channel that could fill it (no consumer
endpoint, no backend_strategy) shipped the stripped 0/[] placeholders as if they were values — the false '0 issues'
story, answerability silently defaulting to 'full', zero per-leaf reasons.

layer2/build._finalize now treats that shape as HONEST-BLANK TELEMETRY WITH REASONS (di._zero_skeleton +
'unbound_by_emit' _emit_gaps per data leaf + answerability ≤ partial + a data_note), never a silent empty card and
never a card-blocking gate. A special/narrative card WITH a backend_strategy (the card-8 working AI summary) and a
bound card are exempt. All non-live, deterministic (offline: DB cfg fail-open to code defaults)."""
import copy

from layer2.build import _finalize


_PAYLOAD = {"title": "AI Summary", "stats": {"total": 7.0, "neutral": 3.0}}
_STRIPPED = {"title": "AI Summary", "stats": {"total": 0.0, "neutral": 0.0}}


def _ci(handling_class="narrative_ai", backend_strategy=None):
    return {
        "card_id": 999, "group_id": None, "is_group_card": False, "page_key": "test-shell/x",
        "run_id": "t-run", "story": {"analytical_story": "s", "template_card_ids": []},
        "column_basket": {"columns": [{"column": "active_power_total_kw", "unit": "kW"}]},
        "asset": {"mfm_id": 1, "table": None, "panel_id": None, "class": "UPS", "name": "X"},
        "swap_candidates": [],
        "catalog_row": {
            "card_id": 999, "handling_class": handling_class, "backend_strategy": backend_strategy,
            "resolver_scope": "meter", "contract": {}, "controls": {}, "feasibility": {},
            "recipe": {"payload_shape": "snapshot", "orientation": "snapshot", "entity_dim": "meter"},
            "default_payload": {"payload": copy.deepcopy(_PAYLOAD),
                                "payload_stripped": copy.deepcopy(_STRIPPED),
                                "data_paths": ["stats.total", "stats.neutral"]},
        },
    }


def _raw(answerability="full", fields=None):
    return {"exact_metadata": copy.deepcopy(_STRIPPED),
            "data_instructions": {"fields": fields or []},
            "answerability": answerability}


def test_zero_skeleton_becomes_honest_blank_telemetry_with_reasons():
    out = _finalize(_ci(), _raw("full"), {"action": "keep"})
    di = out["data_instructions"]
    assert di.get("_zero_skeleton") is True
    assert out["answerability"] == "partial"                      # never a silent 'full'
    assert out["data_note"]                                       # honesty note always present
    gaps = di.get("_emit_gaps") or []
    assert gaps and all(g.get("reason") for g in gaps)            # EVERY blank leaf carries a reason
    assert {g["slot"] for g in gaps} >= {"stats.total", "stats.neutral"}
    assert out["gap"] is False                                    # partial ≠ re-route; verdicts are telemetry


def test_ai_declared_none_keeps_none_but_still_gets_reasons():
    out = _finalize(_ci(), _raw("none"), {"action": "keep"})
    assert out["answerability"] == "none"                         # the AI's honest escape is preserved
    assert out["data_instructions"].get("_zero_skeleton") is True
    assert out["data_instructions"].get("_emit_gaps")


def test_backend_strategy_channel_exempts():
    """The card-8 class: a narrative card whose data arrives through its backend_strategy consumer is NOT a
    zero-skeleton — nothing is downgraded."""
    out = _finalize(_ci(backend_strategy="consumers/real_time_monitoring/pcc_panel.py"), _raw("full"),
                    {"action": "keep"})
    assert out["data_instructions"].get("_zero_skeleton") is None
    assert out["answerability"] == "full"


def test_bound_fields_exempt():
    fields = [{"slot": "stats.total", "kind": "raw", "column": "active_power_total_kw",
               "metric": "total", "source": "live", "agg": "last"}]
    out = _finalize(_ci(handling_class="single_asset"), _raw("full", fields=fields), {"action": "keep"})
    assert out["data_instructions"].get("_zero_skeleton") is None
