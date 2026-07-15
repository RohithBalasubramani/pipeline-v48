"""tests/test_polarity_substitute.py — energy-polarity fn substitution (audit 2026-07-14, 13 F2).

~55% of quantity_mismatch blanks were meters that DO log the slot's register — grounding bound the
wrong-POLARITY energy fn and the guard blanked real data. On a _polarity_conflict refusal, fill now substitutes
the EXPLICIT registry sibling (registry._POLARITY_SIBLINGS) of the slot's own polarity, base-columns-verified;
no sibling / knob off → today's honest blank. Substitution is explicit rows, never inferred (temporal variants
make generic matching ambiguous). Non-live."""
from __future__ import annotations

import pytest

from ems_exec.executor.verify import polarity_sibling_fn, _polarity_conflict


def _reactive_slot_field(fn="windowEnergyKwh"):
    # the audit's exact shape: an active-energy fn emitted onto a Reactive/MVARh slot
    return {"slot": "readings.reactiveEnergy.value", "kind": "derived", "fn": fn,
            "label": "Reactive Energy", "unit": "MVARh"}


def test_sibling_resolves_for_the_audit_shape(monkeypatch):
    import ems_exec.data.neuract as nx
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset({"reactive_energy_import_kvarh"}))
    f = _reactive_slot_field()
    assert _polarity_conflict(f, "windowEnergyKwh") is True     # the guard fires (precondition)
    assert polarity_sibling_fn(f, "windowEnergyKwh", "gic_ups") == "reactiveEnergyMvarh"


def test_sibling_refused_when_base_columns_absent(monkeypatch):
    import ems_exec.data.neuract as nx
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset({"active_energy_import_kwh"}))   # DG-class meter
    assert polarity_sibling_fn(_reactive_slot_field(), "windowEnergyKwh", "gic_dg") is None


def test_unmapped_fn_never_substitutes():
    f = dict(_reactive_slot_field(), fn="worstPhaseSpreadV")
    assert polarity_sibling_fn(f, "worstPhaseSpreadV", None) is None


def test_undisambiguated_slot_never_substitutes():
    f = {"slot": "readings.energy.value", "kind": "derived", "fn": "windowEnergyKwh",
         "label": "Energy", "unit": ""}                          # no polarity token anywhere
    assert polarity_sibling_fn(f, "windowEnergyKwh", None) is None


def test_fill_substitutes_and_notes(monkeypatch):
    import ems_exec.executor.fill as F
    import ems_exec.data.neuract as nx
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset({"reactive_energy_import_kvarh"}))
    ran, notes = [], []
    monkeypatch.setattr(F, "_run_derived", lambda fn, t, w: (ran.append(fn), (42.5, "fid"))[1])
    monkeypatch.setattr(F._degrade, "note", lambda k, e, **kw: notes.append((k, str(e))))
    monkeypatch.setattr("config.app_config.flag_on", lambda key, default=False, cfg_fn=None: True)
    v = F._field_value(_reactive_slot_field(), "gic_ups", frozenset(), latest_row={}, ratings={}, window=None)
    assert ran == ["reactiveEnergyMvarh"]                        # the sibling ran, not the mislabeled fn
    assert v == 42.5
    assert any(k == "polarity_substitute" for k, _ in notes)


def test_fill_knob_off_blanks_as_today(monkeypatch):
    import ems_exec.executor.fill as F
    ran = []
    monkeypatch.setattr(F, "_run_derived", lambda fn, t, w: (ran.append(fn), (42.5, "fid"))[1])
    monkeypatch.setattr("config.app_config.flag_on", lambda key, default=False, cfg_fn=None: False)
    v = F._field_value(_reactive_slot_field(), "gic_ups", frozenset(), latest_row={}, ratings={}, window=None)
    assert v is None and ran == []                               # pre-2026-07-15 behavior: honest blank
