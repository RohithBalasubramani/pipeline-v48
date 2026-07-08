"""derivations/power.py — POWER recoveries (pure fns, no DB). compat KEPT active_power_total_kw + apparent_power_total_kva,
so peaks, load factor and rate-of-change are real from the observed series. [best-possible-recovery: cards 15/36/42]"""
from __future__ import annotations

# app_config is guarded so this pure-fn module imports even without the pipeline config on the path (the load-factor
# min-energized floor then uses its code default). Same fail-open pattern as derivations.nameplate.
try:
    from config.app_config import cfg as _cfg
except Exception:  # pragma: no cover — import-safe without the pipeline config
    def _cfg(key, default):
        return default


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _series(ctx, col):
    return [float(r[col]) for r in (ctx.get("series") or []) if isinstance(r.get(col), (int, float))]


# A sample below this FRACTION of the window peak is treated as STANDSTILL (the asset de-energized / a genset not
# running), not a low-load operating point — it is excluded from the load-factor mean below. Relative (not a fixed kW)
# so it scales across a 5 kW motor and a 900 kW incomer alike; ≈ noise floor of a meter reading ~0 when the source is off.
# DB-TUNABLE (app_config `power.load_factor_energized_fraction`, seeded in db/seed_rescue_overreach_guards.sql); this
# module constant is only the CODE-DEFAULT mirror. It is read via _lf_energized_fraction() so the native load-factor
# mean and the executor.rescue path (which reads the SAME row) can never drift — editing the row moves BOTH floors.
_LF_ENERGIZED_FRACTION = 0.02

# The load-factor DEFINITIONAL ceiling (%) — load factor = mean/peak is DEFINITIONALLY ≤ 100 %, so a result above it is a
# sign/reducer anomaly (a reversed-CT signed-series artifact), not a real utilisation. A small TOLERANCE above it absorbs
# float rounding at the edge (100.3 → 100.0); anything past ceiling+tolerance honest-blanks. Both DB-tunable knobs
# (power.load_factor_ceiling_pct / power.load_factor_ceiling_tolerance_pct); these constants are the code-default mirrors.
_LF_CEILING_PCT = 100.0
_LF_CEILING_TOLERANCE_PCT = 0.5

# The loading-% PLAUSIBILITY ceiling (%) — a present-loading % (|kW| ÷ nameplate rated_kw × 100) far above physical
# possibility means the RATING DENOMINATOR is wrong (a fabricated/name-parsed plate the live power exceeds many-fold, the
# 20000-vs-160 nameplate class), NOT that the asset truly runs at that multiple. Above it, the loading% honest-blanks
# (never a fabricated overload). Applied at the DERIVATION layer so EVERY card's loading% is guarded, not one renderer.
# DB-tunable (power.loading_plausible_max_pct); this constant is the code-default mirror.
_LOADING_PLAUSIBLE_MAX_PCT = 200.0


def _lf_energized_fraction():
    """The fraction-of-peak STANDSTILL floor for the load-factor energized filter, from app_config
    `power.load_factor_energized_fraction` (code default _LF_ENERGIZED_FRACTION=0.02). The SAME row the executor.rescue
    native load-factor path reads, so the two never drift. Clamped to (0,1); a bad/absent row → the code default."""
    try:
        v = float(_cfg("power.load_factor_energized_fraction", _LF_ENERGIZED_FRACTION))
    except (TypeError, ValueError):
        return _LF_ENERGIZED_FRACTION
    return v if 0.0 < v < 1.0 else _LF_ENERGIZED_FRACTION


def _lf_ceiling_pct():
    """The load-factor definitional ceiling (%), from app_config `power.load_factor_ceiling_pct` (code default 100.0).
    A load factor above ceiling+tolerance is a sign/reducer artifact and honest-blanks. Bad/absent row → the default."""
    try:
        v = float(_cfg("power.load_factor_ceiling_pct", _LF_CEILING_PCT))
    except (TypeError, ValueError):
        return _LF_CEILING_PCT
    return v if v > 0 else _LF_CEILING_PCT


def _lf_ceiling_tolerance_pct():
    """The float-rounding tolerance (%) above the load-factor ceiling before honest-blanking, from app_config
    `power.load_factor_ceiling_tolerance_pct` (code default 0.5). Bad/absent row → the default."""
    try:
        v = float(_cfg("power.load_factor_ceiling_tolerance_pct", _LF_CEILING_TOLERANCE_PCT))
    except (TypeError, ValueError):
        return _LF_CEILING_TOLERANCE_PCT
    return v if v >= 0 else _LF_CEILING_TOLERANCE_PCT


def _loading_plausible_max_pct():
    """The loading-% plausibility ceiling (%), from app_config `power.loading_plausible_max_pct` (code default 200.0). A
    loading% above it signals a WRONG rating denominator (not a real overload) → honest-blank. 0/absent → the code
    default; a non-positive/absent knob is treated as 'no ceiling' only if explicitly 0 (else the default guards)."""
    try:
        v = float(_cfg("power.loading_plausible_max_pct", _LOADING_PLAUSIBLE_MAX_PCT))
    except (TypeError, ValueError):
        return _LOADING_PLAUSIBLE_MAX_PCT
    return v if v > 0 else _LOADING_PLAUSIBLE_MAX_PCT

# The MINIMUM number of ENERGIZED samples the single-meter branch needs for a MEANINGFUL load factor. Below it, the
# window is a genuinely-OFF / barely-run asset (a standby genset that logged 0 kW all day except one running hour) —
# and a load factor over 1-2 energized points is DEGENERATE: one point is trivially its own peak → mean==peak → a
# meaningless 100.0 % (dg_1_mfm 24h: 1 energized hourly bucket → 100.0 %; every DG the same). With too few energized
# samples the mean/peak identity carries no information, so we honest-blank (None) rather than assert 100 %. A
# continuously-loaded asset (UPS/feeder, ~24 energized buckets) or a real intermittent DG (many running hours) clears
# this floor → NO-OP, its true ~91-95 % load factor is unchanged. DB-tunable (config.app_config), code default 3.
def _lf_min_energized():
    try:
        return max(1, int(_cfg("power.load_factor_min_energized", 3)))
    except (TypeError, ValueError):
        return 3


def _energized(vals):
    """Keep only the ENERGIZED |power| samples — those above _LF_ENERGIZED_FRACTION of the window peak. A standstill
    sample (a stopped genset / de-energized bus reads 0) carries NO load and must not dilute the load-factor mean into a
    meaningless kW-fraction (dg_1_mfm: 24 off-hours + 1 running hour of 105 kW gave mean 4.2 kW → a bogus '4.0 %' that
    tracked avg-kW, not utilisation). For a continuously-loaded asset (UPS / feeder, no zero samples) EVERY sample clears
    the floor → this is a NO-OP and the identity is unchanged (~91-95 %). [] when the window is a full standstill.

    A genuinely-OFF asset can leave only 1-2 energized samples in the window (dg_1_mfm today = a single running hourly
    bucket). One point is trivially its own peak → mean==peak → a meaningless 100.0 % that says nothing about
    utilisation. So the energized set must clear a MINIMUM count (_lf_min_energized, DB-tunable, default 3) to be a
    meaningful mean/peak basis; below it → [] (honest-blank None load factor), NEVER a fabricated 100 %."""
    if not vals:
        return []
    pk = max(vals)
    if pk <= 0:
        return []
    floor = pk * _lf_energized_fraction()
    lit = [v for v in vals if v > floor]
    # too few energized points → mean/peak is degenerate (1 point == its own peak == 100 %); honest-blank instead.
    return lit if len(lit) >= _lf_min_energized() else []


def load_factor_pct(ctx):
    """Load factor = mean(|active_power|) ÷ peak(|active_power|) × 100 over the ENERGIZED samples of the window — the
    textbook mean/peak utilisation identity, but measured only while the asset is actually carrying load. Taken on
    MAGNITUDE so a reversed-CT/export-convention meter that logs power NEGATIVE (a UPS reads −185..−203 kW) yields its
    real load factor instead of blanking; abs() is a NO-OP for a positively-logged card. real_approx (depends on window
    coverage). ctx: {series:[rows with active_power_total_kw]}. (matches the negative-power→abs convention _verify uses.)

    ENERGIZED-ONLY MEAN [card 71 DG runtime-duty, dg_1_mfm]: an intermittently-running asset (a standby genset) reads a
    HARD ZERO whenever it is stopped, so a mean over the WHOLE single-meter window smears its running load across the idle
    hours and returns a kW-magnitude-looking fraction (dg_1_mfm 24 h: 24 off-hours + one 105 kW running hour → mean 4.2 kW
    ÷ 105 peak = a bogus 4.0 %, which merely echoes the ~4 kW day-average power, NOT a load factor). The single-meter
    branch (_rolled_or_series) excludes standstill (below _energized's floor) so the mean is the average load WHILE
    ENERGIZED — reproducible and granularity-robust. A continuously-loaded UPS/feeder has no zero samples → the filter is
    a NO-OP (identical ~91-95 %). A full-standstill window (nothing energized) or a zero peak → None (honest-blank; never
    a fabricated / avg-kW load factor).

    PANEL ROLL-UP HOOK: a panel_aggregate card's own device table has NO electrical series (the panel is a bus, not a
    meter), so its member-rolled power trend is injected via ctx['rolled_power'] (the SAME [values]/[{value}] series the
    worst-peak tile rolls). When present it takes precedence over the empty single-meter series so the panel's load
    factor is the fleet trend's mean/peak (~94%), never a blank from the empty bus device. The roll-up is a SUM across
    members (a continuously-energized bus), so its trend carries no standstill zeros to strip — it keeps the raw mean/peak
    (the energized filter is scoped to the single-meter branch, where a stopped genset logs the diluting zeros)."""
    # MAGNITUDE (abs): a reversed-CT/export meter logs power NEGATIVE; take |power| so max() is the true peak MAGNITUDE.
    # Without this, max(signed) of an all-negative series is the least-negative (≈0) sample, so mean/peak explodes far
    # past 100 (card 57 saw a 270 'load factor' — a signed-series artifact). abs() is a no-op for positively-logged cards.
    vals = [abs(v) for v in (_rolled_or_series(ctx) or []) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not vals:
        return None
    pk = max(vals)
    if pk <= 0:
        return None
    lf = sum(vals) / len(vals) / pk * 100.0
    # load factor = mean/peak is DEFINITIONALLY ≤ ceiling (100%); a result above it signals a sign/reducer anomaly, not a
    # real reading — honest-blank rather than ship a fabricated >100% utilisation. (min-cap absorbs float rounding at the
    # edge.) Ceiling + tolerance are DB-tunable knobs (power.load_factor_ceiling_pct / _ceiling_tolerance_pct), code
    # defaults 100.0 / 0.5 — no magic literal here.
    ceil = _lf_ceiling_pct()
    if lf > ceil + _lf_ceiling_tolerance_pct():
        return None
    return round(min(lf, ceil), 1)


def _rolled_or_series(ctx):
    """The |active-power| magnitude list to take the load factor over: prefer an injected member-rolled series
    (ctx['rolled_power'] — a panel roll-up's fleet trend, [values] or [{value}]/[{'value':…}] points), else the single
    meter's own active_power_total_kw series. abs() throughout (consumption is a magnitude; reversed-CT feeders log
    negative). [] when neither carries a real sample (honest-degrade → None load factor).

    The SINGLE-METER branch is _energized-filtered (a stopped genset logs a HARD ZERO that would dilute the load-factor
    mean into an avg-kW fraction — card 71/dg_1_mfm); the panel roll-up (a continuously-energized member SUM) keeps its
    raw trend, so the filter never touches the fleet path."""
    rolled = load_factor_series_vals(ctx.get("rolled_power"))
    if rolled:
        return rolled
    return _energized([abs(v) for v in _series(ctx, "active_power_total_kw")])


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


def mean_active_power_kw(ctx):
    """Average active power over the window = mean(|active_power_total_kw|) taken on the ENERGIZED samples only — the
    'Avg Load' (kW) a Fuel-Log / runtime KPI means: the average power WHILE the asset is carrying load, not the day-mean
    diluted by idle hours. Magnitude (abs) so a reversed-CT / export-convention meter logging power NEGATIVE (a UPS reads
    −185..−203 kW) reports its real average load; abs() is a NO-OP for a positively-logged card. real_approx (depends on
    window coverage). ctx: {series:[rows with active_power_total_kw]}.

    ENERGIZED-ONLY MEAN [same rule as load_factor_pct, card 71 dg_1_mfm]: an intermittently-running standby genset reads a
    HARD ZERO whenever stopped, so a mean over the WHOLE window smears its running load across the idle hours and returns
    a meaningless ~4 kW day-average instead of the ~787 kW running load. _energized excludes standstill (below its
    relative floor) so the mean is the average load while energized. A continuously-loaded UPS/feeder has no zero samples
    → the filter is a NO-OP (its raw mean). A full-standstill window (nothing energized — the asset really was OFF) → None
    (honest-blank; NEVER a fabricated / idle-diluted avg load). This is a kW MAGNITUDE, NOT a load-factor % (peak-relative
    utilisation lives in load_factor_pct) — the two never collide (distinct fns, distinct _QUANTITY families)."""
    vals = _energized([abs(v) for v in _series(ctx, "active_power_total_kw")])
    if not vals:
        return None
    return round(sum(vals) / len(vals), 1)


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
    rated_kw are present; None when there is no nameplate (honest-degrade the loading slot, never a fabricated denom).

    PLAUSIBILITY CEILING [nameplate-plausibility wall, generic]: a loading% far above physical possibility means the
    RATING DENOMINATOR is wrong — a fabricated / name-parsed plate (the 20000-vs-160 class) the live power exceeds
    many-fold, NOT that the asset truly runs at that multiple. Above the DB-driven ceiling (power.loading_plausible_max_
    pct, code default 200%) the loading% honest-blanks (None) instead of shipping e.g. '12000% loaded'. Applied HERE at
    the derivation so EVERY card that binds this fn (kpiKwLoadPctOfRated / loadPct / the kpi_load_factor ratio, on any
    asset) is guarded — not one renderer. abs() because reversed-CT feeders read a NEGATIVE active_power_total_kw."""
    row = ctx.get("row") or {}
    p = _f(row.get("active_power_total_kw"))
    rated = _f(ctx.get("rated_kw"))
    if p is None or rated is None or rated <= 0:
        return None
    pct = abs(p) / rated * 100.0
    ceil = _loading_plausible_max_pct()
    if ceil and pct > ceil:
        return None                                            # implausible loading% → wrong rating denominator; blank
    return round(pct, 1)


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
