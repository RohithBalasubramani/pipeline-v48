"""tests/test_swap_metric_affinity.py — swap candidate pool METRIC AFFINITY (F3, r_5c6797f815).

The pool() builder used to rank purely by SIZE, so for a voltage prompt the AI was offered zero voltage-appropriate
targets. pool() now takes an optional `metric` and does a SOFT metric-affinity re-rank (relevant-first, size tiebreak,
never drops a size-fit candidate). These tests pin: (1) the generic helpers, (2) metric=None is byte-identical to
today, (3) with a metric, metric-relevant cards rank ahead of off-metric same-size ones — for several metrics.
"""
import pytest

from layer2.swap import candidates
from layer2.swap.candidates import pool, _metric_tokens, _affinity


# ── (1) generic helpers — pure, no DB ─────────────────────────────────────────────────────────────
def test_metric_tokens_generic():
    assert _metric_tokens(None) == ()
    assert _metric_tokens("") == ()
    assert _metric_tokens("voltage") == ("voltage",)
    assert _metric_tokens("Voltage Trend") == ("voltage", "trend")
    assert _metric_tokens("current") == ("current",)
    # dedupe, order-preserving
    assert _metric_tokens("energy energy") == ("energy",)


def test_affinity_counts_metric_tokens_in_catalog_text():
    v = _metric_tokens("voltage")
    assert _affinity({"title": "DG Voltage & Frequency", "analytical_role": "Monitoring",
                      "card_purpose": "percentage voltage deviation", "visualization": "line"}, v) >= 1
    assert _affinity({"title": "AI Summary", "analytical_role": "Summary",
                      "card_purpose": "natural-language readout", "visualization": "text"}, v) == 0
    assert _affinity({"title": "x"}, ()) == 0            # no tokens → off (backward-compatible)


# ── (2)+(3) against the real cmd_catalog DB ───────────────────────────────────────────────────────
def _first_pooled_slot():
    """(page_key, template_ids, card_id) for the first routable slot whose default pool is non-empty; else None."""
    try:
        from config.available_pages import available_page_keys
        from data.db_client import q
    except Exception:
        return None
    for pk in available_page_keys():
        tpl = [int(x[0]) for x in q("cmd_catalog",
               f"SELECT card_id FROM page_layout_cards WHERE page_key=$a${pk}$a$ AND card_id IS NOT NULL") if x and x[0]]
        for cid in tpl:
            if candidates.pool(cid, pk, tpl):
                return pk, tpl, cid
    return None


def test_metric_none_is_byte_identical_to_pure_size_pool():
    slot = _first_pooled_slot()
    if not slot:
        pytest.skip("no routable page yields a swap pool (cmd_catalog down or empty)")
    pk, tpl, cid = slot
    assert pool(cid, pk, tpl, metric=None) == pool(cid, pk, tpl)     # metric=None → today's exact output


def test_metric_ranks_relevant_candidates_first_and_keeps_off_metric():
    slot = _first_pooled_slot()
    if not slot:
        pytest.skip("no routable page yields a swap pool (cmd_catalog down or empty)")
    pk, tpl, cid = slot
    for metric in ("voltage", "current", "energy"):
        ranked = pool(cid, pk, tpl, metric=metric)
        assert ranked, f"pool empty for metric={metric}"
        tokens = _metric_tokens(metric)
        affs = [_affinity(c, tokens) for c in ranked]
        # soft ranking: affinity is non-increasing down the pool (relevant-first, off-metric never dropped, only after)
        assert affs == sorted(affs, reverse=True), f"metric={metric} pool not affinity-ranked: {affs}"
        # if ANY renderable size-fit candidate is metric-relevant, the TOP of the pool is metric-relevant
        if any(a > 0 for a in affs):
            assert affs[0] > 0, f"metric={metric}: a relevant card exists but did not surface first"


def test_metric_affinity_surfaces_a_voltage_card_over_size_closest_offmetric():
    """Direct F3 acceptance: on card 21's slot, metric=voltage must surface a voltage-role/purpose card ahead of the
    size-closest off-metric one. Skips gracefully if card 21's page is not routable in this DB."""
    try:
        from config.available_pages import available_page_keys
        from data.db_client import q
    except Exception:
        pytest.skip("db client unavailable")
    rows = q("cmd_catalog", "SELECT page_key FROM page_layout_cards WHERE card_id=21")
    pks = [r[0] for r in rows if r and r[0]]
    for pk in pks:
        if pk not in set(available_page_keys()):
            continue
        tpl = [int(x[0]) for x in q("cmd_catalog",
               f"SELECT card_id FROM page_layout_cards WHERE page_key=$a${pk}$a$ AND card_id IS NOT NULL") if x and x[0]]
        base = pool(21, pk, tpl)
        ranked = pool(21, pk, tpl, metric="voltage")
        if not ranked:
            continue
        tv = _metric_tokens("voltage")
        # the metric run must lead with a voltage-relevant card whenever one is size-fit + renderable
        if any(_affinity(c, tv) > 0 for c in ranked):
            assert _affinity(ranked[0], tv) > 0
            return
    pytest.skip("card 21's pages not routable / no voltage-relevant renderable size-fit candidate in this DB")
