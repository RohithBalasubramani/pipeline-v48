"""config/policy_read.py — the ONE set of mechanics for reading cmd_catalog.data_quality_policy scalar knobs.

The per-namespace policy modules (quality_policy, energy_balance_policy, feeder_overview, topology_policy, …) STAY —
each owns its key namespace + code-default mirrors per the atomic rule. What lives here is only the shared plumbing
they all copy-pasted: the SQL-quote escape and the fail-open num/txt row read. NOTE: config/quality_policy.num/txt
deliberately keep their RAISING semantics (topology_policy documents wrapping them); these readers never raise."""


def esc(s):
    """SQL single-quote escape for an interpolated key (the psql-subprocess reader takes no bind params)."""
    return str(s).replace("'", "''")


def _rows(sql):
    """cmd_catalog read that NEVER raises: [] on any failure (DB down / table absent) so accessors fall back.
    db_client.q is imported lazily to keep importers import-safe and framework-free."""
    try:
        from data.db_client import q
        return q("cmd_catalog", sql)
    except Exception:
        return []


def _appcfg(key):
    """The app_config value for `key` (cast to its declared data_type), or None. app_config is the CANONICAL
    scalar-knob home [config F6 consolidation, 2026-07-12]; the data_quality_policy reads below are the transition
    fallback. Type-discriminated by the caller: a 'number' row serves num(), a 'text' row serves txt() — so a
    migrated one-column row can never leak into the other accessor. Never raises."""
    try:
        from config.app_config import cfg
        return cfg(key, None)
    except Exception:
        return None


def num(key, fallback=None):
    """The numeric knob for `key`: app_config first (canonical home), else the legacy data_quality_policy row,
    else `fallback` (also on blank rows / DB down)."""
    v = _appcfg(key)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    rows = _rows(f"SELECT num_value FROM data_quality_policy WHERE key='{esc(key)}'")
    if not rows or rows[0][0] in (None, "", "NULL"):
        return fallback
    try:
        return float(rows[0][0])
    except (TypeError, ValueError):
        return fallback


def txt(key, fallback=None):
    """The text knob for `key`: app_config first (canonical home), else the legacy data_quality_policy row,
    else `fallback` (also on blank rows / DB down)."""
    v = _appcfg(key)
    if isinstance(v, str) and v.strip() not in ("", "NULL"):
        return v
    rows = _rows(f"SELECT txt_value FROM data_quality_policy WHERE key='{esc(key)}'")
    if not rows or rows[0][0] in (None, "", "NULL"):
        return fallback
    return rows[0][0]
