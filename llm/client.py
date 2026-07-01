"""llm/client.py — the single Qwen 3.6 call convention (sync urllib, ai_log-compatible, FAIL-OPEN). [#3]"""
import json
import re
import urllib.request

from llm import config


def call_qwen(system, user, *, timeout=120):
    """POST to Qwen (temp 0, json_object, thinking off); strip <think>; return parsed dict or {} (fail-open)."""
    payload = {
        "model": config.MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        config.LLM_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        d = json.load(urllib.request.urlopen(req, timeout=timeout))
    except Exception:
        return {}
    content = d.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    txt = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}
