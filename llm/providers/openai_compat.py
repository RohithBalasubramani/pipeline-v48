"""llm/providers/openai_compat.py — the OpenAI-compatible /chat/completions wire convention: the shipped vLLM :8200
Qwen endpoint, and any OpenAI-API-compatible server (OpenAI, Groq, Ollama, another vLLM) via V48_LLM_URL/V48_LLM_MODEL.

Byte-identical to the request llm/client.py built before the provider seam existed: json_object / json_schema
response_format, pinned seed, thinking off (chat_template_kwargs — vLLM/Qwen-specific, other servers ignore unknown
keys or a sibling provider omits it). Transport errors are raised RAW for the client to classify. [atomic]"""
import json
import urllib.request


def complete(system, user, *, url, model, timeout, temperature, seed, schema=None, max_tokens=0):
    """ONE wire call → {"text", "finish_reason", "usage"}. No retry, no telemetry, no parsing beyond reply-shape
    extraction — all of that is llm/client.py's shared hardening."""
    payload = {
        "model": model,
        "temperature": temperature,
        "seed": seed,
        "response_format": ({"type": "json_schema", "json_schema": {"name": "out", "schema": schema}}
                            if schema else {"type": "json_object"}),
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if max_tokens and int(max_tokens) > 0:                      # bounded runaway guard; 0/absent → unbounded (legacy)
        payload["max_tokens"] = int(max_tokens)
    payload["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=timeout))
    choice = (d.get("choices") or [{}])[0]
    return {"text": (choice.get("message") or {}).get("content", "") or "",
            "finish_reason": choice.get("finish_reason"),
            "usage": d.get("usage")}
