"""ems_exec/renderers/_story/_facts.py — the shared NEURACT fact-gathering helpers the per-page story builders reuse.

Single concern: turn a scoped asset + panel-fan-out into REAL per-member metric snapshots and window energy deltas, read
ONLY from neuract (ems_exec.data.neuract) via the fan-out door (data.lt_panels.panel_members) with the registry meter
name as the label. Every read honest-degrades: a missing table / column / value → None (never fabricated). The builders
then compute their own Python verdicts over these facts — this file NEVER judges, it only gathers.

NO simulator, NO legacy EMS service. Members come from the ONE fan-out door (panel_members.panel_members); a single-asset scope
with no members degrades to a one-member "self" list so the RTM/feeder builders still have a subject to narrate.
[atomic; DB-driven-underneath; honest-degrade]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx

# the canonical live-electrical columns every story reads (only the ones a table physically has are fetched — the rest
# pad → None, so a table missing a metric honest-blanks that verdict rather than crashing).
LIVE_COLS = [
    "active_power_total_kw", "reactive_power_total_kvar", "apparent_power_total_kva",
    "power_factor_total", "kpi_true_pf",
    "voltage_avg", "current_avg", "frequency_hz",
    "voltage_unbalance_pct", "current_unbalance_pct",
    "kpi_voltage_deviation_pct",
    "thd_voltage_r_pct", "thd_voltage_y_pct", "thd_voltage_b_pct",
    "thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct",
    "thd_compliance_v_avg", "thd_compliance_i_avg",
]

ENERGY_IMPORT_KWH = "active_energy_import_kwh"
REACTIVE_IMPORT_KVARH = "reactive_energy_import_kvarh"


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def sev_warn_fraction():
    """The 'warn at this fraction of the limit' severity policy the story builders share (voltage_current,
    harmonics_pq). DB-editable as story.sev_warn_fraction; code default 0.7. Never raises."""
    try:
        from config.app_config import cfg
        return float(cfg("story.sev_warn_fraction", 0.7))
    except Exception:
        return 0.7


def resolve_members(ctx):
    """The de-duplicated, has_data-filtered LEAF members of the scoped asset, each {mfm_id, name, table, reporting}.

    Uses the ONE fan-out door (data.lt_panels.panel_members). When the scope is a single asset with no outgoing edges
    (orphaned) OR the door is unavailable, degrades to a single "self" member built from ctx (so a per-feeder story
    still has a subject). Names come from the registry; honest-degrade to the table name / mfm id on a stale lookup."""
    mfm_id = ctx.get("mfm_id")
    self_member = {
        "mfm_id": mfm_id,
        "name": _name_for(mfm_id) or ctx.get("asset_table") or (str(mfm_id) if mfm_id is not None else "asset"),
        "table": ctx.get("asset_table"),
        "reporting": bool(ctx.get("asset_table")),
    }
    if mfm_id is None:
        return [self_member], {"orphaned": True, "reporting_count": self_member["reporting"], "expected_count": 1}

    res = _panel_members(int(mfm_id))
    if res is None or res.get("orphaned") or not res.get("members"):
        # single-asset / unmapped topology → narrate the asset itself (honest single-member story)
        return [self_member], {
            "orphaned": bool(res.get("orphaned") if res else True),
            "reporting_count": 1 if self_member["reporting"] else 0,
            "expected_count": 1,
        }
    out = []
    for m in res["members"]:
        mid = m.get("mfm_id")
        out.append({
            "mfm_id": mid,
            "name": _name_for(mid) or (m.get("table") or str(mid)),
            "table": m.get("table"),
            "reporting": bool(m.get("reporting")),
        })
    return out, {
        "orphaned": False,
        "reporting_count": res.get("reporting_count", 0),
        "expected_count": res.get("expected_count", len(out)),
    }


def live_snapshot(table):
    """The latest live-electrical row for a member table → {col: value|None}. {} for no table (honest-degrade)."""
    if not table:
        return {}
    return _nx.latest(table, LIVE_COLS) or {}


def energy_delta(table, window):
    """(kwh, kvarh) counter delta over the window for a member table, or (None, None) — honest-degrade, never faked.

    Reads the window baselines (first row at/after start, last row at/before end) and deltas the import counters; a
    non-monotonic / missing baseline → None for that leg (kVAh then hypots with 0, matching the backend2 semantics)."""
    if not table:
        return None, None
    start, end = (window or (None, None))[0], (window or (None, None))[1]
    first, last = _nx.window(table, [ENERGY_IMPORT_KWH, REACTIVE_IMPORT_KVARH], start, end)
    return _delta(first, last, ENERGY_IMPORT_KWH), _delta(first, last, REACTIVE_IMPORT_KVARH)


def _delta(first, last, col):
    a, b = _num((first or {}).get(col)), _num((last or {}).get(col))
    if a is None or b is None:
        return None
    d = b - a
    return d if d >= 0 else None      # a negative counter delta = a meter reset / gap → honest None, never a fake number


def snapshots_for(members):
    """[{**member, **live_snapshot}] for every reporting member (skips a member with no table). Non-reporting members
    are still returned WITHOUT a snapshot so the caller can honestly report the coverage denominator."""
    out = []
    for m in members:
        snap = live_snapshot(m.get("table")) if m.get("reporting") else {}
        out.append({**m, "live": snap})
    return out


# ── registry / fan-out doors (imported lazily so this module stays import-safe if a registry is mid-edit) ─────────────
def _name_for(mfm_id):
    if mfm_id is None:
        return None
    try:
        from data.neuract_live import meters as _meters
        return _meters.name_for(mfm_id)
    except Exception:
        return None


def _panel_members(mfm_id):
    try:
        from data.lt_panels.panel_members import panel_members
        return panel_members(mfm_id)
    except Exception:
        return None
