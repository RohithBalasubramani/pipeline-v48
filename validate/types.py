"""validate/types.py — annotation-only TypedDicts for the validation boundary [typing F2]. total=False +
runtime-inert; the verdict string families live in validate/verdicts.py."""
from __future__ import annotations

from typing import Any, TypedDict


class RenderVerdictResult(TypedDict):
    n_real: int
    n_data: int
    n_undeclared: int
    verdict: str                  # verdicts.RenderVerdict: 'render' | 'partial' | 'honest_blank'
    answerability: str            # verdicts.Answerability: 'full' | 'partial' | 'none'


class ValidationReport(TypedDict, total=False):
    verdict: str                  # verdicts.PageVerdict page roll-up
    data: dict[str, Any]          # per-column pass/warn/fail + summary {n_columns, n_pass, …}
    payload: dict[str, Any]
    cards: list[dict[str, Any]]
    _schema_issues: list[str]
