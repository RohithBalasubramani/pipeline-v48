"""tests/test_stage_telemetry_item15.py — ITEM 15 [outputs/AI_QUALITY_BACKLOG.md B2]: the basket / asset_resolve /
stories LLM call sites must THREAD THEIR STAGE NAME into the failure recorder (before: 84 outage entries bucketed as
stage='-'), replace their literal timeouts with the DB-driven llm.timeout.<stage> rows, and degrade HONESTLY:
  · layer1b/basket/column_basket — stage='basket', transient-only retry (llm/transient_retry), llm_failed rides in the basket and is surfaced via
    layer1b contract_problems (the basket falls back to the logged floor — never silently empty, never fabricated);
  · layer1b/resolve/asset_resolve — stage='asset_resolve' (timeout now read INSIDE the client from the same
    llm.timeout.asset_resolve row the call site used to read locally);
  · layer1a/story_builder — stage='stories' + on_error='marker' so an OUTAGE is recorded as
    record('layer1a','stories_llm_failed') instead of silently setting every story='' (the degrade path itself is
    unchanged: stories stay '' — telemetry only, no fabrication).

Non-live: every DB/schema read and the LLM call are mocked; no live Qwen and no live neuract dependency."""
from unittest.mock import patch

import obs.failures as failures
from layer1a import story_builder as sb
from layer1b.basket import column_basket as cb
from layer1b.resolve import asset_resolve as ar
from layer1b.schema import build_layer1b_output, validate_layer1b_output


class _Recorder:
    """A call_qwen stand-in that captures every call's kwargs and replays canned results (last result repeats)."""

    def __init__(self, results):
        self.calls = []
        self._results = list(results)

    def __call__(self, system, user, **kw):
        self.calls.append(kw)
        return self._results.pop(0) if len(self._results) > 1 else self._results[0]


# ── layer1b basket (stage='basket') ─────────────────────────────────────────────────────────────────────────────────
_DICT = [
    ["voltage_r_n", "Voltage R N", "raw", "V"],
    ["current_r", "Current R", "raw", "A"],
]
_LOGGED = {"voltage_r_n", "current_r"}
_ASSET = {"table": "gic_x_test", "class": "AHU", "name": "GIC-X-TEST"}


def _run_basket(recorder):
    with patch.object(cb, "col_dict", return_value=[list(c) for c in _DICT]), \
         patch.object(cb, "window_nonnull", return_value=set(_LOGGED)), \
         patch.object(cb, "call_qwen", recorder):
        return cb.build_basket("voltage and current health", _ASSET)


def test_basket_stage_named_and_retry_once_on_outage():
    """A TRANSIENT outage (marker kind not in llm.no_retry_kinds) is retried EXACTLY once, every attempt carries
    stage='basket' (no literal timeout — the per-stage row llm.timeout.basket drives it inside the client), and
    llm_failed=True rides in the basket while the logged floor still fills the columns (honest degrade, never an
    empty basket). [llm/transient_retry — the ONE shared policy]"""
    rec = _Recorder([{"_llm_error": "http", "_llm_error_detail": "connection refused"}])
    b = _run_basket(rec)
    assert len(rec.calls) == 2                                        # transient: one bounded retry, no more
    assert all(c.get("stage") == "basket" for c in rec.calls)
    assert all("timeout" not in c for c in rec.calls)                 # DB row (llm.timeout.basket), not a literal
    assert b["llm_failed"] is True
    assert b["n_columns"] == 2                                        # logged floor rescued the real columns
    assert all(col["has_data"] for col in b["columns"])               # floor columns are real — nothing fabricated


def test_basket_deterministic_failure_fails_fast_no_retry():
    """The no-retry rule [emit-timeout gotcha]: a DETERMINISTIC failure kind (llm.no_retry_kinds — timeout/truncated)
    is NEVER re-sent (retrying doubles the hang); the basket still degrades honestly to the logged floor."""
    rec = _Recorder([{"_llm_error": "timeout", "_llm_error_detail": "read timed out"}])
    b = _run_basket(rec)
    assert len(rec.calls) == 1                                        # fail fast: no second attempt
    assert b["llm_failed"] is True
    assert b["n_columns"] == 2                                        # logged floor rescued the real columns


def test_basket_stage_named_single_call_on_success():
    rec = _Recorder([{"feasible": ["current_r"], "probable": []}])
    b = _run_basket(rec)
    assert len(rec.calls) == 1 and rec.calls[0].get("stage") == "basket"
    assert b["llm_failed"] is False


def test_basket_no_asset_early_return_carries_llm_failed_false():
    assert cb.build_basket("x", None)["llm_failed"] is False


def test_basket_llm_failed_surfaces_via_contract_problems():
    basket = {"columns": [{"column": "current_r"}], "n_columns": 1, "llm_failed": True}
    out = build_layer1b_output({"asset": {"mfm_id": 1}, "how": "AI", "candidates": []}, basket)
    assert any("basket llm_failed" in p for p in validate_layer1b_output(out))


def test_basket_llm_ok_no_contract_problem():
    basket = {"columns": [{"column": "current_r"}], "n_columns": 1, "llm_failed": False}
    out = build_layer1b_output({"asset": {"mfm_id": 1}, "how": "AI", "candidates": []}, basket)
    assert validate_layer1b_output(out) == []


# ── layer1b asset resolve (stage='asset_resolve') ───────────────────────────────────────────────────────────────────
# registry-row contract: [id, name, table, mfm_type_id, load_group, class, has_data, has_feeders, never_wired, table_exists]
_ROWS = [
    [1, "Alpha Meter", "gic_alpha", "", "LG-1", "AHU", True, False, False, True],
    [2, "Beta Meter", "gic_beta", "", "LG-1", "AHU", True, False, False, True],
]


def test_asset_resolve_stage_named_no_literal_timeout():
    rec = _Recorder([{"confident": True, "names": ["Alpha Meter"], "candidates": []}])
    with patch.object(ar, "asset_candidates", return_value=[list(r) for r in _ROWS]), \
         patch.object(ar, "class_from_subject", return_value=None), \
         patch.object(ar, "call_qwen", rec):
        r = ar.resolve_asset("health check for the alpha meter")
    assert rec.calls and all(c.get("stage") == "asset_resolve" for c in rec.calls)
    assert all("timeout" not in c for c in rec.calls)                 # llm.timeout.asset_resolve row, read in the client
    assert r["how"] == "AI" and r["asset"]["mfm_id"] == 1             # resolution outcome unchanged by the telemetry


def test_asset_resolve_outage_still_retries_once_with_stage():
    from layer1b.resolve import empty_fallback as ef                  # the outage path browses the registry — mock it
    rec = _Recorder([{"_llm_error": "http", "_llm_error_detail": "connection refused"}])   # TRANSIENT outage marker
    with patch.object(ar, "asset_candidates", return_value=[list(r) for r in _ROWS]), \
         patch.object(ef, "asset_candidates", return_value=[list(r) for r in _ROWS]), \
         patch.object(ar, "class_from_subject", return_value=None), \
         patch.object(ar, "call_qwen", rec):
        r = ar.resolve_asset("health check for the alpha meter")
    assert len(rec.calls) == 2 and all(c.get("stage") == "asset_resolve" for c in rec.calls)
    assert r["llm_failed"] is True and r["how"] == "ambiguous"        # honest degrade: browse picker, never silent empty


# ── layer1a stories (stage='stories' + stories_llm_failed record) ───────────────────────────────────────────────────
_CARDS = [{"card_id": 5, "title": "T", "analytical_role": "role", "card_purpose": "purpose of the card"}]


def _run_stories(recorder, recorded):
    with patch.object(sb, "read_page_cards", return_value=[dict(c) for c in _CARDS]), \
         patch.object(sb, "call_qwen", recorder), \
         patch.object(failures, "record", lambda *a, **k: recorded.append((a, k))):
        return sb.build_stories("prompt", "page/x", "power", "snapshot")


def test_stories_outage_recorded_with_stage():
    """An LLM outage on the story call is no longer silent: the call names stage='stories' (per-stage timeout row +
    llm telemetry) and the degradation (every story='') is recorded as record('layer1a','stories_llm_failed')."""
    rec, recorded = _Recorder([{"_llm_error": "timeout", "_llm_error_detail": "timed out"}]), []
    cards = _run_stories(rec, recorded)
    assert rec.calls[0].get("stage") == "stories"
    assert rec.calls[0].get("on_error") == "marker"                   # outage distinguishable from an honest empty emit
    assert cards[0]["analytical_story"] == ""                         # degrade path unchanged: blank, never fabricated
    assert recorded and recorded[0][0][:2] == ("layer1a", "stories_llm_failed")
    assert "timeout" in recorded[0][1].get("detail", "")              # the classified kind rides in the detail


def test_stories_success_not_recorded():
    rec, recorded = _Recorder([{"stories": {"5": "the story"}}]), []
    cards = _run_stories(rec, recorded)
    assert cards[0]["analytical_story"] == "the story"
    assert recorded == []                                             # no failure record on the success path
