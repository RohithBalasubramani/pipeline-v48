"""derivations/power.py — POWER recoveries (pure fns, no DB). compat KEPT active_power_total_kw + apparent_power_total_kva,
so peaks, load factor and rate-of-change are real from the observed series. [best-possible-recovery: cards 15/36/42]"""
from __future__ import annotations


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _series(ctx, col):
    return [float(r[col]) for r in (ctx.get("series") or []) if isinstance(r.get(col), (int, float))]


def load_factor_pct(ctx):
    """Load factor = mean(|active_power|) ÷ peak(|active_power|) × 100 — the textbook identity over the window, taken on
    MAGNITUDE so a reversed-CT/export-convention meter that logs power NEGATIVE (a UPS reads −185..−203 kW) yields its
    real load factor instead of blanking. abs() is a NO-OP for a positively-logged card. real_approx (depends on window
    coverage). ctx: {series:[rows with active_power_total_kw]}. (matches the negative-power→abs convention _verify uses.)

    PANEL ROLL-UP HOOK: a panel_aggregate card's own device table has NO electrical series (the panel is a bus, not a
    meter), so its member-rolled power trend is injected via ctx['rolled_power'] (the SAME [values]/[{value}] series the
    worst-peak tile rolls). When present it takes precedence over the empty single-meter series so the panel's load
    factor is the fleet trend's mean/peak (~94%), never a blank from the empty bus device."""
    vals = _rolled_or_series(ctx)
    if not vals:
        return None
    pk = max(vals)
    return round(sum(vals) / len(vals) / pk * 100.0, 1) if pk > 0 else None


def _rolled_or_series(ctx):
    """The |active-power| magnitude list to take the load factor over: prefer an injected member-rolled series
    (ctx['rolled_power'] — a panel roll-up's fleet trend, [values] or [{value}]/[{'value':…}] points), else the single
    meter's own active_power_total_kw series. abs() throughout (consumption is a magnitude; reversed-CT feeders log
    negative). [] when neither carries a real sample (honest-degrade → None load factor)."""
    return load_factor_series_vals(ctx.get("rolled_power")) or [abs(v) for v in _series(ctx, "active_power_total_kw")]


def load_factor_series_vals(rolled):
    """Coerce a member-rolled power series to the |value| magnitude list load_factor_pct averages. Accepts a bare number
    list ([912.5, …]) OR a points list ([{'value':…}] / [{'t','value'}]); drops non-numeric / None entries. [] when the
    input is empty / all-null (honest-degrade — the caller then blanks, never a fabricated load factor)."""
    out = []
    for p in (rolled or []):
        v = p.get("value") if isinstance(p, dict) else p
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if f == f and f not in (float("inf"), float("-inf")):
            out.append(abs(f))
    return out


def load_factor_from_series(rolled):
    """Load factor % straight from a member-rolled power series (the panel-aggregate roll-up path). Same mean÷peak×100
    identity as load_factor_pct, on |value| magnitudes. None on an empty / all-null series (honest-blank). Used by the
    panel_aggregate renderer so a panel's load factor comes from the fleet trend, not the empty bus device table."""
    return load_factor_pct({"rolled_power": rolled})


def worst_peak_kw(ctx):
    """Peak active power over the window = max(|active_power_total_kw|) — the largest MAGNITUDE, so a UPS logging power
    NEGATIVE (−203 kW) reports its true 203 kW worst-peak, not the least-negative sample. abs() is a NO-OP for a
    positively-logged card. real_exact (windowed magnitude max, label as observed)."""
    vals = _series(ctx, "active_power_total_kw")
    return round(max(abs(v) for v in vals), 1) if vals else None


def worst_peak_at(ctx):
    """ts of the window's magnitude peak active power. real_exact. ctx: {series}. (MAGNITUDE so it matches worst_peak_kw —
    a negatively-logged UPS's largest |power| sample, not the least-negative one.)"""
    rows = [r for r in (ctx.get("series") or []) if isinstance(r.get("active_power_total_kw"), (int, float))]
    if not rows:
        return None
    return max(rows, key=lambda r: abs(r["active_power_total_kw"])).get("ts")


def apparent_peak_kva(ctx):
    """Peak apparent power over the window = max(|apparent_power_total_kva|) — the largest MAGNITUDE, so a meter logging
    apparent power NEGATIVE reports its true magnitude peak, not the least-negative sample. abs() is a NO-OP for a
    positively-logged card. real_approx (observed peak, not a nameplate)."""
    vals = _series(ctx, "apparent_power_total_kva")
    return round(max(abs(v) for v in vals), 1) if vals else None


def active_power_delta_per_min(ctx):
    """Rate of change of active power = (last − prev) ÷ Δminutes over the last two samples. real_exact. ctx: {series}."""
    rows = [r for r in (ctx.get("series") or []) if isinstance(r.get("active_power_total_kw"), (int, float))]
    if len(rows) < 2:
        return None
    a, b = rows[-2], rows[-1]
    ta, tb = a.get("ts"), b.get("ts")
    try:
        dt_min = (tb - ta).total_seconds() / 60.0
    except (TypeError, AttributeError):
        return None
    if dt_min <= 0:
        return None
    return round((b["active_power_total_kw"] - a["active_power_total_kw"]) / dt_min, 2)


# ── NAMEPLATE-DRIVEN loading + input/output loss (the FRAME target columns) ──────────────────────────────────────────
# The consumer enriches ctx with the row's real active/apparent power + `rated_kw` (from config.nameplates via
# derivations.nameplate.feeder_rated_kw, honest-degrade None with no nameplate). abs() because reversed-CT feeders read
# a NEGATIVE active_power_total_kw (UPS-01 = −207 kW) — loading is a magnitude.
def kpi_kw_load_pct_of_rated(ctx):
    """Present loading % = |active_power_total_kw| ÷ rated_kw × 100. real_exact when both the live power and a nameplate
    rated_kw are present; None when there is no nameplate (honest-degrade the loading slot, never a fabricated denom)."""
    row = ctx.get("row") or {}
    p = _f(row.get("active_power_total_kw"))
    rated = _f(ctx.get("rated_kw"))
    if p is None or rated is None or rated <= 0:
        return None
    return round(abs(p) / rated * 100.0, 1)


def kpi_load_factor(ctx):
    """Live load factor = |active_power_total_kw| ÷ rated_kw (0–1 ratio, the instantaneous utilisation). None with no
    nameplate. (The WINDOWED load factor avg/peak lives in load_factor_pct; this is the point-in-time KPI tile.)"""
    pct = kpi_kw_load_pct_of_rated(ctx)
    return round(pct / 100.0, 3) if pct is not None else None


def active_power_loss_kw(ctx):
    """Input−output active-power loss = hv_input_kw − lv_output_kw. real_exact when the feeder carries both HV/LV legs;
    else None (honest-degrade — neuract UPS/transformer tables that lack the two legs never fabricate a loss)."""
    row = ctx.get("row") or {}
    hv, lv = _f(row.get("hv_input_kw")), _f(row.get("lv_output_kw"))
    if hv is None or lv is None:
        return None
    return round(hv - lv, 2)


def active_power_loss_pct(ctx):
    """Active-power loss as % of input = (hv_input − lv_output) ÷ hv_input × 100. real_exact; None without both legs."""
    row = ctx.get("row") or {}
    hv, lv = _f(row.get("hv_input_kw")), _f(row.get("lv_output_kw"))
    if hv is None or lv is None or hv == 0:
        return None
    return round((hv - lv) / hv * 100.0, 2)


# ── GATED input/output loss (the loss-plausibility port) ─────────────────────────────────────────────────────────────
# ADDITIVE [#4/#12]: the raw active_power_loss_kw/pct above compute the loss whenever both HV/LV legs are present. But a
# plausible loss lives only inside a physical band [0,10]% (config.topology_policy); a bigger figure means the paired
# 'input' leg is not truly upstream — the loss is bogus and must be dropped (P1 #11, feeder_energypower.py:247-249). The
# gate delegates to derivations.topology.loss_pct_is_plausible so the band stays a single DB-driven knob, no magic number
# here. These are NEW fns — the ungated ones keep their signatures for existing callers (rule #5). abs() load% is UNTOUCHED.
def active_power_loss_kw_gated(ctx):
    """Input−output active-power loss in kW, but ONLY when the computed loss% is physically plausible; else None
    (honest-degrade — no bogus loss from a mis-paired input leg). Same HV/LV legs as active_power_loss_kw."""
    from . import topology as _topo
    pct = active_power_loss_pct(ctx)
    if not _topo.loss_pct_is_plausible(pct):
        return None
    return active_power_loss_kw(ctx)


def active_power_loss_pct_gated(ctx):
    """Active-power loss as % of input, GATED to the plausible band [0,10]% (config.topology_policy); else None. Ports
    the feeder_energypower.py:247-249 trust gate to the per-feeder loss column."""
    from . import topology as _topo
    pct = active_power_loss_pct(ctx)
    return pct if _topo.loss_pct_is_plausible(pct) else None


def rate_of_change_power_kw_per_min(ctx):
    """Alias target for the FRAME's rate-of-change column — same windowed slope as active_power_delta_per_min. None when
    the window has < 2 samples (honest-degrade). ctx: {series}."""
    return active_power_delta_per_min(ctx)
