"""ems_exec/executor/derived.py — derivation execution: a live-data superset ctx (latest row + window baselines +
nameplate:* pseudo-cols) run through the registry fn, plus the site-calendar/period-delta ctx builders. One concern;
fill.py re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from ems_exec.derivations import registry as _registry
from config import nameplates as _np
from config import derivation_binding as _deriv
from config import neuract_dsn as _dsn


# The reversed-CT power columns the energy-from-power ∫ fallback integrates when the cumulative kWh counters are dead.
# Kept HERE (not in the DB base_columns) so the counter leaf still GATES only on its real counter column (the caller's
# base_columns ⊆ present-columns check);
# the series read below merely ENRICHES ctx with power so the fn's own dead-counter fallback can fire. Generic — any
# window/series-scoped fn gets the power series for free; a fn that doesn't read them ignores the extra keys.
_INTEGRATION_POWER_COLS = ("active_power_total_kw", "reactive_power_total_kvar")

# The reversed-CT-aware windowed-energy fns (energy.active_energy_this_month_kwh / reactive_*/apparent_*) read
# ctx[<period>] = {active_import, active_export, reactive_import, reactive_export} — each a (end−start) counter delta
# over that period's sub-window (energy.py:_period_delta). Map each period register-key to its cumulative neuract
# counter COLUMN (the same columns the fns declare in derivation_binding.base_columns). Kept HERE (contract-local,
# next to the fn that consumes it) rather than hardcoded per-card. A meter missing a register → that key delta is
# None → _pick_register honest-blanks (never a fabricated 0).
_PERIOD_COUNTER_COLS = {
    "active_import":   "active_energy_import_kwh",
    "active_export":   "active_energy_export_kwh",
    "reactive_import": "reactive_energy_import_kvarh",
    "reactive_export": "reactive_energy_export_kvarh",
}


def _site_calendar_start(anchor, kind="day"):
    """The START instant of `anchor`'s current SITE-timezone calendar period ('day' | 'week' | 'month'), returned in
    `anchor`'s own tz. A tz-AWARE anchor is converted to config.windows.site_tz FIRST and the calendar arithmetic
    happens in that local wall clock (a UTC run-window end at 00:03Z is 05:33 IST — its site 'today' began at IST
    midnight, NOT 3 minutes ago: the 2026-07-06 card-18 event-count defect); a NAIVE anchor keeps the legacy local
    arithmetic (nothing to convert). Never raises (falls back to the naive midnight)."""
    from datetime import timedelta
    local, back = anchor, None
    try:
        if anchor.tzinfo is not None:
            from config.windows import site_tz
            local, back = anchor.astimezone(site_tz()), anchor.tzinfo
    except Exception:
        local, back = anchor, None
    d0 = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == "week":
        d0 -= timedelta(days=d0.weekday())
    elif kind == "month":
        d0 = d0.replace(day=1)
    try:
        return d0.astimezone(back) if back is not None else d0
    except Exception:
        return d0


def _period_starts(anchor):
    """The sub-window START instants (today / this_week / this_month) at/before the DATA anchor 'now'. `anchor` is a
    datetime (the run window's end, or the table's latest logged ts — never wall-clock unless the table is empty).
    Calendar anchors are SITE-timezone starts (_site_calendar_start — window.site_tz), week starts Monday (ISO).
    Returns {period: start_datetime}; the window END for all three is `anchor` itself."""
    return {
        "today":      _site_calendar_start(anchor, "day"),
        "this_week":  _site_calendar_start(anchor, "week"),
        "this_month": _site_calendar_start(anchor, "month"),
    }


def _period_deltas(asset_table, base, window):
    """Build ctx[today|this_week|this_month] = {active_import, active_export, reactive_import, reactive_export} — each a
    real (end−start) delta of its cumulative neuract counter over that period's sub-window. Generic: only fires when the
    fn declared an energy counter column (base ∩ _PERIOD_COUNTER_COLS), so a non-energy fn pays nothing. Anchors the
    sub-windows to the run window's END, or the table's latest logged ts (honest data-now — never wall-clock on a static
    dump). A genuinely-absent register / empty period → that key stays None (honest-blank; the fn's _pick_register /
    None-guard degrades, never fabricates). {} when no energy counter is declared or the anchor can't be resolved."""
    cols = [c for k, c in _PERIOD_COUNTER_COLS.items() if c in (base or [])]
    if not cols:
        return {}
    from datetime import datetime
    w = window or (None, None)
    anchor_raw = w[1]                                          # the run window's END is the reference 'now' when set
    if not anchor_raw and asset_table:                        # else the DATA's own latest logged ts (never wall-clock)
        anchor_raw = (_nx.latest(asset_table, [_dsn.ts_col()]) or {}).get(_dsn.ts_col())
    if not anchor_raw:
        return {}                                             # empty table / no window → honest-degrade (no periods)
    try:
        anchor = anchor_raw if isinstance(anchor_raw, datetime) else datetime.fromisoformat(str(anchor_raw))
    except (ValueError, TypeError):
        return {}
    out = {}
    for period, start in _period_starts(anchor).items():
        first, last = _nx.window(asset_table, cols, start.isoformat(), anchor.isoformat())
        d = {}
        for key, col in _PERIOD_COUNTER_COLS.items():
            s, e = (first or {}).get(col), (last or {}).get(col)
            d[key] = None if s is None or e is None else e - s   # (end−start) real delta; either endpoint absent → None
        out[period] = d
    return out


def _derived_key(field):
    """The derivation lookup KEY for a derived field — METRIC-WINS: when the field's declared `metric` has its OWN
    cmd_catalog.derivation_binding row, that key wins over the AI's `fn` guess. The metric names the QUANTITY the slot
    means (voltageSpread / maxDeviation); the fn is only the emit's pick of HOW to compute it — and a wrong pick ships a
    real number of the WRONG quantity (card 44: fn=nominalVoltageLN under metric=voltageSpread rendered the ~240 V
    NOMINAL as a 'Worst Spread'). A metric with no curated row changes nothing (the declared fn stands); both absent →
    None (honest-blank). DB-driven — seeding one binding row re-routes every card that names that metric, no code."""
    fn = field.get("fn")
    metric = field.get("metric")
    if metric and metric != fn:
        try:
            if _deriv.binding(metric):
                return metric
        except Exception:
            pass
    return fn or metric


def _run_derived(fn, asset_table, window=None):
    """Execute a NAMED library fn over a live-data superset ctx. Returns (value, fidelity) or (None, None) on
    honest-degrade (missing inputs / unknown fn / no nameplate). NEVER fabricates.

    A window/series-scoped fn (binding.scope in {'series','window'}) ALSO gets ctx['series'] — the ascending windowed
    time-series of its frame columns PLUS the reversed-CT power columns — so ∫power / peaks / load-factor / the dead-
    counter energy recovery have real samples, not just the latest row. Row-scoped fns skip the series read (cheap path
    unchanged). When the counter registers are dead but power is live, `windowEnergyKwh`/`activeEnergyTodayKwh`/
    `todaysEnergyTotalKwh` integrate the power series → real_approx kWh instead of blanking."""
    binding = _deriv.binding(fn)
    fidelity = binding["fidelity"] if binding else None
    base = binding["base_columns"] if binding else []
    scope = (binding.get("scope") if binding else None) or "row"
    frame_cols = [c for c in base if not c.startswith("nameplate:")]

    row = _nx.latest(asset_table, frame_cols) if frame_cols else {}
    w = window or (None, None)
    start_row, end_row = _nx.window(asset_table, frame_cols, w[0], w[1]) if frame_cols else ({}, {})

    series = []
    if scope in ("series", "window") and asset_table:
        # frame cols PLUS the power cols the ∫-fallback needs; series() drops any column the table lacks (safe on meters
        # missing a given register). A row-scoped fn never pays this read.
        sc_cols = list(dict.fromkeys(list(frame_cols) + list(_INTEGRATION_POWER_COLS)))
        series = _nx.series(asset_table, sc_cols, w[0], w[1])

    rated_kw = None
    if any(c.startswith("nameplate:") for c in base):
        np = _np.get_nameplate(asset_table) or {}
        got_rated = False
        for c in base:
            if c.startswith("nameplate:"):
                key = c.split(":", 1)[1]
                v = np.get(key)
                row[c] = v
                if key == "rated_kva":
                    got_rated = v is not None
        if "nameplate:rated_kva" in base and not got_rated:
            return None, None
        # BUG-57: a nameplate-driven fn (kpiKwLoadPctOfRated / kpiLoadFactor) reads ctx['rated_kw'], but the ctx below
        # only carried row['nameplate:rated_kva'] — so the fn always saw rated_kw=None and blanked a computable loading%
        # even with a real nameplate. Populate ctx['rated_kw'] = rated_kva × nominal_pf via the EXISTING kVA→kW accessor
        # (config.nameplates.derive_ratings_for, which applies rating.feeder_pf) — never hardcoded. An asset with NO
        # nameplate → derive_ratings_for → {} → rated_kw stays None → the fn honest-blanks (never fabricates a denom).
        rated_kw = (_np.derive_ratings_for(asset_table) or {}).get("rated_kw")
    # PERIOD-DELTA ctx: the reversed-CT windowed-energy fns (activeEnergy{This Week,This Month}Kwh / reactive_* /
    # apparent_*) read ctx[today|this_week|this_month] = {active_import, active_export, reactive_import, reactive_export}.
    # It was never populated → the row-scoped reactive/apparent legs (no ∫power fallback) FALSE-BLANKED a real delta
    # (cards 36/43/44). Build each period's real (end−start) counter delta from the run window; a genuinely-absent
    # register stays None (honest-blank). Fires ONLY when the fn declared an energy counter column (else {}, no read).
    ctx = {"row": row, "start_row": start_row, "end_row": end_row,
           "series": series, "name": asset_table, "rated_kw": rated_kw}
    ctx.update(_period_deltas(asset_table, base, window))
    # the derivation_binding row separates the lookup KEY (metric) from the registry FN it maps to — run the row's own
    # fn when it names one (metric='voltageSpread' → fn worstPhaseSpreadV), else the key itself (legacy rows key==fn).
    val = _registry.run((binding or {}).get("fn") or fn, ctx)
    # HONEST FIDELITY: a windowed-delta energy metric whose declared counter columns are ALL absent at both window
    # endpoints, yet produced a value, RECOVERED via the ∫power fallback — that is real_approx (a sampled integral), not
    # the real_exact a live hardware counter would give. Report the honest fidelity so the leaf's note reads
    # 'integrated from power'. Generic: keyed off the endpoints, not a hardcoded metric name.
    if val is not None and fidelity == "real_exact" and scope in ("series", "window") and frame_cols:
        counters_dead = all((start_row or {}).get(c) is None and (end_row or {}).get(c) is None for c in frame_cols)
        if counters_dead:
            fidelity = "real_approx"
    return val, fidelity
