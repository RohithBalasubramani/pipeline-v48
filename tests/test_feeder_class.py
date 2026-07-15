"""tests/test_feeder_class.py — the FEEDER-CLASS fact (T2.1-3): the PURE token derivation, the fail-open accessor,
the members.resolve stamp, and the feeder_classes any-of match key across the THREE matchers. All offline (no live DB /
LLM / host): the derivation is pure; the accessor + the matchers run over synthetic rows with data.db_client.q and the
feeder_class_of door monkeypatched.

Everything ADDITIVE + INERT — no recipe declares feeder_classes yet, so the whole suite stays byte-identical. These
tests characterize the new fact so a future recipe can key on it with a proven contract.
"""
from __future__ import annotations

import pytest

from scripts.seed_feeder_class import derive_feeder_class
import data.registry.feeder_class as FC
from ems_exec.executor.members import _spec_match
from ems_exec.executor.roster_modes_series import _member_match
from ems_exec.executor.roster_modes_groups import _match_def


# =====================================================================================================================
#  derive_feeder_class  — the PURE, importable token derivation (priority-ordered, token-exact)
# =====================================================================================================================
@pytest.mark.parametrize("name, expected", [
    ("gic-01-n3-ups-01 cl600kva", "ups"),
    ("gic-01-n8-bpdb-01 for lamination", "bpdb"),
    ("gic-04-n3-bpdp-03", "bpdb"),                       # 'bpdp' misspelling folds to the same 'bpdb' class
    ("gic-01-n10-hhf-01 type-01", "hhf"),
    ("gic-01-n9-solar incomer-1", "solar-incomer"),      # solar+incomer PAIR → its own class
    ("solar incomer", "solar-incomer"),                  # PAIR wins over the bare 'incomer' rule
    ("gic-05-n2-incomer-2", "incomer"),                  # plain incomer (no solar)
    ("gic-01-n1-spare", "spare"),
    ("dg-1 mfm", "dg"),
    ("gic-03-n6-ahu-5", "ahu"),
    ("APFCR panels", "apfcr"),
    ("apfc panel 2", "apfcr"),                           # 'apfc' also folds to 'apfcr'
    ("gic-02-n4-transformer-1", None),                   # unclassified → None (a human adds the row)
    ("", None),
    (None, None),
])
def test_derive_feeder_class(name, expected):
    assert derive_feeder_class(name) == expected


def test_derive_token_exact_no_substring_pun():
    """token-EXACT: 'upstream' must NOT classify as 'ups' (the token is 'upstream', not 'ups')."""
    assert derive_feeder_class("gic-01-n3-upstream-panel") is None


# =====================================================================================================================
#  feeder_class_of  — the fail-open accessor (data/equipment/sections.py pattern)
# =====================================================================================================================
@pytest.fixture(autouse=True)
def _clean_cache():
    FC._CACHE.clear()
    yield
    FC._CACHE.clear()


def _pin_map(monkeypatch, rows):
    """Pin registry_feeder_class: q('cmd_catalog', sql) yields (table_name, feeder_class) rows."""
    import data.db_client as DB
    monkeypatch.setattr(DB, "q", lambda db, sql: list(rows))
    FC._CACHE.clear()


def test_feeder_class_of_reads_and_lowercases(monkeypatch):
    _pin_map(monkeypatch, [("gic_01_n3", "UPS"), ("gic_01_n8", "bpdb")])
    assert FC.feeder_class_of("gic_01_n3") == "ups"      # lower-cased on read
    assert FC.feeder_class_of("gic_01_n8") == "bpdb"
    assert FC.feeder_class_of("nope") is None
    assert FC.feeder_class_of("") is None
    assert FC.feeder_class_of(None) is None


def test_feeder_class_of_caches_after_full_read(monkeypatch):
    _pin_map(monkeypatch, [("gic_01_n3", "ups")])
    assert FC.feeder_class_of("gic_01_n3") == "ups"
    assert FC._CACHE.get("map") == {"gic_01_n3": "ups"}  # published only after the full read


def test_feeder_class_of_fail_open_never_caches(monkeypatch):
    """q raises → the accessor returns None (honest, not a crash) and NEVER caches a partial/empty map (self-heals)."""
    import data.db_client as DB

    def _boom(db, sql):
        raise RuntimeError("feeder door dark")

    monkeypatch.setattr(DB, "q", _boom)
    FC._CACHE.clear()
    assert FC.feeder_class_of("gic_01_n3") is None
    assert FC._CACHE.get("map") is None                  # uncached on failure → next call retries


# =====================================================================================================================
#  members.resolve  — stamps feeder_class beside section (monkeypatch feeder_class_of + the neuract edges)
# =====================================================================================================================
def test_resolve_stamps_feeder_class(monkeypatch):
    from data.neuract_live import members as NLM
    import data.equipment.sections as SE
    from ems_exec.executor import members as M

    monkeypatch.setattr(NLM, "outgoers_of",
                        lambda mid: [{"mfm_id": 1, "name": "gic-01-n3-ups-01",
                                      "neuract_table": "gic_01_n3", "role": "outgoing"}])
    monkeypatch.setattr(NLM, "incomers_of", lambda mid: [])
    monkeypatch.setattr(FC, "feeder_class_of", lambda t: "ups" if t == "gic_01_n3" else None)
    monkeypatch.setattr(SE, "section_of", lambda t: None)          # hermetic: no equipment DB read

    members, _cov = M.resolve(999)
    assert len(members) == 1
    assert members[0]["table"] == "gic_01_n3"
    assert members[0]["feeder_class"] == "ups"


def test_resolve_stamps_none_when_unmapped(monkeypatch):
    from data.neuract_live import members as NLM
    import data.equipment.sections as SE
    from ems_exec.executor import members as M

    monkeypatch.setattr(NLM, "outgoers_of",
                        lambda mid: [{"mfm_id": 2, "name": "gic-02-n4-transformer",
                                      "neuract_table": "gic_02_n4", "role": "outgoing"}])
    monkeypatch.setattr(NLM, "incomers_of", lambda mid: [])
    monkeypatch.setattr(FC, "feeder_class_of", lambda t: None)     # unmapped meter → None (honest)
    monkeypatch.setattr(SE, "section_of", lambda t: None)

    members, _cov = M.resolve(999)
    assert len(members) == 1
    assert members[0]["feeder_class"] is None


# =====================================================================================================================
#  the feeder_classes MATCH KEY across the three matchers (any-of, case-insensitive)
# =====================================================================================================================
def _m(name="m", table=None, type=None, load_group=None, feeder_class=None, role=None):
    return {"name": name, "table": table, "type": type, "load_group": load_group,
            "feeder_class": feeder_class, "role": role}


# -- members._spec_match ------------------------------------------------------------------------------------------
def test_spec_match_feeder_classes_any_of():
    assert _spec_match(_m(feeder_class="ups"), {"feeder_classes": ["UPS"]}) is True   # case-insensitive
    assert _spec_match(_m(feeder_class="bpdb"), {"feeder_classes": ["ups", "bpdb"]}) is True
    assert _spec_match(_m(feeder_class="ups"), {"feeder_classes": ["bpdb"]}) is False


def test_spec_match_feeder_class_none_no_match():
    assert _spec_match(_m(feeder_class=None), {"feeder_classes": ["ups"]}) is False


def test_spec_match_no_key_contract_preserved():
    """A match dict with NO feeder_classes key is unaffected; None/{} still match EVERY member (spec fleet default)."""
    assert _spec_match(_m(feeder_class="ups"), {"types": ["transformer"]}) is False   # feeder_classes absent → no fire
    assert _spec_match(_m(feeder_class="ups"), None) is True
    assert _spec_match(_m(feeder_class="ups"), {}) is True


# -- roster_modes_series._member_match ----------------------------------------------------------------------------
def test_member_match_feeder_classes_any_of():
    assert _member_match(_m(feeder_class="ups"), {"feeder_classes": ["UPS"]}) is True
    assert _member_match(_m(feeder_class="ups"), {"feeder_classes": ["bpdb"]}) is False


def test_member_match_feeder_class_none_no_match():
    assert _member_match(_m(feeder_class=None), {"feeder_classes": ["ups"]}) is False


def test_member_match_no_key_contract_preserved():
    """The series side selects NOTHING with no valid selector; a feeder_classes-less dict never fires the new leg."""
    assert _member_match(_m(feeder_class="ups"), {"types": ["transformer"]}) is False
    assert _member_match(_m(feeder_class="ups"), {}) is False
    assert _member_match(_m(feeder_class="ups"), None) is False


# -- roster_modes_groups._match_def -------------------------------------------------------------------------------
def test_match_def_feeder_classes_any_of():
    defs = [{"id": "g_ups", "feeder_classes": ["ups"]}, {"id": "g_bpdb", "feeder_classes": ["bpdb"]}]
    assert _match_def(_m(feeder_class="ups"), defs)["id"] == "g_ups"
    assert _match_def(_m(feeder_class="BPDB"), defs)["id"] == "g_bpdb"   # case-insensitive


def test_match_def_feeder_class_none_returns_none():
    defs = [{"id": "g_ups", "feeder_classes": ["ups"]}]
    assert _match_def(_m(feeder_class=None), defs) is None               # no fact → member derives its own section


def test_match_def_no_feeder_classes_key_unaffected():
    """A def with no feeder_classes key never matches on the new leg; the role/type/load_group legs are untouched."""
    defs = [{"id": "g_role", "roles": ["incoming"]}]
    assert _match_def(_m(feeder_class="ups", role="outgoing"), defs) is None
    assert _match_def(_m(feeder_class="ups", role="incoming"), defs)["id"] == "g_role"
