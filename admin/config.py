"""admin/config.py — the admin console's constants: paths, port, host-API base, run-id shape, date-param parsing.

ONE home for every knob so no sibling hardcodes a path. The admin server reads FILES only (outputs/logs, outputs/notes,
outputs/validation) — it never opens a DB connection; replay talks to the running host API over HTTP."""
import os
import re
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR = os.path.join(ROOT, "outputs", "logs")
NOTES_DIR = os.path.join(ROOT, "outputs", "notes")
VALIDATION_DIR = os.path.join(ROOT, "outputs", "validation")

PORT = int(os.environ.get("V48_ADMIN_PORT", "8790"))
from config.endpoints import HOST_BASE as HOST_API     # noqa: E402  the ONE :8770 home (config F7; honors V48_HOST_API)

# real pipeline runs — everything else (default / pytest / r_test_*) is dev noise, hidden unless sink=all
RUN_ID_RE = re.compile(r"^r_[0-9a-f]{10}$")

# stage vocabulary in canonical pipeline order (explorer + latency group L2.card fan-out under one node)
STAGE_ORDER = ["PROMPT", "1a", "1b", "validate", "asset_gate", "preflight_reroute", "layer2", "L2.card",
               "L2.swap_revert", "reflect", "degrade", "notes", "exec", "RESPONSE", "RESPONSE_MULTI"]


def parse_when(s):
    """ISO date/datetime string → epoch seconds, or None. Naive strings are LOCAL time (matches every log writer:
    datetime.now().isoformat() and time.time() on the same box)."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)).timestamp()
    except (ValueError, TypeError):
        return None


def window_params(qs):
    """{'from': [..], 'to': [..]} query dict → (t_from, t_to) epoch bounds (None = unbounded). A date-only `to`
    (YYYY-MM-DD) is inclusive: bumped to end-of-day."""
    t_from = parse_when((qs.get("from") or [None])[0])
    raw_to = (qs.get("to") or [None])[0]
    t_to = parse_when(raw_to)
    if t_to is not None and raw_to and len(str(raw_to)) == 10:          # date-only → include the whole day
        t_to = (datetime.fromisoformat(raw_to) + timedelta(days=1)).timestamp()
    return t_from, t_to


def in_window(ts, t_from, t_to):
    if ts is None:
        return False
    if t_from is not None and ts < t_from:
        return False
    if t_to is not None and ts > t_to:
        return False
    return True


def iso(ts):
    """epoch seconds → local ISO string (None-safe)."""
    try:
        return datetime.fromtimestamp(ts).isoformat(timespec="seconds") if ts is not None else None
    except (ValueError, TypeError, OSError):
        return None
