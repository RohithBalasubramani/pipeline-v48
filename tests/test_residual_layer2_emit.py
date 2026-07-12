"""Residual-fix group 'layer2' [A2/A5/C1/C3/C4] — the emit user-message/prompt seams, pinned.

  A5  fields-optional THREE-branch matrix: a member-scope card WITH roster_spec gets the ROSTER CARD guidance
      (roster + fields:[] + KEEP fetch + answerability=member coverage), never the NO-FIELDS/OMIT chrome text.
  C1  token bundle: ✗/★ basket markers are per-line TOKENS defined once in the header; empty metric/rank dropped;
      relevant-cols why-prose only on conf<1.0; endpoint closed-set/retired/choose-by live ONLY in the system prompt;
      slot expected_qty is the bare `| expected_qty=X` (+ `(weak)`) token.
  A2  RELEVANT COLUMNS best-effort carries the SAME-QUANTITY-FAMILY qualifier (defers to the ONE canonical rule).
  C3  NAMEPLATE + DATA WINDOW fact lines wired into the ASSET block; PANEL MEMBERS lines carry last=<ts>.
  C4  FOUR→FIVE walls; no prompt-filename refs in the user message; DUAL-OWNED per-card flag replaces the
      RTM/HPQ fixtures that used to sit in the shared metadata.md.

All offline: cfg()/DB reads fail-open to code defaults; no LLM."""
import os

import layer2.emit.user_message as um
from layer2.emit.user_message import build_user

_P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "layer2", "prompts")

_BASKET = {
    "tables": [],
    "columns": [
        {"column": "active_power_total_kw", "metric": "", "kind": "raw", "unit": "kW", "has_data": True, "rank": None},
        {"column": "current_max_spread", "metric": "", "kind": "derived", "unit": "A", "has_data": True, "rank": None},
        {"column": "thd_voltage_avg", "metric": "", "kind": "raw", "unit": "%", "has_data": False, "rank": None,
         "verdict": "fail"},
    ],
    "probable": [
        {"column": "active_power_total_kw", "confidence": 1.0, "label": "Active Power",
         "why": "exact match for the asked metric"},
        {"column": "current_max_spread", "confidence": 0.7, "label": "Spread",
         "substitute_for": "current unbalance", "why": "closest stand-in"},
    ],
}

_RSPEC = {"slots": [{"slot": "heatmap.history", "scope": "members",
                     "element": {"kw": {"b": "col", "c": "active_power_total_kw"}}}]}


def _ci(handling_class="panel_aggregate", roster_spec=_RSPEC, schema=None):
    return {"run_id": "t", "card_id": 5, "page_key": "p", "is_group_card": False, "group_id": None,
            "story": {"page_story": "s", "analytical_story": "a", "metric": "kw", "intent": "monitor",
                      "template_card_ids": []},
            "asset": {}, "column_basket": _BASKET, "swap_candidates": [],
            "catalog_row": {"title": "RTM", "handling_class": handling_class, "resolver_scope": "panel",
                            "payload_family": "heatmap", "backend_strategy": None,
                            "recipe": {"payload_shape": "HeatmapPayload",
                                       **({"roster_spec": roster_spec} if roster_spec else {})},
                            "contract": {"payload_schema_json": schema or {"heatmap": {}}, "capabilities": []},
                            "controls": {}, "feasibility": {}, "default_payload": None}}


# ── A5: the three no-fields branches ─────────────────────────────────────────────────────────────────────────────────
def test_roster_card_gets_roster_branch_not_chrome_text():
    msg = build_user(_ci())
    assert "★ ROSTER CARD" in msg
    assert "NO-FIELDS CARD" not in msg                          # the old mis-branch (card 18 dropped its roster)
    assert "KEEP the fetch block" in msg                        # the OMIT-fetch contradiction is gone
    assert "MEMBER COVERAGE" in msg                             # answerability = member coverage
    assert "roster_spec (VERBATIM card recipe" in msg           # the recipe row still shows verbatim


def test_panel_aggregate_without_roster_spec_keeps_fanout_branch():
    msg = build_user(_ci(roster_spec=None))
    assert "★ PANEL-AGGREGATE CARD" in msg and "★ ROSTER CARD" not in msg


def test_chrome_class_keeps_no_fields_branch():
    msg = build_user(_ci(handling_class="narrative_ai", roster_spec=None))
    assert "★ NO-FIELDS CARD" in msg and "★ ROSTER CARD" not in msg


# ── C1: token bundle ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_basket_markers_are_tokens_defined_once_in_header():
    msg = build_user(_ci())
    assert "✗ FAILED-VALIDATION" in msg and "mostly-null on this meter" in msg
    assert msg.count("FAILED-VALIDATION") == 2                  # ONE header definition + ONE per-line token
    assert "★ REAL-LOGGED (kind:raw)" in msg
    assert msg.count("REAL-LOGGED") == 2                        # ONE header definition + ONE per-line token
    assert "do NOT wrap in an fn; name_hint=derived is only a spelling guess" not in msg   # old per-line prose gone


def test_empty_metric_and_rank_fields_are_dropped():
    lines = um._basket_lines({"columns": [{"column": "c1", "unit": "kW", "has_data": True,
                                           "metric": "", "rank": None}]})
    assert "| |" not in lines and lines.strip().endswith("data=Y")
    withm = um._basket_lines({"columns": [{"column": "c1", "unit": "kW", "has_data": True,
                                           "metric": "kw", "rank": 1}]})
    assert "| kw |" in withm and "rank=1" in withm


def test_why_prose_only_on_substitute_rows():
    msg = build_user(_ci())
    assert "(exact match for the asked metric)" not in msg      # conf=1.0 → why dropped
    assert "(closest stand-in)" in msg                          # conf<1.0 → why kept


def test_endpoint_closed_set_lives_in_system_prompt_not_user_message():
    msg = build_user(_ci())
    assert "ONLY these endpoints EXIST" not in msg
    assert "RETIRED — DO NOT EXIST" not in msg
    from layer2.emit.emit import _system
    sysmsg = _system(_ci())
    assert "THE CLOSED SET" in sysmsg and "{{LIVE_ENDPOINTS}}" not in sysmsg
    assert "★ RETIRED — DO NOT EXIST" in sysmsg and "{{RETIRED_ENDPOINTS}}" not in sysmsg


def test_slot_expected_qty_is_a_bare_token():
    from layer2.emit.slot_catalog import render_slot_catalog
    txt = render_slot_catalog([
        {"slot": "a.b", "kind": "scalar", "element_key": "b", "time_axis": False,
         "ctx": {"label": "R-Phase", "unit": "V", "section": None}, "quantity": "voltage"},
        {"slot": "a.pct", "kind": "scalar", "element_key": "pct", "time_axis": False,
         "ctx": {"label": "Load", "unit": "%", "section": None}, "quantity": "percent"},
    ])
    assert "| expected_qty=voltage" in txt
    assert "bind ONLY a qty=" not in txt                        # per-line rule prose moved to the header
    # the header carries the ONE definition of the token + the (weak) suffix
    msg = build_user(_ci())
    assert "`| expected_qty=X` takes ONLY a qty=X column/fn" in msg
    assert "`(weak)`" in msg


# ── A2: SAME-QUANTITY qualifier on the best-effort substitute path ───────────────────────────────────────────────────
def test_relevant_columns_substitute_is_same_quantity_qualified():
    msg = build_user(_ci())
    assert "SAME-QUANTITY-FAMILY PROXY RULE" in msg
    assert "DIFFERENT-quantity column is NEVER a substitute" in msg


# ── C3: nameplate + data-window facts ────────────────────────────────────────────────────────────────────────────────
def test_asset_fact_lines_wired_into_user_message(monkeypatch):
    monkeypatch.setattr(um, "nameplate_line", lambda a: "NAMEPLATE (this asset's real rating row): rated_kva=—")
    monkeypatch.setattr(um, "data_window_line", lambda a, b=None: "DATA WINDOW (table t's real logged rows): last=X")
    msg = build_user(_ci())
    i_np, i_dw, i_schema = msg.find("NAMEPLATE ("), msg.find("DATA WINDOW ("), msg.find("DB SCHEMA")
    assert 0 < i_np < i_dw < i_schema                           # both facts sit in the ASSET block, above the schema


def test_asset_fact_lines_omitted_when_unresolvable():
    from layer2.emit.asset_facts import nameplate_line, data_window_line
    assert nameplate_line({}) == "" and nameplate_line(None) == ""
    assert data_window_line({}) == "" and data_window_line(None) == ""
    msg = build_user(_ci())                                     # asset {} → no fact lines, never a crash
    assert "NAMEPLATE (" not in msg


def test_panel_members_lines_carry_last_ts(monkeypatch):
    import layer2.emit.panel_members_block as pmb
    monkeypatch.setattr(pmb, "_member_has_data", lambda t: bool(t))
    monkeypatch.setattr(pmb, "_member_last_ts", lambda t: "2026-07-01T10:00:00+00:00" if t else None)
    lines = pmb._lines([{"name": "F1", "neuract_table": "gic_x"}, {"name": "F2", "neuract_table": None}])
    assert "| last=2026-07-01T10:00:00+00:00" in lines[0]
    assert lines[1].endswith("| last=—")                        # honest '—', never a guessed timestamp


# ── C4: leftovers ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_five_walls_and_no_filename_refs_in_user_message():
    msg = build_user(_ci())
    assert "FOUR WALLS" not in msg and "FIVE PHYSICAL WALLS" in msg
    assert "data_instructions.md" not in msg                    # the model sees a prompt, not filenames


def test_prompts_carry_five_walls_and_closed_source_set():
    # data_instructions_v2.md is the SINGLE Layer-2 contract — it subsumes the retired swap/metadata/data_instructions
    # trio, so every rule those files taught now lives here (and is what the model actually sees).
    di = open(os.path.join(_P, "data_instructions_v2.md"), errors="replace").read()
    assert "FOUR PHYSICAL WALLS" not in di and "THE FIVE PHYSICAL WALLS" in di
    assert "live | test-db | $ctx | const" in di                # documents the gate's closed source set
    assert "mock" not in di.lower()                             # the mock asides are gone
    assert "BEST-EFFORT + ANSWERABILITY" in di
    assert "_morphed` (REQUIRED" in di                          # [A1] the contract is REQUIRED, not audit-only
    assert "sectionContracts" not in di                         # RTM/HPQ fixtures moved out of the shared prompt


def test_dual_owned_flag_is_per_card_from_the_skeleton():
    msg = build_user(_ci(schema={"heatmap": {"sectionContracts": {"incomers": 0}}}))
    assert "DUAL-OWNED metadata keys of THIS card" in msg and "heatmap.sectionContracts" in msg
    msg2 = build_user(_ci())                                    # no matching key → no flag
    assert "DUAL-OWNED metadata keys of THIS card" not in msg2


# ── A1: _morphed contract — undeclared morphs revert (never ship) but surface as telemetry, no auto-promote ─────────
def test_undeclared_morph_reverts_and_surfaces_as_telemetry():
    from layer2.emit.metadata.producer import produce, undeclared_morphs
    default = {"kpi": {"title": "T", "value": 5}}
    stored = {"kpi": {"title": "T", "value": 0}}                # the stripped skeleton (data leaf → placeholder)
    ai = {"kpi": {"title": "Morphed", "value": 0}}              # authored change WITHOUT declaring it
    out, applied, rejected = produce(default, ai, [], stored=stored)
    assert out["kpi"]["title"] == "T" and applied == []         # undeclared ⇒ reverted to the byte-identical default
    tel = undeclared_morphs(default, ai, [], stored=stored)
    assert "kpi.title" in tel                                   # …but VISIBLE (the 2-of-6812 silent no-op, surfaced)
    assert "kpi.value" not in tel                               # data-tier paths are the strip guard, not a morph
    assert undeclared_morphs(default, ai, ["kpi.title"], stored=stored) == []   # declared ⇒ not telemetry
    out2, applied2, _ = produce(default, ai, ["kpi.title"], stored=stored)
    assert out2["kpi"]["title"] == "Morphed" and applied2 == ["kpi.title"]      # the ONLY shipping channel


def test_contract_exemplar_carries_empty_morphed_list():
    di = open(os.path.join(_P, "data_instructions_v2.md"), errors="replace").read()
    assert '"exact_metadata":{"_morphed":[]}' in di             # [A1] the exemplar teaches the REQUIRED key


# ── C2: recovery library filtered to basket-compatible fns; ROSTER section only to member-scope cards ───────────────
def test_recovery_library_filters_to_basket_and_names_the_hidden_count():
    from layer2.emit.emit import _recovery_library_block
    full = _recovery_library_block(None)                        # no card → full library, unchanged
    assert "fns hidden" not in full
    ci = {"column_basket": {"columns": [{"column": "current_r"}, {"column": "current_y"},
                                        {"column": "current_b"}]}, "asset": {}}
    filt = _recovery_library_block(ci)
    assert len(filt) < len(full)
    assert "neutralCurrent" in filt                             # bases all in basket → still offered
    assert "fns hidden" in filt                                 # the trailer names the cut (never silently invisible)


def test_roster_section_ships_only_to_member_scope_cards():
    from layer2.emit.emit import _wants_roster_section, _system
    assert not _wants_roster_section({"catalog_row": {"handling_class": "single_asset", "recipe": {}}})
    assert _wants_roster_section({"catalog_row": {"handling_class": "panel_aggregate", "recipe": {}}})
    assert _wants_roster_section({"catalog_row": {"handling_class": "single_asset",
                                                  "recipe": {"roster_spec": {"slots": []}}}})
    member = _system({"catalog_row": {"handling_class": "panel_aggregate", "recipe": {}},
                      "column_basket": {"columns": []}, "asset": {}})
    plain = _system({"catalog_row": {"handling_class": "single_asset", "recipe": {}},
                     "column_basket": {"columns": []}, "asset": {}})
    assert "## ROSTER (member-scope) slots" in member
    assert "## ROSTER (member-scope) slots" not in plain
    for s in (member, plain):                                   # markers never leak into the prompt
        assert "<!--ROSTER:BEGIN-->" not in s and "<!--ROSTER:END-->" not in s
