"""grounding/energy_register.py — pick the CORRECT cumulative-energy register for a meter (import vs export).

THE PROBLEM (DS-05, DID-01, VC-01, VC-06): 9 meters have `active_energy_import_kwh` uniformly ~0 while all real
energy lives in `active_energy_export_kwh` (reversed CT on a net-import feeder). Every energy derivation
(windowEnergyKwh / todaysEnergyTotalKwh) reads only the import column → the card renders a confidently WRONG 0 kWh,
hiding a real 300+ MWh throughput.

THE FIX (deterministic, no AI): probe the meter's latest cumulative import vs export; if import ≤ `reversed_ct_import_max`
AND export > that threshold, this is a reversed-CT meter → bind the EXPORT register and raise `reversed_ct`. Otherwise
bind the normal import register. Thresholds come from `config.quality_policy` (editable rows), the reason sentence from
`config.reason_templates`. This NAMES a real column — it never emits a fetched number.

Covers: DS-05, DID-01, VC-01, VC-06.
"""
from __future__ import annotations

from config import quality_policy as qp
from config import reason_templates as rt
from config.databases import DATA_DB, DATA_SCHEMA, DATA_TS_CAST, DATA_TS_COL
from data.db_client import q

# the two cumulative energy columns this rule chooses between (the register pair).
IMPORT_COL = "active_energy_import_kwh"
EXPORT_COL = "active_energy_export_kwh"


def _num(x):
    if x in (None, "", "NULL"):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _esc(s):
    return str(s).replace("'", "''")


def _has_column(table, column):
    """True if `column` exists on the live neuract table (schema probe — never assume the register pair is present)."""
    rows = q(DATA_DB,
             "SELECT 1 FROM information_schema.columns "
             f"WHERE table_schema='{_esc(DATA_SCHEMA)}' AND table_name='{_esc(table)}' "
             f"AND column_name='{_esc(column)}' LIMIT 1")
    return bool(rows)


def _latest(table, column):
    """The latest (most-recent-timestamp) value of `column` on the live table, or None if empty/absent."""
    if not _has_column(table, column):
        return None
    rows = q(DATA_DB,
             f"SELECT {column} FROM {DATA_SCHEMA}.{table} "
             f"WHERE {column} IS NOT NULL "
             f"ORDER BY {DATA_TS_COL}{DATA_TS_CAST} DESC LIMIT 1")
    return _num(rows[0][0]) if rows else None


def energy_register(table, window=None):
    """Decide which cumulative energy register a meter's energy derivations should read.

    `table`  — the neuract data table_name (e.g. 'gic_01_n3_ups_01_p1').
    `window` — optional {start_iso, end_iso}; when given, the import/export test uses the window's END value so a
               window that pre-dates the reversal still routes correctly. Absent → uses the meter's latest row.

    Returns a fact-sheet dict (NO fetched energy number, only the chosen column NAME + booleans + reason):
        {
          register:      'import' | 'export',   # which register energy derivations should bind
          energy_column: <the real column name>,# active_energy_import_kwh | active_energy_export_kwh
          reversed_ct:   bool,                   # True → import≈0 ∧ export>0 (reversed-CT feeder)
          has_import, has_export: bool,          # whether each register column exists at all
          import_present, export_present: bool,  # whether each register has a non-null latest value
          reason: <human sentence or None>,      # config.reason_templates 'reversed_ct' when flipped
          fidelity_note: <short tag or None>,    # 'export register (reversed CT)' when flipped
        }
    When NEITHER register column exists, register/energy_column are None and the caller honest-degrades the energy slot.
    """
    import_max = qp.num("reversed_ct_import_max", 1.0)

    has_import = _has_column(table, IMPORT_COL)
    has_export = _has_column(table, EXPORT_COL)

    imp = _latest_at(table, IMPORT_COL, window)
    exp = _latest_at(table, EXPORT_COL, window)

    out = {
        "register": None, "energy_column": None, "reversed_ct": False,
        "has_import": has_import, "has_export": has_export,
        "import_present": imp is not None, "export_present": exp is not None,
        "reason": None, "fidelity_note": None,
    }

    # reversed-CT test: import at/near zero (≤ policy threshold) AND export carries real throughput (> threshold).
    reversed_ct = (
        has_export and exp is not None and exp > import_max
        and (imp is None or imp <= import_max)
    )

    if reversed_ct:
        out.update(register="export", energy_column=EXPORT_COL, reversed_ct=True,
                   reason=rt.reason("reversed_ct"),
                   fidelity_note="export register (reversed CT)")
    elif has_import:
        out.update(register="import", energy_column=IMPORT_COL)
    elif has_export:
        # no import register at all but export exists → still bind export (honest, tagged).
        out.update(register="export", energy_column=EXPORT_COL,
                   fidelity_note="export register (no import column)")
    # else: neither column exists → both None → caller honest-degrades.
    return out


def _latest_at(table, column, window):
    """Latest value of `column`, optionally clamped to the END of `window` (so a historical window routes the register
    by the value AT that window end, not by 'now'). Falls back to the meter's latest row when no window is given."""
    if not window or not window.get("end_iso"):
        return _latest(table, column)
    if not _has_column(table, column):
        return None
    end_iso = _esc(window["end_iso"])
    rows = q(DATA_DB,
             f"SELECT {column} FROM {DATA_SCHEMA}.{table} "
             f"WHERE {column} IS NOT NULL AND {DATA_TS_COL}{DATA_TS_CAST} <= '{end_iso}'{DATA_TS_CAST} "
             f"ORDER BY {DATA_TS_COL}{DATA_TS_CAST} DESC LIMIT 1")
    return _num(rows[0][0]) if rows else _latest(table, column)


def energy_column_for(table, window=None):
    """Convenience: just the chosen real energy column NAME (or None) — for derivation binding that only needs the
    column, not the whole fact-sheet."""
    return energy_register(table, window)["energy_column"]
