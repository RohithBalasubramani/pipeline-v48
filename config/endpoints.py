"""config/endpoints.py — the ONE home for V48 service-endpoint defaults (config-centralization F7, audit 2026-07-12).

The :8770 host default lived in FOUR places (host/server.py, validation/config.py, admin/config.py,
tools/payload_diff/capture.py) and ops/tunnel_monitor.py hardcoded its psql target — export V48_HOST_PORT and the
validation sweep / admin console / payload-diff capture still hit 8770; relocate the data DB via PG_* and the monitor
kept probing :5433. This module is the service-endpoint sibling of config/databases.py (DB wiring): every value is
env-overridable BOOTSTRAP wiring (works with the DB down), read HERE once, consumers import the constant.

NOT here by design: copilot/config.py (deliberately zero-coupled service — its COPILOT_* env family is documented
there; no pipeline-side Python reads :8772); host/web/vite.config.ts (a separate Node process — its
V48_HOST_API/V48_COPILOT_API env reads default to the same values these constants carry); host/notes.py SB_BASE
(Storybook is DB-knob-first per the house pattern — env STORYBOOK_URL > cfg row > default — which an env-only home
here would demote); llm/config.py stays the vLLM endpoint's home (re-exported below so there is one import point).
"""
import os

from llm.config import LLM_URL, MODEL as LLM_MODEL           # noqa: F401 — THE vLLM endpoint home (V48_LLM_URL / V48_LLM_MODEL)
# (the legacy EMS media/WS origin re-export was dropped 2026-07-12 — GLBs ride the web origin at /media/ now;
#  the legacy EMS config module was deleted with zero consumers)

# The V48 host API — host/server.py binds HOST_PORT; every client (validation sweep, admin console, payload-diff
# capture, FE proxy) targets HOST_BASE. V48_HOST_API wins whole (split client/server hosts); else the port composes it.
HOST_PORT = int(os.environ.get("V48_HOST_PORT", "8770"))
HOST_BASE = (os.environ.get("V48_HOST_API") or f"http://127.0.0.1:{HOST_PORT}").rstrip("/")
