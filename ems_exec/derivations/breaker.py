"""derivations/breaker.py — breaker OVERLOAD % (worst-case current ÷ breaker rating_a × 100).

The denominator is the feeder's REAL breaker rating read via data/equipment/ratings (the equipment-schema breaker
table, uniquely bridged by the asset's canonical table_name) — NEVER a defaulted/typical rating: the 133 NULL-rating
rows honest-degrade the whole fn (empty-denominator gate). BASIS: max-phase where phase columns are present in the
ctx frame, else average-phase — average understates a single-phase overload, so max-phase wins whenever the frame
allows it (the basis is STATED in the fn's library note so the AI can never present average as worst-case).

DEFAULT OFF (cert sequencing): the whole fn gates on the cmd_catalog app_config row `equipment.derivations.enabled`
(code default 'off') — off → None outright, and registry.catalog() omits the entry at the SOURCE so certified
prompts never see it [fatal R2-2 fix]. Never raises; every miss → None (honest-degrade, never fabricate)."""
from __future__ import annotations

# same normalized OFF vocabulary as layer2/emit/morphmap/mode.py — absent row / outage / 'off' → disabled
_OFF = ("off", "", "0", "false", "no", "none")

# the neuract per-phase current family the max-phase basis scans for in the ctx frame
_PHASE_COLS = ("current_r", "current_y", "current_b")


def enabled():
    """True ONLY when the `equipment.derivations.enabled` row was deliberately flipped on (code default 'off').
    Shared by this fn body AND registry.catalog()'s source gate so the offer and the execution can never disagree."""
    try:
        from config.app_config import cfg
        return str(cfg("equipment.derivations.enabled", "off")).strip().lower() not in _OFF
    except Exception:
        return False


def _asset_table(ctx):
    """_ctx_table-style asset resolution (mirrors registry's nameplate fns), PLUS ctx['name'] — the executor's
    derived path carries the resolved table under `name` (see executor/derived.py's ctx build). A non-table value
    lands on a breaker-rating miss → honest None."""
    ctx = ctx or {}
    return (ctx.get("asset_table") or ctx.get("table")
            or (ctx.get("row") or {}).get("asset_table") or ctx.get("name"))


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _current_basis(ctx):
    """The overload numerator from the ctx frame: MAX over whichever per-phase current columns the row carries
    (resolved by name at runtime), else current_avg. None when the frame has no current at all."""
    row = (ctx or {}).get("row") or {}
    phases = [f for f in (_num(row.get(c)) for c in _PHASE_COLS) if f is not None]
    if phases:
        return max(phases)
    return _num(row.get("current_avg"))


def overload_pct(ctx):
    """Breaker overload % = current basis ÷ rating_a × 100. None unless a current value AND a positive real
    rating_a exist (the empty-denominator gate: NULL/absent/dup-table rating never gets a default), and None
    outright when the equipment.derivations knob is off. Never raises."""
    if not enabled():
        return None
    table = _asset_table(ctx)
    if not table:
        return None
    try:
        from data.equipment import ratings as _ratings
        rating = _num((_ratings.breaker_rating(table) or {}).get("rating_a"))
    except Exception:
        return None
    if rating is None or rating <= 0:
        return None
    cur = _current_basis(ctx)
    if cur is None:
        return None
    return round(cur / rating * 100.0, 1)
