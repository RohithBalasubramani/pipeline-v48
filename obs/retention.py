"""obs/retention.py — age-based prune of the FILE telemetry the pipeline appends forever [OBS-2 / H15: outputs/logs
grew 485 MB → 1.2 GB in one day with no retention; only the obs_* pg rows (sink_pg._purge) and replay bundle COUNT
(replay/store._prune, replay.keep_traces) were bounded].

Prunes two roots, by file mtime:
  · outputs/logs/    — the per-run jsonl families: ai_*.jsonl, sql_*.jsonl, pipeline_*.jsonl, failures_*.jsonl,
                       trace_*.jsonl (sink_jsonl), response_*.json (host response dumps). NOTHING else in logs/
                       is touched (host.log etc. are not per-run families).
  · outputs/traces/  — replay bundle dirs t_<hex>/ (age-based here; store._prune keeps the newest N regardless).

Knob (document for seeding — db/ is not this module's to edit):
  cmd_catalog.app_config  key='obs.file_retention_days'  data_type=int  value=14
  (default 14 when the row is absent; 0 or negative = keep forever; read via config.app_config.cfg, fail-open —
  any config/DB error prunes NOTHING rather than guessing a window).

ensure_started() spawns ONE daemon thread: prune at start, then every 6 h. Idempotent, never raises — telemetry
housekeeping must not be able to sink the host. Deliberately NOT self-starting on import: the host owner wires
ensure_started() at boot."""
import os
import shutil
import threading
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGS = os.path.join(_ROOT, "outputs", "logs")
_TRACES = os.path.join(_ROOT, "outputs", "traces")

_FAMILIES = ("ai_", "sql_", "pipeline_", "failures_", "trace_", "response_")   # per-run file families ONLY
_INTERVAL_S = 6 * 3600.0

_LOCK = threading.Lock()
_STARTED = False


def _retention_days():
    """The window in days; 0 = keep forever. Fail-open: any config/DB error → 0 (prune nothing)."""
    try:
        from config.app_config import cfg                      # lazy — import must never gate obs
        return int(cfg("obs.file_retention_days", 14) or 0)
    except Exception:
        return 0


def prune(now=None):
    """One prune pass: delete per-run telemetry files/bundle dirs older than the window. Fail-open per entry
    (a locked/vanished file never stops the sweep), never raises. Returns the number of entries removed."""
    removed = 0
    try:
        days = _retention_days()
        if days <= 0:
            return 0
        cutoff = (now or time.time()) - days * 86400.0
        try:
            names = os.listdir(_LOGS)
        except OSError:
            names = []
        for name in names:
            if not (name.startswith(_FAMILIES) and name.endswith((".jsonl", ".json"))):
                continue
            p = os.path.join(_LOGS, name)
            try:
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                    os.remove(p)
                    removed += 1
            except OSError:
                pass
        try:
            names = os.listdir(_TRACES)
        except OSError:
            names = []
        for name in names:
            if not name.startswith("t_"):                      # only replay bundle dirs — never a parked artifact
                continue
            d = os.path.join(_TRACES, name)
            try:
                if os.path.isdir(d) and os.path.getmtime(d) < cutoff:
                    shutil.rmtree(d, ignore_errors=True)
                    removed += 1
            except OSError:
                pass
    except Exception:                                          # housekeeping must never raise into a caller
        pass
    return removed


def ensure_started():
    """Spawn the ONE pruning daemon (prune now, then every 6 h). Idempotent, never raises."""
    global _STARTED
    try:
        with _LOCK:
            if _STARTED:
                return
            threading.Thread(target=_loop, name="obs-file-retention", daemon=True).start()
            _STARTED = True
    except Exception:
        pass


def _loop():
    while True:
        try:
            prune()
        except Exception:
            pass
        time.sleep(_INTERVAL_S)
