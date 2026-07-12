"""llm/ — the ONE pipeline LLM door: client.py (shared hardening: budget/retry/classify/telemetry/replay)
over a pluggable wire provider (llm/providers/<name>.py — env V48_LLM_PROVIDER / app_config llm.provider; default
openai_compat = the shipped vLLM Qwen convention)."""
