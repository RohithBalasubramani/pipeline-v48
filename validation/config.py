"""validation/config.py — the framework's knobs. Env-overridable; sane defaults for the live dev stack.

CONCURRENCY MODEL (the one operational constraint that matters): /api/run drives the vLLM Qwen backend — >2-3
concurrent runs CONTEND and manufacture fake 'llm timeout' failures (certified 2026-07-06: emit fan-out is capped
inside the pipeline; page-level sweeps must stay <=2-3). /api/frame is NO-LLM (executor-only) and tolerates far more.
So concurrency is PER-LANE: `run_concurrency` throttles /api/run; `frame_concurrency` throttles /api/frame. Asking for
--concurrency 1000 auto-throttles the run lane to `run_concurrency_max` and reports the clamp in the run manifest —
exposing real failures, never manufacturing contention ones."""
from __future__ import annotations

import os

BASE_URL = os.environ.get("V48_VALIDATE_BASE", "http://127.0.0.1:8770")

# per-lane concurrency (see module doc). The CLI's --concurrency sets the REQUESTED level; the runner clamps the
# /api/run lane to run_concurrency_max and lets /api/frame checks use frame_concurrency.
RUN_CONCURRENCY_DEFAULT = int(os.environ.get("V48_VALIDATE_RUN_CONC", "2"))
RUN_CONCURRENCY_MAX = int(os.environ.get("V48_VALIDATE_RUN_CONC_MAX", "3"))
FRAME_CONCURRENCY = int(os.environ.get("V48_VALIDATE_FRAME_CONC", "8"))

# timeouts (s). A cold /api/run with LLM + tunnel can take ~200s; the framework treats a timeout as a FAILURE record
# (stage='transport'), never a crash.
RUN_TIMEOUT_S = float(os.environ.get("V48_VALIDATE_RUN_TIMEOUT", "420"))
FRAME_TIMEOUT_S = float(os.environ.get("V48_VALIDATE_FRAME_TIMEOUT", "120"))

# auto-throttle: if the rolling error-rate of the last WINDOW /api/run calls exceeds RATE, halve the run lane (floor 1)
THROTTLE_WINDOW = int(os.environ.get("V48_VALIDATE_THROTTLE_WINDOW", "10"))
THROTTLE_ERROR_RATE = float(os.environ.get("V48_VALIDATE_THROTTLE_RATE", "0.5"))

# artifact layout — every run gets a timestamped session dir so reports are deterministic + diffable across sessions
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.environ.get("V48_VALIDATE_OUT", os.path.join(_ROOT, "outputs", "validation"))
CORPUS_PATH = os.path.join(OUT_DIR, "corpus.jsonl")
PIPELINE_LOG_DIR = os.path.join(_ROOT, "outputs", "logs")   # the pipeline's own per-run artifacts (correlate by run_id)


def session_dir(session_id: str) -> str:
    d = os.path.join(OUT_DIR, "sessions", session_id)
    os.makedirs(os.path.join(d, "cases"), exist_ok=True)
    return d
