"""obs/bus.py — the ONE fan-out: emit(event) → every enabled sink. Sinks are single-purpose siblings
(sink_console / sink_jsonl / sink_pg), each gated by its own DB-tunable app_config knob and each individually
fail-open — a broken Postgres sink degrades to JSONL+console silently, and NOTHING here ever raises into the
pipeline (telemetry only, mirrors obs.failures semantics)."""
import contextvars

_IN_BUS = contextvars.ContextVar("obs_in_bus", default=False)   # reentrancy guard (cfg() during emit runs a DB read)


from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)


def _on(key, default=True):
    v = _cfg(key, "on" if default else "off")
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() not in ("off", "0", "false", "no")


def emit(event):
    """Fan one canonical event (obs.event.*) out to the enabled sinks. Never raises; never re-enters itself
    (the first cfg() call runs a cmd_catalog read that would otherwise loop through db_tap → emit)."""
    if not event or _IN_BUS.get():
        return
    token = _IN_BUS.set(True)
    try:
        if not _on("obs.enabled", True):
            return
        if _on("obs.sink.console", True):
            try:
                from obs import sink_console
                sink_console.write(event)
            except Exception:
                pass
        if _on("obs.sink.jsonl", True):
            try:
                from obs import sink_jsonl
                sink_jsonl.write(event)
            except Exception:
                pass
        if _on("obs.sink.pg", True):
            try:
                from obs import sink_pg
                sink_pg.write(event)
            except Exception:
                pass
    except Exception:
        pass
    finally:
        _IN_BUS.reset(token)
