"""data/equipment/db.py — the ONE door to the local `equipment` schema (cmd_catalog :5432).

SINGLE-DOOR RULE: no `FROM equipment.` / `JOIN equipment.` SQL anywhere outside data/equipment/*.py and
db/seed_equipment_*.sql — enforced case-insensitively by tests/test_equipment_disposition.py (tests exempt).
UTF-8 RULE: never print row text raw to stdout (surrogate crash) — counts / ASCII paraphrase only; use
encode('ascii','replace') when sampling. Error lines written here are ASCII-safe already.

No app_config knob lives in this module — gating belongs to the consuming modules (bridge/edges/ratings/
kitpreview) so the accessor stays a pure reader. Failures are NEVER cached: a transient :5432 blip returns
empty for THIS call and the next call retries (a long-running host is never permanently poisoned).
"""
import sys

from config.databases import CMD_CATALOG
from data.db_client import q

# equipment.mfm columns fetched by mfm_by_table(), in SELECT order (zip target for the row dicts).
_MFM_COLS = (
    "id", "name", "role", "table_name", "section", "zone", "load_profile", "asset_category",
    "rated_capacity_kva", "energy_direction", "energy_scale", "power_scale",
    "equipment_id", "reference_id", "data_source_id",
)

_CACHE = {}


def eq_q(sql):
    """Raw rows from cmd_catalog (raises like q — call sites wrap fail-open)."""
    return q(CMD_CATALOG, sql)


def mfm_by_table():
    """dict: table_name -> [row-dict, ...] over ALL equipment.mfm rows (dups PRESERVED — alias building
    needs them), built once per process in ONE SELECT. {} for THIS call on DB error (failure NOT cached)."""
    if "mfm_by_table" in _CACHE:
        return _CACHE["mfm_by_table"]
    try:
        rows = eq_q(f"SELECT {', '.join(_MFM_COLS)} FROM equipment.mfm")
    except Exception as e:  # noqa: BLE001 — fail-open by contract; never raises to callers
        sys.stderr.write("[equipment.db] mfm_by_table read failed (%s); returning {} (not cached)\n"
                         % type(e).__name__)
        return {}
    by_table = {}
    for r in rows:
        d = dict(zip(_MFM_COLS, r))
        # csv rows are all-text: '' -> None so callers get honest misses, not empty strings
        d = {k: (v if v != "" else None) for k, v in d.items()}
        by_table.setdefault(d["table_name"], []).append(d)
    _CACHE["mfm_by_table"] = by_table
    return by_table


def unique_mfm_row(table_name):
    """THE bridge: the single equipment.mfm row for a canonical table_name; None when absent OR duplicated
    (the 18 dual-view table groups) OR DB down. Never raises."""
    rows = mfm_by_table().get(table_name)
    if not rows or len(rows) != 1:
        return None
    return rows[0]


def clear_cache():
    """Tests + operational reload (mirrors config/app_config.reload)."""
    _CACHE.clear()
