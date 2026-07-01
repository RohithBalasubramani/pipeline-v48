"""derivations/topology.py — TOPOLOGY-aggregate recoveries (pure fns, no DB). A panel consumer reads each child feeder's
compat row, so distribution loss = Σ incomer power − Σ outgoing power, and feeder-bucket rollups are sums over children.
[best-possible-recovery: cards 13/16/17] — NOTE per-section CONTRACT (Σ rated) needs rated, which is NOT in compat (see
nameplate.py, registered only under db_key=lt_panels)."""
from __future__ import annotations


def _sum_active(rows):
    tot, seen = 0.0, False
    for r in rows or []:
        x = (r or {}).get("active_power_total_kw")
        if isinstance(x, (int, float)):
            tot += float(x); seen = True
    return tot if seen else None


def distribution_loss_pct(ctx):
    """Loss% = (Σ incomers active_power − Σ consumers active_power) ÷ Σ incomers × 100, clamped ≥0 — the foundational
    definition of distribution loss. real_exact. ctx: {incomers:[rows], consumers:[rows]}."""
    sup = _sum_active(ctx.get("incomers"))
    dem = _sum_active(ctx.get("consumers"))
    if sup is None or dem is None or sup <= 0:
        return None
    return round(max(sup - dem, 0.0) / sup * 100.0, 1)


def ai_loss_summary(ctx):
    """Template AI prose from the recovered loss% vs the 3% expected band. real_exact. ctx as distribution_loss_pct."""
    loss = distribution_loss_pct(ctx)
    if loss is None:
        return None
    if loss >= 3.0:
        return (f"{loss:.1f}% loss exceeds the 3% expected band — inspect winding temperature and phase loading.")
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
