"""config/ems_backend.py — how the DATA-fill helper reaches V48's ems_backend WS dispatcher. Edit here, not in workers/.
(user 2026-06-30: "we will be using …/ems_backend to render the cards"). [findings/ems_backend_hardcoding.md]"""
import os

from config.app_config import cfg   # operational knobs are DB-tunable (cmd_catalog.app_config, ems_backend.* keys)

# ── WS WIRING (structural — the dispatcher endpoint; stays code/env, NOT a DB knob) ─────────────────────────────────
EMS_WS_SCHEME = os.environ.get("EMS_WS_SCHEME", "ws")
EMS_WS_HOST = os.environ.get("EMS_WS_HOST", "localhost")
EMS_WS_PORT = int(os.environ.get("EMS_WS_PORT", "8890"))     # daphne port for pipeline_v48/ems_backend (CMD copy uses :8888)

# ── OPERATIONAL KNOBS (DB-tunable via cmd_catalog.app_config → cfg(); env var is the fail-open fallback) ─────────────
EMS_CONNECT_TIMEOUT = cfg("ems_backend.connect_timeout_s", float(os.environ.get("EMS_CONNECT_TIMEOUT", "8")))
# BIG ceiling (60s): a large panel aggregate fans out across ALL its feeders (e.g. PCC-Panel-4 = 28 → ~17s for the
# voltage-current event/sag rollup) and the biggest panels can run slower still. This is a CEILING, not a delay — fast
# fetches still return the instant the snapshot arrives; this only prevents big-panel aggregates from being cut off.
EMS_FRAME_TIMEOUT = cfg("ems_backend.frame_timeout_s", float(os.environ.get("EMS_FRAME_TIMEOUT", "60")))
# transient-flake retry: a TIMEOUT/RESET/disconnect (e.g. daphne under concurrent load) is retried; a backend
# `type:error` answer (not configured/registered) is permanent and never retried. Backoff grows per attempt.
EMS_FETCH_ATTEMPTS = int(cfg("ems_backend.fetch_attempts", int(os.environ.get("EMS_FETCH_ATTEMPTS", "3"))))
EMS_RETRY_BACKOFF = cfg("ems_backend.retry_backoff_s", float(os.environ.get("EMS_RETRY_BACKOFF", "0.4")))


def ws_url(mfm_id, endpoint):
    """ws/mfm/<mfm_id>/<endpoint>/ — the dispatcher route (class-correct strategy resolved server-side)."""
    return f"{EMS_WS_SCHEME}://{EMS_WS_HOST}:{EMS_WS_PORT}/ws/mfm/{mfm_id}/{endpoint}/"
