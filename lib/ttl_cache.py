"""lib/ttl_cache.py — a drop-in dict whose entries EXPIRE after a TTL. [poison-permanent-fix 2026-07-09]

WHY: the long-running host server (host/server.py, never hot-reloaded) holds per-process resolution caches that ride
the flaky :5433 tunnel (panel members, registry rows/edges, has_data). A single transient tunnel flap could land a
stale/empty value in one of them and — because a plain dict never forgets — serve it for the WHOLE process life, so
panel_aggregate cards stayed blank until someone restarted the server. Guarding every individual empty-cache path is
fragile (and misses future ones). Bounding the LIFETIME of ANY cached entry fixes the whole class at once: a poisoned
entry lives at most `cache.resolution_ttl_s` seconds, then the next request re-reads and self-heals.

CONTRACT: a drop-in for a plain `{}` at the cache sites — BOTH the `if k in cache: return cache[k]` idiom AND `.get(k)`
are TTL-aware (an expired entry reads as absent through either). `k in cache` becomes False once the entry is older
than the TTL — the caller then re-reads and overwrites in place. Expired entries are purged opportunistically on the
next `__setitem__` (not on the expiry check itself, so the check-then-get path never KeyErrors under the threading
server); this also bounds memory for unbounded key spaces (e.g. frozenset-of-tables keys). TTL = the DB knob
cache.resolution_ttl_s (code default 120s), read lazily + fail-open so a DB outage can't break the cache itself.
Healthy state is unaffected (re-read at most once per TTL; the underlying reads are cheap local-mirror queries).
[atomic; never raises from the cache path]
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

    def get(self, k, default=None):
        """TTL-aware get: an expired entry reads as absent (mirrors __contains__), so callers using the `.get()` idiom
        are safe too — not only the `if k in c: return c[k]` one. [2026-07-12: was serving expired values silently]"""
        return super().get(k) if self.__contains__(k) else default

    def __setitem__(self, k, v):
        # value FIRST, then the timestamp: a concurrent reader between the two statements sees the entry still expired
        # (old ts) rather than a fresh ts pointing at a half-written value.
        super().__setitem__(k, v)
        try:
            self._ts[k] = time.time()
        except Exception:
            pass
        self._purge_expired()

    def _purge_expired(self):
        """Opportunistically drop expired entries on write so an unbounded key space (e.g. frozenset-of-tables keys)
        cannot grow for the whole process life. Best-effort; never raises from the cache path."""
        try:
            ttl = self._ttl_s()
            now = time.time()
            dead = [k for k, ts in list(self._ts.items()) if now - ts >= ttl]
            for k in dead:
                super().pop(k, None)
                self._ts.pop(k, None)
        except Exception:
            pass
