"""tests/test_regress_ttl_cache.py — pins lib/ttl_cache.TTLCache's expiry contract (audit fix 2, 2026-07-12):
`.get()` must NEVER serve an expired value (it used to — only `in` was TTL-aware, so `.get()`-idiom call sites
served poisoned entries past the TTL), `in` and `.get()` agree, a write REFRESHES the entry's clock, and expired
entries are physically evicted on the next write (bounded memory for unbounded key spaces). Offline +
deterministic — the module's `time` binding is replaced by a hand-advanced fake clock; the TTL is pinned via the
constructor so the DB knob (cache.resolution_ttl_s) is never consulted. [audit_prodready TC-3]"""
import lib.ttl_cache as TT


class _Clock:
    """Stand-in for the `time` module inside lib.ttl_cache — advanced by hand, never sleeps."""

    def __init__(self, now=1000.0):
        self.now = now

    def time(self):
        return self.now


def _cache(monkeypatch, ttl=10):
    clock = _Clock()
    monkeypatch.setattr(TT, "time", clock)
    return clock, TT.TTLCache(ttl=ttl)


def test_get_never_serves_an_expired_value(monkeypatch):
    clock, c = _cache(monkeypatch)
    c["k"] = "v"
    assert "k" in c and c.get("k") == "v"                        # fresh: both idioms serve it
    clock.now += 9.9
    assert c.get("k") == "v"                                     # still inside the TTL
    clock.now += 0.2                                             # now 10.1s old — past the 10s TTL
    assert "k" not in c                                          # `in` reads expired-as-absent...
    assert c.get("k") is None                                    # ...and so does .get() (the 2026-07-12 fix)
    assert c.get("k", "DEFAULT") == "DEFAULT"


def test_write_refreshes_the_entry_clock(monkeypatch):
    clock, c = _cache(monkeypatch)
    c["k"] = "v1"
    clock.now += 8
    c["k"] = "v2"                                                # overwrite → fresh timestamp
    clock.now += 8                                               # 16s after v1, only 8s after v2
    assert c.get("k") == "v2" and "k" in c


def test_expired_entries_evicted_on_next_write(monkeypatch):
    clock, c = _cache(monkeypatch)
    c["a"] = 1
    c["b"] = 2
    clock.now += 11                                              # both expired
    c["c"] = 3                                                   # the write purges opportunistically
    assert not dict.__contains__(c, "a")                         # physically gone (not just TTL-masked)
    assert not dict.__contains__(c, "b")
    assert set(c._ts) == {"c"}                                   # timestamp map pruned too (no leak)
    assert c.get("c") == 3 and len(c) == 1
