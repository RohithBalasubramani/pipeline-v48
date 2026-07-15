"""layer2/reconcile_slots.py — DETERMINISTIC COMPLETENESS RECONCILE [completeness-contract finding]: diff the
card's own slot catalog against the emitted field slots; telemetry only (di._slot_issues / di._emit_gaps), never a
render gate. Extracted from layer2/build.py (one concern; build.py re-exports byte-compatibly)."""
import re

def _reconcile_slots(di, dp_payload, basket, *, fields_optional=False, data_note=None):
    """DETERMINISTIC COMPLETENESS RECONCILE [completeness-contract finding] — diff the card's own slot catalog
    (build_slot_catalog over the harvested default) against the emitted field slots. TELEMETRY ONLY, never a render
    gate (per-leaf degradation mandate):
      (a) an emitted slot NOT in the catalog → a `_slot_issues` note (an invented slot resolves to nothing at fill
          time — surfaced here so sweeps can count it, the field itself is left untouched);
      (b) a catalog slot with NO covering field → a per-leaf gap record {slot, cause:'unbound_by_emit', reason}
          appended to di['_emit_gaps'], which ems_exec/executor/fill.py merges into the SAME honest-gap reason
          channel (GAPS_KEY) — so a silently-uncovered leaf always carries a reason (the card-77 family).
    Skipped for fields-optional classes (their data rides run_special/roster, not fields[]). Never raises."""
    if not dp_payload or fields_optional:
        return
    try:
        from layer2.emit.slot_catalog import build_slot_catalog
        catalog = build_slot_catalog(dp_payload, basket)
    except Exception:
        return
    if not catalog:
        return
    star = re.compile(r"\[\d+\]")

    def _norm(s):
        s = str(s or "")
        s = s[5:] if s.startswith("data.") else s
        return s

    # BOTH sides address-normalized [c40/c69 false 'unbound_by_emit' family]: the catalog enumerates slots from the
    # payload ROOT ('data.bars[*].time') while the executor resolves a field slot under EITHER address form — the old
    # one-sided strip normalized only the FIELD slot, so on every `data.*`-rooted card NOTHING ever matched: every
    # bound slot was flagged an issue AND every catalog slot shipped a stale 'unbound_by_emit' gap over its FILLED leaf.
    cat_slots = {_norm(e.get("slot")) for e in catalog}
    covered = set()
    issues = []
    for f in (di.get("fields") or []):
        if not isinstance(f, dict):
            continue
        s = _norm(f.get("slot"))
        if not s:
            continue
        if s in cat_slots:
            covered.add(s); continue
        s_star = star.sub("[*]", s)
        if s_star in cat_slots:
            covered.add(s_star); continue                       # a per-element emission covering a [*] bucket slot
        if (f.get("kind") or "").lower() in ("raw", "bucketed", "time", "event", ""):
            issues.append(f"slot {f.get('slot')!r} not in this card's slot catalog (unresolvable at fill time)")
    unbound = [s for s in (str(e.get("slot")) for e in catalog) if _norm(s) not in covered]
    if issues:
        di["_slot_issues"] = issues
    if unbound:
        note = str(data_note or "").strip()
        # CAP [audit 10 F3]: this was the one UNCAPPED gap producer — a fully-uncovered card dumped its whole slot
        # catalog. Same knob the executor's completion scan honors (reasons.max_unbound_records, default 60).
        try:
            from config.app_config import cfg
            _cap = int(cfg("reasons.max_unbound_records", 60))
        except Exception:
            _cap = 60
        gaps = []
        for s in unbound[:max(1, _cap)]:
            try:
                from config.reason_templates import sentence as _sentence   # PURE — gap_sink writes survivors
                sentence = _sentence("unbound_by_emit", metric=s)
            except Exception:
                sentence = "unbound_by_emit"
            if note:
                sentence = f"{sentence} ({note})"
            gaps.append({"slot": s, "cause": "unbound_by_emit", "metric": s, "column": None, "fn": None,
                         "reason": sentence})
        di["_emit_gaps"] = gaps
