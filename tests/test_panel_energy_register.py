"""tests/test_panel_energy_register.py — SEAM 1: reversed-CT-aware panel energy roll-up + load factor from the rolled
power series. PURE unit tests (no DB, no live data — the neuract reader is monkeypatched).

The panel-aggregate energy roll-up used to sum ONE register (active_energy_import_kwh) per member. A member wired
reversed-CT keeps its real energy on the EXPORT register (import delta flat ~0 — the 3 GIC UPS feeders read import=0
while active_energy_export_kwh moves ~4700 kWh); a forward member (bpdb-01) uses import. The fix reads BOTH registers
per member and picks the one that moved (energy.member_energy_delta → _pick_register), abs()'d for a positive kWh. A
genuinely dark feeder (neither register moves) stays None (honest-blank, never a fabricated 0). Load factor comes from
the member-ROLLED power series (the panel's own bus device has no electrical series), not the empty single meter."""
from __future__ import annotations

from ems_exec.derivations import energy as E
from ems_exec.derivations import power as P
from ems_exec.executor import members as M
from ems_exec.renderers import panel_aggregate as PA


# ── (1) the shared register selector — pick the mover, abs magnitude, honest-None ───────────────────────────────────
def test_member_energy_delta_reversed_ct_picks_export():
    # reversed-CT feeder: import flat (0), export moved (4705) → the real energy is the export magnitude.
    assert E.member_energy_delta(0.0, 4705.0) == 4705.0


def test_member_energy_delta_forward_feeder_picks_import():
    # forward feeder (bpdb-01): import moved (78850), export flat (0) → import.
    assert E.member_energy_delta(78850.0, 0.0) == 78850.0


def test_member_energy_delta_export_positive_magnitude():
    # the export register is a positive cumulative counter; its (end−start) delta is positive → shown as-is.
    assert E.member_energy_delta(0.0, 4705.0) == 4705.0


def test_member_energy_delta_negative_delta_clamps_to_zero():
    # a NEGATIVE delta is a counter reset, not real consumption — clamped ≥ 0 (honest, never a fabricated negative kWh).
    assert E.member_energy_delta(0.0, -4705.0) == 0.0


def test_member_energy_delta_dark_feeder_is_none():
    # neither register moved / both absent → honest None, never a fabricated 0.
    assert E.member_energy_delta(None, None) is None


def test_member_energy_delta_single_register_present():
    # only import present (no export register on the table) → import.
    assert E.member_energy_delta(500.0, None) == 500.0


# ── (2) the ROSTER panel roll-up (members.panel_kwh) — reversed-CT aware, per feeder ────────────────────────────────
def _windowed(tables):
    """Monkeypatch shims: present_columns + window() over a fixture {table: {col: (start, end)}}."""
    def present(tbl):
        return set((tables.get(tbl) or {}).keys())

    def window(tbl, cols, start, end):
        row = tables.get(tbl) or {}
        first = {c: (row[c][0] if c in row else None) for c in cols}
        last = {c: (row[c][1] if c in row else None) for c in cols}
        return first, last
    return present, window


def test_roster_panel_kwh_rolls_up_export_for_reversed_ct(monkeypatch):
    _IMP, _EXP = "active_energy_import_kwh", "active_energy_export_kwh"
    tables = {
        # 3 reversed-CT UPS feeders: import flat, export moves ~4705/4716/4719
        "ups1": {_IMP: (100.0, 100.0), _EXP: (0.0, 4705.0)},
        "ups2": {_IMP: (50.0, 50.0), _EXP: (10.0, 4726.0)},
        "ups3": {_IMP: (0.0, 0.0), _EXP: (0.0, 4719.0)},
        # forward feeder (bpdb-01): import moves, export flat
        "bpdb": {_IMP: (1000.0, 79850.0), _EXP: (0.0, 0.0)},
        # genuinely dark feeder: neither register on the table → contributes nothing
        "dark": {},
    }
    present, window = _windowed(tables)
    monkeypatch.setattr(M._nx, "present_columns", present)
    monkeypatch.setattr(M._nx, "window", window)
    monkeypatch.setattr(M, "_export_col", lambda: _EXP)          # config knob → export register wired
    pairs = [
        ({"mfm_id": 1, "table": "ups1", "role": "outgoing"}, {}),
        ({"mfm_id": 2, "table": "ups2", "role": "outgoing"}, {}),
        ({"mfm_id": 3, "table": "ups3", "role": "outgoing"}, {}),
        ({"mfm_id": 4, "table": "bpdb", "role": "outgoing"}, {}),
        ({"mfm_id": 5, "table": "dark", "role": "outgoing"}, {}),
        ({"mfm_id": 6, "table": "ups1", "role": "incoming"}, {}),  # supply side — excluded (double-count guard)
    ]
    # BEFORE the fix this summed import-only = 78850 (the 3 UPS dropped). AFTER: 4705+4716+4719 + 78850 = 92990.
    assert M.panel_kwh(pairs, (None, None), _IMP) == 92990.0


def test_roster_panel_kwh_all_dark_is_none(monkeypatch):
    _IMP, _EXP = "active_energy_import_kwh", "active_energy_export_kwh"
    tables = {"a": {}, "b": {}}                                   # no register moves anywhere → honest None
    present, window = _windowed(tables)
    monkeypatch.setattr(M._nx, "present_columns", present)
    monkeypatch.setattr(M._nx, "window", window)
    monkeypatch.setattr(M, "_export_col", lambda: _EXP)
    pairs = [({"mfm_id": 1, "table": "a", "role": "outgoing"}, {}),
             ({"mfm_id": 2, "table": "b", "role": "outgoing"}, {})]
    assert M.panel_kwh(pairs, (None, None), _IMP) is None


def test_roster_panel_kwh_import_only_when_export_unconfigured(monkeypatch):
    # roster.energy_export_column unset → legacy import-only Σ (backward compatible), the UPS export is ignored.
    _IMP, _EXP = "active_energy_import_kwh", "active_energy_export_kwh"
    tables = {"ups1": {_IMP: (0.0, 0.0), _EXP: (0.0, 4705.0)},
              "bpdb": {_IMP: (1000.0, 2000.0), _EXP: (0.0, 0.0)}}
    present, window = _windowed(tables)
    monkeypatch.setattr(M._nx, "present_columns", present)
    monkeypatch.setattr(M._nx, "window", window)
    monkeypatch.setattr(M, "_export_col", lambda: None)          # no export register configured
    pairs = [({"mfm_id": 1, "table": "ups1", "role": "outgoing"}, {}),
             ({"mfm_id": 2, "table": "bpdb", "role": "outgoing"}, {})]
    assert M.panel_kwh(pairs, (None, None), _IMP) == 1000.0       # only bpdb's import delta


# ── (3) the RECIPE-LESS renderer roll-up (panel_aggregate._panel_energy_kwh) — same reversed-CT rule ────────────────
def test_recipe_less_panel_energy_kwh_reversed_ct(monkeypatch):
    _IMP, _EXP = PA._ENERGY, PA._ENERGY_EXPORT
    tables = {
        "ups1": {_IMP: (0.0, 0.0), _EXP: (0.0, 4705.0)},         # reversed-CT
        "bpdb": {_IMP: (0.0, 78850.0), _EXP: (0.0, 0.0)},        # forward
        "dark": {},                                              # empty feeder → None (honest-blank)
    }
    present, window = _windowed(tables)
    monkeypatch.setattr(PA._nx, "present_columns", present)
    monkeypatch.setattr(PA._nx, "window", window)
    monkeypatch.setattr(PA, "_ENERGY_POLICY", "pick_mover")
    member_rows = [
        ({"mfm_id": 1, "table": "ups1", "role": "outgoing"}, {}),
        ({"mfm_id": 2, "table": "bpdb", "role": "outgoing"}, {}),
        ({"mfm_id": 3, "table": "dark", "role": "outgoing"}, {}),
    ]
    assert PA._panel_energy_kwh(member_rows, (None, None)) == 83555.0   # 4705 (export) + 78850 (import); dark → excluded
    # the empty feeder alone stays None (never a fabricated 0)
    assert PA._member_energy_kwh({"mfm_id": 3, "table": "dark", "role": "outgoing"}, None, None) is None


def test_recipe_less_import_only_policy(monkeypatch):
    _IMP, _EXP = PA._ENERGY, PA._ENERGY_EXPORT
    tables = {"ups1": {_IMP: (0.0, 0.0), _EXP: (0.0, 4705.0)},
              "bpdb": {_IMP: (0.0, 300.0), _EXP: (0.0, 0.0)}}
    present, window = _windowed(tables)
    monkeypatch.setattr(PA._nx, "present_columns", present)
    monkeypatch.setattr(PA._nx, "window", window)
    monkeypatch.setattr(PA, "_ENERGY_POLICY", "import_only")     # config escape hatch → legacy behavior
    member_rows = [({"mfm_id": 1, "table": "ups1", "role": "outgoing"}, {}),
                   ({"mfm_id": 2, "table": "bpdb", "role": "outgoing"}, {})]
    assert PA._panel_energy_kwh(member_rows, (None, None)) == 300.0     # UPS export ignored under import_only


# ── (4) load factor from the member-ROLLED power series (not the empty panel bus device) ────────────────────────────
def test_load_factor_from_series_known_values():
    # mean(|values|)=100, peak=200 → LF = 100/200*100 = 50.0
    assert P.load_factor_from_series([100.0, 100.0, 200.0, 0.0]) == 50.0


def test_load_factor_from_series_points_shape():
    # a rolled [{t, value}] series — coerced to its |value| magnitudes.
    series = [{"t": "08:00", "value": 900.0}, {"t": "09:00", "value": 912.0}, {"t": "10:00", "value": 970.0}]
    lf = P.load_factor_from_series(series)
    # mean 927.333 / peak 970 * 100 ≈ 95.6
    assert lf == 95.6


def test_load_factor_from_series_reversed_ct_negative():
    # negative-logged (reversed-CT) power → magnitudes; mean 150 / peak 200 = 75.
    assert P.load_factor_from_series([-100.0, -200.0, -150.0]) == 75.0


def test_load_factor_from_empty_series_is_none():
    # no member reported power → honest None, never a fabricated load factor.
    assert P.load_factor_from_series([]) is None
    assert P.load_factor_from_series([None, "NaN"]) is None


def test_load_factor_pct_prefers_injected_rolled_series():
    # a panel-aggregate ctx injects the fleet-rolled power via ctx['rolled_power']; it takes precedence over the empty
    # single-meter series so the panel's load factor is the fleet trend's mean÷peak.
    ctx = {"rolled_power": [900.0, 912.0, 970.0], "series": []}
    assert P.load_factor_pct(ctx) == 95.6
