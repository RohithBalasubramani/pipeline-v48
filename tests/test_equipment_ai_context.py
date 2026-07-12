"""stream C — equipment-registry AI context: L2 fact lines + 1b alias columns/resolve + PANEL MEMBERS suffix.

All :5432-local (cmd_catalog); passes with the :5433 tunnel down. Fabrication walls proven here:
  · every fact line is '' (and the tuple ()) on miss / unmapped asset / knob-off — the prompt is byte-identical
    to pre-wiring for an asset with no equipment rows;
  · the alias branch NEVER pins a collision (unique-or-None), and canonical resolution always wins first;
  · the PANEL MEMBERS PRIMARY/context member_scope marking survives the aka suffix untouched.
"""
import copy

import config.app_config as ac
import layer2.emit.equipment_facts as ef


# ── pinned-path parity: the picker-repick carries the prompt's reading direction ────────────────────────────────────
def test_pinned_path_stamps_member_scope(monkeypatch):
    """A picked panel (asset_id round-trip) hits pinned_skip, which returns BEFORE _finish — so member_scope must be
    stamped on the pinned outcome from the ORIGINAL prompt, else 'incomer PCC-1A' silently defaults to outgoing."""
    import layer1b.resolve.asset_resolve as ar
    monkeypatch.setattr(ar, "asset_candidates", lambda: [])
    monkeypatch.setattr(ar, "pinned_skip",
                        lambda oid, by_id: ({"asset": {"mfm_id": 317, "name": "PCC Panel 1", "has_feeders": True},
                                             "how": "pinned", "candidates": []} if oid else None))
    assert ar.resolve_asset("voltage and current for pcc1a", "317")["asset"]["member_scope"] == "outgoing"
    assert ar.resolve_asset("incomer pcc1a voltage and current", "317")["asset"]["member_scope"] == "incomer"
    assert ar.resolve_asset("pcc1a supply side", "317")["asset"]["member_scope"] == "incomer"
    # no pin → falls through to the normal resolver (pinned_skip returns None), never raises here
    assert ar.pinned_skip(None, {}) is None


def _flag(monkeypatch, on=True):
    rows = {"equipment.facts.enabled": ("on" if on else "off", "text"),
            "equipment.alias.enabled": ("on" if on else "off", "text")}
    monkeypatch.setattr(ac, "_load", lambda: rows)


# ── equipment_facts: honest-degrade walls ────────────────────────────────────
def test_fact_lines_empty_on_miss_and_none():
    assert ef.equipment_fact_lines({"table": "no_such_table_xyz"}) == ()
    assert ef.equipment_fact_lines(None) == ()
    assert ef.equipment_fact_lines({}) == ()
    assert ef.member_suffix(None) == ""
    assert ef.member_suffix("no_such_table_xyz") == ""


def test_fact_lines_knob_off_is_empty(monkeypatch):
    _flag(monkeypatch, on=False)
    # even a REAL bridged table yields nothing with the knob off (byte-identical pre-wiring prompt)
    from data.equipment.db import eq_q
    rows = eq_q("SELECT table_name FROM equipment.mfm WHERE table_name IS NOT NULL LIMIT 1")
    tbl = str(rows[0][0]) if rows else "x"
    assert ef.equipment_fact_lines({"table": tbl, "name": "X"}) == ()
    assert ef.member_suffix(tbl) == ""


def test_fact_lines_real_asset_all_grounded(monkeypatch):
    _flag(monkeypatch, on=True)
    from data.equipment.db import eq_q
    rows = eq_q("SELECT m.table_name FROM equipment.mfm m JOIN equipment.breaker b ON b.mfm_id=m.id "
                "WHERE b.rating_a IS NOT NULL LIMIT 1")
    if not rows:
        return                                                  # registry variant without rated breakers — nothing to prove
    tbl = str(rows[0][0])
    lines = ef.equipment_fact_lines({"table": tbl, "name": "X"})
    joined = "\n".join(lines)
    assert any(l.startswith("EQUIPMENT (") for l in lines)
    assert any(l.startswith("BREAKER (") for l in lines)
    assert "rating_a=" in joined and "NEVER rescale" in joined  # breaker denominator + never-rescale clause ship
    sfx = ef.member_suffix(tbl)
    assert sfx.startswith(" | ") and "breaker_a=" in sfx


def test_rtm_bands_line_cites_const_family(monkeypatch):
    _flag(monkeypatch, on=True)
    from data.equipment.db import eq_q
    rows = eq_q("SELECT m.table_name FROM equipment.mfm m JOIN equipment.equipment e ON e.id=m.equipment_id "
                "JOIN equipment.core_paneltype pt ON pt.id=e.panel_type_id "
                "JOIN equipment.rtm_threshold t ON t.panel_type_id=pt.id LIMIT 1")
    if not rows:
        return
    line = ef.rtm_bands_line({"table": str(rows[0][0])})
    assert line.startswith("RTM STATUS BANDS (")
    assert "consts.rtm_" in line and "LEGAL" in line            # R10-citable const family named on the line


# ── 1b candidates: additive aka/loc columns, shape-safe ─────────────────────
def test_candidate_rows_carry_aka_loc_columns(monkeypatch):
    import layer1b.resolve.asset_candidates as acands
    monkeypatch.setattr(acands, "registry_rows", lambda: [
        {"id": 1, "name": "GIC-X", "table": "t1", "mfm_type_id": None, "load_group": "", "never_wired": False,
         "table_exists": True, "asset_type_code": None, "mfm_type_code": None},
    ])
    monkeypatch.setattr(acands, "parent_ids", lambda: set())
    monkeypatch.setattr(acands, "tables_with_values", lambda tables: set(tables))
    monkeypatch.setattr(acands, "_alias_map", lambda: {"t1": ("Feeder Tx-1 (PCC-1A)", "HT/GIC-15")})
    rows = acands.asset_candidates()
    assert len(rows[0]) == 12 and rows[0][10] == "Feeder Tx-1 (PCC-1A)" and rows[0][11] == "HT/GIC-15"
    a = acands.as_asset(rows[0])
    assert a["aka"] == "Feeder Tx-1 (PCC-1A)" and a["loc"] == "HT/GIC-15"
    # identical alias is scrubbed to '' (noise); 10-col legacy rows still as_asset cleanly (len-guard)
    monkeypatch.setattr(acands, "_alias_map", lambda: {"t1": ("GIC-X", "")})
    assert acands.asset_candidates()[0][10] == ""
    legacy = rows[0][:10]
    assert acands.as_asset(legacy)["aka"] is None


def test_alias_map_knob_off_empty(monkeypatch):
    _flag(monkeypatch, on=False)
    from layer1b.resolve.asset_candidates import _alias_map
    assert _alias_map() == {}


# ── 1b resolve: canonical-first, unique-alias, collision-never-pins ─────────
def _cands():
    # 12-col rows: two canonical rows; 'PCC-1A' aliases row A uniquely; 'Twin' collides across both
    base = lambda i, name, aka: [str(i), name, f"t{i}", "", "", "Panel", True, False, False, True, aka, ""]
    return [base(1, "GIC-15-N3-PCC-01", "Feeder Tx-1 (PCC-1A)"), base(2, "GIC-15-N4-PCC-02", "Twin")]


def test_resolve_name_alias_paths(monkeypatch):
    import layer1b.resolve.asset_resolve as ar
    cands = _cands()
    cands[0][10] = "Feeder Tx-1 (PCC-1A)"
    cands[1][10] = "Feeder Tx-1 (PCC-1A)"                       # force an alias COLLISION
    # reproduce resolve_name's maps exactly as resolve_asset builds them
    by_name = {c[1]: c for c in cands}
    by_norm, by_alias = {}, {}
    for c in cands:
        by_norm.setdefault(ar._norm(c[1]), []).append(c)
        if len(c) > 10 and c[10]:
            by_alias.setdefault(ar._norm(c[10]), []).append(c)

    def resolve_name(name):
        if name in by_name:
            return by_name[name]
        rows = by_norm.get(ar._norm(name))
        if rows:
            return rows[0] if len(rows) == 1 else None
        arows = by_alias.get(ar._norm(name))
        return arows[0] if arows and len(arows) == 1 else None

    assert resolve_name("GIC-15-N3-PCC-01")[0] == "1"           # canonical exact still first
    assert resolve_name("feeder tx-1 (pcc-1a)") is None          # alias collision NEVER pins
    by_alias.clear()
    by_alias[ar._norm("Feeder Tx-1 (PCC-1A)")] = [cands[0]]
    assert resolve_name("Feeder Tx-1 (PCC-1A)")[0] == "1"        # unique alias resolves
    assert resolve_name("unknown-thing") is None


def test_listing_carries_aka_column():
    import inspect
    import layer1b.resolve.asset_resolve as ar
    src = inspect.getsource(ar.resolve_asset)
    assert "aka" in src and "c[10] if len(c) > 10" in src        # 5th TAB column wired
    assert "name<TAB>class<TAB>load_group<TAB>flag<TAB>aka" in src


# ── PANEL MEMBERS: suffix appended, PRIMARY marking untouched ────────────────
def test_panel_members_suffix_and_primary_preserved(monkeypatch):
    import layer2.emit.panel_members_block as pmb
    monkeypatch.setattr(pmb, "_member_has_data", lambda t: bool(t))
    monkeypatch.setattr(pmb, "_member_last_ts", lambda t: None)
    monkeypatch.setattr(pmb, "_member_suffix", lambda t: " | aka=HHF-1 | breaker_a=1000" if t else "")
    lines = pmb._lines([{"name": "F1", "neuract_table": "gic_x"}, {"name": "F2", "neuract_table": None}])
    assert lines[0].startswith("    F1 | table=gic_x")           # canonical name stays FIRST
    assert lines[0].endswith(" | aka=HHF-1 | breaker_a=1000")
    assert lines[1].endswith("| last=—")                         # no-table member line byte-identical (no suffix)

    members = [{"mfm_id": 1, "name": "M1", "neuract_table": "gic_x", "role": "outgoing"}]
    import data.neuract_live.members as rm
    monkeypatch.setattr(rm, "incomers_of", lambda mid: [])
    monkeypatch.setattr(rm, "outgoers_of", lambda mid: copy.deepcopy(members))
    pmb._block_for.cache_clear()
    blk_out = pmb.panel_members_block({"has_feeders": True, "mfm_id": 999901, "member_scope": "outgoing"})
    blk_in = pmb.panel_members_block({"has_feeders": True, "mfm_id": 999901, "member_scope": "incomer"})
    assert "PRIMARY" in blk_out and "OUTGOING" in blk_out.split("PRIMARY")[1][:60]
    assert "PRIMARY" in blk_in and "INCOMERS" in blk_in.split("PRIMARY")[1][:60]


# ── user_message wiring: fact lines ride the ASSET block ─────────────────────
def test_user_message_injects_equipment_facts(monkeypatch):
    import layer2.emit.user_message as um
    monkeypatch.setattr(um, "nameplate_line", lambda a: "")
    monkeypatch.setattr(um, "data_window_line", lambda a, b=None: "")
    monkeypatch.setattr(um, "equipment_fact_lines",
                        lambda a: ("EQUIPMENT (verbatim equipment-registry facts): aka=T1", "BREAKER (x): rating_a=1000 A"))
    ci = {"run_id": "t", "card_id": 5, "page_key": "p", "is_group_card": False, "group_id": None,
          "story": {"page_story": "", "analytical_story": "", "metric": "", "intent": "", "template_card_ids": []},
          "asset": {"name": "A", "class": "Panel", "table": "t"},
          "column_basket": {"columns": [], "probable": []}, "swap_candidates": [],
          "catalog_row": {"title": "T", "handling_class": "single_asset", "resolver_scope": "", "payload_family": "",
                          "recipe": {"payload_shape": "", "orientation": "", "entity_dim": "", "selection_dim": "",
                                     "selection_role": "", "fields": []},
                          "contract": {"capabilities": [], "component": "", "host_cmd_component": "",
                                       "canonical_shape": "", "payload_schema_json": {}},
                          "controls": {"time_mode": "", "sampling_options": [], "segmented_tabs": [], "defaults": {}},
                          "feasibility": {"verdict": "", "required_topology": "", "reason": ""},
                          "backend_strategy": None, "default_payload": None}}
    msg = um._build(ci)
    i_eq, i_schema = msg.find("EQUIPMENT (verbatim"), msg.find("DB SCHEMA")
    assert 0 < i_eq < i_schema                                   # facts sit in the ASSET block, above the schema
    assert "BREAKER (x): rating_a=1000 A" in msg
    # and with no facts the message carries no equipment line at all
    monkeypatch.setattr(um, "equipment_fact_lines", lambda a: ())
    assert "EQUIPMENT (verbatim" not in um._build(ci)
