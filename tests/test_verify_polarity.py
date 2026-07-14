"""tests/test_verify_polarity.py -- unit tests for the energy-POLARITY guard in ems_exec/executor/verify.py.

Covers the T1-1 fact-first slot classification: a field carrying an emit-declared quantity CLASS (stamped by
layer2/emit/slot_catalog.py) reads its polarity from the registry prefix convention via _quantity_polarity BEFORE any
substring scan, so 'active-energy-mvah' classifies ACTIVE instead of the apparent its embedded 'mvah' fragment
token-matches. Quantity-less fields keep the substring fallback byte-for-byte (parity cases mirror
tests/test_page13_dg_cert_defects.py::test_polarity_classifier and ::test_card72_energy_alias_polarity_families_classified).

All offline -- pure classifier reads, no DB.
"""
from __future__ import annotations

from ems_exec.executor.verify import (_fn_output_polarity, _polarity_conflict, _polarity_of_token,
                                      _quantity_polarity)


# === _quantity_polarity: the registry-prefix-convention fact table ==================================================
def test_quantity_polarity_table():
    # classified: q == pol or q.startswith(pol + '-')
    assert _quantity_polarity("active-energy-mvah") == "active"
    assert _quantity_polarity("active-energy-kwh") == "active"
    assert _quantity_polarity("reactive-energy-mvarh") == "reactive"
    assert _quantity_polarity("reactive-energy-kvarh") == "reactive"
    assert _quantity_polarity("apparent-energy-mvah") == "apparent"
    assert _quantity_polarity("apparent-energy-kvah") == "apparent"
    # bare polarity words classify by exact equality
    assert _quantity_polarity("active") == "active"
    assert _quantity_polarity("reactive") == "reactive"
    assert _quantity_polarity("apparent") == "apparent"
    # unclassified: no polarity prefix -> None (never a guess)
    assert _quantity_polarity("energy") is None
    assert _quantity_polarity("power") is None
    assert _quantity_polarity(None) is None
    assert _quantity_polarity("") is None
    assert _quantity_polarity("load-factor-percent") is None
    assert _quantity_polarity("nominal-voltage") is None
    # mid-string polarity is NOT a prefix -> None here (the substring fallback covers it in _polarity_conflict)
    assert _quantity_polarity("peak-apparent-power-kva") is None
    # a prefix must be the whole first dash-segment: 'activefoo' is not 'active-'
    assert _quantity_polarity("activefoo-kwh") is None


# === THE FIX CASE: an emit-declared active-energy quantity never token-scans apparent ===============================
def test_fix_active_energy_mvah_quantity_no_false_conflict_with_active_fn():
    # activeEnergyMvah is a REAL registry fn classified 'active-energy-mvah' (registry._QUANTITY) -- assert the fact
    from ems_exec.derivations import registry as _reg
    assert _reg._QUANTITY.get("activeEnergyMvah") == "active-energy-mvah"
    assert _fn_output_polarity("activeEnergyMvah") == "active"
    # today's substring path alone WOULD call the quantity string apparent ('mvah' needle beats the active prefix)...
    assert _polarity_of_token("active-energy-mvah") == "apparent"
    # ...but the fact-first slot side reads the registry prefix convention -> active == active -> NO conflict
    assert _polarity_conflict({"quantity": "active-energy-mvah"}, "activeEnergyMvah") is False
    # same field against the OTHER active-energy fn family (different quantity string, same polarity) -> no conflict
    assert _reg._QUANTITY.get("windowEnergyKwh") == "active-energy-kwh"
    assert _polarity_conflict({"quantity": "active-energy-mvah"}, "windowEnergyKwh") is False
    # a GENUINE cross-polarity mis-bind on a quantity-carrying field is still refused
    assert _polarity_conflict({"quantity": "reactive-energy-mvarh"}, "activeEnergyMvah") is True
    assert _polarity_conflict({"quantity": "apparent-energy-mvah"}, "windowEnergyKwh") is True


def test_quantity_fallback_blob_keeps_mid_string_polarity():
    # 'peak-apparent-power-kva' has NO classifying prefix (fact side None) but its polarity token still rides the
    # substring fallback because field['quantity'] stays in the blob
    assert _quantity_polarity("peak-apparent-power-kva") is None
    assert _polarity_conflict({"quantity": "peak-apparent-power-kva"}, "windowEnergyKwh") is True
    assert _polarity_conflict({"quantity": "peak-apparent-power-kva"}, "cumulativeApparentMvah") is False


# === parity: quantity-less fields behave exactly as the page13 cert expectations ====================================
def test_parity_polarity_classifier_page13():
    # mirrors test_page13_dg_cert_defects.py::test_polarity_classifier
    assert _polarity_of_token("MVARh", "Reactive") == "reactive"
    assert _polarity_of_token("MWh", "Active") == "active"
    assert _polarity_of_token("kVAh", "Apparent") == "apparent"
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive"}, "windowEnergyKwh") is True
    assert _polarity_conflict({"unit": "MWh", "label": "Active"}, "windowEnergyKwh") is False
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive"}, "reactiveEnergyMvarh") is False
    # unknown polarity on either side never fabricates a blank
    assert _polarity_conflict({"unit": "V"}, "windowEnergyKwh") is False


def test_parity_card72_alias_families_page13():
    # mirrors test_page13_dg_cert_defects.py::test_card72_energy_alias_polarity_families_classified
    assert _fn_output_polarity("active_mwh") == "active"
    assert _fn_output_polarity("reactive_mvarh") == "reactive"
    assert _fn_output_polarity("apparent_mvah") == "apparent"
    assert _polarity_conflict({"unit": "MWh", "label": "Active", "metric": "active_mwh"}, "active_mwh") is False
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive", "metric": "reactive_mvarh"},
                              "reactive_mvarh") is False
    assert _polarity_conflict({"unit": "MVAh", "label": "Apparent", "metric": "apparent_mvah"},
                              "apparent_mvah") is False
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive"}, "active_mwh") is True


# === _fn_output_polarity: unchanged behavior on real registry fns of each polarity ==================================
def test_fn_output_polarity_real_registry_fns():
    from ems_exec.derivations import registry as _reg
    # one REAL registry fn per polarity (assert membership so a registry rename fails loudly here, not silently)
    for fn, quantity, pol in (("windowEnergyKwh", "active-energy-kwh", "active"),
                              ("activeEnergyMvah", "active-energy-mvah", "active"),
                              ("reactiveEnergyMvarh", "reactive-energy-mvarh", "reactive"),
                              ("cumulativeApparentMvah", "apparent-energy-mvah", "apparent")):
        assert _reg._QUANTITY.get(fn) == quantity
        assert _fn_output_polarity(fn) == pol
    # a classified fn whose family carries NO polarity -> None
    assert _reg._QUANTITY.get("loadFactorPct") == "load-factor-percent"
    assert _fn_output_polarity("loadFactorPct") is None
    # unclassified / absent fn keys -> None (never a guess)
    assert _fn_output_polarity("noSuchFnKey") is None
    assert _fn_output_polarity(None) is None
    assert _fn_output_polarity("") is None
