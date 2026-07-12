"""validate/verdicts.py — the DECLARED homes of the three verdict string families [typing F5, 2026-07-12].

Every one of these strings crosses a JSON/DB/FE boundary, so they are str CONSTANTS (+ Literal aliases for
annotations), deliberately NOT enum.Enum — serialization stays byte-identical with no .value churn. Importers
replace their scattered literals 1:1; the values are frozen contracts (the FE and the sweeps match on them).
[atomic; the swap action/origin family lives in layer2/swap/vocab.py — its writer's layer]"""
from typing import Literal

# ── data validation verdict (validate/data_validate per-column + page roll-up) ──────────────────────────────────────
PASS, WARN, FAIL = "pass", "warn", "fail"
PASS_WITH_GAPS, ASSET_PENDING = "pass_with_gaps", "asset_pending"          # page roll-up extras
DataVerdict = Literal["pass", "warn", "fail"]
PageVerdict = Literal["pass", "warn", "pass_with_gaps", "fail", "asset_pending"]
VERDICTS = {PASS, WARN, PASS_WITH_GAPS, FAIL, ASSET_PENDING}

# ── render verdict (validate/render_verdict.compute) ────────────────────────────────────────────────────────────────
RENDER, PARTIAL, HONEST_BLANK = "render", "partial", "honest_blank"
RenderVerdict = Literal["render", "partial", "honest_blank"]

# ── answerability (the FE-facing roll-up of the render verdict) ─────────────────────────────────────────────────────
FULL, PARTIAL_ANSWER, NONE_ANSWER = "full", "partial", "none"
Answerability = Literal["full", "partial", "none"]
ANSWERABILITY = {FULL, PARTIAL_ANSWER, NONE_ANSWER}
