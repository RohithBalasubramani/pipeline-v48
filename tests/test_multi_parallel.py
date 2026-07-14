"""Multi-compare lane/fill PARALLELISM contract [latency 2026-07-14, flag-gated Stage A/B].

Pins the zero-quality-change contract of the parallelized multi path:
  · knobs at 0 (the default) → the EXACT sequential code path (the pool is never even constructed);
  · knobs on → identical values, identical ORDER (all_cards / token first-seen order is load-bearing for merge_all),
    identical exception behavior (first-in-order), shared-1a author-once semantics preserved (phase-1 sequential
    until a lane yields layer1a, phase-2 parallel), reflect-loop rids salted per lane (no cross-lane collision).
All LLM/DB seams mocked — these tests exercise ORCHESTRATION only. [tests]
"""
import threading
import time

import pytest

import run.harness as H
import host.multi_asset as MA


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────────

def _fake_lane(page="energy-power", cards=(1, 2)):
    return {"layer1a": {"page_key": page, "page_title": page, "layout": {}, "cards": [{"card_id": c} for c in cards]},
            "layer2": {c: {"exact_metadata": {}} for c in cards}, "validation": {}, "notes": {}, "errors": {}}


def _knob(monkeypatch, mod, **vals):
    """Patch cfg() in `mod` so only the named knobs change; everything else keeps its code default."""
    real = mod.cfg
    def fake_cfg(key, default=None):
        if key in vals:
            return vals[key]
        return real(key, default)
    monkeypatch.setattr(mod, "cfg", fake_cfg)


def _assets(n=2, cls="UPS"):
    return [{"mfm_id": i + 1, "name": f"{cls}-0{i + 1}", "class": cls, "table": f"g{i + 1}"} for i in range(n)]


def _patch_build_seams(monkeypatch, assemble):
    """The build_response_multi seams every Stage-A test shares: registry resolve, lanes, notes, fill."""
    monkeypatch.setattr(MA, "resolve_assets", lambda ids: _assets(len(ids)))
    monkeypatch.setattr(MA, "run_pipeline_multi",
                        lambda prompt, assets: {"run_id": "r_x", "layer1a": _fake_lane()["layer1a"],
                                                "groups": [{"class": "UPS", "lane": _fake_lane(),
                                                            "assets": assets}]})
    monkeypatch.setattr(MA, "rebind_consumer", lambda recipe, asset: dict(recipe))
    monkeypatch.setattr(MA, "assemble_cards", assemble)


# ── 1. knob-off byte-identity + no-pool guard ────────────────────────────────────────────────────────────────────────

def test_knob_off_never_enters_the_pool(monkeypatch):
    import lib.parallel as LP
    def boom(*a, **k):
        raise AssertionError("run_parallel must NOT be called with knobs at 0")
    monkeypatch.setattr(LP, "run_parallel", boom)
    monkeypatch.setattr(H, "run_parallel", H.run_parallel)   # harness imported the real one at module load

    def assemble(lane_i, asset, dw):
        return [{"card_id": 1, "render_card_id": 1, "payload": {"v": asset["mfm_id"]}}]
    _patch_build_seams(monkeypatch, assemble)
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda p: "groups")
    resp = MA.build_response_multi("compare ups-01 and ups-02", ["1", "2"])
    assert [c["asset"]["id"] for c in resp["cards"]] == [1, 2]
    assert resp["multi_asset"] is True


def test_lane_knob_off_sequential_calls(monkeypatch):
    calls = []
    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None, **kw):
        calls.append((asset_id, layer1a is not None))
        return _fake_lane()
    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    def no_pool(*a, **k):
        raise AssertionError("lane pool must NOT be used at knob 0")
    monkeypatch.setattr(H, "run_parallel", no_pool)
    res = H.run_pipeline_multi("compare a and b", _assets(1) + [{"mfm_id": 9, "name": "TR-01",
                                                                 "class": "Transformer", "table": "g9"}])
    assert calls == [(1, False), (9, True)]
    assert [g["class"] for g in res["groups"]] == ["UPS", "Transformer"]


# ── 2. parallel fill order determinism (sleep-staggered) ─────────────────────────────────────────────────────────────

def test_parallel_fill_preserves_card_order(monkeypatch):
    def assemble(lane_i, asset, dw):
        time.sleep(0.25 if asset["mfm_id"] == 1 else 0.0)     # asset 2 finishes FIRST
        return [{"card_id": 1, "render_card_id": 1, "payload": {}},
                {"card_id": 2, "render_card_id": 2, "payload": {}}]
    _patch_build_seams(monkeypatch, assemble)
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda p: "groups")
    _knob(monkeypatch, MA, **{"multi_asset.fill_concurrency": 3})
    resp = MA.build_response_multi("compare ups-01 and ups-02", ["1", "2"])
    got = [(c["asset"]["id"], c["card_id"]) for c in resp["cards"]]
    assert got == [(1, 1), (1, 2), (2, 1), (2, 2)]            # ORIGINAL order despite reversed completion


def test_parallel_fill_token_first_seen_order(monkeypatch):
    seen = {}
    def assemble(lane_i, asset, dw):
        time.sleep(0.2 if asset["mfm_id"] == 1 else 0.0)
        return [{"card_id": 1, "render_card_id": 1, "payload": {"stats": {"total": asset["mfm_id"]}}}]
    _patch_build_seams(monkeypatch, assemble)
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda p: "overlay")
    def spy_merge(cards, tokens_by_id):
        seen["tokens"] = list(tokens_by_id.values())
        return cards
    monkeypatch.setattr("host.compare_overlay.merge_all", spy_merge)
    _knob(monkeypatch, MA, **{"multi_asset.fill_concurrency": 3})
    MA.build_response_multi("compare ups-01 and ups-02", ["1", "2"])
    assert seen["tokens"] == ["U01", "U02"]                   # first-seen = asset order, not completion order


# ── 3. fill exception parity (first-in-order) ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cc", [0, 3])
def test_fill_exception_first_in_order_both_branches(monkeypatch, cc):
    def assemble(lane_i, asset, dw):
        raise ValueError(f"a{asset['mfm_id']}")
    _patch_build_seams(monkeypatch, assemble)
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda p: "groups")
    _knob(monkeypatch, MA, **{"multi_asset.fill_concurrency": cc})
    with pytest.raises(ValueError, match="a1"):               # asset 1's exception wins in BOTH branches
        MA.build_response_multi("compare ups-01 and ups-02", ["1", "2"])


# ── 4. compare_mode hoist ────────────────────────────────────────────────────────────────────────────────────────────

def test_compare_mode_called_once_and_honored_when_hoisted(monkeypatch):
    calls = []
    def assemble(lane_i, asset, dw):
        return [{"card_id": 1, "render_card_id": 1, "payload": {}}]
    _patch_build_seams(monkeypatch, assemble)
    def fake_mode(p):
        calls.append(p)
        time.sleep(0.05)
        return "groups"
    monkeypatch.setattr("host.compare_mode.compare_mode", fake_mode)
    _knob(monkeypatch, MA, **{"multi_asset.fill_concurrency": 3})
    resp = MA.build_response_multi("compare ups-01 and ups-02", ["1", "2"])
    assert calls == ["compare ups-01 and ups-02"]             # exactly once, hoisted
    assert resp["multi_asset"] is True                        # mode honored (groups)


def test_compare_mode_not_called_for_single_asset(monkeypatch):
    calls = []
    def assemble(lane_i, asset, dw):
        return [{"card_id": 1, "render_card_id": 1, "payload": {}}]
    monkeypatch.setattr(MA, "resolve_assets", lambda ids: _assets(1))
    monkeypatch.setattr(MA, "run_pipeline_multi",
                        lambda prompt, assets: {"run_id": "r_x", "layer1a": _fake_lane()["layer1a"],
                                                "groups": [{"class": "UPS", "lane": _fake_lane(), "assets": assets}]})
    monkeypatch.setattr(MA, "rebind_consumer", lambda recipe, asset: dict(recipe))
    monkeypatch.setattr(MA, "assemble_cards", assemble)
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda p: calls.append(p) or "overlay")
    _knob(monkeypatch, MA, **{"multi_asset.fill_concurrency": 3})
    resp = MA.build_response_multi("ups-01 overview", ["1"])
    assert calls == []                                        # 1 asset = not a compare → no mode LLM call
    assert resp["multi_asset"] is True                        # degenerates to groups


# ── 5. Stage B phase split + real overlap ────────────────────────────────────────────────────────────────────────────

def test_lane_parallel_phase_split_order_and_overlap(monkeypatch):
    calls = []
    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None, **kw):
        t0 = time.time(); time.sleep(0.3)
        calls.append({"asset_id": asset_id, "injected": layer1a is not None, "t0": t0, "t1": time.time()})
        return _fake_lane()
    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    _knob(monkeypatch, H, **{"multi_asset.lane_concurrency": 2})
    assets = [{"mfm_id": 1, "name": "UPS-01", "class": "UPS", "table": "g1"},
              {"mfm_id": 2, "name": "TR-01", "class": "Transformer", "table": "g2"},
              {"mfm_id": 3, "name": "DG-1", "class": "DG", "table": "g3"}]
    res = H.run_pipeline_multi("compare all three", assets)
    assert [c["injected"] for c in calls] == [False, True, True]          # phase-1 routes, phase-2 injects
    a, b = calls[1], calls[2]                                             # the two phase-2 lanes OVERLAP in time
    assert max(a["t0"], b["t0"]) < min(a["t1"], b["t1"])
    assert [g["class"] for g in res["groups"]] == ["UPS", "Transformer", "DG"]   # insertion order, not completion


# ── 6. data_unavailable lane0 → sequential-until-shared_1a ───────────────────────────────────────────────────────────

def test_lane0_without_layer1a_keeps_phase1_sequential(monkeypatch):
    calls = []
    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None, **kw):
        calls.append({"asset_id": asset_id, "injected": layer1a is not None})
        if len(calls) == 1:
            return {"layer1a": None, "data_unavailable": True, "errors": {}}      # outage lane: NO template
        return _fake_lane()
    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    _knob(monkeypatch, H, **{"multi_asset.lane_concurrency": 2})
    assets = [{"mfm_id": 1, "name": "A", "class": "C1", "table": "g1"},
              {"mfm_id": 2, "name": "B", "class": "C2", "table": "g2"},
              {"mfm_id": 3, "name": "C", "class": "C3", "table": "g3"}]
    res = H.run_pipeline_multi("compare", assets)
    # lane1 yields no template → lane2 STILL runs sequentially un-injected (today's rule); lane3 injects lane2's 1a
    assert [c["injected"] for c in calls] == [False, False, True]
    assert res["layer1a"]["page_key"] == "energy-power"
    assert [g["class"] for g in res["groups"]] == ["C1", "C2", "C3"]


# ── 7. reflect-loop rid salting ──────────────────────────────────────────────────────────────────────────────────────

def test_reflect_rid_single_path_byte_identical_and_lane_salted():
    from run.run_id import make_run_id
    # the loop-attempt rid derivation (harness _reflect_loop line): attempt 2, single path vs lane
    single = make_run_id("p", salt="loop2")
    lane = make_run_id("p", salt="class:UPS:loop2")
    assert single == make_run_id("p", salt=f"{''}loop2")          # "" lane_salt → byte-identical to historical
    assert lane != single                                          # lanes can never collide with each other/single
    assert make_run_id("p", salt="class:DG:loop2") != lane


def test_run_lane_passes_class_lane_salt(monkeypatch):
    seen = {}
    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None, lane_salt=""):
        seen["lane_salt"] = lane_salt
        return _fake_lane()
    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    H._run_lane("p", "UPS", [{"mfm_id": 1}], None, shared_1a=None)
    assert seen["lane_salt"] == "class:UPS:"


# ── 8. lane exception parity (Stage B) ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cc", [0, 2])
def test_lane_exception_first_in_order_both_branches(monkeypatch, cc):
    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None, **kw):
        if layer1a is None:
            return _fake_lane()                                # lane0 routes fine
        raise RuntimeError(f"lane{asset_id}")                  # every phase-2 lane raises
    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    _knob(monkeypatch, H, **{"multi_asset.lane_concurrency": cc})
    assets = [{"mfm_id": 1, "name": "A", "class": "C1", "table": "g1"},
              {"mfm_id": 2, "name": "B", "class": "C2", "table": "g2"},
              {"mfm_id": 3, "name": "C", "class": "C3", "table": "g3"}]
    with pytest.raises(RuntimeError, match="lane2"):           # FIRST-in-order phase-2 lane, both branches
        H.run_pipeline_multi("compare", assets)


# ── 9. single-group prompt: pool never entered even with the knob high ───────────────────────────────────────────────

def test_single_class_never_enters_lane_pool(monkeypatch):
    def fake_run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None, **kw):
        return _fake_lane()
    monkeypatch.setattr(H, "run_pipeline", fake_run_pipeline)
    def no_pool(*a, **k):
        raise AssertionError("single class must not fan out")
    monkeypatch.setattr(H, "run_parallel", no_pool)
    _knob(monkeypatch, H, **{"multi_asset.lane_concurrency": 8})
    res = H.run_pipeline_multi("compare ups-01 and ups-02", _assets(2))
    assert len(res["groups"]) == 1


# ── 10. sectioned compare under parallel fills ───────────────────────────────────────────────────────────────────────

def test_sectioned_compare_distinct_tids_order_preserved(monkeypatch):
    secs = [{"mfm_id": 317, "name": "PCC-Panel-1 — Section A", "class": "Panel", "table": "gp", "section": "A"},
            {"mfm_id": 317, "name": "PCC-Panel-1 — Section B", "class": "Panel", "table": "gp", "section": "B"}]
    monkeypatch.setattr(MA, "resolve_assets", lambda ids: secs)
    monkeypatch.setattr(MA, "run_pipeline_multi",
                        lambda prompt, assets: {"run_id": "r_x", "layer1a": _fake_lane()["layer1a"],
                                                "groups": [{"class": "Panel", "lane": _fake_lane(), "assets": assets}]})
    monkeypatch.setattr(MA, "rebind_consumer", lambda recipe, asset: dict(recipe))
    def assemble(lane_i, asset, dw):
        time.sleep(0.15 if asset["section"] == "A" else 0.0)   # B finishes first
        return [{"card_id": 1, "render_card_id": 1, "payload": {}}]
    monkeypatch.setattr(MA, "assemble_cards", assemble)
    monkeypatch.setattr("host.compare_mode.compare_mode", lambda p: "groups")
    _knob(monkeypatch, MA, **{"multi_asset.fill_concurrency": 2})
    resp = MA.build_response_multi("compare pcc 1a and 1b", [{"id": 317, "section": "A"},
                                                             {"id": 317, "section": "B"}])
    assert [c["asset"]["id"] for c in resp["cards"]] == ["317A", "317B"]
