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


# ── 3-mode INPUT/OUTPUT resolution + the loss-plausibility GATE ──────────────────────────────────────────────────────
# Ported from CMD_V2 backend2 feeder_energypower.py. The consumer resolves the topology ONCE (which meter pairs with
# this one) and passes the mode + the paired reads into ctx; these pure fns then decide whether a computed loss is
# physically trustworthy. Mirrors _io_values :237-287. The mode itself is the consumer's topology classification
# ('loss' = has a modelled upstream input meter; 'share' = an outgoing feeder vs its panel incomers; 'output_only' = no
# modelled upstream). Missing input → honest-degrade to output_only (never a guessed loss).
def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def loss_pct_is_plausible(loss_pct):
    """True when a computed input↔output loss_pct falls inside the DB-driven plausible band [min,max]% (default 0–10).
    A None or out-of-band figure means the pairing is bogus (the 'input' meter is not really upstream) → the loss block
    must be dropped for output_only. Ports feeder_energypower.py:247-249. Band from config.topology_policy (editable)."""
    v = _f(loss_pct)
    if v is None:
        return False
    lo, hi = _tp.loss_plausible_band_pct()
    return lo <= v <= hi


def io_resolution(ctx):
    """Classify the input/output relationship for a meter and, when it is 'loss', GATE the loss on plausibility.
    ADDITIVE port of feeder_energypower.py _io_values :237-287 (V48's distribution_loss_pct above stays the panel-level
    Σ-incomer−Σ-outgoing recovery; this is the per-meter pairing variant). Returns a dict of io_* target fields, or None
    to honest-degrade. ctx:
      {mode:'loss', in_kw, out_kw}          → {io_mode, hv_input_kw, lv_output_kw, active_power_loss_kw,
                                               active_power_loss_pct} when the loss is plausible; else downgrades to
                                               {io_mode:'output_only', output_kw} (P1 #11 gate).
      {mode:'share', feeder_kwh, incomers:[{name, kwh}]} → {io_mode:'share', io_feeder_kwh, io_panel_incoming_kwh,
                                               io_share_pct, io_incomers}.
      {mode:'output_only', out_kw}          → {io_mode:'output_only', output_kw}.
    """
    c = ctx or {}
    mode = c.get("mode")

    if mode == "loss":
        in_kw, out_kw = _f(c.get("in_kw")), _f(c.get("out_kw"))
        loss_pct = (round((in_kw - out_kw) / in_kw * 100.0, 2)
                    if in_kw is not None and out_kw is not None and in_kw > 0 else None)
        # Trust the loss block ONLY when the pairing is physically plausible (band from config); else the paired meter
        # is not truly upstream — fall back to output_only rather than surface a bogus loss (P1 #11).
        if not loss_pct_is_plausible(loss_pct):
            return {"io_mode": "output_only",
                    "output_kw": round(out_kw, 1) if out_kw is not None else None}
        return {
            "io_mode": "loss",
            "hv_input_kw": round(in_kw, 1),
            "lv_output_kw": round(out_kw, 1) if out_kw is not None else None,
            "active_power_loss_kw": round(in_kw - out_kw, 1),
            "active_power_loss_pct": loss_pct,
        }

    if mode == "share":
        feeder = _f(c.get("feeder_kwh"))
        incs, total = [], 0.0
        for x in (c.get("incomers") or []):
            e = _f((x or {}).get("kwh")) or 0.0
            total += e
            incs.append({"name": (x or {}).get("name"), "kwh": round(e, 1)})
        for item in incs:
            item["pct"] = round(item["kwh"] / total * 100.0, 2) if total > 0 else None
        return {
            "io_mode": "share",
            "io_feeder_kwh": round(feeder, 1) if feeder is not None else None,
            "io_panel_incoming_kwh": round(total, 1),
            "io_share_pct": (round(feeder / total * 100.0, 2)
                             if feeder is not None and total > 0 else None),
            "io_incomers": incs,
        }

    # output_only (or an unrecognised/missing mode): no modelled upstream input meter → no loss block (honest-degrade).
    out_kw = _f(c.get("out_kw"))
    return {"io_mode": "output_only",
            "output_kw": round(out_kw, 1) if out_kw is not None else None}
