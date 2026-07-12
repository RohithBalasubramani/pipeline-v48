"""config/app_config.py — DB-backed pipeline/site config. Reads cmd_catalog.app_config ONCE (process-cached on SUCCESS),
casts to the declared type, and falls back to the caller's default when the key is absent or the DB is unreachable. This
makes thresholds / windows / vocab / route-config editable as DB rows without a code edit. [config → DB]

Usage:  from config.app_config import cfg
        THRESHOLD = cfg('validation.null_rate_fail', 1.0)          # number
        WINDOW    = cfg('windows.default_range', 'today')          # text
        VOCAB     = cfg('metrics.keyword_map', {...})              # json

fail-open: a missing key OR any DB error → the passed default (never raises, never blocks import).

NEVER-CACHE-EMPTY [2026-07-12, matches data/ttl_cache.py 2026-07-09]: a FAILED load is NOT cached. If cmd_catalog is
unreachable at the first cfg() call (host booting while :5432 restarts, a reseed in flight, a tunnel flap), the old
`@lru_cache` pinned an empty map for the whole process life — silently reverting EVERY knob (timeouts, guided-json
determinism, TTLs, feature flags, reason templates) to its code default until a manual restart. Now a failure returns
the code defaults for at most `_RETRY_BACKOFF_S` and then self-heals on the next call after cmd_catalog recovers."""
import json
import sys
import time

_CACHE = None            # {key: (value, data_type)} once loaded OK; None until a SUCCESSFUL load (never pins a failure)
_LAST_FAIL = 0.0         # wall-clock of the last failed load — backoff so a dead DB is not hammered every cfg() call
_RETRY_BACKOFF_S = 5.0   # after a failed load, serve code defaults without re-hitting the DB for this long, then retry


def _load():
    """{key: (value, data_type)} from cmd_catalog.app_config, cached per process ONLY on success. Empty dict (NOT cached)
    on any error, with a short retry backoff so the config self-heals once cmd_catalog is reachable again (fail-open)."""
    global _CACHE, _LAST_FAIL
    if _CACHE is not None:
        return _CACHE
    if time.time() - _LAST_FAIL < _RETRY_BACKOFF_S:
        return {}                        # recent failure: fail-open to code defaults without re-hammering the DB
    try:
        # Imports live HERE (not at module top) so `from config.app_config import cfg` is unconditionally safe —
        # a missing driver/DSN degrades to code defaults at call time instead of breaking the importer.
        from data.db_client import q
        from config.databases import CMD_CATALOG
        loaded = {r[0]: (r[1], r[2]) for r in q(CMD_CATALOG, "SELECT key, value, data_type FROM app_config")}
        _CACHE = loaded                  # cache the SUCCESS only
        return _CACHE
    except Exception as e:
        _LAST_FAIL = time.time()
        # Observability: a config fall-open silently reverts every knob to its code default — say so once per backoff.
        print(f"[app_config] cmd_catalog.app_config load FAILED, serving code defaults ({type(e).__name__}: {e})",
              file=sys.stderr)
        return {}                        # NOT cached: the next call after the backoff retries


def _reset():
    """Drop the process cache + failure backoff (test hook / post-seed refresh)."""
    global _CACHE, _LAST_FAIL
    _CACHE = None
    _LAST_FAIL = 0.0


_load.cache_clear = _reset               # back-compat: conftest + reload() call _load.cache_clear()


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


# THE boolean-knob vocabulary (dedup D6, 2026-07-12) — the ONE truthy/falsy token set every flag knob resolves by,
# regardless of the row's declared data_type. Repairs the drifted inline copies: data/equipment/edges.py (and the old
# asset_3d parse) were missing 't' — the natural psql boolean literal — so an operator writing `t` flipped
# llm.guided_json.* on but left equipment.topology.enabled off (an invisible config foot-gun).
_FLAG_ON = ("1", "true", "yes", "t", "on")
_FLAG_OFF = ("0", "false", "no", "f", "off", "none", "")


def flag_on(key, default=False, cfg_fn=None):
    """The row as a BOOLEAN flag: an ON token → True, an OFF token → False, absent row / unrecognized text → `default`
    (so default-on knobs like equipment.facts.enabled keep their fail-open-to-on semantics). Callers with their own
    guarded/test-seamed cfg reader pass it as `cfg_fn` (mirrors llm/transient_retry.no_retry_kinds)."""
    raw = (cfg_fn or cfg)(key, None)
    if raw is None:
        return bool(default)
    s = str(raw).strip().lower()
    if s in _FLAG_ON:
        return True
    if s in _FLAG_OFF:
        return False
    return bool(default)


def reload():
    """Drop the process cache (call after seeding/editing app_config in the same process)."""
    _reset()
