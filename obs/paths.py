"""obs/paths.py — the ONE writer-side output-dir door (V48_OBS_DIR / V48_OBS_NOTES_DIR).

Every obs WRITER (failures/ai_log/stage/sql_trace/sink_jsonl/notes + host/server._dump_response) resolves its
output dir through here, per call: explicit override (replay/isolate) > env > the prod default. That makes
test/prod telemetry isolation STRUCTURAL — tests/conftest.py sets V48_OBS_DIR to a session tmpdir, and every
writer (including subprocesses, which inherit env) lands in the throwaway dir; pre-2026-07-12 pytest records
leaked into the prod console via real-shaped rids because isolation relied on a rid-namespace filter alone
[audit 2026-07-14, 03].

ASYMMETRIC CONTRACT (deliberate): READERS keep their prod constants — admin/config.LOGS_DIR, profiler/logmine,
sweep/config, obs/retention, obs/query, host/inspector_api serve the PRODUCTION history and must not follow a
test redirect. Only writers resolve through this module."""
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OVERRIDE = {"logs": None, "notes": None}       # replay/isolate.py sets these (engine-only, never the serving path)


def set_override(logs_dir, notes_dir=None):
    """Point every writer at `logs_dir` (notes default to the same dir — matches replay/isolate's historical
    single-bundle behavior). Wins over env and default until clear_override()."""
    _OVERRIDE["logs"] = logs_dir
    _OVERRIDE["notes"] = notes_dir or logs_dir
    return logs_dir


def clear_override():
    _OVERRIDE["logs"] = _OVERRIDE["notes"] = None


def logs_dir():
    return _OVERRIDE["logs"] or os.environ.get("V48_OBS_DIR") or os.path.join(_ROOT, "outputs", "logs")


def notes_dir():
    return _OVERRIDE["notes"] or os.environ.get("V48_OBS_NOTES_DIR") or os.path.join(_ROOT, "outputs", "notes")
