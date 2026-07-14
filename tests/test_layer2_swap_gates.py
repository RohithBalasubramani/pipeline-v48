"""Swap-architecture conformance — the six REQUIRED behaviors, unit-level against the REAL cmd_catalog (no LLM):

  (a) the AI swap_decision is gated DETERMINISTICALLY (confidence / vague / pool / dedup / cascade);
  (b) an UNRENDERABLE current card (feasibility drop/no_data) is FORCE-SWAPPED to a renderable pool candidate;
  (c) the pool = size-matched candidates filtered to render_real + recoverable-default + registered renderer,
      off-page/off-template, available pages only, closest-first;
  (d) an ACCEPTED swap RE-EMITS Layer 2 for the TARGET shape (the output is finalized against the FINAL card);
  (e) already_chosen prevents two slots landing on the same target (gate, forced pick, AND the settle post-pass);
  (f) Layer 1a drops a whole template only at >= cfg feasibility.template_max_unrenderable_frac and reselects.
"""
import pytest

from config.swap import MIN_CONFIDENCE
from config import feasibility as feas_cfg
from data.db_client import q
from layer2.swap.decide import gate as swap_gate
from layer2.swap import gate_force_renderable, candidates
from layer1a.parse.template_feasibility_gate import filter_renderable_templates

_BASE = dict(pool_ids=[99, 98], template_card_ids=[7], already_chosen=set(), page_card_ids=[5, 7],
             current_card_id=5)
_POOL = [{"card_id": 99, "title": "closest"}, {"card_id": 98, "title": "second"}]


def _swap(conf=None, crit="sankey flow angle", to=99):
    return {"action": "swap", "confidence": MIN_CONFIDENCE if conf is None else conf,
            "criterion": crit, "swap_to_id": to}


def _template(pk):
    return [int(x[0]) for x in q("cmd_catalog",
            f"SELECT card_id FROM page_layout_cards WHERE page_key=$a${pk}$a$ AND card_id IS NOT NULL") if x and x[0]]


# ── (a) deterministic gating of the AI decision ──────────────────────────────────────────────────
def test_a_keep_is_normalized():
    d = swap_gate({"action": "keep"}, **_BASE)
    assert d["action"] == "keep" and d["origin"] == "kept" and d["swap_to_id"] is None


def test_a_confidence_gate():
    assert swap_gate(_swap(conf=MIN_CONFIDENCE - 0.01), **_BASE)["origin"] == "kept"
    assert swap_gate(_swap(conf=MIN_CONFIDENCE), **_BASE)["origin"] == "swapped"
    assert swap_gate(_swap(conf="junk"), **_BASE)["origin"] == "kept"          # unparseable confidence never passes


def test_a_vague_criterion_rejected():
    assert swap_gate(_swap(crit="better"), **_BASE)["origin"] == "kept"        # config.swap VAGUE_CRITERIA
    assert swap_gate(_swap(crit=""), **_BASE)["origin"] == "kept"


def test_a_target_must_be_in_slot_pool():
    assert swap_gate(_swap(to=1234), **_BASE)["origin"] == "kept"              # off-pool → kept


def test_a_cascade_all_or_nothing():
    d = _swap()
    d["cascade"] = [{"swap_to_id": 98}]
    assert swap_gate(dict(d), **_BASE)["origin"] == "swapped"                  # every partner resolves in-pool
    d["cascade"] = [{"swap_to_id": 4321}]
    assert swap_gate(dict(d), **_BASE)["origin"] == "kept"                     # one partner off-pool → whole swap off


# ── (b) force-swap of an unrenderable current card ───────────────────────────────────────────────
def test_b_unrenderable_vocab_is_the_config_knob():
    # no hardcoded verdict list in the gate: the vocab IS config.feasibility.UNRENDERABLE_VERDICTS (DB-driven,
    # lazy PEP-562 attr — each access re-reads cfg(), so equality not identity).
    assert tuple(feas_cfg.UNRENDERABLE_VERDICTS) == ("drop", "no_data")
    for v in feas_cfg.UNRENDERABLE_VERDICTS:
        assert gate_force_renderable.is_unrenderable(v)
    for v in ("render_real", "static_chrome", None, ""):
        assert not gate_force_renderable.is_unrenderable(v)


@pytest.mark.parametrize("verdict", list(feas_cfg.UNRENDERABLE_VERDICTS))
def test_b_force_swap_overrides_ai_keep(verdict):
    d = swap_gate({"action": "keep"}, **_BASE, current_verdict=verdict, pool=_POOL)
    assert d["action"] == "swap" and d["origin"] == "swapped"
    assert d["swap_to_id"] == 99 and d.get("forced_renderable") is True        # pool[0] = closest renderable


def test_b_force_swap_overrides_a_gated_out_ai_swap():
    # the AI wanted a swap but failed the confidence gate; the card still can't render → forced anyway.
    d = swap_gate(_swap(conf=0.1), **_BASE, current_verdict="drop", pool=_POOL)
    assert d["origin"] == "swapped" and d["swap_to_id"] == 99 and d.get("forced_renderable") is True


def test_b_renderable_current_card_is_never_forced():
    for verdict in ("render_real", "static_chrome", None):
        d = swap_gate({"action": "keep"}, **_BASE, current_verdict=verdict, pool=_POOL)
        assert d["action"] == "keep" and "forced_renderable" not in d


def test_b_no_candidate_keeps_honestly_and_flags():
    d = swap_gate({"action": "keep"}, **_BASE, current_verdict="no_data", pool=[])
    assert d["action"] == "keep" and d.get("forced_kept_unrenderable") is True
    assert d.get("forced_renderable") is False                                 # honest: nothing invented


def test_b_forced_swap_is_stamped_settle_priority_confidence():
    # a FORCED swap is MANDATORY: it must outrank every optional AI stylistic swap (confidence in [0,1]) in the
    # settle's highest-confidence-first ordering, else a collision reverts it and the UNRENDERABLE card ships.
    d = swap_gate(_swap(conf=0.1), **_BASE, current_verdict="drop", pool=_POOL)
    assert d["confidence"] == gate_force_renderable.FORCED_SWAP_CONFIDENCE
    assert d["confidence"] > 1.0                                               # > the AI's whole range
    assert d["ai_confidence"] == 0.1                                           # the AI's own value kept for audit


def test_b_forced_swap_wins_settle_collision_against_stylistic_swap():
    # slot 12's card is UNRENDERABLE (forced swap to 77); slot 11 merely PREFERS 77 (stylistic, conf 0.99).
    # The forced swap must win the target; the stylistic slot reverts to KEEP (its own card still renders fine).
    from grounding.swap_settle import settle
    forced = swap_gate({"action": "keep"}, **_BASE, current_verdict="drop",
                       pool=[{"card_id": 77, "title": "only fit"}])
    outputs = {
        11: {"swap_decision": {"action": "swap", "swap_to_id": 77, "confidence": 0.99}},
        12: {"swap_decision": forced},
    }
    st = settle(outputs, page_card_ids=[11, 12], template_card_ids=[11, 12])
    assert {"card_id": 12, "target": 77} in st["swaps"]                        # the MANDATORY swap claims the target
    assert outputs[11]["swap_decision"]["action"] == "keep"                    # the optional swap reverts harmlessly
    assert outputs[11]["swap_decision"].get("settled_revert") is True


# ── (b') T1-12 DATALESS AI-NOMINATION (flag swap.dataless_nomination, default off) ────────────────
_NOM_POOL = [{"card_id": 99, "title": "closest"}, {"card_id": 98, "title": "second"}]


def _enable_nomination(monkeypatch):
    """Flip the DATALESS_NOMINATION lazy knob on for one test (restored on teardown)."""
    monkeypatch.setattr(feas_cfg, "DATALESS_NOMINATION", True, raising=False)


def test_bprime_flag_off_ignores_nomination_closest_size_wins():
    # DEFAULT OFF: a pure-dataless force-swap ignores the AI nomination and takes the closest-size candidate (99),
    # byte-identical to the pre-T1-12 behavior. answerability='none' + a renderable current verdict = pure dataless.
    d = gate_force_renderable.enforce({"action": "keep", "confidence": 0.3}, verdict="render_real", pool=_NOM_POOL,
                                      already_chosen=set(), answerability="none", ai_nomination=98)
    assert d[0]["swap_to_id"] == 99 and "nominated" not in d[0]


def test_bprime_nomination_valid_in_pool_wins(monkeypatch):
    _enable_nomination(monkeypatch)
    d, kept = gate_force_renderable.enforce({"action": "keep", "confidence": 0.3}, verdict="render_real",
                                            pool=_NOM_POOL, already_chosen=set(), answerability="none", ai_nomination=98)
    assert d["swap_to_id"] == 98 and d["nominated"] is True and d["forced_renderable"] is True
    assert d["action"] == "swap" and d["origin"] == "swapped" and kept is False
    assert d["forced_dataless"] is True                                        # per-asset dataless marker rides through
    assert d["confidence"] == gate_force_renderable.FORCED_SWAP_CONFIDENCE     # mandatory settle priority
    assert d["ai_confidence"] == 0.3                                           # AI's own value kept for audit


def test_bprime_nomination_off_pool_falls_back(monkeypatch):
    _enable_nomination(monkeypatch)
    d, _ = gate_force_renderable.enforce({"action": "keep"}, verdict="render_real", pool=_NOM_POOL,
                                         already_chosen=set(), answerability="none", ai_nomination=1234)
    assert d["swap_to_id"] == 99 and "nominated" not in d                      # off-pool → closest-size fallback


def test_bprime_nomination_taken_falls_back(monkeypatch):
    _enable_nomination(monkeypatch)
    d, _ = gate_force_renderable.enforce({"action": "keep"}, verdict="render_real", pool=_NOM_POOL,
                                         already_chosen={98}, answerability="none", ai_nomination=98)
    assert d["swap_to_id"] == 99 and "nominated" not in d                      # nominated target claimed → fallback


def test_bprime_static_unrenderable_ignores_nomination(monkeypatch):
    _enable_nomination(monkeypatch)
    # a STATIC-unrenderable verdict (drop) is NOT the pure-dataless branch — the card KIND cannot render, so the
    # nomination is never consulted even with the knob on: the deterministic closest-size loop wins (99).
    d, _ = gate_force_renderable.enforce({"action": "keep"}, verdict="drop", pool=_NOM_POOL,
                                         already_chosen=set(), answerability="none", ai_nomination=98)
    assert d["swap_to_id"] == 99 and "nominated" not in d


def test_bprime_nomination_via_swap_gate_captures_pre_normalization(monkeypatch):
    # end-to-end through decide.gate: even a LOW-confidence AI swap (the gate chain would normalize it to KEEP) has its
    # raw swap_to_id captured pre-normalization and honored by the dataless nomination.
    _enable_nomination(monkeypatch)
    d = swap_gate({"action": "swap", "swap_to_id": 98, "confidence": 0.1, "criterion": "x"},
                  pool_ids=[99, 98], template_card_ids=[7], already_chosen=set(), page_card_ids=[5, 7],
                  current_card_id=5, current_verdict="render_real", pool=_NOM_POOL, answerability="none")
    assert d["swap_to_id"] == 98 and d.get("nominated") is True


# ── (e) already_chosen dedup — gate, forced pick, settle post-pass ───────────────────────────────
def test_e_gate_rejects_already_chosen_target():
    d = swap_gate(_swap(to=99), **{**_BASE, "already_chosen": {99}})
    assert d["origin"] == "kept"


def test_e_gate_rejects_template_and_page_targets():
    assert swap_gate(_swap(to=7), **{**_BASE, "pool_ids": [7, 99]})["origin"] == "kept"   # template card
    assert swap_gate(_swap(to=5), **{**_BASE, "pool_ids": [5, 99]})["origin"] == "kept"   # already on the page


def test_e_forced_swap_skips_claimed_targets():
    d = swap_gate({"action": "keep"}, **{**_BASE, "already_chosen": {99}}, current_verdict="drop", pool=_POOL)
    assert d["swap_to_id"] == 98 and d.get("forced_renderable") is True        # pool[0] claimed → next closest
    d2 = swap_gate({"action": "keep"}, **{**_BASE, "already_chosen": {99, 98}}, current_verdict="drop", pool=_POOL)
    assert d2["action"] == "keep" and d2.get("forced_kept_unrenderable") is True   # every candidate claimed


def test_e_settle_postpass_reverts_the_lower_confidence_duplicate():
    # the production runner emits in parallel with empty already_chosen; grounding.swap_settle.settle is the
    # deterministic second pass that resolves target collisions (highest confidence wins, loser reverts to KEEP).
    from grounding.swap_settle import settle
    outputs = {
        11: {"swap_decision": {"action": "swap", "swap_to_id": 77, "confidence": 0.95}},
        12: {"swap_decision": {"action": "swap", "swap_to_id": 77, "confidence": 0.92}},
        13: {"swap_decision": {"action": "keep"}},
    }
    st = settle(outputs, page_card_ids=[11, 12, 13], template_card_ids=[11, 12, 13])
    assert {"card_id": 11, "target": 77} in st["swaps"]                        # higher confidence claims the target
    assert outputs[12]["swap_decision"]["action"] == "keep"                    # loser reverted to its own card
    assert outputs[12]["swap_decision"].get("settled_revert") is True
    assert 77 in st["already_chosen"]


# ── (c) the pool, against the REAL DB ─────────────────────────────────────────────────────────────
def _pool_pages(limit_pages=2):
    """(page_key, template_ids, {card_id: pool}) for the first routable pages that yield a non-empty pool."""
    from config.available_pages import available_page_keys
    found = []
    for pk in available_page_keys():
        tpl = _template(pk)
        pools = {cid: candidates.pool(cid, pk, tpl) for cid in tpl}
        if any(pools.values()):
            found.append((pk, tpl, pools))
        if len(found) >= limit_pages:
            break
    return found


def test_c_pool_conformance_real_db():
    from grounding.swap_settle import is_registered
    from grounding.default_assemble import has_default
    from config.swap import SIZE_TOLERANCE, SWAP_POOL_MAX
    from config.available_pages import available_page_keys
    pages = _pool_pages()
    assert pages, "no routable page yields any swap pool — swap architecture would be dead"
    avail_ids = candidates._available_card_ids()
    assert avail_ids, "available-pages card universe is empty"
    for pk, tpl, pools in pages:
        page_ids = set(_template(pk))
        for cid, pool in pools.items():
            assert len(pool) <= SWAP_POOL_MAX
            slot = q("cmd_catalog", f"SELECT width_px, height_px FROM card_grid_size WHERE card_id={cid} LIMIT 1")
            w, h = (int(slot[0][0]), int(slot[0][1])) if slot and slot[0] and slot[0][0] else (None, None)
            last_dist = -1
            for c in pool:
                tid = c["card_id"]
                assert tid not in page_ids and tid not in tpl and tid != cid          # off-page, off-template
                assert tid in avail_ids                                               # on an available page
                v = q("cmd_catalog", f"SELECT verdict FROM card_feasibility WHERE card_id={tid}")
                assert v and v[0][0] in candidates.POOL_VERDICTS                      # renderable verdict (DB knob)
                assert is_registered(tid)                                             # has a front-end renderer [FR-5]
                assert has_default(tid, pk)                                           # recoverable default [META-05]
                if w and h:                                                           # ±tolerance size match, closest-first
                    assert abs(c["width_px"] - w) <= w * SIZE_TOLERANCE + 1
                    assert abs(c["height_px"] - h) <= h * SIZE_TOLERANCE + 1
                    dist = abs(c["width_px"] - w) + abs(c["height_px"] - h)
                    assert dist >= last_dist
                    last_dist = dist


# ── (d) accepted swap re-emits for the TARGET shape ───────────────────────────────────────────────
def test_d_swap_target_input_inherits_slot_and_settles():
    from layer2.card_input import build_card_input, build_swap_target_input
    pages = _pool_pages(limit_pages=1)
    assert pages
    pk, tpl, pools = pages[0]
    cid = next(c for c, p in pools.items() if p)
    tgt = pools[cid][0]["card_id"]
    l1a = {"page_key": pk, "story": "s", "metric": "energy", "intent": "monitor",
           "cards": [{"card_id": cid, "title": "t", "analytical_story": "slot angle", "role_in_story": "lead"}],
           "interdependency_groups": []}
    l1b = {"asset": None, "column_basket": {"tables": [], "columns": []}}
    ci = build_card_input("t-run", cid, l1a, l1b)
    tci = build_swap_target_input("t-run", tgt, ci, l1b)
    assert tci["card_id"] == tgt and tci["catalog_row"]["card_id"] == tgt      # the TARGET's own shape/recipe/defaults
    assert tci["story"] == ci["story"]                                         # inherits the slot's analytical angle
    assert tci["swap_candidates"] == []                                        # slot settled — never re-swap


def test_d_run_card_reemits_and_finalizes_against_the_target(monkeypatch):
    import layer2.build as build
    pages = _pool_pages(limit_pages=1)
    assert pages
    pk, tpl, pools = pages[0]
    cid = next(c for c, p in pools.items() if p)
    tgt = pools[cid][0]["card_id"]
    seen = []

    def fake_emit(ci):
        seen.append(ci)
        if len(seen) == 1:                                                     # pass 1: the AI swaps to pool[0]
            return {"swap_decision": {"action": "swap", "swap_to_id": tgt, "confidence": 0.99,
                                      "criterion": "hourly energy trend angle"},
                    "exact_metadata": {"k": "original-shape"}, "data_instructions": {"fields": []}}
        return {"swap_decision": {"action": "keep"},                           # pass 2: emit FOR THE TARGET
                "exact_metadata": {"k": "target-shape"}, "data_instructions": {"fields": []},
                "analytical_story": "re-emitted for target"}

    monkeypatch.setattr(build, "emit", fake_emit)
    l1a = {"page_key": pk, "story": "s", "metric": "energy", "intent": "monitor",
           "cards": [{"card_id": cid, "title": "t", "analytical_story": "slot angle", "role_in_story": "lead"}],
           "interdependency_groups": []}
    l1b = {"asset": None, "column_basket": {"tables": [], "columns": []}}
    out = build.run_card("t-run", cid, l1a, l1b)
    assert len(seen) == 2                                                      # RE-EMIT happened
    assert seen[1]["card_id"] == tgt and seen[1]["swap_candidates"] == []      # ...for the TARGET, slot settled
    assert out["card_id"] == tgt and out["_reemit_of"] == cid                  # finalized against the FINAL card
    assert out["swap_decision"]["action"] == "swap" and out["swap_decision"]["swap_to_id"] == tgt


# ── (f) Layer 1a whole-template drop + reselect at the config threshold ───────────────────────────
def _specs(*keys):
    return [{"page_key": k} for k in keys]


def test_f_template_dropped_at_threshold_and_reselected():
    counts = {"A": {"total": 10, "unrenderable": 4},      # 0.40 >= thr → dropped
              "B": {"total": 10, "unrenderable": 3},      # 0.30 → kept (the reselect target)
              "C": {"total": 0, "unrenderable": 0}}       # unknown → kept (never drop on missing data)
    kept, dropped = filter_renderable_templates(_specs("A", "B", "C"), counts, threshold=0.40)
    assert dropped == ["A"]
    assert [s["page_key"] for s in kept] == ["B", "C"]


def test_f_all_disqualified_falls_back_to_least_unrenderable():
    counts = {"A": {"total": 10, "unrenderable": 9}, "B": {"total": 10, "unrenderable": 5}}
    kept, dropped = filter_renderable_templates(_specs("A", "B"), counts, threshold=0.40)
    assert [s["page_key"] for s in kept] == ["B"] and dropped == ["A"]         # never routes to nothing


def test_f_threshold_is_the_config_knob():
    from config.feasibility import TEMPLATE_MAX_UNRENDERABLE_FRAC as THR
    assert 0 < THR <= 1
    counts = {"A": {"total": 100, "unrenderable": int(THR * 100)}, "B": {"total": 100, "unrenderable": 0}}
    kept, dropped = filter_renderable_templates(_specs("A", "B"), counts)      # default threshold = the cfg row
    assert dropped == ["A"] and [s["page_key"] for s in kept] == ["B"]
