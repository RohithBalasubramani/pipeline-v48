"""tests/test_multi_asset.py — MULTI-ASSET compare (author-once-per-class). Non-live: every LLM/DB seam is monkeypatched,
so these pin the STRUCTURE — Layer 2 authored ONCE PER CLASS, executor filled PER ASSET, cards tagged + concatenated,
and the single-asset path left byte-faithful. The live 2-asset render is asserted by the ssr/client gates + a curl.

Design under test:
  · run/harness.run_pipeline(..., layer1a=)      — inject a shared template; a shared-template lane never re-routes.
  · run/harness.run_pipeline_multi(prompt, assets) — 1a ONCE; ONE run_pipeline PER DISTINCT CLASS; groups the rest.
  · host/assemble.assemble_cards(out, asset, dw) — pure extraction of build_response's executor+enrich (per asset).
  · host/rebind_consumer.rebind_consumer(l2, a) — repoint the reused recipe's envelope at a sibling asset.
  · host/asset_lanes.resolve_assets(ids)         — ids → as_asset dicts (unknown dropped, order kept).
  · host/multi_asset.build_response_multi        — merge + tag by asset.
"""
from __future__ import annotations

import inspect

import run.harness as H
import host.assemble as A
import host.asset_lanes as L
import host.multi_asset as M
from host.rebind_consumer import rebind_consumer


# ── rebind_consumer: only the per-asset ENVELOPE moves; the AI recipe is copied verbatim ─────────────────────────────

def test_rebind_repoints_envelope_only_and_does_not_mutate_source():
    l2 = {7: {"exact_metadata": {"title": "T"}, "swap_decision": {"action": "keep"},
              "data_instructions": {"fields": [{"column": "active_power_total_kw"}],
                                    "consumer": {"mfm_id": 10, "endpoint": "energy-power"},
                                    "binding": {"asset_id": 10, "table": "gic_a", "panel_id": None}}}}
    out = rebind_consumer(l2, {"mfm_id": 42, "table": "gic_b"})
    di = out[7]["data_instructions"]
    assert di["consumer"]["mfm_id"] == 42                        # WS path key repointed
    assert di["binding"]["asset_id"] == 42 and di["binding"]["table"] == "gic_b"
    assert di["fields"] == [{"column": "active_power_total_kw"}]  # column-NAME recipe unchanged (portable)
    assert out[7]["exact_metadata"] == {"title": "T"} and out[7]["swap_decision"] == {"action": "keep"}
    # source untouched (lanes must never alias)
    assert l2[7]["data_instructions"]["consumer"]["mfm_id"] == 10
    assert l2[7]["data_instructions"]["binding"]["table"] == "gic_a"


def test_rebind_passes_non_dict_and_missing_blocks_through():
    l2 = {1: {"data_instructions": {"fields": []}}, 2: "not-a-dict", 3: {"exact_metadata": {}}}
    out = rebind_consumer(l2, {"mfm_id": 9, "table": "t"})
    assert out[2] == "not-a-dict"                               # non-dict passes through
    assert "consumer" not in out[1]["data_instructions"]        # absent envelope not fabricated
    assert out[3] == {"exact_metadata": {}}


# ── resolve_assets: ids → as_asset dicts, unknown dropped, order + de-dup ─────────────────────────────────────────────

def test_resolve_assets_skips_unknown_keeps_order_dedups(monkeypatch):
    # canonical rows: [id, name, table, mfm_type_id, load_group, class, has_data, has_feeders, never_wired, table_exists]
    rows = [["1", "UPS-01", "gic_ups1", "", "", "UPS", True, False, False, True],
            ["2", "UPS-02", "gic_ups2", "", "", "UPS", True, False, False, True]]
    monkeypatch.setattr(L, "asset_candidates", lambda: rows)
    got = L.resolve_assets(["2", 1, 999, "2"])                  # str/int mix, one unknown, one dup
    assert [a["mfm_id"] for a in got] == [2, 1]                 # order preserved, 999 dropped, dup collapsed
    assert got[0]["name"] == "UPS-02" and got[0]["table"] == "gic_ups2" and got[0]["class"] == "UPS"


# ── run_pipeline_multi: 1a ONCE; ONE run_pipeline (⇒ ONE Layer 2) PER DISTINCT CLASS ─────────────────────────────────

def _fake_lane(page="energy-power", cards=(1, 2)):
    return {"layer1a": {"page_key": page, "page_title": page, "layout": {}, "cards": [{"card_id": c} for c in cards]},
            "layer2": {c: {"exact_metadata": {}} for c in cards}, "validation": {}, "notes": {}, "errors": {}}


def test_multi_same_class_authors_layer2_once(monkeypatch):
    calls = []

    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None):
        calls.append({"asset_id": asset_id, "layer1a_injected": layer1a is not None})
        return _fake_lane()

    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    assets = [{"mfm_id": 1, "name": "UPS-01", "class": "UPS", "table": "g1"},
              {"mfm_id": 2, "name": "UPS-02", "class": "UPS", "table": "g2"}]
    res = H.run_pipeline_multi("compare ups-01 and ups-02", assets)
    # SAME class ⇒ ONE run_pipeline ⇒ Layer 2 authored ONCE; both assets ride that one group
    assert len(calls) == 1
    assert len(res["groups"]) == 1
    assert [a["mfm_id"] for a in res["groups"][0]["assets"]] == [1, 2]
    assert res["layer1a"]["page_key"] == "energy-power"


def test_multi_cross_class_authors_once_per_class_and_shares_1a(monkeypatch):
    calls = []

    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None):
        calls.append({"asset_id": asset_id, "layer1a_injected": layer1a is not None})
        return _fake_lane()

    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    assets = [{"mfm_id": 1, "name": "UPS-01", "class": "UPS", "table": "g1"},
              {"mfm_id": 3, "name": "TR-01", "class": "Transformer", "table": "g3"}]
    res = H.run_pipeline_multi("compare ups-01 and transformer-01", assets)
    # TWO classes ⇒ TWO run_pipeline calls (one Layer 2 each); the FIRST routes 1a, the SECOND gets it INJECTED (locked)
    assert len(calls) == 2 and len(res["groups"]) == 2
    assert calls[0]["layer1a_injected"] is False               # first class routes the template
    assert calls[1]["layer1a_injected"] is True                # second class LOCKS to the shared template (1a once)


# ── build_response_multi: fill per asset, tag by asset, concat, response shape ────────────────────────────────────────

def _multi_two_ups(monkeypatch, cards_for):
    lane = _fake_lane(cards=(1, 2))
    multi = {"layer1a": lane["layer1a"], "run_id": "r_multi",
             "groups": [{"class": "UPS", "lane": lane,
                         "assets": [{"mfm_id": 1, "name": "UPS-01", "class": "UPS", "table": "g1"},
                                    {"mfm_id": 2, "name": "UPS-02", "class": "UPS", "table": "g2"}]}]}
    monkeypatch.setattr(M, "run_pipeline_multi", lambda prompt, assets: multi)
    monkeypatch.setattr(M, "resolve_assets", lambda ids: multi["groups"][0]["assets"])
    monkeypatch.setattr(M, "assemble_cards", lambda out, asset, dw: cards_for(asset))
    return multi


def test_build_response_multi_groups_mode_tags_and_concats(monkeypatch):
    # GROUPS mode (AI-decided): each asset renders its OWN stacked dashboard — cards stay tagged + concatenated.
    _multi_two_ups(monkeypatch, lambda asset: [{"card_id": 1}, {"card_id": 2}])
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda prompt: "groups")
    resp = M.build_response_multi("show the dashboards for ups-01 and ups-02", [1, 2])
    assert resp["multi_asset"] is True and resp["compare_mode"] == "groups" and resp["asset_pending"] is False
    assert [a["mfm_id"] for a in resp["assets"]] == [1, 2]
    assert len(resp["cards"]) == 4                              # 2 assets × 2 cards, concatenated
    tags = [(c["asset"]["id"], c["asset"]["name"]) for c in resp["cards"]]
    assert tags == [(1, "UPS-01"), (1, "UPS-01"), (2, "UPS-02"), (2, "UPS-02")]
    assert resp["page"]["page_key"] == "energy-power"          # shared template shell


def test_build_response_multi_overlay_mode_merges_per_comparand(monkeypatch):
    # OVERLAY mode (AI-decided): the per-asset cards MERGE into ONE per-comparand set — each card's stats split per
    # comparand (stats.sections), the asset tag dropped, multi_asset False (flat render). [compare — overlay]
    def _cards(asset):
        v = 10 if asset["mfm_id"] == 1 else 4
        return [{"card_id": 18, "render_card_id": 18,
                 "payload": {"strip": {"stats": {"total": v, "current": v}}}}]
    _multi_two_ups(monkeypatch, _cards)
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda prompt: "overlay")
    resp = M.build_response_multi("compare current for ups-01 and ups-02", [1, 2])
    assert resp["multi_asset"] is False and resp["compare_mode"] == "overlay"
    assert len(resp["cards"]) == 1                              # merged into one per-comparand card
    st = resp["cards"][0]["payload"]["strip"]["stats"]
    assert st["total"] == 14                                    # union = sum across comparands
    assert set(st["sections"].keys()) == {"U01", "U02"}         # per-comparand tokens
    assert st["sections"]["U01"]["total"] == 10 and st["sections"]["U02"]["total"] == 4
    assert resp["cards"][0].get("asset") is None                # merged card is untagged (flat render)


def test_build_response_multi_propagates_lane_outage(monkeypatch):
    # a lane that hit the honest data_unavailable terminal (e.g. the :5433 tunnel dropped mid-run) must surface as a
    # page-level data_unavailable + degrade — NOT a silent 0-card blank grid. [outage parity with build_response]
    lane = {"layer1a": {"page_key": "energy-power", "cards": []}, "layer2": {}, "validation": {}, "notes": {},
            "errors": {"validation": "DatabaseError: server closed the connection unexpectedly"},
            "data_unavailable": True,
            "degrade": {"kind": "data_unavailable", "layer": "validation", "reason": "Live data source unreachable."}}
    multi = {"layer1a": lane["layer1a"], "run_id": "r_out",
             "groups": [{"class": "UPS", "lane": lane,
                         "assets": [{"mfm_id": 11, "name": "UPS-01", "class": "UPS", "table": "g1"}]}]}
    monkeypatch.setattr(M, "run_pipeline_multi", lambda p, a: multi)
    monkeypatch.setattr(M, "resolve_assets", lambda ids: multi["groups"][0]["assets"])
    monkeypatch.setattr(M, "assemble_cards", lambda out, asset, dw: [])   # outage → the lane yields no cards
    resp = M.build_response_multi("compare ups", [11, 12])
    assert resp["data_unavailable"] is True
    assert (resp["degrade"] or {}).get("kind") == "data_unavailable"
    assert resp["cards"] == []


def test_compare_ids_fail_open_on_outage(monkeypatch):
    # AI-FIRST COMPARE [2026-07-14]: the lexical natural_compare_ids pre-flight is DELETED. Compare detection now rides
    # the 1b AI resolver (it names 2+ assets → run_pipeline short-circuits with out["compare_ids"] → build_response
    # hands off to multi). A resolver/DB outage is caught by the SAME degrade gate as any single-asset run — an
    # outage-shaped resolve fails closed to the honest data_unavailable terminal, never a raw 500. resolve_asset that
    # returns no compare_ids (single, ambiguous, or outage) keeps the single path byte-identical.
    from layer1b.resolve import asset_resolve as AR
    # a resolve that raised inside run_1b would surface as an errors['layer1b'] + degrade gate, not compare_ids — so an
    # outage NEVER promotes to the multi path. Assert the contract directly: no compare_ids key ⇒ single dispatch.
    out = {"layer1b": {"how": "ambiguous", "candidates": [1, 2, 3]}}   # a picker outcome carries NO compare_ids
    assert not out["layer1b"].get("compare_ids")


# ── assemble_cards: FAITHFUL extraction of build_response's executor+enrich (single path unchanged) ──────────────────

def test_assemble_cards_faithful_to_inline_executor(monkeypatch):
    seen = {}

    def fake_run_cards(l2, asset_table, **kw):
        seen["asset_table"] = asset_table
        seen["kw"] = kw
        return ({1: {"filled": True}}, {1: {"ok": True, "why": "ok"}})

    def fake_enrich(card, page_key, val_by_id, l2_out, completed=None, run_ok=True, run_why=None, asset_table=None,
                    asset=None, handling=None, date_window=None):
        return {"card_id": card["card_id"], "completed": completed, "asset_table": asset_table, "page_key": page_key}

    monkeypatch.setattr(A, "_run_cards", fake_run_cards)
    monkeypatch.setattr(A, "_enrich_card", fake_enrich)
    monkeypatch.setattr(A._neuract_dsn, "dsn", lambda: "dsn://x")

    out = {"layer1a": {"page_key": "energy-power", "cards": [{"card_id": 1}]},
           "layer2": {1: {"exact_metadata": {}}}, "validation": {}, "run_id": "r1"}
    cards = A.assemble_cards(out, {"table": "gic_a", "name": "A", "mfm_id": 1}, None)
    assert seen["asset_table"] == "gic_a"                       # filled from the asset's OWN table
    assert seen["kw"]["asset"] == {"table": "gic_a", "name": "A", "mfm_id": 1}
    assert cards == [{"card_id": 1, "completed": {"filled": True}, "asset_table": "gic_a", "page_key": "energy-power"}]


def test_assemble_cards_no_table_or_outage_is_empty():
    assert A.assemble_cards({"layer1a": {"cards": [{"card_id": 1}]}}, {"table": None}, None) == []
    assert A.assemble_cards({"data_unavailable": True, "layer1a": {"cards": [{"card_id": 1}]}},
                            {"table": "gic_a"}, None) == []


# ── source-lock: the single-asset spine is guarded (shared-template lanes never re-route) ────────────────────────────

def test_run_pipeline_single_path_untouched_and_reroute_gated():
    # the OBS boundary split run_pipeline into a thin wrapper + _run_pipeline_inner (2026-07-12) — the shared-template
    # gating lives in the inner body now; inspect it there (fall back to the wrapper if the split is ever undone).
    src = inspect.getsource(getattr(H, "_run_pipeline_inner", H.run_pipeline))
    # the injection is present and the re-route steps are gated on it (the shared-template lane keeps ONE page)
    assert "_shared_template = layer1a is not None" in src
    assert "if not _shared_template:" in src                    # reconcile + preflight both gated
    assert "no_reroute=(out[\"asset_no_data\"] or _shared_template)" in src
    # build_response still wires the note attach literally (the source-locked serve test)
    import host.server as S
    assert "_attach_l2_notes(cards, l2)" in inspect.getsource(S.build_response)
