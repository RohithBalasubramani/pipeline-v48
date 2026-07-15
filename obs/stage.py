"""obs/stage.py — END-TO-END pipeline stage log. Each call prints `[<run_id>] <stage>: <fields>` to stderr (so it lands
in the host log — `tail -f outputs/host.log`) AND appends outputs/logs/pipeline_<run_id>.jsonl (replayable). Lets you
watch a single prompt's whole backend flow: 1a → 1b → validate → asset-gate → Layer 2 (per card) → fill → frames."""
import json
import os
import sys
import time

from obs.paths import logs_dir as _logs_dir     # the ONE writer-dir door (V48_OBS_DIR-aware) [audit 03]


def stage(run_id, name, **fields):
    parts = "  ".join(f"{k}={v}" for k, v in fields.items())
    print(f"  [{run_id}] {name:<11} {parts}", file=sys.stderr, flush=True)
    try:
        _d = _logs_dir()
        os.makedirs(_d, exist_ok=True)
        with open(os.path.join(_d, f"pipeline_{run_id}.jsonl"), "a") as f:
            f.write(json.dumps({"ts": time.time(), "stage": name, **fields}) + "\n")
    except Exception:
        pass
    # TRACE FORWARD [obs]: mirror this legacy stage line into the ACTIVE trace as a kind='legacy' annotation event
    # (obs_stage_events, stage='legacy.<name>') — every existing call site becomes trace-queryable with zero call-site
    # edits, and the run_id binds onto the trace so pipeline_<rid>.jsonl joins obs_traces.run_ids. No trace → no-op.
    try:
        from obs import trace as _trace
        t = _trace.current()
        if t is not None:
            if run_id and run_id not in ("-", "default", "pytest"):   # placeholder ids never bind
                _trace.bind_run_id(run_id)
            from obs import event as _event, bus as _bus
            _bus.emit(_event.legacy_event(t, run_id, name, fields))
    except Exception:
        pass
    # failures fan-out [#17; fullsweep_20260706 telemetry gap: failures_ fired on 1/42 defect cards — it only saw
    # llm/harness records]. Every layer already reports its defects THROUGH this stage hook (host exec ok=False,
    # L2.card fail=…, reflect gaps=N, ERROR=… everywhere), so mirror those signals onto obs.failures without touching
    # any layer's code. Telemetry only — never raises, never alters the stage record.
    try:
        sig = _failure_signal(fields)
        if sig is not None:
            from obs.failures import record as _record
            _record(name, sig[0], card_id=fields.get("card", fields.get("id")),
                    detail=str(sig[1] or ""), run_id=run_id or "default")   # recorder owns truncation (head+tail)
    except Exception:
        pass


def _failure_signal(fields):
    """(reason, detail) when a stage's OWN fields signal a defect/degradation, else None. Data-driven over the existing
    stage vocabulary — no new call sites, no per-card logic:
      · ERROR=…      → any stage that caught an exception            ('stage_error')
      · fail=…       → L2.card's llm/emit failure kind               ('card_fail')
      · ok=False     → host exec card failure (why=…)                ('exec_fail')
      · gap=… truthy → L2.card's per-card answerability gap          ('fill_gap')
      · gaps=N > 0   → reflect/preflight aggregated fill-gap count   ('fill_gap')"""
    if "ERROR" in fields:
        return "stage_error", fields.get("ERROR")
    if fields.get("fail"):
        return "card_fail", fields.get("fail")
    if fields.get("ok") is False:
        return "exec_fail", fields.get("why")
    if fields.get("gap"):
        return "fill_gap", fields.get("gap")
    try:
        if int(fields.get("gaps") or 0) > 0:
            return "fill_gap", f"gaps={fields.get('gaps')}"
    except (TypeError, ValueError):
        pass
    return None
