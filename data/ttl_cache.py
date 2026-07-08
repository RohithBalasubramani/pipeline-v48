"""data/ttl_cache.py — a drop-in dict whose entries EXPIRE after a TTL. [poison-permanent-fix 2026-07-09]

WHY: the long-running host server (host/server.py, never hot-reloaded) holds per-process resolution caches that ride
the flaky :5433 tunnel (panel members, registry rows/edges, has_data). A single transient tunnel flap could land a
stale/empty value in one of them and — because a plain dict never forgets — serve it for the WHOLE process life, so
panel_aggregate cards stayed blank until someone restarted the server. Guarding every individual empty-cache path is
fragile (and misses future ones). Bounding the LIFETIME of ANY cached entry fixes the whole class at once: a poisoned
entry lives at most `cache.resolution_ttl_s` seconds, then the next request re-reads and self-heals.

CONTRACT: a byte-for-byte drop-in for a plain `{}` at the cache sites (`if k in cache: return cache[k]` /
`cache[k] = v`). `k in cache` becomes False once the entry is older than the TTL — the caller then re-reads and
overwrites in place. No deletion on expiry (avoids a check-then-get KeyError under the threading server); a fresh
`__setitem__` overwrites the stale value + restamps. TTL = the DB knob cache.resolution_ttl_s (code default 120s),
read lazily + fail-open so a DB outage can't break the cache itself. Healthy state is unaffected (re-read at most once
per TTL; the underlying reads are cheap local-mirror queries). [atomic; never raises from the cache path]
"""
import time

_TTL_DEFAULT = 120


def _cfg_ttl():
    try:
        from config.app_config import cfg
        v = int(cfg("cache.resolution_ttl_s", _TTL_DEFAULT))
        return v if v > 0 else _TTL_DEFAULT
    except Exception:
        return _TTL_DEFAULT


class TTLCache(dict):
    """Plain-dict semantics + per-entry expiry. `ttl` None → the DB knob (cache.resolution_ttl_s); an int pins it."""

    def __init__(self, ttl=None):
        super().__init__()
        self._ts = {}
        self._ttl = ttl

    def _ttl_s(self):
        return self._ttl if self._ttl is not None else _cfg_ttl()

    def __contains__(self, k):
        try:
            return super().__contains__(k) and (time.time() - self._ts.get(k, 0.0)) < self._ttl_s()
        except Exception:
            return False

    def __setitem__(self, k, v):
        try:
            self._ts[k] = time.time()
        except Exception:
            pass
        super().__setitem__(k, v)
