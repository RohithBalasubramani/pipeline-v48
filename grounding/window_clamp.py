"""grounding/window_clamp.py — clamp a card's requested time window to the meter's ACTUAL logged range (NO AI).

THE PROBLEM (DS-02): the live data window is only ~6 days (2026-06-25 → now). Any 30d/90d/YTD card asking for a start
before the first logged row gets a null/blank energy delta with no explanation — the user can't tell "no data yet" from
"broken". Cumulative-energy deltas silently return None when the window start pre-dates the first row.

THE FIX (deterministic): probe the meter's min/max timestamp once, clamp [req_start, req_end] into that range, and
attach a machine reason ('data available from <date>') via config.reason_templates when the window was actually
narrowed or is fully outside the logged range. NEVER extrapolates synthetic history. This NAMES the real bounds; POST
does the fetch.

Covers: DS-02 (+ feeds the window into energy_register / normalizers).
"""
from __future__ import annotations

from config import reason_templates as rt
from config.databases import DATA_DB, DATA_SCHEMA, DATA_TS_CAST, DATA_TS_COL
from data.db_client import q


def _esc(s):
    return str(s).replace("'", "''")


def meter_range(table):
    """(min_ts_iso, max_ts_iso, row_count) for the live neuract table, or (None, None, 0) if empty/absent.
    The single source of a meter's logged extent — read once per card so downstream clamps agree."""
    try:
        rows = q(DATA_DB,
                 f"SELECT min({DATA_TS_COL}{DATA_TS_CAST}), max({DATA_TS_COL}{DATA_TS_CAST}), count(*) "
                 f"FROM {DATA_SCHEMA}.{table}")
    except RuntimeError:
        # table absent → treat as no range (caller honest-degrades). q() already logged the DB error.
        return None, None, 0
    if not rows or not rows[0]:
        return None, None, 0
    mn, mx, cnt = (rows[0] + [None, None, 0])[:3]
    cnt = int(cnt) if str(cnt).strip().isdigit() else 0
    mn = None if mn in (None, "", "NULL") else mn
    mx = None if mx in (None, "", "NULL") else mx
    return mn, mx, cnt


def _date_of(iso):
    """The YYYY-MM-DD date part of a timestamp string (for the human 'data from <date>' sentence)."""
    if not iso:
        return None
    return str(iso).strip().split(" ")[0].split("T")[0]


def window_clamp(table, req):
    """Clamp a requested window to the meter's logged range.

    `table` — the neuract data table_name.
    `req`   — {start_iso, end_iso} requested by the card (either may be None = open-ended).

    Returns a fact-sheet dict (bounds + booleans + reason; NO fetched rows):
        {
          start_iso, end_iso:   <clamped ISO bounds or None>,      # what POST should actually fetch
          req_start, req_end:   <the original request>,
          meter_min, meter_max: <the meter's logged extent>,
          row_count:            <rows in the table>,
          clamped:              bool,   # True → the requested window was narrowed to the logged range
          fully_before:         bool,   # True → the ENTIRE requested window pre-dates the first logged row (no overlap)
          has_data:             bool,   # table has ≥1 row at all
          since:                <YYYY-MM-DD of first logged row, for the reason sentence>,
          reason:               <config 'window_clamped' sentence or None>,
        }
    fully_before → the caller honest-degrades the trailing-window card with the 'data from <since>' reason (this is the
    correct ~6-day-window behaviour, NOT a regression).
    """
    req = req or {}
    req_start, req_end = req.get("start_iso"), req.get("end_iso")
    mn, mx, cnt = meter_range(table)

    out = {
        "start_iso": req_start, "end_iso": req_end,
        "req_start": req_start, "req_end": req_end,
        "meter_min": mn, "meter_max": mx, "row_count": cnt,
        "clamped": False, "fully_before": False, "has_data": cnt > 0,
        "since": _date_of(mn), "reason": None,
    }
    if not mn:                       # empty table → nothing to clamp against.
        return out

    start, end, clamped = req_start, req_end, False

    # clamp the start up to the first logged row.
    if start is None or str(start) < str(mn):
        if start is not None:
            clamped = True
        start = mn
    # clamp the end down to the last logged row.
    if end is None or str(end) > str(mx):
        if end is not None:
            clamped = True
        end = mx

    # the requested window ends before ANY data existed → no overlap at all.
    fully_before = req_end is not None and str(req_end) < str(mn)

    out.update(start_iso=start, end_iso=end, clamped=clamped, fully_before=fully_before)
    if clamped or fully_before:
        out["reason"] = rt.reason("window_clamped", since=_date_of(mn))
    return out
