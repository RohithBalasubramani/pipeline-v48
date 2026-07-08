"""ems_exec/renderers/_insight.py — the grounded AI-summary NARRATOR (a byte-faithful port of the "qwen 3.6" model via
local vLLM). Django-free, pure stdlib, so it imports and unit-tests anywhere.

A renderer builds a PRE-JUDGED `story` dict — every threshold/severity decision ALREADY COMPUTED in Python — and the
model only NARRATES it. That keeps summaries both fast and correct (thinking is disabled at the source, so the model must
never do arithmetic it could get wrong).

Contract guarantees the callers rely on:
- Endpoint/model are env-overridable; default = the EMS vLLM "qwen 3.6" on :8200 (the pipeline model — see obs/ai_log.py,
  which monkeypatches urllib.urlopen to log every :8200 call; importing it here wires that logging with zero coupling).
- Results are cached by content hash and shared across calls, so the model fires only when the numbers actually change —
  never once per tick.
- ANY failure (endpoint down/slow, bad JSON, missing field) returns the caller's deterministic `fallback` dict. The
  summary is decoration, never load-bearing — a number is NEVER fabricated, only narrated or fallen back to.

Ported verbatim (behaviour-identical) from /home/rohith/CMD/backend2/panels/insight.py; the ONLY additions are (1) the
`import obs.ai_log` side-effect to route :8200 traffic through the run logger and (2) DB-driven knob fallbacks via
config.app_config (identical defaults, so behaviour is unchanged until a row exists). [atomic; DB-driven; honest-degrade]
"""
import hashlib
import json
import os
import re
import urllib.request

# side-effect import: obs/ai_log.py monkeypatches urllib.request.urlopen so every :8200 call is written to
# outputs/logs/ai_<run_id>.jsonl. We POST through urllib.request.urlopen below, so importing this module = free logging.
try:  # never let the observability wiring break the narrator (honest-degrade: no log, model still runs)
    import obs.ai_log  # noqa: F401
except Exception:  # pragma: no cover
    pass

try:  # DB-driven knobs with the current env-default as the code fallback (behaviour-identical until a row exists)
    from config.app_config import cfg as _cfg
except Exception:  # pragma: no cover — keep the port import-safe outside the pipeline tree
    def _cfg(_key, default):
        return default


def _env(key, default, cast=str):
    """A knob: cmd_catalog.app_config first (DB-driven), else the process env, else the hardcoded default."""
    dbv = _cfg(key, None)
    if dbv is not None:
        try:
            return cast(dbv)
        except Exception:
            pass
    raw = os.getenv(key.split(".")[-1].upper()) or os.getenv(_LEGACY_ENV.get(key, ""))
    if raw is not None:
        try:
            return cast(raw)
        except Exception:
            pass
    return default


# legacy env names (kept so the backend2 EMS_INSIGHT_* overrides still work verbatim)
_LEGACY_ENV = {
    "insight.llm_url": "EMS_INSIGHT_LLM_URL",
    "insight.llm_model": "EMS_INSIGHT_LLM_MODEL",
    "insight.timeout": "EMS_INSIGHT_TIMEOUT",
    "insight.temperature": "EMS_INSIGHT_TEMPERATURE",
}

LLM_URL = _env("insight.llm_url", "http://localhost:8200/v1")
LLM_MODEL = _env("insight.llm_model", "Qwen/Qwen3.6-35B-A3B-FP8")
LLM_TIMEOUT = _env("insight.timeout", 8.0, float)
LLM_TEMPERATURE = _env("insight.temperature", 0.2, float)

_CACHE = {}
_CACHE_MAX = 2048
_THINK_CLOSE = re.compile(r"</think>", re.IGNORECASE)
_WS = re.compile(r"\s{2,}")

_SYSTEM = (
    "You write the AI SUMMARY line of an EMS (Energy Management System) dashboard panel. "
    "You are given a JSON 'story' whose numbers and verdicts are ALREADY COMPUTED. "
    "Narrate them in plain English — do NOT recompute, compare, or judge anything yourself.\n"
    "Rules:\n"
    "- Use ONLY the values, labels and verdicts in the story. Invent NOTHING — never state a "
    "number, name, or status that is not present in the story.\n"
    "- Return STRICT JSON only, with EXACTLY these keys: {fields}. Each value is ONE tight, "
    "factual sentence — plain prose, no markdown, no preamble.\n"
    "- Lead with the most decision-relevant fact and cite the actual values (with units) that matter.\n"
    "- If the story carries an 'asked_about' quantity, LEAD with THAT quantity's status/value first, "
    "then any more-critical event."
)


def _messages(story, fields):
    system = _SYSTEM.replace("{fields}", ", ".join(f'"{f}"' for f in fields))
    user = ("STORY (all facts are pre-computed — narrate them, do not judge):\n"
            + json.dumps(story, ensure_ascii=False, default=str, indent=2)
            + f"\n\nReturn JSON with exactly these keys: {list(fields)}.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _strip_think(s):
    # vLLM/qwen3.x sometimes leaves a dangling </think> with no opening tag.
    s = s or ""
    if _THINK_CLOSE.search(s):
        s = _THINK_CLOSE.split(s)[-1]
    return s.strip()


def _post(messages, timeout):
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": LLM_TEMPERATURE,
        "stream": False,
        "response_format": {"type": "json_object"},
        # disable the reasoning block at the source -> ~0.8s and no stray math
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        LLM_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["choices"][0]["message"]["content"]


def _narrate_sync(story, fields, timeout):
    """Blocking. Returns {f: sentence} for every f in `fields`, or None on ANY
    failure (so the caller falls back wholesale rather than showing half a result)."""
    try:
        obj = json.loads(_strip_think(_post(_messages(story, fields), timeout)))
    except Exception:
        return None
    out = {}
    for f in fields:
        v = obj.get(f)
        if not isinstance(v, str) or not v.strip():
            return None
        out[f] = _WS.sub(" ", v).strip()
    return out


def _key(story, fields):
    blob = json.dumps([LLM_MODEL, story, list(fields)], sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def _store(key, result):
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.clear()
    _CACHE[key] = result


def summary_sync(story, *, fields, fallback, timeout=None):
    """Synchronous variant (tests / non-async callers). Same cache + fallback rules."""
    timeout = LLM_TIMEOUT if timeout is None else timeout
    key = _key(story, fields)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    result = _narrate_sync(story, list(fields), timeout)
    if result is None:
        return dict(fallback)
    _store(key, result)
    return result
