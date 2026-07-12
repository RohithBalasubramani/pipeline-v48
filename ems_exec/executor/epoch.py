"""ems_exec/executor/epoch.py — the ONE 'this magnitude is an epoch-ms timestamp' heuristic for the axis passes.

yscale and xaxis each carried a private `_is_epoch_list` with a raw `> 1e10` literal; the floor is now the DB knob
chart.epoch_list_floor (code default 1e10, preserving both passes' behavior byte-for-byte).

DELIBERATELY DISTINCT from fab_guards.epoch_ms_floor (1e12) — CLOSED as two heuristics, not one (audit closeout
2026-07-12): this floor asks "does this LIST look like a timestamp axis?" (a lenient shape test over ≥2 values —
1e10 admits epoch-seconds-scale and near-past ms values so a plausible axis is never mis-scaled as data), while the
CLASS-1 guard asks "is this SINGLE rendered value certainly a leaked epoch-ms artifact?" (a strict per-value
fabrication verdict — 1e12 ≈ 2001 in ms, safely above every real kW/kWh/V/A reading). Tightening this floor to 1e12
would mis-scale second-resolution axes; loosening the guard to 1e10 would null real cumulative-kWh-scale outliers.
Do NOT unify the two knobs. xaxis additionally requires the list to be non-decreasing — that predicate stays local."""


def epoch_list_floor():
    """The numeric floor above which a list element counts as an epoch-ms timestamp. Never raises."""
    try:
        from config.app_config import cfg
        return float(cfg("chart.epoch_list_floor", 1e10))
    except Exception:
        return 1e10


def is_epoch_number_list(v):
    """A list of ≥2 numbers (bools excluded) all above the epoch floor — the shared core of the axis passes' checks."""
    if not (isinstance(v, list) and len(v) >= 2):
        return False
    floor = epoch_list_floor()
    return all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > floor for x in v)
