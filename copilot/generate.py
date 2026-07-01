"""Pure-AI suggestion generation.

retrieve.retrieve() grounds the model in real EMS entities; the 4B model then
produces the inline autofill + 5 complete query suggestions. No deterministic
template synthesis — the model is the source of suggestions (per design decision).
Light guardrails only: parse JSON, keep autofill prefix-consistent, dedupe.
"""
import json
import re

import llm
import prompts
import retrieve
from config import LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_TIMEOUT, MAX_SUGGESTIONS

# response_format=json_object keeps output valid JSON with a generic (fast, cached)
# grammar — much lower per-call overhead than a strict per-schema guided grammar.
JSON_OBJECT = {"type": "json_object"}


def _clean(s):
    return re.sub(r"\s{2,}", " ", (s or "").strip())


def _relevance_rank(text, suggestions):
    """Order suggestions by how well they CONTINUE the on-screen text:
    literal prefix-continuations first, then by shared leading-token count.
    (Ordering guardrail only — does not invent or drop content.)"""
    lt = text.lower().strip()
    toks = lt.split()

    def score(s):
        sl = s.lower()
        if lt and sl.startswith(lt):
            return 10_000 + len(s)          # continues the exact typed text -> top
        st = sl.split()
        common = 0
        for a, b in zip(toks, st):
            if a == b:
                common += 1
            else:
                break
        return common                        # else: shared leading words

    return sorted(suggestions, key=score, reverse=True)


def generate(text, grounding=None, timeout=LLM_TIMEOUT):
    text = text or ""
    g = grounding if grounding is not None else retrieve.retrieve(text)
    messages = [
        {"role": "system", "content": prompts.SYSTEM},
        {"role": "user", "content": prompts.build_user(text, g)},
    ]
    try:
        raw = llm.chat(messages, temperature=LLM_TEMPERATURE, max_tokens=LLM_MAX_TOKENS,
                       timeout=timeout, response_format=JSON_OBJECT)
        obj = json.loads(raw)
    except Exception as e:
        # pure-AI design: no model -> no suggestions (honest, simple)
        return {"autofill": "", "ghost": "", "suggestions": [],
                "source": "unavailable", "error": str(e)[:160]}

    autofill = _clean(obj.get("autofill"))
    low = text.lower()
    # autofill must continue the user's exact text
    if autofill and not autofill.lower().startswith(low.strip()):
        autofill = ""
    ghost = autofill[len(text):] if autofill[:len(text)].lower() == low else ""

    seen, suggestions = set(), []
    for s in (obj.get("suggestions") or []):
        s = _clean(s) if isinstance(s, str) else ""
        if s and s.lower() not in seen:
            seen.add(s.lower())
            suggestions.append(s)

    suggestions = _relevance_rank(text, suggestions)   # continuations of the typed text first
    return {"autofill": autofill, "ghost": ghost,
            "suggestions": suggestions[:MAX_SUGGESTIONS], "source": "model"}


if __name__ == "__main__":
    import sys
    import time
    txt = sys.argv[1] if len(sys.argv) > 1 else "show trans"
    t0 = time.time()
    out = generate(txt)
    out["latency_ms"] = int((time.time() - t0) * 1000)
    print(json.dumps(out, indent=2))
