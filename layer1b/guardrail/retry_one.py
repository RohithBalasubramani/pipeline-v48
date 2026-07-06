"""layer1b/guardrail/retry_one.py — ONE bounded retry for a fail-open LLM call. [hardening: silent {} outage]

llm.client.call_qwen is fail-open (returns {} on ANY transport/parse error), so a single transient timeout/refused
socket silently became an 'empty' resolution. This guardrail retries the call EXACTLY ONCE when the first attempt
returned a falsy result, and reports whether the LLM ultimately failed — so callers can distinguish 'the model chose
to emit nothing' from 'the model was never heard'. Generic (any zero-arg call), no per-card/per-prompt logic.
"""


def retry_once(call):
    """call: zero-arg callable returning the parsed LLM dict ({} on failure). Returns (result, llm_failed):
    result = the first truthy result (or {}), llm_failed = True when BOTH attempts came back empty/falsy."""
    res = call() or {}
    if res:
        return res, False
    res = call() or {}
    return res, not bool(res)
