"""STREAM B (equipment wiring) — ratings/limits accessors + the breakerOverloadPct derivation, pinned.

  · breaker_rating resolves the REAL rating for a breaker-backed feeder; None for dup-table / no-row / unknown /
    DB-error; a NULL rating_a row keeps rating_a=None (NEVER defaulted).
  · breaker_state is the TRI-STATE emit probe: True rated, False known-empty (hide), None unknown (NEVER hides).
  · overload_pct = current ÷ rating_a × 100 with the max-phase basis (else current_avg) and honest None propagation
    (no current / no rating / non-positive rating / knob off).
  · SOURCE GATE [fatal R2-2]: at default knobs registry.catalog() omits the fn entirely — no library line, no
    hidden-count drift, no note key on any legacy entry, no 'breaker' byte anywhere in the system prompt — while
    LIBRARY still resolves it and run() returns None (a hallucinated reference can never fill).
  · emit filter (knob-ON only): 'breaker:' pseudo-base is non-plain; known-empty hides; unknown never hides;
    the generalized pseudo-prefix split is a byte-no-op for every legacy entry.
  · rtm_bands_for_asset returns panel-type default bands (normalized basis strings, explicit provenance) only when
    a real row chain matches; else None. rtm_const_key spellings == the 72 seeded consts.rtm_* rows (parity).
  · voltage_deviation_pct only from the 7 populated rows; NO accessor exists for the 0/120-NULL config columns.

ALL :5432-local (cmd_catalog); passes with the :5433 neuract tunnel down. No 'live' marker needed.
"""
import re

import pytest

from data.equipment import db as _eqdb
from data.equipment import ratings
from ems_exec.derivations import breaker, registry

_UNIQ = "(SELECT count(*) FROM equipment.mfm m2 WHERE m2.table_name = m.table_name) = 1"


@pytest.fixture(autouse=True)
def _fresh_equipment_caches():
    """The equipment door + ratings caches persist per process — clear around every test so a monkeypatched eq_q or
    a prior test's rows never leak into the next (mirrors conftest's app_config cache hygiene)."""
    _eqdb.clear_cache(); ratings.clear_cache()
    yield
    _eqdb.clear_cache(); ratings.clear_cache()


def _first(sql):
    rows = _eqdb.eq_q(sql)
    return rows[0] if rows else None


def _rated_fixture():
    r = _first("SELECT m.table_name, b.rating_a FROM equipment.breaker b JOIN equipment.mfm m ON b.mfm_id = m.id "
               f"WHERE b.rating_a IS NOT NULL AND {_UNIQ} LIMIT 1")
    if not r:
        pytest.skip("no uniquely-bridged rated breaker row in equipment schema")
    return r[0], float(r[1])


def _null_rated_fixture():
    r = _first("SELECT m.table_name FROM equipment.breaker b JOIN equipment.mfm m ON b.mfm_id = m.id "
               f"WHERE b.rating_a IS NULL AND {_UNIQ} LIMIT 1")
    if not r:
        pytest.skip("no uniquely-bridged NULL-rated breaker row in equipment schema")
    return r[0]


def _dup_table_fixture():
    r = _first("SELECT table_name FROM equipment.mfm GROUP BY table_name HAVING count(*) > 1 LIMIT 1")
    if not r:
        pytest.skip("no duplicated table_name group in equipment schema")
    return r[0]


def _no_breaker_fixture():
    r = _first("SELECT m.table_name FROM equipment.mfm m LEFT JOIN equipment.breaker b ON b.mfm_id = m.id "
               f"WHERE b.id IS NULL AND {_UNIQ} LIMIT 1")
    if not r:
        pytest.skip("every uniquely-bridged meter has a breaker row")
    return r[0]


# ── breaker_rating: real rating for a breaker-backed feeder; honest None everywhere else ────────────────────────────
def test_breaker_rating_resolves_for_breaker_backed_feeder():
    table, rating = _rated_fixture()
    got = ratings.breaker_rating(table)
    assert got is not None
    assert got["rating_a"] == rating and rating > 0
    assert got["breaker_type"] in ("ACB", "MCCB")
    assert set(got) == {"rating_a", "breaker_type", "glb_node", "panel_key"}


def test_breaker_rating_null_rated_row_keeps_none_rating():
    got = ratings.breaker_rating(_null_rated_fixture())
    assert got is not None
    assert got["rating_a"] is None                              # NEVER defaulted — the denominator is real or absent
    assert got["breaker_type"] in ("ACB", "MCCB")


def test_breaker_rating_none_for_missing_dup_and_unbridged():
    assert ratings.breaker_rating("zz_no_such_table_stream_b") is None
    assert ratings.breaker_rating(_dup_table_fixture()) is None  # dup-table meter: un-bridgeable, honest skip
    assert ratings.breaker_rating(_no_breaker_fixture()) is None
    assert ratings.breaker_rating(None) is None
    assert ratings.breaker_rating("") is None


def test_breaker_rating_fail_open_on_db_error(monkeypatch):
    def _boom(sql):
        raise RuntimeError("db down")
    monkeypatch.setattr(ratings._db, "eq_q", _boom)
    assert ratings.breaker_rating("anything") is None


# ── breaker_state: the tri-state emit probe ──────────────────────────────────────────────────────────────────────────
def test_breaker_state_tristate():
    table, _ = _rated_fixture()
    assert ratings.breaker_state(table) is True
    assert ratings.breaker_state(_null_rated_fixture()) is False   # known-empty → the fn may be hidden
    assert ratings.breaker_state(_no_breaker_fixture()) is False
    assert ratings.breaker_state(_dup_table_fixture()) is False
    assert ratings.breaker_state("zz_no_such_table_stream_b") is False
    assert ratings.breaker_state(None) is None                     # no asset → UNKNOWN — never hides


def test_breaker_state_unknown_on_db_error(monkeypatch):
    def _boom(sql):
        raise RuntimeError("db down")
    monkeypatch.setattr(ratings._db, "eq_q", _boom)
    assert ratings.breaker_state("anything") is None               # unknown — never hides (mirrors _nameplate_rated)


# ── overload_pct: math, basis, honest None propagation, knob gate ────────────────────────────────────────────────────
def test_overload_pct_max_phase_basis(monkeypatch):
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    monkeypatch.setattr(ratings, "breaker_rating", lambda t: {"rating_a": 2000.0})
    ctx = {"asset_table": "t", "row": {"current_r": 900, "current_y": 1000, "current_b": 950, "current_avg": 950}}
    assert breaker.overload_pct(ctx) == 50.0                       # max-phase (1000), never the average


def test_overload_pct_falls_back_to_current_avg(monkeypatch):
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    monkeypatch.setattr(ratings, "breaker_rating", lambda t: {"rating_a": 2000.0})
    assert breaker.overload_pct({"asset_table": "t", "row": {"current_avg": "500"}}) == 25.0


def test_overload_pct_honest_none_propagation(monkeypatch):
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    monkeypatch.setattr(ratings, "breaker_rating", lambda t: {"rating_a": 2000.0})
    assert breaker.overload_pct({"asset_table": "t", "row": {}}) is None            # no current anywhere
    assert breaker.overload_pct({"row": {"current_avg": 500}}) is None              # no asset table
    monkeypatch.setattr(ratings, "breaker_rating", lambda t: {"rating_a": None})
    assert breaker.overload_pct({"asset_table": "t", "row": {"current_avg": 500}}) is None  # NULL rating (133 rows)
    monkeypatch.setattr(ratings, "breaker_rating", lambda t: None)
    assert breaker.overload_pct({"asset_table": "t", "row": {"current_avg": 500}}) is None  # no breaker row
    monkeypatch.setattr(ratings, "breaker_rating", lambda t: {"rating_a": 0})
    assert breaker.overload_pct({"asset_table": "t", "row": {"current_avg": 500}}) is None  # 0 denominator


def test_overload_pct_none_at_knob_off_even_when_computable(monkeypatch):
    monkeypatch.setattr(ratings, "breaker_rating", lambda t: {"rating_a": 2000.0})
    assert breaker.enabled() is False                              # live row + code default are both 'off'
    assert breaker.overload_pct({"asset_table": "t", "row": {"current_avg": 500}}) is None


def test_overload_pct_live_rating_end_to_end(monkeypatch):
    table, rating = _rated_fixture()
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    ctx = {"asset_table": table, "row": {"current_avg": rating / 2.0}}
    assert breaker.overload_pct(ctx) == 50.0                       # real equipment.breaker denominator
    assert registry.run("breakerOverloadPct", ctx) == 50.0         # the executor's generic path resolves it too


# ── the SOURCE gate [fatal R2-2]: knobs-off → absent from catalog(), unfillable via run() ────────────────────────────
def test_catalog_omits_breaker_fn_at_default_knobs():
    assert breaker.enabled() is False
    names = {e["fn"] for e in registry.catalog()}
    assert "breakerOverloadPct" not in names
    assert "breakerOverloadPct" in registry.LIBRARY               # the descriptor exists; only the OFFER is gated
    assert all("note" not in e for e in registry.catalog())       # no legacy entry gains a note key (byte-identity)
    ctx = {"asset_table": "t", "row": {"current_avg": 500}}
    assert registry.run("breakerOverloadPct", ctx) is None        # hallucinated reference can never fill


def test_catalog_offers_breaker_fn_at_knob_on(monkeypatch):
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    entries = {e["fn"]: e for e in registry.catalog()}
    e = entries.get("breakerOverloadPct")
    assert e is not None
    assert e["base_columns"] == ["current_avg", "breaker:rating_a"]
    assert e["quantity"] == "load-percent-of-rated"               # existing HARD class — the quantity walls accept it
    assert "max-phase" in e["note"]                               # the basis is STATED (avg never reads as worst-case)


def test_catalog_gate_fails_closed(monkeypatch):
    def _boom():
        raise RuntimeError("knob read broke")
    monkeypatch.setattr(breaker, "enabled", _boom)
    assert "breakerOverloadPct" not in {e["fn"] for e in registry.catalog()}


def test_quantity_map_has_hard_class():
    assert registry._QUANTITY["breakerOverloadPct"] == "load-percent-of-rated"


# ── emit filter: pseudo-prefix split is a legacy no-op; tri-state hiding on the knob-ON path only ────────────────────
def _card(table, cols=("current_avg",)):
    return {"asset": {"table": table},
            "column_basket": {"columns": [{"column": c} for c in cols]}}


def test_pseudo_prefix_split_is_noop_for_legacy_entries():
    from layer2.emit.emit import _PSEUDO_BASE
    for e in registry.catalog():                                  # default knobs: the pre-existing library only
        base = [str(b) for b in e["base_columns"]]
        assert [b for b in base if _PSEUDO_BASE.match(b)] == [b for b in base if b.startswith("nameplate:")]


def test_emit_hides_breaker_fn_when_rating_known_empty(monkeypatch):
    from layer2.emit.emit import _recovery_library_block
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    monkeypatch.setattr(ratings, "breaker_state", lambda t: False)
    block = _recovery_library_block(_card("some_table"))
    assert "breakerOverloadPct" not in block
    assert re.search(r"\(\d+ fns hidden", block)                  # the cut is named, never silently invisible


def test_emit_offers_breaker_fn_when_rated_or_unknown(monkeypatch):
    from layer2.emit.emit import _recovery_library_block
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    monkeypatch.setattr(ratings, "breaker_state", lambda t: True)
    assert "breakerOverloadPct" in _recovery_library_block(_card("some_table"))
    monkeypatch.setattr(ratings, "breaker_state", lambda t: None)
    assert "breakerOverloadPct" in _recovery_library_block(_card("some_table"))  # unknown NEVER hides


def test_emit_hides_breaker_fn_for_real_unrated_feeder(monkeypatch):
    from layer2.emit.emit import _recovery_library_block
    monkeypatch.setattr(breaker, "enabled", lambda: True)         # the design's proof case (2): rating absent → hidden
    assert "breakerOverloadPct" not in _recovery_library_block(_card(_null_rated_fixture()))


def test_emit_basket_filter_still_applies_to_current_avg(monkeypatch):
    from layer2.emit.emit import _recovery_library_block
    monkeypatch.setattr(breaker, "enabled", lambda: True)
    monkeypatch.setattr(ratings, "breaker_state", lambda t: True)
    block = _recovery_library_block(_card("some_table", cols=("voltage_avg",)))
    assert "breakerOverloadPct" not in block                      # plain base current_avg not in basket → hidden


def test_system_prompt_has_no_breaker_bytes_at_default_knobs():
    from layer2.emit.emit import _recovery_library_block, _system
    assert breaker.enabled() is False
    assert "breakerOverloadPct" not in _recovery_library_block(None)
    assert "breaker:" not in _recovery_library_block(None)
    sysmsg = _system(None)                                        # the FULL knobs-off SYSTEM prompt [fatal R2-2 pin]
    assert "breakerOverloadPct" not in sysmsg and "breaker:" not in sysmsg


# ── rtm bands: real chain only, normalized basis, explicit provenance; const-key seed parity ────────────────────────
def _rtm_fixture():
    r = _first(
        "SELECT m.table_name, pt.code FROM equipment.mfm m "
        "JOIN equipment.equipment e ON e.id = m.equipment_id "
        "JOIN equipment.core_paneltype pt ON pt.id = e.panel_type_id "
        "JOIN equipment.rtm_threshold t ON t.panel_type_id = pt.id "
        f"WHERE {_UNIQ} LIMIT 1")
    if not r:
        pytest.skip("no uniquely-bridged meter with a panel-type rtm chain")
    return r[0], r[1]


def test_rtm_bands_resolve_for_real_chain():
    table, code = _rtm_fixture()
    got = ratings.rtm_bands_for_asset(table)
    assert got is not None
    assert got["panel_type"] == code
    assert got["provenance"] == "panel_type_default"              # hosting-equipment type, NOT a per-meter calibration
    bands = got["bands"]
    assert set(bands) == {"kw", "amp", "kvar", "volt", "pf", "i_unbal"}
    for b in bands.values():
        assert all(isinstance(b[k], float) for k in ("low_max", "normal_max", "moderate_max", "high_max"))
    assert bands["kw"]["basis"] == "% of rated kW"
    assert bands["amp"]["basis"] == "% of rated kVA"              # amp bands are NOT % of amps — basis is stated
    assert bands["pf"]["basis"] == "raw, DESCENDING >="
    rows = {r[0]: r for r in _eqdb.eq_q(
        "SELECT t.metric, t.low_max, t.high_max FROM equipment.rtm_threshold t "
        f"JOIN equipment.core_paneltype pt ON pt.id = t.panel_type_id WHERE pt.code = '{code}'")}
    for metric, b in bands.items():                               # values are the DB rows, verbatim
        assert b["low_max"] == float(rows[metric][1]) and b["high_max"] == float(rows[metric][2])


def test_rtm_bands_none_when_no_real_row_matches(monkeypatch):
    assert ratings.rtm_bands_for_asset("zz_no_such_table_stream_b") is None
    assert ratings.rtm_bands_for_asset(_dup_table_fixture()) is None
    assert ratings.rtm_bands_for_asset(None) is None
    monkeypatch.setattr(ratings._db, "unique_mfm_row", lambda t: {"equipment_id": None})
    assert ratings.rtm_bands_for_asset("any") is None             # bridged meter with no equipment link
    monkeypatch.setattr(ratings._db, "unique_mfm_row", lambda t: {"equipment_id": "7"})
    monkeypatch.setattr(ratings._db, "eq_q", lambda sql: (_ for _ in ()).throw(RuntimeError("db down")))
    assert ratings.rtm_bands_for_asset("any") is None             # fail-open on DB error


def test_rtm_const_key_spelling_and_seed_parity():
    from data.db_client import q
    assert ratings.rtm_const_key("lt_panel", "kw", "low") == "consts.rtm_lt_panel_kw_low"
    expected = {}
    for r in _eqdb.eq_q(
            "SELECT pt.code, t.metric, t.low_max, t.normal_max, t.moderate_max, t.high_max "
            "FROM equipment.rtm_threshold t JOIN equipment.core_paneltype pt ON pt.id = t.panel_type_id"):
        for band, val in zip(("low", "normal", "moderate", "high"), r[2:6]):
            expected[ratings.rtm_const_key(r[0], r[1], band)] = float(val)
    assert len(expected) == 72                                    # 6 metrics × 3 panel types × 4 bands
    rows = q("cmd_catalog", "SELECT key, value, data_type FROM app_config WHERE key LIKE 'consts.rtm_%'")
    assert {r[0] for r in rows} == set(expected)                  # seed and key-speller can never fork
    for key, value, dt in rows:
        assert dt == "number"                                     # the NOT NULL data_type convention, supplied
        assert float(value) == expected[key]


# ── voltage deviation limit (7/120) + the all-NULL columns stay unwired ──────────────────────────────────────────────
def _voltage_fixture():
    r = _first(
        "SELECT m.table_name, c.voltage_statutory_deviation_pct FROM equipment.equipment_config c "
        "JOIN equipment.mfm m ON m.equipment_id = c.equipment_id "
        f"WHERE c.voltage_statutory_deviation_pct IS NOT NULL AND {_UNIQ} LIMIT 1")
    if not r:
        pytest.skip("no uniquely-bridged meter with a populated voltage deviation limit")
    return r[0], float(r[1])


def test_voltage_deviation_pct_resolves_only_from_populated_rows():
    table, expected = _voltage_fixture()
    assert ratings.voltage_deviation_pct(table) == expected
    assert ratings.voltage_deviation_pct("zz_no_such_table_stream_b") is None
    assert ratings.voltage_deviation_pct(None) is None


def test_no_accessor_for_the_null_upstream_config_columns():
    # 27/28 numeric equipment_config columns are 0/120 NULL upstream BY DESIGN, and rated_kva's authority is
    # public.asset_nameplate — ratings.py must not grow accessors for any of them.
    for name in ("rated_kva", "rated_kw", "contracted_kw", "critical_load_kw", "thd_v_limit_pct", "thd_i_limit_pct",
                 "demand_limit_kw", "target_efficiency_pct", "energy_target_kwh_today", "subsidy_limit_kw",
                 "nominal_voltage_v", "rated_current_a"):
        assert not hasattr(ratings, name)
