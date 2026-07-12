"""Layer-2 ROSTER vocabulary [generalization package §2] — card_fill_recipe context wiring + gate_roster validation.
The recipe row is AUTHORITATIVE: the AI's only decision surface is the COLUMN inside col/delta/phase_mean/prefer_abs
bindings; gate_roster VALIDATES (telemetry) and normalizes to recipe truth (omitted slots backfill verbatim)."""
import json
import os

from layer2.gates import gate_roster
from layer2.catalog.card_fill_recipe import _expand

_BASKET = {"columns": [{"column": "active_power_total_kw"}, {"column": "active_power_r_kw"},
                       {"column": "active_energy_import_kwh"}, {"column": "voltage_avg"},
                       {"column": "kpi_true_pf"}, {"column": "power_factor_total"}]}

_SPEC = {"slots": [
    {"slot": "rail.vm.consumers[]", "scope": "members", "role_filter": "load", "group_by": None, "cap": 10,
     "element": {"kw": {"b": "col", "c": "active_power_total_kw"},
                 "kwh": {"b": "delta", "c": "active_energy_import_kwh"},
                 "pf": {"b": "prefer_abs", "cs": ["kpi_true_pf", "power_factor_total"]},
                 "utilizationPct": {"b": "null", "why": "no rated capacity"}},
     "agg": {"totalKw": {"agg": "sum_magnitude", "of": "kw"}}},
    {"slot": "rail.vm.kpis", "mode": "const", "v": 0},
]}


def test_conforming_emission_folds_column_choice():
    """A clean emission (recipe slot verbatim, real basket column) passes; the AI's column folds into recipe truth."""
    roster = [{"slot": "rail.vm.consumers[]", "scope": "members", "role_filter": "load",
               "element": {"kw": {"b": "col", "c": "active_power_r_kw"}}}]
    ok, issues, norm = gate_roster(roster, _SPEC, _BASKET)
    assert ok and issues == []
    got = {s["slot"]: s for s in norm}
    assert set(got) == {"rail.vm.consumers[]", "rail.vm.kpis"}            # omitted slot backfilled verbatim
    e = got["rail.vm.consumers[]"]["element"]
    assert e["kw"] == {"b": "col", "c": "active_power_r_kw"}              # AI column folded in
    assert e["kwh"] == {"b": "delta", "c": "active_energy_import_kwh"}    # untouched keys = recipe verbatim
    assert e["utilizationPct"]["b"] == "null"                             # honest-null preserved
    # non-element slot verbatim — modulo the `_gated` trust stamp (the executor's roster_for skips its re-fold on
    # gate-normalized slots so sanctioned deviations, e.g. the section-compare overlay, survive [sections])
    assert got["rail.vm.kpis"].get("_gated") is True
    assert {k: v for k, v in got["rail.vm.kpis"].items() if k != "_gated"} == _SPEC["slots"][1]


def test_bare_string_shorthand_is_a_col_binding():
    roster = [{"slot": "rail.vm.consumers[]", "element": {"kw": "active_power_r_kw"}}]
    ok, issues, norm = gate_roster(roster, _SPEC, _BASKET)
    assert ok, issues
    e = [s for s in norm if s["slot"] == "rail.vm.consumers[]"][0]["element"]
    assert e["kw"] == {"b": "col", "c": "active_power_r_kw"}


def test_verbatim_recipe_repeat_needs_no_basket_check():
    """Repeating the recipe's own binding is recipe truth ('repeat it or omit it') — member-scope columns live on
    MEMBER tables, so the panel's own basket may not carry them; only a CHANGED column is the AI's decision."""
    spec = {"slots": [{"slot": "heatmap.history", "scope": "members",
                       "element": {"iub": {"b": "col", "c": "current_unbalance_pct"},
                                   "pf": {"b": "prefer_abs", "cs": ["kpi_true_pf", "power_factor_total"]}}}]}
    roster = [{"slot": "heatmap.history",
               "element": {"iub": {"b": "col", "c": "current_unbalance_pct"},
                           "pf": {"b": "prefer_abs", "cs": ["kpi_true_pf", "power_factor_total"]}}}]
    ok, issues, norm = gate_roster(roster, spec, {"columns": [{"column": "active_power_total_kw"}]})
    assert ok and issues == []
    assert norm[0]["element"] == spec["slots"][0]["element"]


def test_hallucinated_column_rejected_recipe_ships():
    """A column not in the basket is rejected (verbatim-real rule) — the recipe binding ships instead."""
    roster = [{"slot": "rail.vm.consumers[]", "element": {"kw": {"b": "col", "c": "instantaneous_power"},
                                                          "pf": {"b": "prefer_abs", "cs": ["kpi_true_pf", "made_up"]}}}]
    ok, issues, norm = gate_roster(roster, _SPEC, _BASKET)
    assert not ok
    assert any("'instantaneous_power' not in basket" in i for i in issues)
    assert any("'made_up' not in basket" in i for i in issues)
    e = [s for s in norm if s["slot"] == "rail.vm.consumers[]"][0]["element"]
    assert e["kw"] == {"b": "col", "c": "active_power_total_kw"}          # recipe truth, not the hallucination
    assert e["pf"]["cs"] == ["kpi_true_pf", "power_factor_total"]


def test_unknown_slot_and_invented_element_key_rejected():
    roster = [{"slot": "rail.vm.invented[]", "element": {"kw": "active_power_total_kw"}},
              {"slot": "rail.vm.consumers[]", "element": {"efficiencyPct": "active_power_total_kw"}}]
    ok, issues, _ = gate_roster(roster, _SPEC, _BASKET)
    assert not ok
    assert any("not in card recipe" in i for i in issues)                 # hallucinated member slot
    assert any("not in recipe (invented)" in i for i in issues)           # hallucinated element key


def test_honest_null_key_refuses_a_column_binding():
    roster = [{"slot": "rail.vm.consumers[]", "element": {"utilizationPct": "active_power_total_kw"}}]
    ok, issues, norm = gate_roster(roster, _SPEC, _BASKET)
    assert not ok and any("honest-null" in i for i in issues)
    e = [s for s in norm if s["slot"] == "rail.vm.consumers[]"][0]["element"]
    assert e["utilizationPct"]["b"] == "null"                             # stays honest-null


def test_structural_fields_and_reducers_are_fixed():
    roster = [{"slot": "rail.vm.consumers[]", "role_filter": "supply", "cap": 99,
               "agg": {"totalKw": {"agg": "mean", "of": "kw"}}}]
    ok, issues, _ = gate_roster(roster, _SPEC, _BASKET)
    assert not ok
    assert any("role_filter='supply' != recipe 'load'" in i for i in issues)
    assert any("cap 99 > recipe cap 10" in i for i in issues)
    assert any("thresholds/reducers are fixed" in i for i in issues)


def test_roster_without_recipe_rejected():
    ok, issues, norm = gate_roster([{"slot": "x", "element": {}}], None, _BASKET)
    assert not ok and norm == [] and any("no roster recipe" in i for i in issues)


def test_empty_emission_backfills_full_recipe():
    """Deterministic fail-open: an AI that emits no roster still ships the complete recipe-derived roster."""
    ok, issues, norm = gate_roster([], _SPEC, _BASKET)
    assert ok and issues == []
    assert [s["slot"] for s in norm] == ["rail.vm.consumers[]", "rail.vm.kpis"]
    assert norm[0]["element"] == _SPEC["slots"][0]["element"]             # verbatim


def test_same_as_slot_expansion_is_intra_row():
    spec = {"slots": [{"slot": "a[]", "element": {"kw": {"b": "col", "c": "active_power_total_kw"}}},
                      {"slot": "b[]", "element": {"$same_as_slot": "a[]"}}]}
    out = _expand(spec)
    assert out["slots"][1]["element"] == out["slots"][0]["element"]


def test_card5_recipe_row_reaches_the_recipe_dict():
    """[package §2c] card_data_recipe.read merges the card_fill_recipe.roster_spec row (card 5 = RTM heatmap roster)."""
    from layer2.catalog.card_data_recipe import read
    rec = read(5)
    slots = [s["slot"] for s in (rec.get("roster_spec") or {}).get("slots", [])]
    assert "heatmap.history" in slots


def test_user_message_shows_roster_spec_verbatim():
    """[package §2c] the roster_spec row appears VERBATIM (compact JSON) inside the THIS CARD block."""
    from layer2.emit.user_message import build_user
    rspec = {"slots": [{"slot": "heatmap.history", "scope": "members",
                        "element": {"kw": {"b": "col", "c": "active_power_total_kw"}}}]}
    ci = {"run_id": "t", "card_id": 5, "page_key": "p", "is_group_card": False, "group_id": None,
          "story": {"page_story": "s", "analytical_story": "a", "metric": "kw", "intent": "monitor",
                    "template_card_ids": []},
          "asset": {}, "column_basket": _BASKET, "swap_candidates": [],
          "catalog_row": {"title": "RTM", "handling_class": "panel_aggregate", "resolver_scope": "panel",
                          "payload_family": "heatmap", "backend_strategy": None,
                          "recipe": {"payload_shape": "HeatmapPayload", "roster_spec": rspec},
                          "contract": {"payload_schema_json": {"heatmap": {}}, "capabilities": []},
                          "controls": {}, "feasibility": {}, "default_payload": None}}
    msg = build_user(ci)
    assert json.dumps(rspec, separators=(",", ":")) in msg                # VERBATIM row
    assert "roster_spec (VERBATIM card recipe" in msg
    ci["catalog_row"]["recipe"] = {"payload_shape": "HeatmapPayload"}     # no roster card → block omitted
    assert "roster_spec (VERBATIM" not in build_user(ci)


def test_prompt_carries_the_roster_rules():
    """[package §2b] data_instructions_v2.md (the single Layer-2 contract) teaches the roster vocabulary (emit key,
    column-only authority, honest-null)."""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "layer2", "prompts", "data_instructions_v2.md")
    txt = open(p).read()
    assert "## ROSTER (member-scope) slots" in txt
    assert "data_instructions.roster" in txt
    assert "NEVER emit roster for a card whose context has" in txt
    assert 'A recipe binding of {"b":"null"} is an HONEST-NULL key' in txt
