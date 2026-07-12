"""validation/ — RENAMED to sweep/ (2026-07-12): `validate/` (in-pipeline gates, load-bearing) vs `validation/`
(offline cert/corpus harness) differed by a suffix and were routinely confused — the refactor-campaign ledger
follow-up #1 and the architecture audit both called the rename.

This is a COMPAT ALIAS package so every historical entry keeps working:
    python3 -m validation.cli …          → runs sweep/cli.py
    from validation.corpus import fill   → sweep.corpus.fill
New code must import `sweep.*` directly. Output paths (outputs/validation/) are unchanged.
"""
import sweep as _home

# submodule search resolves through sweep/'s directory. NOT identity-preserving for the `import validation.x` form:
# that creates a SECOND module object from the same file (`validation.cli is sweep.cli` == False) with its own
# module-level state — unlike the tree's sys.modules[...] facades. Safe in practice because sweep modules import
# each other as sweep.* (shared state lives in the sweep.* instances) and `-m validation.cli` runs as __main__;
# but never `import validation.x` in new code — use `from validation import x` (returns the sweep module via
# __getattr__ until a submodule import shadows it) or, better, import sweep.* directly. [refactor-integrity OBS-2]
__path__ = _home.__path__


def __getattr__(name):
    import importlib
    return importlib.import_module(f"sweep.{name}")
