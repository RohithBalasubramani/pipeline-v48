"""llm/providers/ — the PROVIDER seam: one atomic module per wire convention, so a NEW AI provider is ONE new file
here plus a selection knob — zero edits to llm/client.py or any call site.

A provider module implements exactly ONE function:

    complete(system, user, *, url, model, timeout, temperature, seed, schema=None, max_tokens=0)
        -> {"text": str, "finish_reason": str|None, "usage": dict|None}

raising its transport errors (urllib HTTPError / URLError / OSError / timeout) for llm/client._classify_transport to
classify. EVERYTHING ELSE stays in llm/client.py and is therefore shared by every provider: the prompt-budget
preflight, the bounded parse retry, truncation fail-fast, failure classification + obs telemetry, the <think> strip,
JSON extraction, and the replay seam. A provider is ONLY the wire format.

SELECTION: env V48_LLM_PROVIDER > app_config row llm.provider > 'openai_compat' (the shipped vLLM/OpenAI-compatible
convention). An unknown or broken provider name falls back to openai_compat (fail-open — a bad row must never take the
pipeline down); the URL/model still come from llm/config.py (V48_LLM_URL / V48_LLM_MODEL). [atomic; one concern each]
"""
import importlib
import os

_DEFAULT = "openai_compat"


def provider_name():
    """The selected provider name: env V48_LLM_PROVIDER > app_config llm.provider > 'openai_compat'. Never raises."""
    name = (os.environ.get("V48_LLM_PROVIDER") or "").strip()
    if not name:
        try:
            from config.app_config import cfg
            name = str(cfg("llm.provider", _DEFAULT) or _DEFAULT).strip()
        except Exception:
            name = _DEFAULT
    return name or _DEFAULT


def resolve():
    """The selected provider MODULE (its complete() is the wire call). Unknown/broken name → openai_compat (fail-open,
    recorded nowhere here — the client's transport classification still surfaces a genuinely dead endpoint)."""
    name = provider_name()
    try:
        return importlib.import_module(f"llm.providers.{name}")
    except Exception:
        return importlib.import_module(f"llm.providers.{_DEFAULT}")
