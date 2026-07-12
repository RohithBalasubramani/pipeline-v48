"""ems_exec/executor/energy_registers.py — the ENERGY-REGISTER pick_mover: the reversed-CT cumulative-register
convention (import↔export pair map + windowed/bucketed delta selection) [monoliths F7, 2026-07-12].

Moved out of members.py: the register-pair map + mover selection is a DATASET convention, not a panel-membership
concern — the SINGLE-METER fill path (fill.py) and bindings.py consumed it by reaching into the panel fan-out module.
members.py re-exports every symbol byte-compatibly. The invariant these functions carry: ANY windowed energy delta on
a paired import register reads BOTH registers and picks the mover (derivations.energy.member_energy_delta), so the
per-member leaves, the entries reducers, the trend buckets and the panel Σ can never contradict each other (the
cards-12/13/14/16 false-zero / 79670-vs-93771 self-contradiction). [atomic; DB-driven pair map; honest-null]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from ems_exec.renderers import _agg


def _delta_of(pair):
    """The clamped (end−start)≥0 delta of one member's (start,end) counter pair, or None (missing baseline / empty)."""
    if pair is None:
        return None
    return _agg.windowed_delta([pair])


def _export_col():
    """The configured EXPORT energy register for reversed-CT panel roll-ups (roster.energy_export_column). None when
    unset → panel_kwh degrades to the legacy import-only Σ (backward compatible)."""
    try:
        from config.app_config import cfg
        v = cfg("roster.energy_export_column", "active_energy_export_kwh")
        return v or None
    except Exception:
        return "active_energy_export_kwh"


def register_pairs():
    """The IMPORT→EXPORT cumulative-register pair map for reversed-CT pick_mover reads (app_config
    roster.energy_register_pairs; the active pair's export side defaults to roster.energy_export_column). ANY windowed
    energy delta on a paired import register must read BOTH registers and pick the mover — the roster `delta` binding
    and the bucketed `energy_delta` fold reuse THIS one map, so the per-member leaves, the entries reducers and the
    panel Σ (panel_kwh) can never contradict each other again (the cards-12/13/14/16 false-zero / 79670-vs-93771
    self-contradiction). Editable row; code default = the two neuract energy counter pairs."""
    default = {
        "active_energy_import_kwh": "active_energy_export_kwh",
        "reactive_energy_import_kvarh": "reactive_energy_export_kvarh",
    }
    try:
        from config.app_config import cfg
        pairs = cfg("roster.energy_register_pairs", default)
        pairs = pairs if isinstance(pairs, dict) and pairs else default
        energy_col = cfg("roster.energy_column", "active_energy_import_kwh")
    except Exception:
        pairs, energy_col = default, "active_energy_import_kwh"
    out = {}
    for imp, exp in pairs.items():
        if imp == energy_col:
            exp = _export_col()          # the legacy roster.energy_export_column knob stays the ACTIVE pair's valve:
        if exp:                          # unset → that pair drops → legacy import-only Σ (backward compatible)
            out[imp] = exp
    return out


def member_delta(member, window, col, ndigits=1):
    """ONE member's windowed counter delta for `col`. None when the column is absent / the table is empty / the window
    has no rows (honest-null, never a fabricated 0).

    PICK_MOVER (reversed-CT unification, cards 12/13/14/16): when `col` is a paired energy import register
    (register_pairs), the member's delta is read from BOTH the import and the export register and the MOVER wins
    (energy.member_energy_delta — a reversed-CT feeder keeps its real kWh on export while import stays flat ~0). This
    is the SAME selection panel_kwh already applies, so a roster `delta` element leaf can never render 0.0 while the
    panel Σ carries that member's real export energy. An unpaired column keeps the legacy single-register delta."""
    export_col = register_pairs().get(col)
    if export_col:
        imp = _delta_of(member_delta_pair(member, window, col))
        exp = _delta_of(member_delta_pair(member, window, export_col))
        from ems_exec.derivations import energy as _energy
        picked = _energy.member_energy_delta(imp, exp)
        if picked is None:
            return None
        return round(picked, ndigits) if ndigits is not None else picked
    pair = member_delta_pair(member, window, col)
    if pair is None:
        return None
    return _agg.windowed_delta([pair], ndigits=ndigits)


def _bucketed_energy_delta(tbl, col, window, sampling):
    """ONE member's per-bucket windowed energy delta [{t, value}] with the reversed-CT pick_mover applied PER BUCKET:
    when `col` is a paired import register (register_pairs), both the import and the export register are bucket-deltaed
    and each bucket keeps whichever register MOVED (energy.member_energy_delta — larger |delta| wins, abs magnitude).
    A bucket where neither register moved keeps the flat register's honest 0.0/None; an unpaired column reads the
    single register (legacy). This is the same selection member_delta/panel_kwh apply to the scalar leaves, so a trend
    bucket can never show 0 kWh for a feeder whose export register moved (card-16 UPS false-zero)."""
    start, end = (window or (None, None))
    imp_pts = _nx.bucketed_delta(tbl, col, start, end, sampling=sampling)
    export_col = register_pairs().get(col)
    if not export_col:
        return imp_pts
    exp_pts = _nx.bucketed_delta(tbl, export_col, start, end, sampling=sampling)
    if not exp_pts:
        return imp_pts
    from ems_exec.derivations import energy as _energy
    by_t = {pt.get("t"): pt.get("value") for pt in imp_pts}
    out_t = list(dict.fromkeys([pt.get("t") for pt in imp_pts] + [pt.get("t") for pt in exp_pts]))
    exp_by_t = {pt.get("t"): pt.get("value") for pt in exp_pts}
    out = []
    for t in sorted(x for x in out_t if x is not None):
        out.append({"t": t, "value": _energy.member_energy_delta(by_t.get(t), exp_by_t.get(t))})
    return out


def member_delta_pair(member, window, col):
    """The (baseline, close) counter pair for one member over the window, or None (no table / column / rows)."""
    tbl = member.get("table")
    if not tbl or not col:
        return None
    try:
        if col not in _nx.present_columns(tbl):
            return None
        start, end = (window or (None, None))
        first, last = _nx.window(tbl, [col], start, end)
        return (first.get(col), last.get(col))
    except Exception:
        return None
