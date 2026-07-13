"""tests/test_regress_store_never_cache_empty.py — pins the cache-poison legs of audit fix 12 (2026-07-12):

  · host/payload_store: a DB-ERROR load of _skeleton_payload/_raw_default_payload must NOT be cached (pinning
    None demoted the card to the generic HonestBlank tier / lost the executor's shape oracle for the process
    life); the next call RETRIES and a successful read (row present OR genuinely absent) IS cached.

  (The former layer1b/compare/detect._panel_alias_index leg was retired with the lexical compare detector —
  AI-first compare, 2026-07-14; the same never-publish-partial pattern still guards asset_resolve._pcc_alias_index.)

Offline + deterministic — every leg monkeypatches `data.db_client.q` (the seam both modules import inside the
function, so it binds at call time); no sockets. [audit_prodready TC-3]"""
import json

import host.payload_store as PS


def _q_down(db, sql):
    raise RuntimeError('connection to server at "127.0.0.1", port 5432 failed: Connection refused')


# ── host/payload_store._skeleton_payload ─────────────────────────────────────────────────────────────────────────────

def test_skeleton_db_error_is_not_cached_and_retries(monkeypatch):
    monkeypatch.setattr(PS, "_SKELETON_CACHE", {})
    monkeypatch.setattr("data.db_client.q", _q_down)
    assert PS._skeleton_payload(4242) is None                    # honest degrade on the outage...
    assert PS._SKELETON_CACHE == {}                              # ...but the failure was NOT pinned
    monkeypatch.setattr("data.db_client.q",
                        lambda db, sql: [(json.dumps({"title": "Card", "value": 0.0}),)])
    out = PS._skeleton_payload(4242)                             # DB back → the SAME card re-reads (self-heals)
    assert isinstance(out, dict) and out["title"] == "Card"
    assert 4242 in PS._SKELETON_CACHE                            # the SUCCESS is cached


def test_skeleton_genuinely_absent_row_is_cached(monkeypatch):
    monkeypatch.setattr(PS, "_SKELETON_CACHE", {})
    calls = {"n": 0}

    def q_empty(db, sql):
        calls["n"] += 1
        return []                                                # read SUCCEEDED, card has no harvested payload

    monkeypatch.setattr("data.db_client.q", q_empty)
    assert PS._skeleton_payload(4243) is None
    assert 4243 in PS._SKELETON_CACHE                            # trustworthy absence IS cacheable...
    assert PS._skeleton_payload(4243) is None
    assert calls["n"] == 1                                       # ...so the second call never re-queries


# ── host/payload_store._raw_default_payload (the executor's shape oracle) ────────────────────────────────────────────

def test_raw_default_db_error_is_not_cached_and_retries(monkeypatch):
    monkeypatch.setattr(PS, "_RAW_DEFAULT_CACHE", {})
    monkeypatch.setattr("data.db_client.q", _q_down)
    assert PS._raw_default_payload(4242) is None
    assert PS._RAW_DEFAULT_CACHE == {}                           # losing the shape oracle until restart = same poison class
    monkeypatch.setattr("data.db_client.q",
                        lambda db, sql: [(json.dumps({"title": "Card", "series": [1, 2]}),)])
    out = PS._raw_default_payload(4242)
    assert out == {"title": "Card", "series": [1, 2]}
    assert PS._RAW_DEFAULT_CACHE[4242] == out
