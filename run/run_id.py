"""run/run_id.py — deterministic-ish run id from the prompt (no Math.random/Date in this env). [obs]"""
import hashlib


def make_run_id(prompt, salt=""):
    h = hashlib.sha1((salt + "|" + (prompt or "")).encode()).hexdigest()[:10]
    return f"r_{h}"
