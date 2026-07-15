"""fab_guards/knobs.py — the DB-knob accessors + the shared gap helpers every guard class reads: guard on/off
valves (fab_guards.<name>), the epoch-ms floor, the CLASS-1 time-axis token exemption vocab, the reason-template
renderer and the numeric predicate. One concern; every sibling class module builds on these."""
from __future__ import annotations

# ── DB knobs (code defaults) ──────────────────────────────────────────────────────────────────────────────────────────
def _epoch_floor():
    """The magnitude at/above which a bare number is treated as an epoch-MILLIS timestamp. 1e12 ms ≈ year 2001; every
    real EMS reading (kW/kWh/V/A/%/count/pf) sits many orders below it. DB knob fab_guards.epoch_ms_floor.
    DELIBERATELY DISTINCT from chart.epoch_list_floor (1e10, executor/epoch.py) — that one is a lenient LIST-shape
    test for axis detection; this one is a strict per-VALUE fabrication verdict. Do NOT unify (closed 2026-07-12;
    rationale in epoch.py's module doc)."""
    try:
        from config.app_config import cfg
        return float(cfg("fab_guards.epoch_ms_floor", 1_000_000_000_000))   # 1e12
    except Exception:
        return 1_000_000_000_000.0


def _guard_on(name):
    """Per-class valve (default on) — fab_guards.<name> == 'off' disables ONE class without a code change."""
    try:
        from config.app_config import cfg
        return str(cfg(f"fab_guards.{name}", "on")).strip().lower() != "off"
    except Exception:
        return True


# ── time-axis token set (CLASS 1 exemption) ─────────────────────────────────────────────────────────────────────────
# A leaf whose key is a designated TIME axis is ALLOWED to hold epoch ms. Union of the DB time_axis_keys vocab and the
# closed token set the contract names (…ticks/…labels/…indexes/…timestamps/axisStart/axisEnd/ts/time + a per-element
# point label/time key). Matched case-insensitively by suffix so mislabels on value/scale keys (maxLine/expectedMax/
# valuePct) never qualify. BOTH token sets are DB-driven (fab_guards.time_axis_suffixes / .time_axis_exact) with the
# code-default mirrors below — no hardcoded key list steers the CLASS-1 exemption.
_TIME_SUFFIXES_DEFAULT = ("ticks", "labels", "indexes", "timestamps", "timestamp",
                          "axisstart", "axisend", "axisstartms", "axisendms", "startms", "endms")
_TIME_EXACT_DEFAULT = ("ts", "time", "label")


def _time_axis_suffixes():
    """The key SUFFIXES that mark a leaf as a designated TIME axis (…ticks/…labels/…indexes/…timestamps/…startMs): a
    leaf whose key ENDS WITH one of these is allowed to hold epoch ms (CLASS-1 exemption). DB knob
    fab_guards.time_axis_suffixes (JSON list, lowercased) with the code-default mirror. Returned as a TUPLE for
    str.endswith()."""
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.time_axis_suffixes", None)
        if rows:
            return tuple(str(s).strip().lower() for s in rows)
    except Exception:
        pass
    return _TIME_SUFFIXES_DEFAULT


def _time_axis_exact():
    """The EXACT (whole-key) time-axis tokens (ts/time/label): a leaf whose key IS one of these is a time axis. DB knob
    fab_guards.time_axis_exact (JSON list, lowercased) with the code-default mirror."""
    try:
        from config.app_config import cfg
        rows = cfg("fab_guards.time_axis_exact", None)
        if rows:
            return {str(s).strip().lower() for s in rows}
    except Exception:
        pass
    return set(_TIME_EXACT_DEFAULT)


def _is_time_axis_key(key):
    k = (key or "").lower()
    if k in _time_axis_exact() or k.endswith(_time_axis_suffixes()):
        return True
    try:
        from config.vocab import vocab
        keys = {str(x).lower() for x in (vocab("time_axis_keys") or [])}
    except Exception:
        keys = set()
    return k in keys


def _reason(cause, metric, **kw):
    """The editable cmd_catalog.reason_template sentence for a machine cause; code-default to the cause key on outage.
    Extra kwargs pass through to the template — null_column_reading's {column} placeholder rendered LITERALLY in
    every served sentence because the column never reached the formatter [audit 2026-07-14, 11 F4]."""
    try:
        from config.reason_templates import reason as _r
        return _r(cause, metric=metric, **kw)
    except Exception:
        return cause


def _add_gap(gaps, slot, cause, metric, column=None):
    gaps.append({"slot": slot, "cause": cause, "metric": str(metric), "column": column, "fn": None,
                 "reason": _reason(cause, metric, **({"column": column} if column is not None else {}))})


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  CLASS 1 — EPOCH-MILLIS TIME-LEAK — scan the WHOLE payload; blank a non-time leaf holding an epoch-ms magnitude.
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
