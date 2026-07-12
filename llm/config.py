"""llm/config.py — LLM_URL / MODEL constants (overridable via env). [contract 1 env]

Env names are V48_-prefixed (V48_LLM_URL / V48_LLM_MODEL) so a generic `MODEL` or `LLM_URL` in the caller's
environment can't silently repoint the pipeline; the unprefixed legacy names are honored as fallback."""
import os

LLM_URL = (os.environ.get("V48_LLM_URL")
           or os.environ.get("LLM_URL", "http://localhost:8200/v1/chat/completions"))
MODEL = (os.environ.get("V48_LLM_MODEL")
         or os.environ.get("MODEL", "Qwen/Qwen3.6-35B-A3B-FP8"))
