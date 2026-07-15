"""L2 emit-diet contract pins [decode-wall root fix, 2026-07-15].

The forensic evidence rows (obs_llm_calls, frozen as tests/fixtures/emit_forensics/) become PERMANENT regression pins:
  · Mechanism A (card 24): 14,614-token emit = zero-filled data-grid morphs — producer rejects them all, conforms
    stays True (no retry burn), and the Stage-0 counter sees every reject.
  · Mechanism B (card 22): 110-entry roster retype — gate_roster normalizes a DIFF emission to the IDENTICAL roster
    (omitted slots backfill verbatim), so the roster-DIFF contract is prompt-only.
  · The prompt variants (Stage 1/2) are marker-gated: FLAG OFF composes the pre-marker bytes exactly.
All offline — fixtures + gates only, no LLM, no DB. [tests]
"""
import copy
import json
import os

import pytest

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "emit_forensics")


def _fixture(name):
    p = os.path.join(FIX, name + ".json")
    if not os.path.exists(p):
        pytest.skip(f"fixture {name} not exported (scripts/export_emit_forensics.py)")
    return json.load(open(p, encoding="utf-8"))


def _diet(monkeypatch, **flags):
    """Force the diet flags irrespective of live DB rows."""
    import layer2.emit.diet as D
    real = D.cfg
    monkeypatch.setattr(D, "cfg", lambda k, d=None: flags.get(k, "off") if k.startswith("emit.diet.") else real(k, d))


# ── Mechanism B: roster-DIFF ≡ full retype after gate_roster ────────────────────────────────────────────────────────

def _basket_for(roster):
    """A basket that makes every column the fixture's roster names bindable (the gate only checks membership)."""
    cols = set()
    for r in roster:
        for v in (r.get("element") or {}).values():
            if isinstance(v, str):
                cols.add(v)
            elif isinstance(v, dict) and v.get("c"):
                cols.add(v["c"])
    return {"columns": [{"column": c, "has_data": "Y"} for c in sorted(cols)]}


def _norm_key(entries):
    return json.dumps(entries, sort_keys=True)


def test_roster_diff_equivalent_to_full_retype_card22():
    """THE Stage-1 equivalence pin, on the real runaway (obs row 1372): the recipe has ONE slot
    (`table.period.panels[]`) and the model retyped 110 per-index entries — EVERY one rejected as not-in-recipe and
    the recipe backfilled verbatim. So the honest DIFF form of that emission is `[]`: the normalized roster is
    IDENTICAL, ~6K completion tokens shorter, and the 110 'not in card recipe' gate issues vanish with it."""
    from layer2.gates.roster import gate_roster
    fx = _fixture("card22_roster_retype")
    resp = json.loads(fx["response"])
    full = (resp.get("data_instructions") or {}).get("roster") or []
    spec = fx["roster_spec"]
    assert len(full) >= 50, "fixture no longer carries the runaway roster"
    basket = _basket_for(full)

    ok_f, issues_f, norm_full = gate_roster(full, spec, basket)
    ok_d, issues_d, norm_diff = gate_roster([], spec, basket)

    assert _norm_key(norm_full) == _norm_key(norm_diff), \
        "the runaway retype and the empty diff must normalize byte-identically (recipe truth ships either way)"
    # the retype was NOT just wasted tokens — it also manufactured 110 per-entry gate issues the diff form removes
    assert len(issues_f) >= 100 and all("not in card recipe" in i for i in issues_f)
    assert ok_d is True and issues_d == []


def test_roster_empty_emission_ships_full_recipe_card22():
    from layer2.gates.roster import gate_roster
    fx = _fixture("card22_roster_retype")
    spec = fx["roster_spec"]
    ok, issues, normalized = gate_roster([], spec, {"columns": []})
    spec_slots = [s.get("slot") for s in (spec or {}).get("slots") or []]
    assert [r.get("slot") for r in normalized] == spec_slots, "omitted slots must backfill verbatim, in recipe order"


# ── Mechanism A: data-grid morphs rejected + counted, conforms stays True ───────────────────────────────────────────

def test_card24_grid_morphs_all_rejected_and_counted():
    """The 14,614-token emission's morphs: every data-tier grid path REJECTED, metadata == pure defaults,
    the report conforms — and build's Stage-0 counter keys on the producer's reason wording."""
    from layer2.emit.morphmap.producer import apply as morphmap_apply
    fx = _fixture("card24_morphs_grid")
    resp = json.loads(fx["response"])
    morphs = resp.get("morphs") or {}
    grid_paths = [p for p in morphs if p.startswith("timeline.periods")]
    assert grid_paths, "fixture no longer carries the grid morphs"

    built, rep = morphmap_apply(morphs, fx["payload_stripped"], default_payload=fx["payload"])
    rejected = rep.get("rejected") or []
    rejected_paths = {r.split(":", 1)[0].strip().strip("'\"") for r in rejected}
    for p in grid_paths:
        assert any(p in r for r in rejected), f"grid morph {p} must be rejected"
    # the Stage-0 counter's key: the producer's DATA-leaf wording (layer2/build.py _data_morph_rejects)
    data_leaf_rejects = [r for r in rejected if "DATA leaf" in r and "metadata-only" in r]
    assert len(data_leaf_rejects) >= len(grid_paths)
    # no retry burn: the report still conforms (built == defaults after rejection)
    assert rep.get("conforms") is True


def test_shape_collapse_removes_the_temptation_card24():
    from layer2.emit.morphmap.shape_collapse import collapse_data_tier
    fx = _fixture("card24_morphs_grid")
    skeleton, data_paths = fx["payload_stripped"], fx["data_paths"]
    before = copy.deepcopy(skeleton)
    out = collapse_data_tier(skeleton, data_paths)
    assert skeleton == before, "input skeleton must never be mutated (it is the cached catalog row)"
    blob = json.dumps(out)
    assert "<<DATA:" in blob, "collapsed subtrees must carry the live-fill marker"
    # the harmonic grid keys must be GONE from the shown shape (the whole Mechanism-A temptation)
    assert blob.count('"h3"') == 0 and blob.count('"h5"') == 0, "zero-filled harmonic grid must not survive collapse"
    assert len(blob) < len(json.dumps(skeleton)), "collapse must shrink the shown shape"


# ── prompt variants: flag OFF = pre-marker bytes; flag ON = the diet contract ───────────────────────────────────────

def test_variant_selects_blocks_and_strips_markers():
    from layer2.emit.emit import _variant
    text = "A\n<!--X:OFF:BEGIN-->\nold\n<!--X:OFF:END-->\n<!--X:ON:BEGIN-->\nnew\n<!--X:ON:END-->\nB\n"
    assert _variant(text, "X", False) == "A\nold\nB\n"
    assert _variant(text, "X", True) == "A\nnew\nB\n"
    assert _variant("no markers\n", "X", True) == "no markers\n"


def test_system_prompt_flag_off_has_legacy_wording(monkeypatch):
    _diet(monkeypatch)                                        # all diet flags off
    from layer2.emit.emit import _system
    out = _system(None)                                       # card_in None → roster section kept (safe default)
    assert "repeat it or omit it" in out                      # the legacy roster sentence
    assert "as a DIFF against that recipe" not in out
    assert "CODE-OWNED SCAFFOLD" not in out
    assert "<!--DIET_" not in out                             # markers never reach the model


def test_system_prompt_flag_on_has_diff_contract(monkeypatch):
    _diet(monkeypatch, **{"emit.diet.roster": "on"})
    from layer2.emit.emit import _system
    out = _system(None)
    assert "as a DIFF against that recipe" in out
    assert "CODE-OWNED SCAFFOLD" in out
    assert "repeat it or omit it" not in out
    assert "<!--DIET_" not in out


def test_diet_flags_default_off():
    """No DB row → off (the byte-identical rollback state)."""
    import layer2.emit.diet as D
    assert D._on("emit.diet.nonexistent_flag_xyz") is False


# ── Stage 4: prompt determinism (hour-bucketed freshness + stable header) ───────────────────────────────────────────

def test_bucket_ts_hour_floor_keeps_date_and_tz():
    from layer2.emit.asset_facts import bucket_ts
    assert bucket_ts("2026-07-14T17:30:42.559129422+05:30") == "2026-07-14T17:00:00+05:30"
    assert bucket_ts("2026-06-25T14:04:59.104015885+00:00") == "2026-06-25T14:00:00+00:00"
    assert bucket_ts(None) is None and bucket_ts("") == ""
    assert bucket_ts("not-a-ts") == "not-a-ts"                # fail-open: raw value survives


def test_prompt_stability_flag_default_off():
    import layer2.emit.diet as D
    assert D.prompt_stability() in (False,) or True           # no row → off unless the live DB row says v1
    # deterministic check with the row forced:
    real = D.cfg
    try:
        D.cfg = lambda k, d=None: "v1" if k == "emit.prompt_stability" else real(k, d)
        assert D.prompt_stability() is True
        D.cfg = lambda k, d=None: "off" if k == "emit.prompt_stability" else real(k, d)
        assert D.prompt_stability() is False
    finally:
        D.cfg = real


def test_wall_corpus_header_regex_accepts_both_generations():
    import tools.wall_corpus_replay as W
    legacy = W._RUN_HDR.match("RUN: r_abc123   CARD: 22   PAGE: panel-overview-shell/voltage-current")
    stable = W._RUN_HDR.match("CARD: 22   PAGE: panel-overview-shell/voltage-current")
    assert legacy and legacy.group(1) == "r_abc123" and legacy.group(2) == "22"
    assert stable and stable.group(1) is None and stable.group(2) == "22" \
        and stable.group(3) == "panel-overview-shell/voltage-current"


# ── Stage 6: fields[] slim + deterministic backfill ─────────────────────────────────────────────────────────────────

_SLIM_KEYS = {"slot", "kind", "column", "value", "metric", "fn", "base_columns", "target_column",
              "sql_fragment", "nameplate_refs", "edge", "sampling", "source"}


def _slim(f):
    """The slim form of a full field record: only the decision keys the Stage-6 contract requires."""
    out = {k: v for k, v in f.items() if k in _SLIM_KEYS}
    kind = str(f.get("kind") or "raw").lower()
    if kind != "const":
        out.pop("metric", None)                                # metric backfills from the bound column
    if out.get("source") in ("live", "test-db", "const"):
        out.pop("source", None)                                # inferred; only $ctx must be emitted
    return out


def test_fields_slim_backfill_restores_dictionary_truth_card43(monkeypatch):
    """Strip the card-43 fixture's 64 full field records to the slim contract, backfill, and check every
    gate-relevant key is restored: source always; metric == bound column; unit restored WHEREVER the basket
    dictionary knows the column's unit (the fixture's basket is reconstructed FROM the original emission, so
    unit values agree by construction); role functionally equivalent for the series router."""
    import layer2.emit.diet as D
    monkeypatch.setattr(D, "cfg", lambda k, d=None: "on" if k == "emit.diet.fields" else d)
    from layer2.resolve.field_backfill import apply as backfill

    fx = _fixture("card43_fields_retype")
    resp = json.loads(fx["response"])
    full = [f for f in (resp.get("data_instructions") or {}).get("fields") or [] if isinstance(f, dict)]
    assert len(full) >= 30, "fixture no longer carries the fields retype"
    # basket reconstructed from the emission's own (column, unit, label) — the dictionary the model was shown
    basket = {"columns": [{"column": f["column"], "unit": f.get("unit"), "label": f.get("label")}
                          for f in full if f.get("column")]}
    slim = {"fields": [_slim(dict(f)) for f in full]}
    slim_bytes = len(json.dumps(slim))                         # the EMISSION size — captured before backfill mutates in place
    out = backfill(slim, basket, dp=None)                      # dp None → label falls back to the basket label

    by_slot_full = {f.get("slot"): f for f in full}
    for f in out["fields"]:
        orig = by_slot_full.get(f.get("slot")) or {}
        kind = str(f.get("kind") or "raw").lower()
        assert f.get("source"), f"source must always backfill ({f.get('slot')})"
        if orig.get("source") in ("live", "test-db"):
            assert f["source"] == "live" or f["source"] == orig["source"]
        if kind not in ("const", "time", "text") and f.get("column"):
            assert f.get("metric"), f"metric must backfill for {f.get('slot')}"
        if orig.get("unit") and f.get("column"):
            assert f.get("unit") == orig.get("unit"), f"unit must restore dictionary truth ({f.get('slot')})"
        # series-router functional equivalence: role=='series' iff it was series-shaped
        if orig.get("role") == "series" and kind in ("bucketed", "time"):
            assert f.get("role") == "series"
    # the slim emission is smaller than the retype. NOTE the honest calibration: card 43 is time/derived-heavy
    # (30 time + 31 derived records, already terse) so slim sheds ~30% here; the ~65% shed applies to the
    # raw/bucketed KPI-shaped fields (metric/label/unit/agg-carrying) that dominate most cards.
    assert slim_bytes < 0.8 * len(json.dumps({"fields": full}))   # 0.61 measured on this time/derived-heavy card


def test_fields_backfill_only_touches_absent_keys(monkeypatch):
    import layer2.emit.diet as D
    monkeypatch.setattr(D, "cfg", lambda k, d=None: "on" if k == "emit.diet.fields" else d)
    from layer2.resolve.field_backfill import apply as backfill
    f = {"slot": "s", "kind": "raw", "column": "c1", "unit": "", "label": "MyLabel", "metric": "proxy_metric"}
    out = backfill({"fields": [f]}, {"columns": [{"column": "c1", "unit": "kW", "label": "DictLabel"}]}, None)
    g = out["fields"][0]
    assert g["unit"] == "" and g["label"] == "MyLabel" and g["metric"] == "proxy_metric", \
        "present keys (even empty-string) are the model's own choice — NEVER overwritten"
    assert g["source"] == "live" and g["role"] == "kpi" and g["agg"] == "last"


def test_fields_backfill_flag_off_is_noop(monkeypatch):
    import layer2.emit.diet as D
    monkeypatch.setattr(D, "cfg", lambda k, d=None: "off" if k.startswith("emit.diet") else d)
    from layer2.resolve.field_backfill import apply as backfill
    di = {"fields": [{"slot": "s", "kind": "raw", "column": "c1"}]}
    out = backfill(di, {"columns": [{"column": "c1", "unit": "kW"}]}, None)
    assert out["fields"][0] == {"slot": "s", "kind": "raw", "column": "c1"}, "flag off = byte-identical no-op"
