"""llm/client.py — the single pipeline LLM call convention (ai_log-compatible), PROVIDER-NEUTRAL since the provider
seam: the wire format lives in llm/providers/<name>.py (default openai_compat = the shipped vLLM Qwen 3.6 :8200
convention, byte-identical request); everything in THIS file — budget preflight, retry, classification, telemetry,
replay — is shared by every provider, so adding/swapping a provider is one new file + one knob, no edit here. [#3]

HARDENED [2026-07-03 mechanics findings 1/3/4/5]:
  · every failure is CLASSIFIED (timeout | http_<code> | transport | no_json | parse | truncated) and RECORDED via
    obs.failures — a silent fail-open {} no longer hides a vLLM outage from telemetry;
  · `on_error` lets a caller pick honest degrade semantics: "empty" (legacy {}), "marker" ({"_llm_error": kind} — the
    Layer-2 emit path, so a transport failure is distinguishable from an honest empty emission), or "raise"
    (fail-CLOSED — the router path can surface an outage instead of a silent keys[0] fallback);
  · ONE bounded parse-retry (app_config llm.parse_retry, default 1) re-sends WITH the parse error + reply tail appended
    (seed/temp are pinned, so the appended error text is what makes the retry non-identical);
  · timeouts are DB-driven per stage (app_config llm.timeout + llm.timeout.<stage>), no more hardcoded 120s cliff;
  · optional max_tokens bound (app_config llm.max_tokens; absent row = unbounded, today's behavior) with
    finish_reason=='length' classified as 'truncated';

TRUNCATION = FAIL-FAST [backlog A3, ai_r_f9787f915f]: finish_reason=length is DETERMINISTIC for a pinned-seed
temp-0 call — the same oversized prompt truncates again, and the parse-retry APPENDS the error text so the retry
prompt only GROWS (46,438→46,589 ptok against a 65,536 window) and truncates with FEWER completion tokens. So:
  · the finish=='length' check runs BEFORE the parse-success return — a truncated-but-balanced JSON reply (a nested
    object can close early and still parse) can never ship unmarked;
  · kinds in app_config llm.no_retry_kinds (default 'timeout,truncated' — the SAME row layer2/emit/emit.py honors
    for its transport retry) break out of the parse-retry loop: deterministic failures fail fast, once;
  · PROMPT-BUDGET PREFLIGHT: before every send, tokens are estimated as (len(system)+len(user))//4 and checked
    against app_config llm.prompt_budget_tok (code default 45000 ≈ 64K window − ~20K completion floor; 0 = off).
    Over budget → kind 'over_budget', the call is NEVER sent — a doomed call would only burn the full timeout.
  · optional `schema` kwarg → vLLM structured output (response_format json_schema), so a caller can make an invalid
    page_key/enum emission impossible (verified live against :8200).

DETERMINISM [L1 misroute defect]: temperature=0 alone is NOT deterministic on a batching server — greedy decoding
still varies run-to-run because concurrent batch composition changes the floating-point reduction order, so a
near-tie route can flip UNDER SWEEP LOAD while it stays stable in isolation ('dg engine and cooling' misroute).
Pinning `seed` fixes the RNG/tie-break so the SAME prompt always yields the SAME completion regardless of what else
is in the batch. Both knobs are DB-driven (app_config llm.seed / llm.temperature) with a code-default fallback, so
they are tunable without a code edit and never block import."""
from llm.parse import strip_think as _strip_think, extract_json as _extract_json   # the ONE reply parse (EH F7)
import json
import re
import threading
import time
import urllib.error

from llm import config
from llm import providers as _providers                        # the wire-format seam (llm/providers/<name>.complete)
from obs import llm_tap                                        # trace-linked per-call telemetry (fail-open, no-op untraced)


class LlmError(Exception):
    """A classified LLM call failure (kind: timeout | http_<code> | transport | no_json | parse | truncated |
    over_budget)."""

    def __init__(self, kind, detail=""):
        self.kind, self.detail = kind, str(detail)[:300]
        super().__init__(f"{kind}: {self.detail}")


from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)


def _timeout_for(stage, explicit):
    """Per-call timeout: explicit arg wins; else the per-stage app_config row (llm.timeout.<stage>), else the base
    llm.timeout row, else 120s. DB-driven exactly like llm.seed/llm.temperature."""
    if explicit is not None:
        return explicit
    base = float(_cfg("llm.timeout", 120))
    return float(_cfg(f"llm.timeout.{stage}", base)) if stage else base


def _max_tokens_for(stage):
    """Per-stage completion cap, mirroring _timeout_for: llm.max_tokens.<stage> row wins, else the base llm.max_tokens
    row, else 0 = UNBOUNDED (the historical behavior — byte-identical until a row lands). The cap is the RUNAWAY
    GUILLOTINE [decode-wall root fix 2026-07-15]: post-diet a legitimate l2_emit is ~200-2,900 completion tokens, so
    a >6K emission is by definition pathology (the 14.6K zero-filled-grid class) — better one honest-blank truncation
    at ~85s than a 150s wall that poisons sibling decodes. finish_reason=length stays classified 'truncated' =
    fail-fast, no-retry, honest-blank card (llm.no_retry_kinds)."""
    base = int(_cfg("llm.max_tokens", 0) or 0)
    return int(_cfg(f"llm.max_tokens.{stage}", base) or 0) if stage else base


def _record(kind, stage, detail=""):
    """Failure telemetry — obs.failures, keyed by the current ai_log run id. Never raises (telemetry only).
    card_id rides the decision contextvar the emit path already sets (llm_tap.set_decision at layer2/emit) —
    call_qwen clears it in its finally AFTER _fail runs, so it is live here. Without it every llm failure
    record had card_id=null and a timeout could not be attributed to a card [audit 05 F6]."""
    try:
        from obs import failures, ai_log, llm_tap
        d = llm_tap.current_decision() or {}
        failures.record("llm", kind, card_id=d.get("card_id"),
                        detail=f"stage={stage or '-'} {detail}",     # recorder owns truncation (head+tail)
                        run_id=getattr(ai_log, "_RUN_ID", "default"))
    except Exception:
        pass


def _fail(kind, detail, stage, on_error):
    _record(kind, stage, detail)
    llm_tap.mark_failure(stage, kind, detail)                  # the classified OUTCOME onto the active stage span
    if on_error == "raise":
        raise LlmError(kind, detail)
    if on_error == "marker":
        return {"_llm_error": kind, "_llm_error_detail": str(detail)[:300]}
    return {}


def _classify_transport(e):
    if isinstance(e, urllib.error.HTTPError):
        return f"http_{e.code}", str(e)
    if isinstance(e, (TimeoutError, OSError)) and "timed out" in str(e).lower():
        return "timeout", str(e)
    return "transport", f"{type(e).__name__}: {e}"


def _guided_on(stage):
    """Per-call guided-decoding flag [item 17]: app_config row llm.guided_json.<stage>, DEFAULT OFF (absent row = off,
    no stage = off) — so a json_schema kwarg is inert until the row is flipped on. Truthy set mirrors app_config _cast."""
    if not stage:
        return False
    from config.app_config import flag_on
    return flag_on(f"llm.guided_json.{stage}", False, _cfg)   # THE boolean-knob vocabulary (D6); _cfg keeps the test seam


# ── GLOBAL vLLM ADMISSION CONTROL [2026-07-12] ───────────────────────────────────────────────────────────────────────
# The per-run emit cap (layer2.emit_concurrency=4) is applied INSIDE each run, so N concurrent /api/run requests put up
# to 4×N ~22K-token emits on the single :8200 vLLM at once — the documented contention that manufactures false 'timeout'
# failures (and, because timeout is in no_retry_kinds, hard-fails cards → reflect re-routes that DOUBLE the load). This
# bounds TOTAL in-flight vLLM calls per process regardless of how many runs fan out. DB-knob `llm.global_concurrency`;
# DEFAULT 0 = DISABLED (byte-identical to today) so it is inert until an operator sets it, like neuract.statement_timeout.
# Sized once ENABLED and fixed for the process, like a connection-pool size — but the DISABLED sentinel re-resolves
# per call (cfg() fails open to the 0 default on a cmd_catalog blip, so pinning False at first use would silently
# disable an operator-enabled cap for the process life). Only the False→semaphore transition exists; a live
# semaphore is never resized or replaced.
_ADMISSION = None                    # BoundedSemaphore once sized; False = disabled sentinel; None = not yet resolved
_ADMISSION_LOCK = threading.Lock()


def _admission_sem():
    global _ADMISSION
    sem = _ADMISSION
    if sem is not None and sem is not False:
        return sem
    with _ADMISSION_LOCK:
        if _ADMISSION is None or _ADMISSION is False:
            n = int(_cfg("llm.global_concurrency", 0) or 0)
            _ADMISSION = threading.BoundedSemaphore(n) if n > 0 else False
    return _ADMISSION


try:
    from replay import hooks as _replay_hooks                  # record/replay seam (fail-open; None → bare calls)
except Exception:
    _replay_hooks = None


def call_qwen(system, user, *, timeout=None, stage=None, schema=None, json_schema=None, on_error="empty"):
    """The public LLM call — all semantics live in _call_qwen_raw below (docstring there). This thin wrapper is the
    REPLAY SEAM [replay/hooks.py]: outside a capture session it is a pass-through; during a traced request every call
    is recorded full-fidelity into outputs/traces/<trace_id>/; during a pinned replay the recorded outcome (return
    value or raised LlmError) is served from the tape instead of touching :8200."""
    try:
        if _replay_hooks is None:
            return _call_qwen_raw(system, user, timeout=timeout, stage=stage, schema=schema,
                                  json_schema=json_schema, on_error=on_error)
        return _replay_hooks.llm(_call_qwen_raw, system, user, timeout=timeout, stage=stage, schema=schema,
                                 json_schema=json_schema, on_error=on_error)
    finally:
        # DECISION INSPECTOR: the stage-declared decision context (llm_tap.set_decision — candidates etc.) covers
        # exactly ONE call_qwen (all its attempts are the same decision); clear it here so a later un-annotated
        # call on this context can never inherit a stale one.
        llm_tap.clear_decision()


def _call_qwen_raw(system, user, *, timeout=None, stage=None, schema=None, json_schema=None, on_error="empty"):
    """POST to Qwen (temp 0 + pinned seed = fully deterministic, json_object, thinking off); strip <think>; return the
    parsed dict.

    timeout  — explicit seconds; None → DB-driven (llm.timeout / llm.timeout.<stage>).
    stage    — telemetry + per-stage timeout key (e.g. 'l2_emit', 'route', 'asset_resolve').
    schema   — optional JSON schema dict → vLLM structured output (response_format json_schema); e.g. the router can
               enum-constrain page_key so an invalid emission is impossible. Other callers unchanged.
    json_schema — the FLAG-GATED sibling of `schema` [item 17]: attached (same response_format json_schema param —
               probed live on :8200 vLLM 0.16.1; the legacy `guided_json` extra-body param is silently IGNORED there)
               ONLY when the per-call app_config row llm.guided_json.<stage> is on (DEFAULT OFF). Kwarg absent, flag
               off, or explicit `schema` present → the request payload is byte-identical to today's.
    on_error — 'empty' (legacy: {} on any failure) | 'marker' ({"_llm_error": kind, "_llm_error_detail": ...} so the
               caller can distinguish an outage from an honest empty emission) | 'raise' (LlmError — fail-closed).
    Every failure is classified + recorded via obs.failures regardless of on_error.

    Deterministic failures fail FAST [A3]: kinds in llm.no_retry_kinds (default timeout,truncated) skip the parse
    retry; a prompt estimated over llm.prompt_budget_tok (chars/4; default 45000, 0=off) is never sent at all and
    fails as kind 'over_budget'."""
    # ITEM 17 [guided_json, default-off]: promote json_schema → schema only when the per-stage flag row is on. An
    # explicit `schema` kwarg keeps its existing unconditional contract and always wins over json_schema.
    if json_schema is not None and schema is None and _guided_on(stage):
        schema = json_schema
    tmo = _timeout_for(stage, timeout)
    # PROVIDER SEAM: the wire call is the selected llm/providers/<name> module (env V48_LLM_PROVIDER > app_config
    # llm.provider > openai_compat — the shipped vLLM convention, request byte-identical to the pre-seam client).
    # Everything below this line is provider-NEUTRAL shared hardening; adding a provider never touches this file.
    provider = _providers.resolve()
    temperature = _cfg("llm.temperature", 0)
    seed = _cfg("llm.seed", 42)
    max_tokens = _max_tokens_for(stage)                          # per-stage runaway guard; no rows → unbounded (legacy)

    parse_retries = max(0, int(_cfg("llm.parse_retry", 1)))
    # Deterministic failure kinds NEVER retry [A3] — sourced from THE one llm.no_retry_kinds reader
    # (llm/transient_retry.no_retry_kinds, D10) so this inner loop and the transport loop can never drift.
    from llm.transient_retry import no_retry_kinds as _no_retry_kinds
    no_retry = _no_retry_kinds(_cfg)
    budget_tok = int(_cfg("llm.prompt_budget_tok", 45000) or 0)    # chars/4 estimate ceiling; 0 = preflight off
    # DECISION INSPECTOR: the exact call configuration rides every llm_tap record (obs_llm_calls.params) so the
    # inspector shows model/temperature/seed/format per decision without re-deriving them from config history.
    _params = {"temperature": temperature, "seed": seed, "url": config.LLM_URL,
               "response_format": ("json_schema" if schema else "json_object"), "timeout_s": tmo}
    if max_tokens > 0:
        _params["max_tokens"] = max_tokens
    # EXACT-MATCH RESPONSE CACHE [Stage 5, llm/response_cache — flag llm.response_cache, default off]: identical
    # prompts at temp0/seed42 measurably return DIFFERENT completions under concurrent batching (obs 5507 vs 5513),
    # so the cache both skips the decode AND imposes the run-to-run determinism the serving stack cannot. A hit is
    # the raw parsed envelope — the caller's full gate chain re-runs on it; only clean parse-successes are stored.
    from llm import response_cache as _rcache
    _ck = (_rcache.key_for(stage, config.MODEL, seed, temperature, schema, system, user)
           if _rcache.enabled(stage, temperature, seed) else None)
    if _ck is not None:
        _cached = _rcache.lookup(_ck, stage=stage)
        if _cached is not None:
            return _cached
    attempt_user = user
    err_kind, err_detail = "parse", ""
    for attempt in range(parse_retries + 1):
        # PROMPT-BUDGET PREFLIGHT [A3]: an over-window prompt deterministically truncates/times out — never send it.
        est_tok = (len(system) + len(attempt_user)) // 4
        if budget_tok > 0 and est_tok > budget_tok:
            if attempt == 0:
                return _fail("over_budget", f"prompt≈{est_tok} tok > llm.prompt_budget_tok={budget_tok} — "
                             "call not sent (a doomed call would deterministically truncate or time out)",
                             stage, on_error)
            # the GROWN retry prompt crossed the budget — skip the doomed retry, keep the real failure kind
            err_detail += f" (parse-retry skipped: grown retry prompt≈{est_tok} tok > budget {budget_tok})"
            break
        _t0 = time.time()
        # ADMISSION: hold a global slot only across the wire call (released before parsing). Fail-open — if no slot frees
        # within llm.admission_wait_s, proceed anyway so back-pressure can never itself become an outage.
        _sem = _admission_sem()
        _slot = _sem.acquire(timeout=float(_cfg("llm.admission_wait_s", 60))) if _sem else False
        try:
            try:
                reply = provider.complete(system, attempt_user, url=config.LLM_URL, model=config.MODEL, timeout=tmo,
                                          temperature=temperature, seed=seed, schema=schema, max_tokens=max_tokens)
            except Exception as e:                               # transport/HTTP failure — classified, never retried here
                kind, detail = _classify_transport(e)
                llm_tap.record(stage=stage, system=system, user=attempt_user, latency_s=time.time() - _t0,
                               attempt=attempt, error_kind=kind, model=config.MODEL, params=_params)
                return _fail(kind, f"{detail} (prompt≈{(len(system) + len(user)) // 4} tok)", stage, on_error)
        finally:
            if _slot:
                _sem.release()
        content = (reply or {}).get("text") or ""
        finish = (reply or {}).get("finish_reason")
        # OBS TAP [one place]: every attempt's prompt/reply/usage/latency, trace-linked (obs_llm_calls). The vLLM
        # `usage` block (prompt/completion token counts) was previously discarded — it now rides the trace.
        llm_tap.record(stage=stage, system=system, user=attempt_user, response_text=content,
                       usage=(reply or {}).get("usage"), latency_s=time.time() - _t0, finish_reason=finish,
                       attempt=attempt, model=config.MODEL, params=_params)
        txt = _strip_think(content)   # THE shared strip [EH F7 — corpus-parity-proven vs the old paired-only sub]
        # TRUNCATION FIRST [A3]: finish=length means the completion hit the token ceiling — even a reply that parses
        # as balanced JSON is suspect (a nested object can close early), so classify BEFORE any parse-success return.
        if finish == "length":
            err_kind = "truncated"
            err_detail = f"finish_reason=length (completion hit max_tokens; prompt≈{est_tok} tok)"
        else:
            obj, err_kind, err_detail = _extract_json(content)   # THE shared parse [EH F7, corpus-parity-proven]
            if err_kind is None:
                if _ck is not None:
                    _rcache.store(_ck, stage, config.MODEL, obj)   # clean parse only — error paths never reach here
                return obj
        # DETERMINISTIC failure → fail fast, once [A3]: retrying a truncation only re-truncates on a longer prompt.
        if err_kind in no_retry:
            break
        # ONE bounded retry WITH the parse error shown (pinned seed/temp: the appended error text makes the retry
        # non-identical, so the model can actually correct itself).
        if attempt < parse_retries:
            attempt_user = (user + "\n\nYOUR PREVIOUS REPLY WAS NOT USABLE (" + err_detail + "). "
                            "Tail of that reply: " + txt[-300:].replace("\x00", "") +
                            "\nReturn ONLY the corrected, COMPLETE JSON object — nothing else.")
            continue
    return _fail(err_kind, err_detail, stage, on_error)
