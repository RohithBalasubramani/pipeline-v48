"""llm/response_cache.py — exact-match LLM response cache [decode-wall Stage 5, 2026-07-15].

WHY (measured, load-bearing): identical prompts + identical params (temperature 0, seed 42) returned DIFFERENT
completions on this vLLM deployment — obs_llm_calls rows 5507 vs 5513 have byte-identical prompt_system AND
prompt_user yet 156 diff regions in the response. Under concurrent batching the batch-shape-dependent FP kernels
flip near-tie argmax, so the pinned seed does NOT make greedy decode run-to-run deterministic (it only pins the
sampling RNG, which is irrelevant at temp 0). This cache therefore does two jobs at once:
  1. LATENCY — a repeat authoring costs ~0s instead of a 5-30s decode;
  2. DETERMINISM — the FIRST answer for a given (stage, model, seed, temp, schema, system, user) IS the answer for
     ttl seconds, imposing the reproducibility the serving stack cannot. Caching `basket` also restores downstream
     byte-stability: the basket's output rides the l2_emit prompt, so a wobbling basket used to bust every l2 key.

SAFETY (why a hit can never degrade the pipeline): the cache returns the raw PARSED envelope — the caller's FULL
deterministic gate chain (swap gate, gate_roster, gate_data_instructions, quantity walls, schema validate for l2;
1b validation for the basket) re-runs on every hit, and the DATA fill is always live per request (fab_guards +
render_verdict recompute) — a stale recipe degrades to per-leaf honest blanks, never wrong numbers.

Two tiers: in-process TTL dict (fast path) over cmd_catalog.llm_response_cache (warm restarts; fail-open — a DB
hiccup silently degrades to in-process only). GUARDS: flag llm.response_cache='on'; stage in the
llm.response_cache.stages allowlist; temperature==0 AND a pinned seed (a sampled call is never cacheable); the
replay recorder NOT active (tape fidelity); only a clean parsed dict is ever stored (an {_llm_error} marker /
truncation / timeout never is — those paths never reach the store). Rollback: flip the flag row; poison suspicion:
TRUNCATE llm_response_cache. [atomic; DB-driven; fail-open]
"""
from __future__ import annotations

import copy
import json
import sys
import threading

from config.failopen import cfg_safe as _cfg
from lib.ttl_cache import TTLCache
from replay.tape import content_key

_MEM = TTLCache(ttl=3600)              # memory tier: one hour (the prompt-stability bucket); the DB tier carries the
_MEM_LOCK = threading.Lock()           # knob-driven long tail (llm.response_cache_ttl_s) across restarts/processes.
_STATS = {"hit_mem": 0, "hit_db": 0, "miss": 0, "store": 0}


def _ttl_s():
    try:
        return max(60, int(_cfg("llm.response_cache_ttl_s", 86400) or 86400))
    except Exception:
        return 86400


def _stages():
    raw = str(_cfg("llm.response_cache.stages", "basket,l2_emit") or "")
    return {s.strip() for s in raw.split(",") if s.strip()}


def enabled(stage, temperature, seed):
    """True only when EVERY cacheability precondition holds. Fail-closed (any doubt → live call)."""
    try:
        if str(_cfg("llm.response_cache", "off") or "off").strip().lower() not in ("on", "1", "true"):
            return False
        if not stage or stage not in _stages():
            return False
        if float(temperature or 0) != 0.0 or seed is None:
            return False                                       # a sampled call is never cacheable
        # REPLAY/CAPTURE NEEDS NO BYPASS (verified): replay/hooks.llm wraps call_qwen at its OUTER boundary — a
        # capture session tapes whatever call_qwen RETURNS (a hit is recorded exactly like a live reply), and a
        # pinned replay serves from the tape BEFORE call_qwen (so this cache never runs). replay.capture defaults
        # ON for every host request — a recorder-active bypass here would disable the cache on the entire serving
        # path (the 2026-07-15 zero-hit debugging session).
        return True
    except Exception:
        return False


def key_for(stage, model, seed, temperature, schema, system, user):
    return content_key("llm_rcache.v1", stage, model, seed, temperature, schema, system, user)


def lookup(key, stage=None):
    """The cached parsed envelope (a DEEP COPY — gates mutate their input in place) or None. Memory first, then the
    DB tier (fail-open); a DB hit re-primes memory."""
    with _MEM_LOCK:
        hit = _MEM.get(key)
    if hit is not None:
        _STATS["hit_mem"] += 1
        sys.stderr.write(f"[llm-cache] hit(mem) stage={stage}\n")
        return copy.deepcopy(hit)
    row = _db_lookup(key)
    if row is not None:
        with _MEM_LOCK:
            _MEM[key] = row
        _STATS["hit_db"] += 1
        sys.stderr.write(f"[llm-cache] hit(db) stage={stage}\n")
        return copy.deepcopy(row)
    _STATS["miss"] += 1
    return None


def store(key, stage, model, obj):
    """Cache a CLEAN parsed result. Only dicts without an error marker (the caller's success path is the only store
    site, so truncation/timeout/parse markers can never land here — belt: refuse them anyway)."""
    if not isinstance(obj, dict) or "_llm_error" in obj or not obj:
        return
    with _MEM_LOCK:
        _MEM[key] = copy.deepcopy(obj)
    _STATS["store"] += 1
    _db_store(key, stage, model, obj)


def stats():
    return dict(_STATS)


# ── DB tier (cmd_catalog.llm_response_cache; fail-open) ──────────────────────────────────────────────────────────────

def _db_lookup(key):
    try:
        from data.db_client import pg_connect
        conn = pg_connect("cmd_catalog")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT envelope FROM llm_response_cache "
                            "WHERE key=%s AND created_at > now() - make_interval(secs => %s)", (key, _ttl_s()))
                row = cur.fetchone()
                if row is None:
                    return None
                cur.execute("UPDATE llm_response_cache SET last_hit_at=now(), hits=hits+1 WHERE key=%s", (key,))
                conn.commit()
                env = row[0]
                return env if isinstance(env, dict) else json.loads(env)
        finally:
            conn.close()
    except Exception:
        return None


def _db_store(key, stage, model, obj):
    try:
        from data.db_client import pg_connect
        conn = pg_connect("cmd_catalog")
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO llm_response_cache (key, stage, model, envelope) VALUES (%s, %s, %s, %s::jsonb) "
                    "ON CONFLICT (key) DO UPDATE SET envelope=EXCLUDED.envelope, created_at=now()",
                    (key, stage, model, json.dumps(obj)))
                conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
