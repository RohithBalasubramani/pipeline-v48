"""validation/ — RENAMED to sweep/ (2026-07-12): `validate/` (in-pipeline gates, load-bearing) vs `validation/`
(offline cert/corpus harness) differed by a suffix and were routinely confused — the refactor-campaign ledger
follow-up #1 and the architecture audit both called the rename.

This is a COMPAT ALIAS package so every historical entry keeps working:
    python3 -m validation.cli …          → runs sweep/cli.py
    from validation.corpus import fill   → sweep.corpus.fill
New code must import `sweep.*` directly. Output paths (outputs/validation/) are unchanged.
"""
import sweep as _home

# submodule search resolves through sweep/'s directory: `-m validation.cli` and `import validation.x.y` both load
# sweep's files (their internal imports all point at sweep.*, so state lives in ONE place).
__path__ = _home.__path__


def __getattr__(name):
    import importlib
    return importlib.import_module(f"sweep.{name}")
