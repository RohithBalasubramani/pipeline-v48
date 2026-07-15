"""data/connect_retry.py — bounded, jittered retry for OUTAGE-shaped FRESH-CONNECT failures (ONE concern).

The hardened db-tunnel.service restarts in 3–30s (RestartSec), but any run in flight during that window failed
its first connect instantly (5s fail-fast) and terminated as a whole-page data_unavailable — degradation was
correct but TOTAL; the user had to re-prompt [audit 2026-07-14, 01 F3]. One bounded connect retry converts most
"user re-prompts" into "run succeeds seconds later".

Contract:
  · ONLY outage-shaped failures retry (data/outage.is_outage_exc) — a logic error re-raises immediately;
  · budget = app_config db.connect_retry_s (code default 0 = OFF: offline tests and a config outage are
    byte-identical to today); each attempt keeps the 5s connect fail-fast;
  · jittered backoff (min(2^k,4)*0.5 + rand(0,0.5)) per CALLER — no shared state, no thundering-herd alignment;
  · RE-ENTRANCY GUARD: the budget read itself connects (cfg → q → pg_connect); a nested connect inside the
    retry loop passes straight through unretried (threading.local flag).
Wire points: data/db_client._checkout + the stale-retry reconnect; data/neuract_pool._new. Exhausted retry
re-raises the LAST exception, so every caller's normalization (_q_fail RuntimeError contract) holds unchanged."""
import random
import threading
import time

_LOCAL = threading.local()


def _budget_s():
    try:
        from config.app_config import cfg
        return max(0.0, float(cfg("db.connect_retry_s", 0.0) or 0.0))
    except Exception:
        return 0.0


def with_retry(connect_fn, label=""):
    """connect_fn() with the bounded outage-retry policy. Returns the connection; re-raises on a non-outage
    failure or when the budget is exhausted."""
    if getattr(_LOCAL, "inside", False):
        return connect_fn()                        # nested connect (the cfg read) — never retried
    _LOCAL.inside = True
    try:
        try:
            return connect_fn()
        except Exception as e:
            from data.outage import is_outage_exc
            if not is_outage_exc(e):
                raise
            budget = _budget_s()
            if budget <= 0:
                raise
            t0, k, last = time.time(), 0, e
            while (time.time() - t0) < budget:
                time.sleep(min(2 ** k, 4) * 0.5 + random.uniform(0, 0.5))
                k += 1
                try:
                    return connect_fn()
                except Exception as e2:
                    if not is_outage_exc(e2):
                        raise
                    last = e2
            raise last
    finally:
        _LOCAL.inside = False
