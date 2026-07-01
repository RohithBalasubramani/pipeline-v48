"""Build copilot_index.sqlite — the standalone suggestion corpus.

Sources (read-only): the LIVE target_version1.neuract DB @ :5433 (assets + metrics) and
cmd_catalog @ :5432 (cards / pages / exemplar questions). Flattened into one SQLite index.

The key idea (per design): EMS cards and templates ALREADY encode what a meaningful
EMS query is, so we use that semantics deeply, not just titles:
  * cards.user_question / sem_answers / page_specs.reusable_answers
        -> first-class EXEMPLAR QUESTIONS (the strongest suggestion seeds)
  * card_purpose / output_insight / decision_support / visualization / sem_*
        -> rich match keywords + payload context fed to the model
  * card_data_recipe.fields  -> the REAL metrics each card renders -> meaningful
        metrics get a popularity boost over the long tail of raw columns; cards
        carry their metric set for context-aware suggestion
  * card_controls.time_options -> REAL time presets ("Today","Last 7 days",...)
        that fill the {time} slot instead of hardcoded guesses

Usage:
    python3 build.py            # rebuild from DBs + curated/embedded aliases
    python3 build.py --llm      # also generate colloquial aliases via the 4B model

Corpus is tiny (~1k short strings) -> retrieval is in-memory Python ranking;
SQLite is the durable, inspectable, re-buildable store.

This is a single-purpose package (atomised from the old build.py monolith). The barrel
re-exports the module's public surface so `import build` / `from build import ...` keeps
working; the sub-modules use the copilot's own same-dir config.py/db.py/aliases.py/llm.py/
has_data.py/validated.py, so the copilot dir is placed on sys.path here.
"""
import os as _os
import sys as _sys

# Ensure the copilot dir (this package's parent) is importable so the sub-modules' bare
# imports (`import db`, `from config import ...`, `import aliases`, `import llm`,
# `import has_data`, `import validated`) resolve — same as when build.py ran from copilot/.
_COPILOT_DIR = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _COPILOT_DIR not in _sys.path:
    _sys.path.insert(0, _COPILOT_DIR)

from .alias_build import add_llm_aliases, build_aliases
from .assets import _v48_assets
from .cli import main
from .entities import fetch_entities
from .metrics import _derive_metric_labels
from .naming import (
    _asset_location,
    _DERIVED_HINTS,
    _fallback_asset_name,
    _GIC_PREFIX,
    _infer_kind,
    _infer_unit,
    _SKIP_ASSET,
    _tidy,
    _title,
    _UNIT_SUFFIX,
)
from .parsing import (
    _j,
    _QLEN,
    _recipe_metrics,
    _split_questions,
    _TEXTY,
    _time_presets,
)
from .schema import SCHEMA

__all__ = [
    "SCHEMA",
    "add_llm_aliases",
    "build_aliases",
    "fetch_entities",
    "main",
    "_v48_assets",
    "_derive_metric_labels",
    "_recipe_metrics",
    "_split_questions",
    "_time_presets",
    "_j",
    "_fallback_asset_name",
    "_asset_location",
    "_tidy",
    "_infer_unit",
    "_infer_kind",
    "_title",
    "_SKIP_ASSET",
    "_GIC_PREFIX",
    "_UNIT_SUFFIX",
    "_DERIVED_HINTS",
    "_TEXTY",
    "_QLEN",
]


if __name__ == "__main__":
    main()
