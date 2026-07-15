"""obs/gap_sink.py — the ONE failures-sink writer for per-leaf GAP records, called at the serve boundary.

Gap records ({slot, cause, metric, column, fn, reason}) used to hit the sink at CONSTRUCTION — before executor
fill, before _prune_stale_gaps, before the roster cap/dedup — so leaves that filled seconds later and records a
cap rejected still counted (unbound_by_emit 106,678 rows ≈4.5× served truth; no_reading ~50× on roster pages)
[audit 2026-07-14, 10/11]. Producers now build sentences via the PURE config.reason_templates.sentence(); this
module writes once per SURVIVING record at exactly two points that together equal the served render.gaps:
  · ems_exec/executor/fill.py — after _prune_stale_gaps + _attach_unbound_gaps (the fill()-path cards);
  · host/enrich._merge_emit_gaps — the emit-gap records still blank in the SERVED payload (covers the
    L2 reconcile channel, special-renderer cards, and the zero-skeleton path).
Line shape is identical to the historical _tell_failures output (stage="reason", reason=<cause>, detail=<sentence>)
— zero consumer changes (failures_report / coverage / stagelogs). Telemetry only: never raises."""


def record_gaps(gaps, run_id=None):
    """Write one stage=='reason' failures row per surviving gap record; dedup by (slot, cause) within the call."""
    try:
        from obs import ai_log, failures
        rid = run_id or getattr(ai_log, "_RUN_ID", "default")
        seen = set()
        for g in gaps or []:
            if not isinstance(g, dict) or not g.get("cause"):
                continue
            key = (g.get("slot"), g.get("cause"))
            if key in seen:
                continue
            seen.add(key)
            failures.record("reason", g["cause"], detail=str(g.get("reason") or g["cause"]), run_id=rid)
    except Exception:
        pass
