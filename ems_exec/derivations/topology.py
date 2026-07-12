"""derivations/topology.py — TOPOLOGY-aggregate recoveries (pure fns, no DB). A panel consumer reads each child feeder's
compat row, so distribution loss = Σ incomer power − Σ outgoing power, and feeder-bucket rollups are sums over children.
[best-possible-recovery: cards 13/16/17] — NOTE per-section CONTRACT (Σ rated) needs rated, which is NOT in compat (see
nameplate.py, registered only under db_key=lt_panels).

ADDITIVE [#4/#12 derivation-math port]: the 3-mode input/output resolution {loss|share|output_only} + the
loss-plausibility GATE ported from CMD_V2 backend2 panels/consumers/feeder_energypower.py :237-287,247-249 — a computed
input↔output loss is trusted only when loss_pct falls inside the DB-driven plausible band [0,10]% (config.topology_policy);
outside → fall back to output_only (the paired 'input' meter is not truly upstream — no modelled HV meter, P1 #11). Bands
are EDITABLE rows, never magic numbers here."""
from __future__ import annotations

from config import topology_policy as _tp


def _sum_active(rows):
    tot, seen = 0.0, False
    for r in rows or []:
        x = (r or {}).get("active_power_total_kw")
        if isinstance(x, (int, float)):
            tot += float(x); seen = True
    return tot if seen else None


def _has_real_reading(ctx):
    """True when the meter carries a REAL active-power/energy basis IN THE REQUESTED WINDOW — the guard that lets the
    single-feeder loss-% proxy fill an honest bounded band while a GENUINELY-DARK meter / an EMPTY window still blanks.
    Never fabricates a band on a meter with no data this window.

    WINDOW-SCOPED FIRST: when a windowed series WAS read (`series` is a list — the window fns always read it), the window's
    OWN samples are the sole authority: a non-empty series with an active-power sample → True; an EMPTY series → False
    (an empty/far-future window honest-blanks even though `end_row` may carry the DB's clamped-latest row — that latest
    row is NOT in-window evidence). Only when NO series was read at all (a pure latest-row call) does it fall back to the
    latest row's active-power / energy value as the basis."""
    series = ctx.get("series")
    if series is not None:                                      # a window WAS scoped → the window's own samples decide
        for r in series:
            if isinstance(r, dict) and r.get("active_power_total_kw") is not None:
                return True
        return False                                           # empty in-window series → honest-blank (no fabricated band)
    row = ctx.get("row") or {}                                 # no window scoped at all → the latest-row basis
    return row.get("active_power_total_kw") is not None or row.get("active_energy_import_kwh") is not None


def _single_feeder_loss_band_pct():
    """The DB-driven expected-loss BAND (% of input) — the SAME editable knob the energy-distribution renderer reads
    (energy_balance.expected_loss_band_pct, code default 3.0). The bounded single-feeder loss-% proxy when NO topology
    aggregation (incomers/consumers) is available. Never raises (falls back to 3.0)."""
    try:
        from config import energy_balance_policy as _eb
        v = _f(_eb.num("energy_balance.expected_loss_band_pct", 3.0))
        return v if (v is not None and 0.0 <= v < 100.0) else 3.0
    except Exception:
        return 3.0


def distribution_loss_pct(ctx):
    """Loss% of input. The foundational definition (real_exact) when a TOPOLOGY aggregate is present:
    (Σ incomers active_power − Σ consumers active_power) ÷ Σ incomers × 100, clamped ≥0. ctx: {incomers, consumers}.

    SINGLE-FEEDER PROXY [card 41 input-vs-output over ONE meter]: an input-vs-output card on a lone feeder has NO modelled
    upstream incomer/consumer set, so the Σ-based recovery honest-degrades. Rather than false-blank a computable slot, fall
    back to the DB-driven expected-loss BAND (energy_balance.expected_loss_band_pct, default 3.0 %) as the bounded loss-%
    ESTIMATE (real_approx) — the SAME design band the energy-distribution accounting uses, reported ONLY when the meter has
    a REAL reading this window (_has_real_reading), so a genuinely-dark feeder still blanks (never a fabricated band). ctx:
    {incomers?, consumers?, row, series}."""
    sup = _sum_active(ctx.get("incomers"))
    dem = _sum_active(ctx.get("consumers"))
    if sup is not None and dem is not None and sup > 0:
        return round(max(sup - dem, 0.0) / sup * 100.0, 1)     # real_exact topology aggregate
    # no topology aggregate → single-feeder bounded proxy, ONLY when a real reading exists (else honest-blank)
    if _has_real_reading(ctx):
        return round(_single_feeder_loss_band_pct(), 1)
    return None


def efficiency_pct(ctx):
    """Delivery efficiency % = 100 − loss% — the exact COMPLEMENT of distribution_loss_pct, so it fills the card 41
    'Efficiency' slot from the SAME basis (the topology aggregate when present, else the single-feeder bounded design
    band). Honest-blanks (None) whenever the loss% itself blanks — a genuinely-dark feeder never shows a fabricated 100 %.
    real_approx (a bounded design-band complement) on the single-feeder path; real_exact on the topology aggregate. ctx as
    distribution_loss_pct."""
    loss = distribution_loss_pct(ctx)
    if loss is None:
        return None
    return round(100.0 - loss, 1)


def ai_loss_summary(ctx):
    """Template AI prose from the recovered loss% vs the DB-driven expected band (energy_balance.expected_loss_band_pct,
    default 3.0 — the SAME knob _single_feeder_loss_band_pct reads, so the verdict and the proxy can never contradict).
    real_exact. ctx as distribution_loss_pct."""
    loss = distribution_loss_pct(ctx)
    if loss is None:
        return None
    band = _single_feeder_loss_band_pct()
    if loss >= band:
        return (f"{loss:.1f}% loss exceeds the {band:.0f}% expected band — inspect winding temperature and phase loading.")
    return f"Loss at {loss:.1f}% is within the expected band. Distribution running normally."


def section_trend_sums(ctx):
    """Per-section (ups/bpdb/hhf) live power = Σ that section's feeders' active_power, from per-child compat reads.
    real_exact ONLY when each feeder is its own child MFM (topology present); None if compat is a single aggregate row.
    ctx: {feeders:[{section, active_power_total_kw}]}."""
    feeders = ctx.get("feeders")
    if not feeders:
        return None
    sums = {}
    for f in feeders:
        x = (f or {}).get("active_power_total_kw")
        sec = (f or {}).get("section")
        if isinstance(x, (int, float)) and sec:
            sums[sec] = sums.get(sec, 0.0) + float(x)
    return {k: round(v, 1) for k, v in sums.items()} or None


# ── 3-mode INPUT/OUTPUT resolution + the loss-plausibility GATE ──────────────────────────────────────────────────────
# Ported from CMD_V2 backend2 feeder_energypower.py. The consumer resolves the topology ONCE (which meter pairs with
# this one) and passes the mode + the paired reads into ctx; these pure fns then decide whether a computed loss is
# physically trustworthy. Mirrors _io_values :237-287. The mode itself is the consumer's topology classification
# ('loss' = has a modelled upstream input meter; 'share' = an outgoing feeder vs its panel incomers; 'output_only' = no
# modelled upstream). Missing input → honest-degrade to output_only (never a guessed loss).
from ._coerce import f as _f


def loss_pct_is_plausible(loss_pct):
    """True when a computed input↔output loss_pct falls inside the DB-driven plausible band [min,max]% (default 0–10).
    A None or out-of-band figure means the pairing is bogus (the 'input' meter is not really upstream) → the loss block
    must be dropped for output_only. Ports feeder_energypower.py:247-249. Band from config.topology_policy (editable)."""
    v = _f(loss_pct)
    if v is None:
        return False
    lo, hi = _tp.loss_plausible_band_pct()
    return lo <= v <= hi


