"""llm/transient_retry.py — the ONE bounded LLM retry policy: retry TRANSIENT failures only.

A 'timeout'/'truncated' failure is DETERMINISTIC for a given prompt (the same emit will time out / overrun again),
so retrying only DOUBLES the wall-clock hang (the card-5 32K-tok heatmap 2x-timeout page-hang). layer2/emit carried
the policy-correct loop; layer1b's retry_one.py blindly re-sent EVERY falsy result — a timed-out asset_resolve/basket
call was re-sent and doubled the hang. This module hoists the emit loop so every layer shares one policy.

Knobs (cmd_catalog.app_config): llm.transport_retry (bounded attempts, default 1) and llm.no_retry_kinds
(default 'timeout,truncated' — the deterministic kinds that must fail fast)."""


def no_retry_kinds(cfg_fn=None):
    """The deterministic-failure kinds that must NEVER be retried — THE one reader of the llm.no_retry_kinds row
    (dedup D10, 2026-07-12): llm/client's inner parse loop (which passes its own guarded `_cfg` so its fail-open and
    test seams keep working) and this transport loop both source it here. Fail-open: config unavailable → the code
    default."""
    if cfg_fn is None:
        try:
            from config.app_config import cfg as cfg_fn
        except Exception:
            def cfg_fn(_k, d):
                return d
    raw = cfg_fn("llm.no_retry_kinds", "timeout,truncated")
    return {k.strip() for k in str(raw or "").split(",") if k.strip()}


_no_retry_kinds = no_retry_kinds   # internal alias (existing callers below)


def _transport_retries():
    from config.app_config import cfg
    return max(0, int(cfg("llm.transport_retry", 1)))


def retry_transient(call):
    """call: zero-arg callable returning a call_qwen(..., on_error='marker') dict — {} or a parsed reply, with
    `_llm_error` = the classified failure kind on error. Re-calls ONLY while the failure kind is transient (absent
    from llm.no_retry_kinds), bounded by llm.transport_retry. Returns the final dict ({} at worst, never None)."""
    raw = call()
    retries = _transport_retries()
    no_retry = _no_retry_kinds()
    while isinstance(raw, dict) and raw.get("_llm_error") and raw.get("_llm_error") not in no_retry and retries > 0:
        retries -= 1
        raw = call()
    return raw or {}


def retry_transient_result(call):
    """The layer1b caller contract: (result_without_marker, llm_failed). `llm_failed` is True when the model was
    NEVER HEARD (the final attempt still carries `_llm_error`) — distinguishing 'the model chose to emit nothing'
    from 'the model was never heard'. The failure marker is stripped so callers keep consuming a plain reply dict."""
    raw = retry_transient(call)
    if isinstance(raw, dict) and raw.get("_llm_error"):
        return {}, True
    return (raw or {}), False
