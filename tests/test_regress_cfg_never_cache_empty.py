"""tests/test_regress_cfg_never_cache_empty.py — pins config/app_config.py's NEVER-CACHE-EMPTY contract
(audit fix 1, 2026-07-12): a FAILED app_config load must NOT be cached (the old @lru_cache pinned an empty
map for the process life, silently reverting EVERY knob to its code default until a restart), a recent
failure backs off without re-hammering the DB, and the config SELF-HEALS on the first call after the DB is
back. Offline + deterministic — the DB read (`data.db_client.q`, imported inside _load) is monkeypatched;
the backoff clock is advanced by rewinding _LAST_FAIL, never by sleeping. [audit_prodready TC-3]"""
import time

import config.app_config as AC


def _db_down(*a, **k):
    raise RuntimeError('connection to server at "127.0.0.1", port 5432 failed: Connection refused')


def test_failed_load_is_not_cached_and_serves_default(monkeypatch):
    AC._reset()
    monkeypatch.setattr("data.db_client.q", _db_down)
    assert AC.cfg("regress.some_key", "DEFAULT") == "DEFAULT"   # fail-open to the code default
    assert AC._CACHE is None                                     # the failure was NOT pinned as an empty map
    assert AC._LAST_FAIL > 0.0                                   # ...but the backoff clock was armed


def test_backoff_serves_defaults_without_rehammering(monkeypatch):
    AC._reset()
    calls = {"n": 0}

    def counting_down(*a, **k):
        calls["n"] += 1
        _db_down()

    monkeypatch.setattr("data.db_client.q", counting_down)
    assert AC.cfg("regress.some_key", 7) == 7
    assert AC.cfg("regress.some_key", 7) == 7                    # inside _RETRY_BACKOFF_S: no second DB hit
    assert calls["n"] == 1


def test_self_heals_after_backoff_and_caches_success(monkeypatch):
    AC._reset()
    monkeypatch.setattr("data.db_client.q", _db_down)
    assert AC.cfg("regress.some_key", 7) == 7                    # first call fails open
    calls = {"n": 0}

    def db_back(db, sql):
        calls["n"] += 1
        return [("regress.some_key", "42", "int")]

    monkeypatch.setattr("data.db_client.q", db_back)
    monkeypatch.setattr(AC, "_LAST_FAIL", time.time() - 2 * AC._RETRY_BACKOFF_S)   # backoff elapsed
    assert AC.cfg("regress.some_key", 7) == 42                   # SELF-HEALED: the real row, no restart
    assert AC._CACHE is not None                                 # the SUCCESS is cached...
    assert AC.cfg("regress.some_key", 7) == 42
    assert calls["n"] == 1                                       # ...so the second call never re-queries
