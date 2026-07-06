"""config/event_thresholds.py — thin reader over cmd_catalog.event_threshold (the numeric power-quality event bands).

The simulator's boolean ``*_event_active`` flags never fire, so the V&C
event_timeline / sag-swell KPIs must detect events off the RAW numeric columns
crossing their statutory limits (services.fetch_events.fetch_threshold_events,
P0 #7). Every band lives here as an EDITABLE ROW — column name + crossing
direction ('below'|'above') + threshold — so an engineer retunes IS-12360 /
IEEE-1159 / IEEE-519 limits by editing a row, NOT a magic number in a consumer.

Each row is one detector spec keyed by ``alias`` (the wire event type):
  * ``column_name`` — the physical numeric column the crossing is measured on
  * ``direction``   — 'below' (falling crossing, e.g. sag) | 'above' (rising)
  * ``num_value``   — the threshold value

Fallback: a missing row / unreachable DB → the code default below (never raises,
never blocks import) — mirrors config.quality_policy / config.nameplates.

Accessors:
  num(alias, default)   — the threshold number for an alias, or default
  txt(alias, default)   — the crossing direction for an alias, or default
  column(alias, default) — the physical column name for an alias, or default
  specs(aliases)        — [(alias, column, direction, threshold), ...] ready for
                          fetch_threshold_events (skips any alias with no
                          resolvable column/direction/threshold — honest-degrade)
"""
from data.db_client import q


# ── Code-default bands (the fallback when the DB row is absent / DB is down) ──
# Ported verbatim from backend2 panels.consumers.{voltagecurrent,powerquality,
# derived}.EVENT_THRESHOLDS. (column_name, direction, threshold).
#   SAG/SWELL  — IS-12360 / IEEE-1159 ±10% sustained voltage deviation
#   I_UNBAL    — current-unbalance % statutory limit
#   NEUTRAL    — neutral-current stress (A)
#   I_THD/V_THD— IEEE-519 harmonic-distortion compliance headroom (%)
#   TRUE_PF    — true-power-factor floor (below → PF-gap event)
_DEFAULTS: dict[str, tuple[str, str, float]] = {
    'SAG':      ('kpi_voltage_deviation_pct', 'below', -10.0),
    'SWELL':    ('kpi_voltage_deviation_pct', 'above',  10.0),
    'I_UNBAL':  ('current_unbalance_pct',     'above',  10.0),
    'NEUTRAL':  ('current_neutral',           'above',  30.0),
    'I_THD':    ('thd_compliance_i_avg',      'above',   8.0),
    'V_THD':    ('thd_compliance_v_avg',      'above',   5.0),
    'TRUE_PF':  ('kpi_true_pf',               'below',   0.9),
}


def _row(alias):
    """The (column_name, direction, num_value) DB row for ``alias`` → dict, or None (missing row / DB down)."""
    try:
        rows = q("cmd_catalog",
                 "SELECT column_name, direction, num_value FROM event_threshold "
                 f"WHERE alias='{_esc(alias)}'")
    except Exception:
        return None
    if not rows:
        return None
    col, direction, num = rows[0]
    return {
        "column_name": (None if col in (None, "", "NULL") else col),
        "direction":   (None if direction in (None, "", "NULL") else direction),
        "num_value":   (None if num in (None, "", "NULL") else float(num)),
    }


def num(alias, default=None):
    """The threshold number for ``alias`` (e.g. SAG=-10), or the code-default / caller ``default``."""
    r = _row(alias)
    if r is not None and r["num_value"] is not None:
        return r["num_value"]
    d = _DEFAULTS.get(alias)
    if d is not None:
        return d[2]
    return default


def txt(alias, default=None):
    """The crossing direction ('below'|'above') for ``alias``, or the code-default / caller ``default``."""
    r = _row(alias)
    if r is not None and r["direction"] is not None:
        return r["direction"]
    d = _DEFAULTS.get(alias)
    if d is not None:
        return d[1]
    return default


def column(alias, default=None):
    """The physical numeric column ``alias`` is measured on, or the code-default / caller ``default``."""
    r = _row(alias)
    if r is not None and r["column_name"] is not None:
        return r["column_name"]
    d = _DEFAULTS.get(alias)
    if d is not None:
        return d[0]
    return default


def spec(alias):
    """(alias, column, direction, threshold) for one alias, or None if any part is unresolvable (honest-degrade)."""
    col = column(alias, None)
    direction = txt(alias, None)
    thr = num(alias, None)
    if col is None or direction is None or thr is None:
        return None
    return (alias, col, direction, float(thr))


def specs(aliases):
    """[(alias, column, direction, threshold), ...] for ``aliases`` — ready to hand to fetch_threshold_events.

    Any alias that can't be fully resolved (no column / direction / threshold in the row OR the code default) is
    dropped rather than fabricated — the detector then simply won't count that event type. [honest-degrade]"""
    out = []
    for a in aliases:
        s = spec(a)
        if s is not None:
            out.append(s)
    return out


def _esc(s):
    return str(s).replace("'", "''")
