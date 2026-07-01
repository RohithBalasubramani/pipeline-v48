"""config/app_config.py — DB-backed pipeline/site config. Reads cmd_catalog.app_config ONCE (process-cached), casts to
the declared type, and falls back to the caller's default when the key is absent or the DB is unreachable. This makes
thresholds / windows / vocab / route-config editable as DB rows without a code edit. [config → DB]

Usage:  from config.app_config import cfg
        THRESHOLD = cfg('validation.null_rate_fail', 1.0)          # number
        WINDOW    = cfg('windows.default_range', 'today')          # text
        VOCAB     = cfg('metrics.keyword_map', {...})              # json

fail-open: a missing key OR any DB error → the passed default (never raises, never blocks import)."""
import json
from functools import lru_cache

from data.db_client import q
from config.databases import CMD_CATALOG


@lru_cache(maxsize=1)
def _load():
    """{key: (value, data_type)} from cmd_catalog.app_config, cached per process. Empty dict on any error (fail-open)."""
    try:
        return {r[0]: (r[1], r[2]) for r in q(CMD_CATALOG, "SELECT key, value, data_type FROM app_config")}
    except Exception:
        return {}


def _cast(val, dt, default):
    try:
        if dt == "number":
            return float(val)
        if dt == "int":
            return int(float(val))
        if dt == "bool":
            return str(val).strip().lower() in ("1", "true", "yes", "t", "on")
        if dt == "json":
            return json.loads(val)
        return val
    except Exception:
        return default


def cfg(key, default):
    """DB value for `key` (cast to its data_type), else `default`. The default is the current hardcoded constant, so a
    call is DB-driven yet behaves identically until a row exists. Editing the row changes behavior with no code change."""
    row = _load().get(key)
    if row is None:
        return default
    return _cast(row[0], row[1], default)


def reload():
    """Drop the process cache (call after seeding/editing app_config in the same process)."""
    _load.cache_clear()
