"""tests/test_describe_column_dictionary.py -- T1-9: the vocab.column_dictionary curated-FACTS door in
layer1b/basket/describe.py (seed db/seed_column_dictionary.sql).

Contract under test:
  (a) DEFAULT PARITY -- with the dictionary absent/empty ({}), describe()/kind()/unit() are byte-identical to the
      pre-dictionary convention. The PINNED matrix below was produced by RUNNING the pre-edit functions on
      2026-07-14 (event flag / _kwh suffix / voltage_ prefix / thd_ prefix / unknown column) -- the door must
      not move a byte when no row is curated.
  (b) OVERRIDE -- a curated entry rebinds one column's kind+unit+label VERBATIM (lookup is lowercase; the label
      dedup knob never blanks a curated label); every other column still follows the convention. An entry that
      declares only SOME fields overrides those and falls through per-field for the rest.
  (c) FAIL-OPEN -- a malformed row (list/string/number) or a raising cfg() -> {} -> pure convention.
"""
import pytest

import layer1b.basket.describe as D


def _cfg(overrides):
    """A cfg(key, default) stand-in: curated overrides, else the caller's code default (absent-row semantics)."""
    return lambda key, default: overrides.get(key, default)


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    # default lane: no DB rows at all -> cfg serves code defaults (column_dictionary None -> {}, label_dedup True)
    monkeypatch.setattr(D, "cfg", _cfg({}))


# ---------------------------------------------------------------------------------------------------------------
# PINNED pre-edit outputs: [label, kind, unit] from describe() as the code behaved BEFORE the dictionary door
# (captured 2026-07-14 by calling the then-current functions). kind()/unit() are positions 1/2 of the same triple.
PINNED = {
    "sag_event_active":               ["", "event", ""],     # event flag rule (EVENT_NAME_PATTERN): no unit
    "current_imbalance_event_active": ["", "event", ""],     # the hardening-doc example flag (was mislabeled 'A')
    "active_energy_kwh":              ["", "raw", "kWh"],    # _kwh suffix
    "voltage_ln_avg":                 ["", "raw", "V"],      # voltage_ prefix
    "thd_current_r":                  ["", "raw", "%"],      # thd_ prefix
    "thd_voltage_r_pct":              ["", "derived", "%"],  # _pct suffix (unit) + _DERIVED pattern (kind)
    "frobnicator_flux":               ["", "raw", ""],       # unknown column -> dimensionless raw
}


def test_default_empty_dict_parity():
    # (a) no curated row: every function equals its pinned pre-edit output, column by column
    assert D._column_dictionary() == {}
    for col, want in PINNED.items():
        assert D.describe(col) == want, col
        assert D.kind(col) == want[1], col
        assert D.unit(col) == want[2], col


def test_explicit_empty_row_parity(monkeypatch):
    # (a) the seed's literal default value '{}' parsed to an empty dict behaves exactly like no row
    monkeypatch.setattr(D, "cfg", _cfg({"vocab.column_dictionary": {}}))
    assert D._column_dictionary() == {}
    for col, want in PINNED.items():
        assert D.describe(col) == want, col


def test_override_rebinds_kind_unit_label(monkeypatch):
    # (b) one curated row rebinds thd_current_r wholesale: convention said raw/%/'' -- FACTS say derived/A/label
    row = {"thd_current_r": {"kind": "derived", "unit": "A", "label": "THD Current (R phase)"}}
    monkeypatch.setattr(D, "cfg", _cfg({"vocab.column_dictionary": row}))
    assert D.kind("thd_current_r") == "derived"
    assert D.unit("thd_current_r") == "A"
    # curated label is emitted VERBATIM even though label_dedup defaults on (it differs by intent)
    assert D.describe("thd_current_r") == ["THD Current (R phase)", "derived", "A"]
    # lookup is lowercase-keyed: a mixed-case caller hits the same entry
    assert D.describe("THD_Current_R") == ["THD Current (R phase)", "derived", "A"]
    # every OTHER column still follows the convention untouched
    for col, want in PINNED.items():
        if col != "thd_current_r":
            assert D.describe(col) == want, col


def test_partial_entry_falls_through_per_field(monkeypatch):
    # (b) an entry declaring ONLY a unit overrides the unit; kind and label still come from the convention
    row = {"voltage_ln_avg": {"unit": "kV"}}
    monkeypatch.setattr(D, "cfg", _cfg({"vocab.column_dictionary": row}))
    assert D.unit("voltage_ln_avg") == "kV"
    assert D.kind("voltage_ln_avg") == PINNED["voltage_ln_avg"][1]     # 'raw' -- convention
    assert D.describe("voltage_ln_avg") == ["", "raw", "kV"]           # label still dedup-blanked


def test_malformed_row_falls_back_to_convention(monkeypatch):
    # (c) list / string / number where a dict belongs -> {} -> pinned convention outputs, no raise
    for bad in (["thd_current_r", "derived"], "thd_current_r=derived", 42, True):
        monkeypatch.setattr(D, "cfg", _cfg({"vocab.column_dictionary": bad}))
        assert D._column_dictionary() == {}
        for col, want in PINNED.items():
            assert D.describe(col) == want, (bad, col)


def test_cfg_raising_falls_back(monkeypatch):
    # (c) a raising reader (DB wedge mid-call) is swallowed by the guarded try/except -> {} -> convention
    def boom(key, default):
        raise RuntimeError("db down")
    monkeypatch.setattr(D, "cfg", boom)
    assert D._column_dictionary() == {}
    assert D.kind("voltage_ln_avg") == "raw"
    assert D.unit("voltage_ln_avg") == "V"
