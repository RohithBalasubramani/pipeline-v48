"""derivations/energy.py — ENERGY recoveries (pure fns, no DB). Period ACTIVE energy is a windowed delta of the
cumulative active register (or ∫active-power when that counter is dead). REACTIVE / APPARENT ENERGY fill ONLY from a
real reactive/apparent ENERGY register — a meter without that register HONEST-BLANKS; there is NO ∫reactive-power→
reactive-ENERGY synthesis (fabrication-by-substitution, card-72). ∫power recovery is legitimate only for ACTIVE energy
and POWER/load-factor quantities. [best-possible-recovery: cards 14/39; card-72 energy-register rule]"""
from __future__ import annotations

import math


from ._coerce import f as _f


def _expected_loss_band_pct():
    """The config-driven EXPECTED-LOSS BAND (% of input) — the SAME editable knob the energy-distribution renderer reads
    (energy_balance.expected_loss_band_pct, code default 3.0). Used as the single-feeder expected-loss/loss-% proxy basis
    when NO per-asset target efficiency is wired into ctx (an input-vs-output card over ONE meter has no modelled upstream
    input meter, so the bounded design band IS the honest estimate). DB-driven; never raises (falls back to 3.0)."""
    try:
        from config import energy_balance_policy as _eb
        v = _f(_eb.num("energy_balance.expected_loss_band_pct", 3.0))
        return v if (v is not None and 0.0 <= v < 100.0) else 3.0
    except Exception:
        return 3.0


def window_energy_kwh(ctx):
    """Period active energy = cumulative import at window END − at window START (a windowed_delta). real_exact.
    ctx: {start_row, end_row} each with active_energy_import_kwh.

    DEAD-COUNTER FALLBACK: when the cumulative counter is all-NULL (many meters log power but never the kWh register),
    the delta is unresolvable → integrate the observed power series instead (real_approx, 'integrated from power'). The
    counter path is preferred (real_exact); integration only runs when it returns None. Never fabricates."""
    s = _f((ctx.get("start_row") or {}).get("active_energy_import_kwh"))
    e = _f((ctx.get("end_row") or {}).get("active_energy_import_kwh"))
    if s is None or e is None:
        return energy_from_power_kwh(ctx)
    return round(max(e - s, 0.0), 1)


def todays_energy_total_kwh(ctx):
    """The card window's TOTAL energy = active + reactive windowed deltas, REVERSED-CT AWARE — the CMD_V2 mapper's own
    contract (energyPowerMapper: totalEnergy = activeEnergyToday + reactiveEnergyToday). Each leg is the (end−start)
    delta over the CARD'S OWN window rows (ctx start_row/end_row — the SAME window the sibling component KPIs fill
    from, so the donut total always equals its parts) with _pick_register choosing the register that MOVED (a
    reversed-CT feeder keeps its real kWh on EXPORT while import stays flat — the 2026-07-06 card-39 defect shipped
    the 231 kvarh import delta as the 'kWh' total while the real 4674 kWh sat on export). Dead counters → ∫power
    (real_approx). Never mixes quantities into a leg: kvarh only ever feeds the reactive term. real_exact."""
    s, e = ctx.get("start_row") or {}, ctx.get("end_row") or {}

    def _leg_delta(imp_col, exp_col):
        i0, i1 = _f(s.get(imp_col)), _f(e.get(imp_col))
        x0, x1 = _f(s.get(exp_col)), _f(e.get(exp_col))
        imp = (i1 - i0) if None not in (i0, i1) else None
        exp = (x1 - x0) if None not in (x0, x1) else None
        return _pick_register(imp, exp)

    active = _leg_delta("active_energy_import_kwh", "active_energy_export_kwh")
    reactive = _leg_delta("reactive_energy_import_kvarh", "reactive_energy_export_kvarh")
    if active is None:
        # DEAD-COUNTER FALLBACK: no cumulative register moved/exists → integrate the observed active-power series
        # (real_approx). The reactive leg has no power fallback (kept exact-or-zero) so the total never over-states.
        return energy_from_power_kwh(ctx)
    return round(active + (reactive or 0.0), 1)


# progressActivePct is ROW-DRIVEN now: its formula lives in cmd_catalog.derivation_binding.expression (executed by
# derivations/evaluate.py); the python body was DELETED 2026-07-03 after the live 3-table parity gate.


def mvah_active(ctx):
    """Cumulative active energy import in MWh (MVAh active leg). real_exact. ctx: {row}."""
    a = _f((ctx.get("row") or {}).get("active_energy_import_kwh"))
    return round(a / 1000.0, 2) if a is not None else None


def mvah_reactive(ctx):
    """Reactive ENERGY in MVArh — the reactive leg of the MVAh apparent quadrature. Fills ONLY from a REAL reactive-
    ENERGY REGISTER; otherwise HONEST-BLANKS (None). There is NO ∫power fallback for this ENERGY leaf.

    REAL SOURCE (real_exact): the cumulative reactive-energy import register (reactive_energy_import_kvarh) / 1000.

    NO ∫POWER RECOVERY [card-72 fab-by-substitution, DEFINITIVE 2026-07-07]: an earlier fix integrated the live
    reactive-POWER series (∫|reactive_power|dt) to synthesize reactive kVArh whenever the reactive-ENERGY register was
    absent (dg_1_mfm has reactive_power_total_kvar but NO reactive_energy_import_kvarh). The adversarial audit correctly
    calls that FABRICATION-BY-SUBSTITUTION: you cannot report reactive/apparent ENERGY for a meter that carries NO
    reactive/apparent ENERGY REGISTER — synthesizing an energy READING from ∫power where the register does not exist
    manufactures a measurement the meter never took. A reactive-ENERGY leaf therefore fills real-or-honest-blank ONLY:
    the register is present → its value; the register is absent → None (the honest 'column_absent' the gap channel
    already reports off the binding's reactive_energy_import_kvarh base). (∫power recovery remains legitimate for a
    POWER / load-factor quantity — energy_from_power_kwh still serves those — it is BANNED only for ENERGY-register
    leaves, which this is.) ctx: {row}."""
    r = _f((ctx.get("row") or {}).get("reactive_energy_import_kvarh"))
    if r is None:
        return None                                            # reactive-energy REGISTER absent → honest-blank, no ∫power
    return round(r / 1000.0, 2)                                # real_exact: the cumulative counter register only


def cumulative_apparent_mvah(ctx):
    """Apparent energy MVAh = hypot(active MVAh, reactive MVArh) — the textbook quadrature identity. real_exact.

    HONEST-BLANK when EITHER leg is genuinely UNAVAILABLE (None): apparent energy is undefined without both the active
    AND the reactive component, so it must NEVER ship the active MWh magnitude relabeled 'Apparent' (the `r or 0.0`
    substitution filled 27.83 MVAh from a 27.83 MWh active reading with zero reactive basis — a fab-by-substitution).
    A register that IS present and reads a real 0.0 (mvah_reactive → 0.0, not None) still computes apparent = |active|
    legitimately (that is a true quadrature with a zero reactive leg, not a missing one).

    NO SYNTHESIZED REACTIVE LEG [card-72, DEFINITIVE 2026-07-07]: mvah_reactive fills ONLY from a real reactive-ENERGY
    register (no ∫reactive-power recovery — see its docstring). So a meter with NO reactive-energy register (dg_1_mfm)
    yields r=None here and this apparent-ENERGY leaf HONEST-BLANKS — it never ships hypot(active, ∫-synthesized-reactive),
    which would be a fabricated apparent-energy reading for a meter that has no apparent/reactive energy register at all.
    Apparent energy fills real only when BOTH energy legs are real. Never fabricates."""
    a, r = mvah_active(ctx), mvah_reactive(ctx)
    if a is None or r is None:
        return None
    return round(math.hypot(a, r), 2)


def expected_loss_kwh(ctx):
    """Expected loss (kWh) = window energy × (1 − target_efficiency%/100) — the design-band conversion/distribution loss
    over the meter's OWN real windowed energy throughput.

    real_exact when a per-asset `target_efficiency_pct` is wired into ctx. When it is NOT (a single-feeder input-vs-output
    card has no modelled upstream HV meter, so no asset-specific efficiency is carried), fall back to the DB-driven
    expected-loss BAND (energy_balance.expected_loss_band_pct, default 3.0 %): expected_loss = window_energy × band/100.
    This is the SAME bounded design band the energy-distribution renderer reads — a legitimate single-feeder ESTIMATE
    (real_approx), NOT a fabricated number: it multiplies the meter's REAL windowed energy by a published design band, so
    the leaf FILLS the honest proxy it is instead of false-blanking. Still honest-degrades to None when the window carries
    NO real energy basis (window_energy_kwh None → a genuinely-dark meter blanks). ctx: {start_row, end_row, series,
    target_efficiency_pct?}."""
    win = window_energy_kwh(ctx)
    if win is None:
        return None                                            # no real windowed energy basis → honest-blank
    eff = _f(ctx.get("target_efficiency_pct"))
    if eff is None:
        eff = 100.0 - _expected_loss_band_pct()                # single-feeder: design-band efficiency (100 − band %)
    return round(win * (1.0 - eff / 100.0), 1)


# ── REVERSED-CT-AWARE windowed energy deltas (the FRAME target columns) ──────────────────────────────────────────────
# The consumer pre-computes, per window (today/week/month), the delta of BOTH the import and the export register (via
# services.fetch_energy_delta) and puts them in ctx as `<period>` → {"active_import", "active_export", "reactive_import",
# "reactive_export"}. These pure fns SELECT the register that actually moved: many feeders are wired reversed-CT (UPS-01
# import=0, export=311353) so the real consumption lives on the EXPORT register. Rule: pick whichever register has the
# larger |delta| (the flat one is ~0 by definition). None when neither register produced a usable delta (honest-degrade).
def _pick_register(imp, exp):
    """Choose the register that moved over the window. Reversed-CT feeders keep the true energy on `export`, forward
    feeders on `import`; the un-wired register is flat (~0). Returns the signed magnitude of the mover, or None."""
    i, e = _f(imp), _f(exp)
    if i is None and e is None:
        return None
    ia = abs(i) if i is not None else -1.0
    ea = abs(e) if e is not None else -1.0
    chosen = e if ea >= ia else i
    return None if chosen is None else max(chosen, 0.0)


def _period_delta(ctx, period, leg):
    """Real windowed consumption for one energy leg over `period` ('today'|'this_week'|'this_month'), reversed-CT aware.
    `leg` = 'active'|'reactive'. Reads ctx[period] = {active_import, active_export, reactive_import, reactive_export}."""
    d = ctx.get(period) or {}
    return _pick_register(d.get(f"{leg}_import"), d.get(f"{leg}_export"))


# ── PANEL ROLL-UP register selection — the SAME reversed-CT rule, applied per FEEDER inside a panel aggregate ──────────
# The panel-aggregate energy roll-up (renderers/panel_aggregate) sums each member feeder's windowed energy delta. A member
# may be wired reversed-CT (import register flat / export moves — the 3 GIC UPS feeders read import_delta=0 while their
# real ~4700 kWh lives on active_energy_export_kwh) while a sibling (bpdb-01) uses import normally. Reuses _pick_register
# so the roll-up picks, PER FEEDER, whichever register actually moved and returns its POSITIVE magnitude for display; a
# genuinely dark feeder (neither register moved / no rows) → None (honest-blank, never a fabricated 0).
def member_energy_delta(import_delta, export_delta):
    """The real per-feeder windowed energy magnitude for a panel roll-up, reversed-CT aware. `import_delta` /
    `export_delta` are each ONE member's already-computed (end−start) counter delta (or None when the register is
    absent / the table is empty). Picks the register that moved (larger |delta|; the un-wired one is flat ~0) and
    returns its abs magnitude so a reversed-CT feeder shows a POSITIVE kWh; None when neither register moved."""
    return _pick_register(import_delta, export_delta)


def active_energy_today_kwh(ctx):
    v = _period_delta(ctx, "today", "active")
    if v is None:
        return energy_from_power_kwh(ctx)      # DEAD-COUNTER FALLBACK: integrate the windowed active-power series
    return round(v, 1)


def active_energy_this_week_kwh(ctx):
    v = _period_delta(ctx, "this_week", "active")
    if v is None:
        return energy_from_power_kwh(ctx)
    return round(v, 1)


def active_energy_this_month_kwh(ctx):
    v = _period_delta(ctx, "this_month", "active")
    if v is None:
        return energy_from_power_kwh(ctx)
    return round(v, 1)


def reactive_energy_today_kvarh(ctx):
    v = _period_delta(ctx, "today", "reactive")
    return round(v, 1) if v is not None else None


def reactive_energy_this_week_kvarh(ctx):
    v = _period_delta(ctx, "this_week", "reactive")
    return round(v, 1) if v is not None else None


def reactive_energy_this_month_kvarh(ctx):
    v = _period_delta(ctx, "this_month", "reactive")
    return round(v, 1) if v is not None else None


def _apparent(active, reactive):
    """Apparent energy = √(active² + reactive²) — the textbook quadrature identity. None if the active leg is absent."""
    if active is None:
        return None
    return round(math.hypot(active, reactive or 0.0), 1)


def apparent_energy_today_kvah(ctx):
    return _apparent(active_energy_today_kwh(ctx), reactive_energy_today_kvarh(ctx))


def apparent_energy_this_week_kvah(ctx):
    return _apparent(active_energy_this_week_kwh(ctx), reactive_energy_this_week_kvarh(ctx))


def apparent_energy_this_month_kvah(ctx):
    return _apparent(active_energy_this_month_kwh(ctx), reactive_energy_this_month_kvarh(ctx))


def specific_energy_consumption(ctx):
    """SEC = today's active energy ÷ a production base (units). real_exact only when the consumer wires a production
    base into ctx['production_base_units']; else None (honest-degrade — never fabricate a denominator)."""
    base = _f(ctx.get("production_base_units"))
    if base is None or base <= 0:
        return None
    e = active_energy_today_kwh(ctx)
    return round(e / base, 3) if e is not None else None


# ── ENERGY-FROM-POWER integration (the DEAD-COUNTER recovery) ────────────────────────────────────────────────────────
# Many meters log active_power_total_kw continuously but leave the 4 cumulative energy-counter registers (active/reactive
# import/export kWh/kVArh) all-NULL — so every windowed-delta energy derivation (windowEnergyKwh / activeEnergyTodayKwh /
# todaysEnergyTotalKwh) honest-blanks even though the throughput is fully observable. Energy IS the time-integral of power
# (∫P dt), so kWh is RECOVERABLE by trapezoidally integrating the observed power series over the window. fidelity is
# real_approx (a sampled integral, not a hardware counter); the honest note is 'integrated from power'.
#
# ctx: {series:[{active_power_total_kw, ts}...]} — the SAME series shape the power fns read (ts is a datetime; the executor
# builds it from the windowed bucketed power reads). Reversed-CT aware: a reversed-CT feeder logs a NEGATIVE power, and
# consumption is a magnitude, so each sample is abs()'d before integrating. Honest-degrade to None when the window carries
# < 2 usable samples or no positive elapsed time (NEVER a fabricated number, NEVER a numeric op on None).
def _dt_hours(ta, tb):
    """Elapsed hours between two series timestamps (datetime OR ISO string), or None if unparseable / non-positive."""
    def _dt(x):
        if hasattr(x, "timestamp"):
            return x
        try:
            from datetime import datetime
            return datetime.fromisoformat(str(x))
        except (TypeError, ValueError):
            return None
    a, b = _dt(ta), _dt(tb)
    if a is None or b is None:
        return None
    try:
        h = (b - a).total_seconds() / 3600.0
    except (TypeError, AttributeError):
        return None
    return h if h > 0 else None


def energy_from_power_kwh(ctx, power_col="active_power_total_kw"):
    """Windowed active energy (kWh) = trapezoidal ∫ |power| dt over the observed power series. The DEAD-COUNTER recovery:
    real_approx, honest note 'integrated from power'. ctx: {series:[{<power_col>, ts}...]} (ts a datetime/ISO instant,
    ascending). Reversed-CT aware (each sample abs()'d — consumption is a magnitude). None when < 2 usable samples or the
    window has no positive elapsed time (honest-degrade; never a fabricated kWh, never NaN)."""
    pts = []
    for r in (ctx.get("series") or []):
        if not isinstance(r, dict):
            continue
        p = _f(r.get(power_col))
        t = r.get("ts")
        if p is not None and t is not None:
            pts.append((t, abs(p)))
    if len(pts) < 2:
        return None
    total = 0.0
    covered = False
    for (ta, pa), (tb, pb) in zip(pts, pts[1:]):
        h = _dt_hours(ta, tb)
        if h is None:
            continue
        total += (pa + pb) / 2.0 * h          # trapezoid: avg-power (kW) × elapsed (h) = kWh
        covered = True
    return round(total, 1) if covered else None


def reactive_energy_from_power_kvarh(ctx):
    """DISABLED [card-72 fab-by-substitution, DEFINITIVE 2026-07-07] — always honest-blanks (None).

    This once integrated the reactive-POWER series (∫|reactive_power|dt) to synthesize a reactive-ENERGY kVArh reading
    when the reactive-ENERGY register was absent. The adversarial audit ruled that FABRICATION-BY-SUBSTITUTION: a meter
    with NO reactive-energy REGISTER (dg_1_mfm) cannot report reactive ENERGY — an energy reading synthesized from
    ∫power is a measurement the meter never took. Reactive/apparent ENERGY fills real-or-honest-blank ONLY (from a real
    reactive/apparent energy register). The symbol is KEPT (registry/catalog reference) but neutered to None so no
    ENERGY-register leaf can ever synthesize a value. (∫power recovery for a POWER/load-factor quantity stays legitimate
    via energy_from_power_kwh — it is banned only here, for the reactive-ENERGY leaf.)"""
    return None


