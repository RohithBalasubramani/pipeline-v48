"""llm/client.py — the single Qwen 3.6 call convention (sync urllib, ai_log-compatible). [#3]

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
import json
import re
import urllib.error
import urllib.request

from llm import config


class LlmError(Exception):
    """A classified LLM call failure (kind: timeout | http_<code> | transport | no_json | parse | truncated |
    over_budget)."""

    def __init__(self, kind, detail=""):
        self.kind, self.detail = kind, str(detail)[:300]
        super().__init__(f"{kind}: {self.detail}")


def _cfg(key, default):
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


def _timeout_for(stage, explicit):
    """Per-call timeout: explicit arg wins; else the per-stage app_config row (llm.timeout.<stage>), else the base
    llm.timeout row, else 120s. DB-driven exactly like llm.seed/llm.temperature."""
    if explicit is not None:
        return explicit
    base = float(_cfg("llm.timeout", 120))
    return float(_cfg(f"llm.timeout.{stage}", base)) if stage else base


def _record(kind, stage, detail=""):
    """Failure telemetry — obs.failures, keyed by the current ai_log run id. Never raises (telemetry only)."""
    try:
        from obs import failures, ai_log
        failures.record("llm", kind, detail=f"stage={stage or '-'} {detail}"[:280],
                        run_id=getattr(ai_log, "_RUN_ID", "default"))
    except Exception:
        pass


def _fail(kind, detail, stage, on_error):
    _record(kind, stage, detail)
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
    return str(_cfg(f"llm.guided_json.{stage}", "off")).strip().lower() in ("1", "true", "yes", "t", "on")


def call_qwen(system, user, *, timeout=None, stage=None, schema=None, json_schema=None, on_error="empty"):
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
    payload = {
        "model": config.MODEL,
        "temperature": _cfg("llm.temperature", 0),
        "seed": _cfg("llm.seed", 42),
        "response_format": ({"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
                            if schema else {"type": "json_object"}),
        "chat_template_kwargs": {"enable_thinking": False},
    }
    max_tokens = int(_cfg("llm.max_tokens", 0) or 0)
    if max_tokens > 0:                                          # bounded runaway guard; no row → unbounded (legacy)
        payload["max_tokens"] = max_tokens

    parse_retries = max(0, int(_cfg("llm.parse_retry", 1)))
    # Deterministic failure kinds NEVER retry [A3] — same row + default as layer2/emit/emit.py's transport retry, so
    # the emit-level rule can no longer be bypassed by this inner loop.
    no_retry = {k.strip() for k in str(_cfg("llm.no_retry_kinds", "timeout,truncated") or "").split(",") if k.strip()}
    budget_tok = int(_cfg("llm.prompt_budget_tok", 45000) or 0)    # chars/4 estimate ceiling; 0 = preflight off
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
        payload["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": attempt_user}]
        req = urllib.request.Request(
            config.LLM_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            d = json.load(urllib.request.urlopen(req, timeout=tmo))
        except Exception as e:                                   # transport/HTTP failure — classified, never retried here
            kind, detail = _classify_transport(e)
            return _fail(kind, f"{detail} (prompt≈{(len(system) + len(user)) // 4} tok)", stage, on_error)
        choice = (d.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "") or ""
        finish = choice.get("finish_reason")
        txt = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        # TRUNCATION FIRST [A3]: finish=length means the completion hit the token ceiling — even a reply that parses
        # as balanced JSON is suspect (a nested object can close early), so classify BEFORE any parse-success return.
        if finish == "length":
            err_kind = "truncated"
            err_detail = f"finish_reason=length (completion hit max_tokens; prompt≈{est_tok} tok)"
        else:
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception as e:
                    err_kind, err_detail = "parse", f"invalid JSON: {e}"
            else:
                err_kind, err_detail = "no_json", "no JSON object in the reply"
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
