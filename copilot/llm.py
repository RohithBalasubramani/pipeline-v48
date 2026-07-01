"""Tiny stdlib OpenAI-compatible client for the copilot's OWN 4B endpoint (:8201).

No third-party deps (urllib only) so the layer stays self-contained. Mirrors the
call shape of pipeline_v46/backend/layer1/ai_router.py but shares no code with it.
"""
import json
import urllib.error
import urllib.request

from config import LLM_MODEL, LLM_URL


def chat(messages, *, temperature=0.3, max_tokens=0, timeout=8.0,
         response_format=None, guided_json=None):
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens and max_tokens > 0:  # 0 -> no cap, model stops at EOS
        payload["max_tokens"] = max_tokens
    if response_format:
        payload["response_format"] = response_format
    if guided_json:
        payload["guided_json"] = guided_json  # vLLM guided decoding
    req = urllib.request.Request(
        LLM_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read().decode())
    return body["choices"][0]["message"]["content"]


def is_up(timeout=2.0):
    """True if the copilot model endpoint is serving the expected model."""
    try:
        req = urllib.request.Request(LLM_URL.rstrip("/") + "/models")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
        return any(m.get("id") == LLM_MODEL for m in body.get("data", []))
    except Exception:
        return False
