"""tests/test_derivation_alias.py — derivation-key normalize + alias resolution (audit 2026-07-14, 14 F1).

Emit invents free-form derivation keys (camelCase/snake_case/kebab, unit-suffixed variants); ~56% of
derivation_unbound named a computable quantity. binding() now resolves: exact > normalized fold (case/-/_/pct
folded; MAGNITUDE unit tokens deliberately KEPT — folding kvarh onto an MVARh fn would be a silent ×1000
mismatch; unique-hit only) > the curated derivation_alias table. A miss everywhere stays the honest
derivation_unbound. Alias rows must never cross polarity (property-checked against registry._QUANTITY)."""
from __future__ import annotations

import pytest

import config.derivation_binding as DB


def _fake_rows(metrics):
    def fake_q(db, sql):
        if "FROM derivation_binding WHERE metric=" in sql:
            m = sql.split("metric='")[1].split("'")[0]
            if m in metrics:
                return [[m, metrics[m], "col_a,col_b", "real_exact", "row"]]
            return []
        if "SELECT metric FROM derivation_binding" in sql:
            return [[m] for m in metrics]
        if "FROM derivation_alias WHERE alias=" in sql:
            a = sql.split("alias='")[1].split("'")[0]
            return [["totalKwh"]] if a == "totalenergykwh" else []
        raise AssertionError(sql)
    return fake_q


@pytest.fixture(autouse=True)
def _fresh_cache():
    DB._norm_cache.clear()
    yield
    DB._norm_cache.clear()


def test_exact_match_unchanged(monkeypatch):
    monkeypatch.setattr(DB, "q", _fake_rows({"windowEnergyKwh": "window_energy_kwh"}))
    b = DB.binding("windowEnergyKwh")
    assert b and b["fn"] == "window_energy_kwh"


def test_normalized_fold_resolves_spelling_variants(monkeypatch):
    monkeypatch.setattr(DB, "q", _fake_rows({"lossPct": "loss_pct", "windowEnergyKwh": "window_energy_kwh"}))
    assert DB.binding("loss-pct")["fn"] == "loss_pct"            # kebab + pct fold
    assert DB.binding("window_energy_kwh")["fn"] == "window_energy_kwh"   # snake fold, unit KEPT in both sides


def test_ambiguous_fold_stays_unbound(monkeypatch):
    # two rows folding identically (loadFactorPct / load-factor-percent) — never guess between them
    monkeypatch.setattr(DB, "q", _fake_rows({"loadFactorPct": "a", "load-factor-percent": "b"}))
    assert DB.binding("load_factor") is None


def test_unit_magnitude_never_folds(monkeypatch):
    # reactiveEnergyKvarh must NOT resolve to an MVARh row via the fold (×1000 mismatch)
    monkeypatch.setattr(DB, "q", _fake_rows({"reactiveEnergyMvarh": "mvah_reactive"}))
    assert DB.binding("reactiveEnergyKvarh") is None


def test_alias_table_resolves_curated_pairs(monkeypatch):
    monkeypatch.setattr(DB, "q", _fake_rows({"totalKwh": "window_energy_kwh"}))
    b = DB.binding("totalEnergyKwh")                             # normalized 'totalenergykwh' → alias row → totalKwh
    assert b and b["fn"] == "window_energy_kwh"


def test_unknown_key_stays_honest_none(monkeypatch):
    monkeypatch.setattr(DB, "q", _fake_rows({"totalKwh": "x"}))
    assert DB.binding("hotspotAgingFactor") is None


def test_seeded_aliases_never_cross_polarity():
    """Property over the SEED FILE rows: an alias's implied polarity (from its own name tokens) must match the
    target metric's registry polarity — the never-alias-across-quantities rule, pinned at the source."""
    import os
    import re
    from ems_exec.derivations import registry as R
    from ems_exec.executor.verify import _quantity_polarity, _polarity_of_token
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sql = open(os.path.join(root, "db", "seed_derivation_alias.sql")).read()
    pairs = re.findall(r"\('([a-z0-9]+)',\s*'([A-Za-z0-9_-]+)'", sql)
    assert len(pairs) >= 10
    for alias, metric in pairs:
        target_pol = _quantity_polarity(R._QUANTITY.get(metric))
        alias_pol = _polarity_of_token(alias)
        if alias_pol and target_pol:
            assert alias_pol == target_pol, f"alias {alias!r} ({alias_pol}) crosses polarity to {metric!r} ({target_pol})"
