"""llm/config.py — LLM_URL / MODEL constants (overridable via env). [contract 1 env]"""
import os

LLM_URL = os.environ.get("LLM_URL", "http://localhost:8200/v1/chat/completions")
MODEL = os.environ.get("MODEL", "Qwen/Qwen3.6-35B-A3B-FP8")
