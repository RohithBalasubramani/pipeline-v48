"""layer2/window_backfill.py — the DEFAULT-WINDOW BACKFILL engine [R1]: deterministic date math resolving the
bounded window a card's data_instructions fills over, honoring (in order) the AI's own explicit bounds, the AI's
declared range (window/fetch-spec/per-slot consensus, calendar tokens anchored at the site-tz calendar start), and
only then the DB default range — anchored to the DATA's reference now. Extracted from layer2/build.py (one concern:
window resolution; build.py re-exports byte-compatibly). Consumed once from layer2/build._finalize."""

def _lookback_delta(text):
    """Lookback prose from the config.windows preset table ('1 day' / '24 hours' / '30 min' / '7 days') → timedelta,
    or None when unparseable. Units are physical time words, not domain vocab — the RANGE vocabulary itself stays in
    the DB (app_config windows.time_windows)."""
    import re
    from datetime import timedelta
    m = re.search(r"(\d+(?:\.\d+)?)\s*(week|day|hour|hr|min)", str(text or "").lower())
    if not m:
        return None
    secs = {"week": 604800.0, "day": 86400.0, "hour": 3600.0, "hr": 3600.0, "min": 60.0}[m.group(2)]
    return timedelta(seconds=float(m.group(1)) * secs)


def _range_delta(token):
    """Lookback for a DECLARED range token — a config.windows TIME_WINDOWS preset name first (DB truth), else a
    GENERIC parse of the token's own words/digits ('last-7-days' → 7 days, 'this-month'/'last-30-days' → ~30 days,
    'today'/'yesterday' → 1 day, '24h' → 24 hours). None when nothing parses (caller falls back to the DB default
    range). No domain vocab beyond physical time words — new presets are DB rows."""
    from datetime import timedelta
    t = str(token or "").strip().lower()
    if not t:
        return None
    from config.windows import TIME_WINDOWS
    preset = TIME_WINDOWS.get(t)
    if preset:
        d = _lookback_delta(preset.get("lookback"))
        if d:
            return d
    tt = t.replace("-", " ").replace("_", " ")
    d = _lookback_delta(tt)
    if d:
        return d
    words = {"month": 30 * 86400.0, "week": 7 * 86400.0, "today": 86400.0, "yesterday": 86400.0, "day": 86400.0}
    for w, secs in words.items():
        if w in tt.split():
            return timedelta(seconds=secs)
    if "24h" in tt:
        return timedelta(hours=24)
    return None


def _window_anchor(table):
    """(datetime, source) — the DATA's reference 'now' the default window anchors to (anchor-now-to-data, always ON):
      1) the resolved TABLE's own latest logged ts — safe on a static/lagging dump, where a wall-clock 'now' sits
         AFTER the last row and the trailing window would come back EMPTY;
      2) the configured reference now — app_config `windows.reference_now` row, else the same EMS_REFERENCE_NOW env
         the legacy EMS launch used (docs/IMPLEMENTATION_PROGRESS.md);
      3) wall-clock UTC — only reached when the resolved device table is EMPTY (e.g. the PCC panel devices 317-320,
         whose data is the member fan-out) AND no reference row/env is pinned. Never raises."""
    from datetime import datetime, timezone
    if table:
        try:
            from config import neuract_dsn as _dsn
            from ems_exec.data import neuract as _nx
            ts = (_nx.latest(table, [_dsn.ts_col()]) or {}).get(_dsn.ts_col())
            if ts:
                return datetime.fromisoformat(str(ts)), "table_latest_ts"
        except Exception:
            pass
    import os
    from config.app_config import cfg
    ref = cfg("windows.reference_now", "") or os.environ.get("EMS_REFERENCE_NOW") or ""
    if ref:
        try:
            return datetime.fromisoformat(str(ref)), "reference_now"
        except Exception:
            pass
    from replay.clock import now as _replay_now                 # frozen to the original instant during a replay
    return _replay_now(timezone.utc), "wall_clock"


def _slots_declared_range(di, recipe_slots=None):
    """The emit's OWN per-slot range CONSENSUS [c14 'Monthly'-value-under-'Last 24h'-label]: the AI often declares its
    period on the SLOTS (fields[].range / roster[].range — the roster interpreter honors them per-slot: the MTD delta
    IS computed) while window/fetch stay null; the backfill then picked the 24h DB default and the coherence
    pass 'truthfully' rewrote the AI's Monthly label to Last-24h — inverting the mismatch instead of fixing it. When
    EVERY range-declaring slot (fields + roster emission + the card_fill_recipe row's own slots) agrees on ONE
    parseable token, that token IS the card's declared range. Disagreement / nothing declared → None (DB default)."""
    toks = set()
    for coll in ((di or {}).get("fields"), (di or {}).get("roster"), recipe_slots):
        for f in (coll or []):
            if isinstance(f, dict) and f.get("range"):
                toks.add(str(f["range"]).strip().lower())
    if len(toks) != 1:
        return None
    tok = next(iter(toks))
    return tok if _range_delta(tok) is not None else None


def _calendar_start(token, end):
    """The SITE-timezone CALENDAR start for a calendar range token ('today' → site midnight; 'this-week' → Monday;
    'this-month' → the 1st) anchored at `end` — so a declared calendar range backfills the true calendar window, not
    a rolling lookback approximation. None for a non-calendar token / on any failure (caller keeps end - delta)."""
    key = str(token or "").strip().lower().replace("_", "-")
    kind = {"today": "day", "day": "day", "this-week": "week", "week": "week",
            "this-month": "month", "month": "month", "monthly": "month"}.get(key)
    if not kind or end is None:
        return None
    try:
        from datetime import timedelta
        local, back = end, None
        if end.tzinfo is not None:
            from config.windows import site_tz
            local, back = end.astimezone(site_tz()), end.tzinfo
        d0 = local.replace(hour=0, minute=0, second=0, microsecond=0)
        if kind == "week":
            d0 -= timedelta(days=d0.weekday())
        elif kind == "month":
            d0 = d0.replace(day=1)
        return d0.astimezone(back) if back is not None else d0
    except Exception:
        return None


def _backfill_default_window(di, table, recipe_slots=None):
    """DEFAULT WINDOW BACKFILL [R1]: when the AI's data_instructions.window carries NO usable start/end (only lookback
    prose), the executor's _window_of resolves (None, None) and every bucketed/series/windowed-delta fill folds the
    table's ENTIRE logged history (188 buckets on card 17). Backfill a BOUNDED default window, deterministically:
      • the AI's own explicit bounds win — an existing window.start/end is honored untouched, and custom-range
        start/end the AI authored in the fetch spec is promoted into the window (AI-first, no override);
      • else the AI's OWN DECLARED range drives the bounds [window/label coherence, c16/c14]: window.lookback/
        window.range, the fetch spec's range ('last-7-days'), or — when those are null — the PER-SLOT range
        consensus (fields[].range / roster[].range / the recipe row's slots: the c14 emit declared 'this-month' ONLY
        on its roster slots) resolves via _range_delta, so the fill window AGREES with the range the values are
        actually computed over; a CALENDAR token anchors at the site-tz calendar start (true MTD, not a 30-day roll);
      • only when nothing was declared (or it is unparseable) does the DB knob decide: app_config
        `windows.default_range` row (falling back to the existing `windows.default_window` row
        config.windows.DEFAULT_WINDOW reads) → its config.windows.TIME_WINDOWS preset lookback, anchored to the
        data's reference now (_window_anchor).
    The FE date pick still overrides at fetch (host ctx.window beats di.window in the executor's _window_of).
    Mutates di; returns a telemetry note when a backfill was applied, else None. The structured note also rides
    di.window.backfill (visible in traces/sweeps — telemetry, never a render gate)."""
    from config.windows import ensure_nonzero_span
    w = di.get("window") if isinstance(di.get("window"), dict) else {}
    if w.get("start") or w.get("end"):
        # AI-authored bounds — honored as-is, EXCEPT a degenerate zero-width span (a same-day custom-range where the
        # AI wrote start==end): a counter delta over [today,today] folds every member to a false 0.0 (card-12). Extend
        # the END to span the full period so the delta reads the real energy; a normal forward window is untouched.
        s2, e2 = ensure_nonzero_span(w.get("start"), w.get("end"))
        if (s2, e2) != (w.get("start"), w.get("end")):
            di["window"] = {**w, "start": s2, "end": e2, "backfill": {"origin": "nonzero_span_guard"}}
            return "zero-width AI-authored window extended to a full-day span (custom-range start==end folds delta to 0)"
        return None
    eb = di.get("fetch") if isinstance(di.get("fetch"), dict) else {}
    if eb.get("start") or eb.get("end"):
        # Promote the AI's fetch-spec custom-range bounds, but never as a degenerate zero-width span (card-12's
        # 'today' custom-range emitted start==end==YYYY-MM-DD → member_delta over [today,today] == 0.0). Guarantee a
        # non-zero exclusive span so a same-day window spans [day 00:00, day+1 00:00) and the delta reads real kWh.
        s2, e2 = ensure_nonzero_span(eb.get("start"), eb.get("end"))
        origin = "fetch_spec" if (s2, e2) == (eb.get("start"), eb.get("end")) else "fetch_spec_nonzero_span"
        di["window"] = {**w, "start": s2, "end": e2, "backfill": {"origin": origin}}
        return ("window bounds promoted from the AI's fetch custom-range spec" if origin == "fetch_spec"
                else "zero-width fetch custom-range span extended to a full day (start==end folds delta to 0)")
    from config.app_config import cfg
    from config.windows import TIME_WINDOWS, DEFAULT_WINDOW
    declared = next((str(v) for v in (w.get("lookback"), w.get("range"), eb.get("range")) if v), None) \
        or _slots_declared_range(di, recipe_slots)
    delta = _range_delta(declared)
    if delta is not None:
        rng, origin = declared, "declared_range"                # AI-first: the emit's own range drives the bounds
    else:
        rng, origin = str(cfg("windows.default_range", DEFAULT_WINDOW)), "default_range"
        preset = TIME_WINDOWS.get(rng) or TIME_WINDOWS.get(DEFAULT_WINDOW) or {}
        delta = _lookback_delta(preset.get("lookback")) or _lookback_delta("24 hours")
    end, anchor = _window_anchor(table)
    cal = _calendar_start(rng, end) if origin == "declared_range" else None
    start = cal if cal is not None else end - delta
    # NON-ZERO SPAN GUARD (same guarantee as the custom-range paths above): a calendar anchor whose day is the same as
    # the anchor's own latest-ts (a 'today' whose data-now sits at site-midnight) would resolve start==end and fold the
    # delta to 0.0. Extend the end to at least a full day so the read always spans a real period; a normal window
    # (end strictly after start) is returned unchanged.
    s_iso, e_iso = ensure_nonzero_span(start.isoformat(), end.isoformat())
    di["window"] = {**w, "start": s_iso, "end": e_iso,
                    "backfill": {"origin": origin, "range": rng, "anchor": anchor}}
    return f"{origin} window backfilled: {rng} [{s_iso} .. {e_iso}] anchored to {anchor}"
