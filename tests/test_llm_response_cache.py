"""Exact-match LLM response cache contract [decode-wall Stage 5, 2026-07-15].

Pins the safety guards: flag-off = zero cache activity (byte-identical path); allowlist/temp/seed/recorder gates;
hits are DEEP COPIES (gates mutate their input); error markers are never stored; the key is sensitive to every
input byte. The DB tier is exercised against the real local cmd_catalog with throwaway keys. [tests]
"""
import uuid

import llm.response_cache as RC


def _flags(monkeypatch, **rows):
    real = RC._cfg
    monkeypatch.setattr(RC, "_cfg", lambda k, d=None: rows.get(k, real(k, d) if not k.startswith("llm.response_cache") else d))


def test_disabled_by_default(monkeypatch):
    _flags(monkeypatch)                                        # no rows → off
    assert RC.enabled("l2_emit", 0, 42) is False


def test_guards(monkeypatch):
    _flags(monkeypatch, **{"llm.response_cache": "on", "llm.response_cache.stages": "basket,l2_emit"})
    assert RC.enabled("l2_emit", 0, 42) is True
    assert RC.enabled("basket", 0.0, 42) is True
    assert RC.enabled("route", 0, 42) is False                 # not allowlisted
    assert RC.enabled("l2_emit", 0.7, 42) is False             # sampled call
    assert RC.enabled("l2_emit", 0, None) is False             # unpinned seed
    assert RC.enabled(None, 0, 42) is False


def test_capture_session_does_not_bypass(monkeypatch):
    """replay.capture is ON for every host request and hooks.llm tapes call_qwen's RETURN (a hit is recorded like a
    live reply; a pinned replay serves from the tape BEFORE call_qwen) — so an active recorder must NOT disable the
    cache (the zero-hit-on-serving-path defect, 2026-07-15)."""
    _flags(monkeypatch, **{"llm.response_cache": "on", "llm.response_cache.stages": "l2_emit"})
    import replay.recorder as rec
    monkeypatch.setattr(rec, "active", lambda: object())       # truthy = a capture session
    assert RC.enabled("l2_emit", 0, 42) is True


def test_key_sensitivity():
    base = ("l2_emit", "m", 42, 0, None, "sys", "user")
    k = RC.key_for(*base)
    assert RC.key_for("l2_emit", "m", 42, 0, None, "sys", "user2") != k     # user byte
    assert RC.key_for("l2_emit", "m", 42, 0, None, "sys2", "user") != k     # system byte
    assert RC.key_for("l2_emit", "m2", 42, 0, None, "sys", "user") != k     # model
    assert RC.key_for("l2_emit", "m", 43, 0, None, "sys", "user") != k      # seed
    assert RC.key_for("basket", "m", 42, 0, None, "sys", "user") != k       # stage
    assert RC.key_for(*base) == k                                            # deterministic


def test_hit_is_deepcopy_and_error_markers_never_stored(monkeypatch):
    monkeypatch.setattr(RC, "_db_store", lambda *a, **k: None)
    monkeypatch.setattr(RC, "_db_lookup", lambda k: None)
    key = "test_" + uuid.uuid4().hex
    RC.store(key, "l2_emit", "m", {"a": {"b": 1}})
    hit1 = RC.lookup(key)
    hit1["a"]["b"] = 999                                       # mutate the hit (gates do this)
    hit2 = RC.lookup(key)
    assert hit2["a"]["b"] == 1, "a mutated hit must never poison the cache"
    # error markers refused even if a caller misuses store()
    key2 = "test_" + uuid.uuid4().hex
    RC.store(key2, "l2_emit", "m", {"_llm_error": "timeout"})
    assert RC.lookup(key2) is None
    RC.store(key2, "l2_emit", "m", "not a dict")
    assert RC.lookup(key2) is None
    RC.store(key2, "l2_emit", "m", {})
    assert RC.lookup(key2) is None


def test_db_tier_roundtrip_real_table():
    """Against the real local cmd_catalog (table created by db/llm_response_cache_schema.sql)."""
    import psycopg2
    try:
        c = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", password="postgres",
                             dbname="cmd_catalog", connect_timeout=3)
    except Exception:
        import pytest
        pytest.skip("local cmd_catalog unavailable")
    with c.cursor() as cur:
        cur.execute("SELECT to_regclass('llm_response_cache')")
        if cur.fetchone()[0] is None:
            import pytest
            c.close()
            pytest.skip("llm_response_cache table not created yet")
    c.close()
    key = "test_dbtier_" + uuid.uuid4().hex
    RC._db_store(key, "l2_emit", "m", {"x": 1})
    assert RC._db_lookup(key) == {"x": 1}
    # cleanup
    import psycopg2
    c = psycopg2.connect(host="127.0.0.1", port=5432, user="postgres", password="postgres", dbname="cmd_catalog")
    with c.cursor() as cur:
        cur.execute("DELETE FROM llm_response_cache WHERE key=%s", (key,))
    c.commit(); c.close()
