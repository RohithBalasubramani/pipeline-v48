"""llm/prompt_load.py — THE prompt-file loader (one concern; dedup D8, refactor campaign 2026-07-12).

Reads `<base_dir>/prompts/<name>`. The per-layer prompts/ FOLDERS stay where they are — the atomic structure is the
folders, not the loader; callers pass their own layer dir.

`errors="replace"` is the house default (a stray non-UTF-8 byte in a prompt file degrades to U+FFFD instead of
crashing the layer) — before this home, only layer2/emit/emit.py's inline copy survived that; the four layer1a/1b
copies raised. Pass errors=None for byte-strict reads.
"""
import os


def load(base_dir, name, errors="replace"):
    with open(os.path.join(base_dir, "prompts", name), encoding="utf-8", errors=errors) as f:
        return f.read()
