"""layer2/build.py — Layer 2 GENERAL per-card entry (contract 5). One fan-out unit:
assemble input -> AI emit {swap, exact_metadata(morphs), data_instructions} -> deterministic gates -> Layer2CardOutput.
On an ACCEPTED swap, RE-EMIT for the swapped-in card (it has a different shape) — the payload always matches the FINAL
card. AI DECIDES (swap + morphs + recipe); deterministic code SUPPORTS (copy defaults, gate, assemble). [spec §2 L2]"""
import re

from layer2.card_input import build_card_input, build_swap_target_input
from layer2.emit.emit import emit
from layer2.emit.metadata.producer import produce, metadata_reference, undeclared_morphs
from layer2.emit.data.consumer_binding import build as consumer_build
from layer2.resolve.column_override import apply as override_columns
from layer2.swap.decide import gate as swap_gate
from layer2.gates import (gate_exact_metadata, gate_data_instructions, gate_roster, enforce_exact_metadata,
                          enforce_free_metadata)
from layer2.schema import validate_layer2_card_output
from data.db_client import q


def _page_card_ids(page_key):
    return [int(x[0]) for x in q("cmd_catalog",
            f"SELECT DISTINCT card_id FROM page_layout_cards WHERE page_key=$a${page_key}$a$ AND card_id IS NOT NULL") if x and x[0]]


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


def _seedfree_default(dp):
    """The card's default payload for `_default_payload` — the SEEDLESS skeleton, so NO Storybook seed can ride the L2
    output to the executor's graft/config-chrome-byte-copy/offline-replay (ZERO-fabrication mandate). The executor uses
    `_default_payload` only for data-leaf PATHS + a value SOURCE (config-chrome byte-copy fill.py:822, container graft
    fill.py:801); the raw `dp['payload']` carried live Storybook seeds (card-42 'Welding Overlap', card-51 battery
    prose) that could survive an UNdeclared sibling leaf. `dp['payload_stripped']` is the STORED, byte-verified seedless
    skeleton (same chrome structure + same leaf PATHS — 0 dropped chrome keys across all 155 rows; only seed VALUES
    blanked to typed placeholders), so it is a strictly-safe drop-in. If a row lacks the stored skeleton (should not
    happen — 155/155 built), fall back to the RUNTIME graft-blank of the raw copy (grounding.default_assemble.
    blank_data_leaves) — NEVER re-introduce raw seeds. None when the card was never harvested."""
    if not dp:
        return None
    stored = dp.get("payload_stripped")
    if stored is not None:
        return stored
    raw = dp.get("payload")
    if raw is None:
        return None
    try:                                                       # stored skeleton absent (should not happen — 155/155 built):
        from grounding.default_assemble import strip_to_placeholders   # apply the SAME build-time strip to the raw source
        return strip_to_placeholders(raw)                      # (data leaves + narrative/clock/role scrub) — NEVER raw seeds
    except Exception:
        return None                                            # honest-degrade: no seedless source → no offline-replay/graft default


def _window_anchor(table):
    """(datetime, source) — the DATA's reference 'now' the default window anchors to (anchor-now-to-data, always ON):
      1) the resolved TABLE's own latest logged ts — safe on a static/lagging dump, where a wall-clock 'now' sits
         AFTER the last row and the trailing window would come back EMPTY;
      2) the configured reference now — app_config `windows.reference_now` row, else the same EMS_REFERENCE_NOW env
         the ems_backend launch uses (docs/IMPLEMENTATION_PROGRESS.md);
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
    return datetime.now(timezone.utc), "wall_clock"


def _slots_declared_range(di, recipe_slots=None):
    """The emit's OWN per-slot range CONSENSUS [c14 'Monthly'-value-under-'Last 24h'-label]: the AI often declares its
    period on the SLOTS (fields[].range / roster[].range — the roster interpreter honors them per-slot: the MTD delta
    IS computed) while window/ems_backend stay null; the backfill then picked the 24h DB default and the coherence
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
        start/end the AI authored in the ems_backend spec is promoted into the window (AI-first, no override);
      • else the AI's OWN DECLARED range drives the bounds [window/label coherence, c16/c14]: window.lookback/
        window.range, the ems_backend spec's range ('last-7-days'), or — when those are null — the PER-SLOT range
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
    w = di.get("window") if isinstance(di.get("window"), dict) else {}
    if w.get("start") or w.get("end"):
        return None                                            # AI-authored bounds — honored as-is
    eb = di.get("ems_backend") if isinstance(di.get("ems_backend"), dict) else {}
    if eb.get("start") or eb.get("end"):
        di["window"] = {**w, "start": eb.get("start"), "end": eb.get("end"),
                        "backfill": {"origin": "ems_backend_spec"}}
        return "window bounds promoted from the AI's ems_backend custom-range spec"
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
    di["window"] = {**w, "start": start.isoformat(), "end": end.isoformat(),
                    "backfill": {"origin": origin, "range": rng, "anchor": anchor}}
    return f"{origin} window backfilled: {rng} [{start.isoformat()} .. {end.isoformat()}] anchored to {anchor}"


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
        gaps = []
        for s in unbound:
            try:
                from config.reason_templates import reason as _reason
                sentence = _reason("unbound_by_emit", metric=s)
            except Exception:
                sentence = "unbound_by_emit"
            if note:
                sentence = f"{sentence} ({note})"
            gaps.append({"slot": s, "cause": "unbound_by_emit", "metric": s, "column": None, "fn": None,
                         "reason": sentence})
        di["_emit_gaps"] = gaps


def _fn_quantity_map():
    """{library fn -> its output quantity string} from the derivation registry, for the cross-domain honesty check."""
    try:
        from ems_exec.derivations.registry import catalog
        return {e["fn"]: e.get("quantity") for e in catalog()}
    except Exception:
        return {}


def _cross_domain_fields(di):
    """Data fields whose bound column/fn measures a DIFFERENT physical DOMAIN than the field's own slot — a wrong-KIND
    stand-in that must never claim "full" (E: a current column under a voltage-THD leaf; G: an energy fn in a 'years'
    leaf). Generic + DB-driven: config.metrics.quantity_family over the SLOT PATH's own semantic (not the AI-authored
    metric label, which the AI can bend to match its wrong pick) vs the bound column / fn quantity. A None family on
    EITHER side → NOT flagged (no false positive on a legitimate same-quantity bind). Returns
    [(slot, slot_family, source, source_family)]."""
    from config.metrics import quantity_family, slot_semantic_label
    fn_q = _fn_quantity_map()
    out = []
    for f in (di.get("fields") or []):
        if f.get("kind") in ("time", "const", "event"):
            continue
        slot = f.get("slot") or ""
        sfam = quantity_family(slot_semantic_label(slot))
        if not sfam:
            continue
        if f.get("kind") == "derived":
            src = f.get("fn") or ""
            cfam = quantity_family(fn_q.get(src) or src)
        else:                                             # raw / bucketed → its real column
            src = f.get("column") or ""
            cfam = quantity_family(src)
        if cfam and cfam != sfam:
            out.append((slot, sfam, src, cfam))
    return out


def _cross_domain_note(xdom):
    """One truthful user-facing sentence: the leaf's real quantity isn't measured, a different-quantity stand-in fills
    it. The honest override for a wrong-kind fill (per-leaf degradation, never a card-block)."""
    slot, sfam, src, cfam = xdom[0]
    extra = f" (and {len(xdom) - 1} other leaf(s))" if len(xdom) > 1 else ""
    return (f"{sfam} isn't measured for this leaf on this asset — a {cfam} value ({src}) is shown as an approximate "
            f"stand-in{extra}; treat it as indicative, not the exact {sfam} reading.")


def _finalize(ci, raw, swap, *, reemit_of=None):
    """Produce the Layer2CardOutput for the FINAL card (ci) from its AI emit (raw) + the resolved swap decision."""
    basket = ci["column_basket"]
    dp = ci["catalog_row"].get("default_payload")
    # LLM-TRANSPORT HONESTY [empty-fields family, cards 74/76]: a failed call is now a MARKER ({"_llm_error": kind}),
    # never a silent {} that reads as an intentional empty emission. The card still renders its byte-identical
    # metadata frame (per-leaf degradation), but answerability NEVER defaults to "full", conforms=False, and the
    # failure stage is 'llm' so sweeps bucket it apart from emit quality.
    llm_err = raw.get("_llm_error") if isinstance(raw, dict) else None
    ai_meta = raw.get("exact_metadata") or {}
    morphed = ai_meta.pop("_morphed", []) if isinstance(ai_meta, dict) else []
    failures = []
    if llm_err:
        failures.append(f"llm call failed ({llm_err}): {raw.get('_llm_error_detail') or ''}".strip())

    if dp:
        # REFERENCE = the STRIPPED default (data leaves → typed placeholders), NOT the raw seed-bearing default: the
        # byte-identity gate/enforce must compare metadata against what exact_metadata is actually built from, else a
        # correctly-stripped data leaf (0/[]) reads as a 'violation' and enforce reverts it back to the seed (389.2).
        # STORED skeleton (card_payloads.payload_stripped, scripts/build_stripped_payloads.py) — the pre-cleaned,
        # inspectable DB row; NULL (un-built) → producer falls back to the identical on-the-fly strip.
        _stored = dp.get("payload_stripped")
        ref = metadata_reference(dp["payload"], stored=_stored)
        exact_metadata, applied, rejected = produce(dp["payload"], ai_meta, morphed, stored=_stored)
        # UNDECLARED-MORPH TELEMETRY [A1]: metadata paths the AI authored off-default WITHOUT declaring in _morphed —
        # produce() silently reverts those to the byte-identical default (2-of-6812 _morphed compliance made ALL
        # authoring a silent no-op). Telemetry only, NO auto-promote (the byte-identity seam stays closed).
        _undeclared = undeclared_morphs(dp["payload"], ai_meta, morphed, stored=_stored)
        failures += [f"morph rejected: {r}" for r in rejected]
        ok_m, m_issues = gate_exact_metadata(exact_metadata, ref, morphed=applied)
        # LOAD-BEARING byte-identity enforcement [META-02]: if the gate flags a metadata byte-identity/chrome/shape
        # violation, REVERT the offending METADATA leaf to its byte-identical default (the stripped ref) so the resting
        # render is guaranteed conforming — WITHOUT re-introducing a seed data value.
        if not ok_m:
            exact_metadata, reverted = enforce_exact_metadata(exact_metadata, ref, morphed=applied)
            failures += [f"reverted to default: {p}" for p in reverted]
            ok_m, m_issues = gate_exact_metadata(exact_metadata, ref, morphed=applied)
        failures += m_issues
    else:
        # NO harvested default (no stored payload_stripped): the AI authors exact_metadata off the CONTRACT EXAMPLE,
        # which carries demo numbers and clock labels ('13:14:10') — shipped verbatim they render a FABRICATED live
        # time axis (cards 6/160). enforce_exact_metadata (needs a default ref) can't cover this, so the ONE scrub the
        # no-default path needs is FOLDED into the gates layer as enforce_free_metadata: data leaves → typed
        # placeholders, narrative/clock scrubbed, reusing the canonical strip worker (NOT a second strip, NOT a runtime
        # strip_to_placeholders caller). Chrome untouched; never raises.
        exact_metadata, applied = enforce_free_metadata(ai_meta), []
        _undeclared = []
        ok_m = bool(ai_meta)
        if not ok_m:
            failures.append("no default payload + empty exact_metadata")

    di = raw.get("data_instructions") or {"fields": []}
    # NESTED-ENVELOPE RESCUE [A4]: some emits nest `answerability`/`data_note` INSIDE data_instructions instead of the
    # top level (29 across the log archive) — hoist them out (they are card-envelope keys, not fill recipe) so the
    # honesty channel never loses a declared verdict/note. Top-level wins when both exist.
    _nested_answer = di.pop("answerability", None) if isinstance(di, dict) else None
    _nested_note = di.pop("data_note", None) if isinstance(di, dict) else None
    _declared_answer = raw.get("answerability") or _nested_answer
    _declared_note = raw.get("data_note") or _nested_note
    # NORMALIZATION TELEMETRY [silent-normalization defect]: override notes ride di._normalized (visible in traces /
    # sweeps — hallucination counts feed the prompt-steer loop) and NEVER gate conforms — per-leaf degradation.
    di, ov_notes = override_columns(di, basket, data_note=raw.get("data_note"), applied_morphs=applied)
    if ov_notes:
        di["_normalized"] = ov_notes
    # DETERMINISTIC ENVELOPE COMPLETION [META-08]: backfill payload_shape/orientation/entity_dim from the catalog
    # card_data_recipe whenever the AI omitted them (a Qwen fail-open ships an incomplete envelope the FE mapper can't
    # key on). The recipe is the ground-truth per-card shape, so the envelope is ALWAYS complete even on emit failure.
    cr = ci["catalog_row"]
    _recipe = cr.get("recipe") or {}
    for _k in ("payload_shape", "orientation", "entity_dim"):
        if di.get(_k) in (None, "") and _recipe.get(_k) is not None:
            di[_k] = _recipe.get(_k)
    if "fields" not in di:
        di["fields"] = []
    # DEFAULT WINDOW BACKFILL [R1] — only for a DATA-bearing card (fields / a roster emission / a roster recipe): a
    # window with no usable start/end reaches the executor as (None, None) and folds the ENTIRE table history into
    # bucketed/series/windowed-delta fills. Runs BEFORE consumer_build so the shipped consumer sees the same window.
    if di["fields"] or di.get("roster") or _recipe.get("roster_spec"):
        _backfill_default_window(di, (ci.get("asset") or {}).get("table"),
                                 recipe_slots=(_recipe.get("roster_spec") or {}).get("slots"))
    # DETERMINISTIC: attach the consumer-driving params so the DATA-fill helper drives V48's ems_backend WS dispatcher
    di["consumer"] = consumer_build(cr, ci.get("asset"), ci["page_key"], window=di.get("window"), ai_spec=di.get("ems_backend"))
    if di.get("binding") is None and ci.get("asset"):
        a = ci["asset"]
        di["binding"] = {"asset_id": a.get("mfm_id"), "table": a.get("table"),
                         "panel_id": a.get("panel_id"), "ts_col": None, "nameplate_scope": "default"}
    # WINDOW/LABEL COHERENCE [c14 'Monthly'+range=this-month over a 24h fill]: a period-declaring metadata leaf
    # (periodLabel / range) must AGREE with the fill window the shipped consumer will use — a stale default period
    # caption over a different fill window mislabels every number under it. Deterministic per-leaf self-heal (morph to
    # the window truth / blank, policy row gates.window_label_policy), telemetry via di._window_label + the rewritten
    # paths in _applied_morphs. Never a card gate. [layer2/coherence.py, db/seed_emit_coherence.sql]
    from layer2.coherence import reconcile_window_labels
    _wl = reconcile_window_labels(exact_metadata, di)
    if _wl:
        applied = list(applied) + [w["path"] for w in _wl]
        di["_window_label"] = _wl
    # ROSTER gate [package §2d] — runs BEFORE the fields gate so a ROSTER-SERVED card is recognized there: validate
    # the AI's member-scope emission against the card's card_fill_recipe row + the column basket (slots must exist in
    # the recipe; columns verbatim-real; recipe honest-null keys stay null). VALIDATION not correction — the recipe
    # row is authoritative, clean AI column choices fold in, and omitted slots backfill verbatim, so the shipped
    # roster is ALWAYS the complete recipe truth (issues are telemetry, never a render gate — per-leaf degradation).
    # ORDERING IS LOAD-BEARING [roster-aware failures]: a roster-served card (recipe row present) legitimately emits
    # fields: [] — its DATA rides the roster interpreter, not fields[]. gate_data_instructions only accepts that when
    # di["roster"] is already populated, so the recipe backfill MUST land first; running it after the fields gate
    # recorded a FALSE 'data_instructions.fields is empty' payload_error on conforming roster cards (26/27/5).
    _rspec = _recipe.get("roster_spec")
    r_issues = []
    roster_honest_blank = None
    if _rspec or di.get("roster"):
        _ok_r, r_issues, di["roster"] = gate_roster(di.get("roster") or [], _rspec, basket)
        # HONEST-BLANK ROSTER NORMALIZATION [empty-roster payload_error, sweep card 21]: when the AI emits a roster on a
        # card whose recipe carries NO roster_spec, gate_roster ALREADY drops it to [] — the card's member data rides
        # its backend_strategy consumer's panel-member fan-out (or honest-blanks per member), NOT a roster_spec. That
        # is a per-LEAF honest-blank normalization, NOT a card conformance error, so its telemetry MUST NOT become the
        # card-blocking failure.detail/payload_error (the mandate: degrade per-leaf, never per-card; verdicts are
        # telemetry, not render gates). Partition it out of `failures`: it stays a data_note (visible in traces) and the
        # card renders its real component with member leaves honest-blank. Generic — no card id/vocab, any recipe-less
        # roster card. A GENUINE mis-binding (hallucinated column / bad slot on a card that HAS a recipe) still fails.
        _no_recipe = [i for i in r_issues if "no roster recipe" in i]
        if _no_recipe and not _rspec:
            r_issues = [i for i in r_issues if i not in _no_recipe]
            roster_honest_blank = ("member data rides the panel-aggregation consumer, not a roster recipe — "
                                   "per-member leaves honest-blank where no data")
    # fields[] is OPTIONAL for the classes whose DATA never comes from fields (pure chrome / run_special widget
    # builders) — ONE DB-driven vocabulary (config.gates_vocab, shared with the emit prompt + validate) so the
    # prompt and the gate can never disagree [A6a].
    from config.gates_vocab import fields_optional_classes as _foc
    _fields_optional = cr.get("handling_class") in _foc()
    ok_d, d_issues = gate_data_instructions(di, basket, is_group_card=ci["is_group_card"],
                                            fields_optional=_fields_optional,
                                            answerability=_declared_answer,
                                            exact_metadata=exact_metadata)
    failures += d_issues
    failures += r_issues                # roster telemetry AFTER gate issues — the failure reason stays a real gate hit

    # DETERMINISTIC COMPLETENESS RECONCILE — slot-catalog coverage diff (telemetry + the per-leaf 'unbound_by_emit'
    # reason records fill.py merges into the honest-gap channel). Never a render gate.
    _reconcile_slots(di, dp["payload"] if dp else None, basket, fields_optional=_fields_optional,
                     data_note=_declared_note)

    conforms = ok_m and ok_d and bool(exact_metadata) and not llm_err
    # BEST-EFFORT / ANSWERABILITY: the AI reports whether it could answer the card's story with REAL columns —
    # "full" (exact), "partial" (rendered via a real substitute, + data_note), or "none" (a genuine GAP that the
    # orchestrator may re-route on). gap drives the reflect-loop; data_note (loop-1 note) is saved for the user.
    # ★ NO FAIL-OPEN [A4]: an emit that DECLARES no answerability (top-level or nested) defaults to "partial" —
    # the absence of a declaration is NOT a declaration of full (the old absence→"full" default stamped ~10% of
    # emits fully-answered by code). Same for an invalid token. An LLM-transport failure degrades identically.
    answerability = _declared_answer or "partial"
    if answerability not in ("full", "partial", "none"):
        answerability = "partial"
    data_note = _declared_note or None
    if llm_err and not data_note:
        data_note = "AI emit unavailable (transport failure) — default metadata shown, data leaves honest-blank"
    # HONEST-NONE EMPTY-SCHEMA note [card 74]: fields:[] on a none/empty-basket emission is legitimate (gate carve-out)
    # but must stay EXPLAINED — surface a note when the AI omitted one.
    if not (di.get("fields") or di.get("roster")) and not _fields_optional and not data_note \
            and (str(_declared_answer or "").lower() == "none" or not (basket.get("columns") or [])):
        data_note = "no measurable columns for this card's story on this asset — leaves honest-blank"
    # an honest-blank roster normalization (recipe-less roster dropped to []) is a per-leaf degradation, not a full
    # answer — surface it as the user-facing note + soften answerability (the card still renders, its member leaves
    # honest-blank). Never a gap/re-route; never a card-blocking failure.
    if roster_honest_blank:
        data_note = data_note or roster_honest_blank
        if answerability == "full":
            answerability = "partial"
    # ZERO-SKELETON HONESTY [cards 19/25 — 'emit zero-skeleton']: an emit that binds NOTHING (fields [] AND no roster)
    # on a card that HAS data leaves, with NO data channel that could ever fill them either (no consumer endpoint AND
    # no backend_strategy — so neither the ws consumer fan-out nor a run_special builder will write a leaf), ships the
    # stripped skeleton's 0/[] typed placeholders as if they were values: the false '0 issues' story. Treat it as
    # HONEST-BLANK TELEMETRY WITH REASONS, never a silent empty card: every catalog slot gets an 'unbound_by_emit'
    # per-leaf reason (_emit_gaps — the same channel fill.py merges), answerability never claims "full", and a
    # data_note explains the blanks. Generic — no card ids; a special/narrative card WITH a backend_strategy (card 8's
    # working AI summary) or a panel_aggregate consumer is exempt (its data arrives through that channel). Telemetry
    # marker di._zero_skeleton; never a card-blocking gate (per-LEAF degradation mandate).
    _consumer = di.get("consumer") if isinstance(di.get("consumer"), dict) else {}
    if (dp and (dp.get("data_paths") or [])) and not di.get("fields") and not di.get("roster") \
            and not (_consumer.get("endpoint") or _consumer.get("backend_strategy")):
        di["_zero_skeleton"] = True
        if not di.get("_emit_gaps"):                            # fields-optional classes skipped the reconcile — every
            _reconcile_slots(di, dp["payload"], basket,         # data leaf still needs its per-leaf reason
                             fields_optional=False, data_note=_declared_note)
        if answerability == "full":
            answerability = "partial"
        data_note = data_note or ("nothing could be bound for this card on this asset — every data leaf renders an "
                                  "honest blank (per-leaf reasons attached), not a zero")
    gap = answerability == "none"
    # TOPOLOGY INFEASIBILITY IS PRE-L2 NOW [validation-streamline]: the deterministic 'requires feeder topology but the
    # asset has no feeders' check moved into run_validate (validate/build._expected_gaps) — the harness re-routes on its
    # roll-up BEFORE the N-emit fan-out, so a whole infeasible page no longer burns a full LLM pass to be discovered in
    # reflect. The residual post-L2 gap here is ONLY the AI-discovered answerability='none'. Per-card honesty stays:
    # an infeasible card that slipped through (below the re-route threshold) keeps the explanatory note, per-leaf.
    # (Special-renderer / fields-optional classes are exempt as before: their required_mesh is the 3D/SLD chrome.)
    feas = ci["catalog_row"].get("feasibility") or {}
    if (feas.get("required_topology") or feas.get("required_mesh")) and not (ci.get("asset") or {}).get("has_feeders") \
            and not _fields_optional:
        data_note = data_note or "card needs feeder topology; the resolved asset has no feeders"
        if answerability == "full":
            answerability = "partial"
    # CROSS-DOMAIN HONESTY [semantic mis-bind E / bad derived math G]: a data field bound to a column/fn of a DIFFERENT
    # physical domain than its slot (a current column under a voltage-THD leaf; an energy fn in a 'years' leaf) is a
    # wrong-KIND stand-in — it must NEVER claim "full". Deterministically force ≥partial + a truthful generated note
    # (overriding a possibly-false AI note). Generic + DB-driven (config.metrics.quantity_family); per-leaf telemetry,
    # never a card-blocking failure. This is the honesty backstop for a substitute the prompt tried to prevent.
    _xdom = _cross_domain_fields(di)
    if _xdom:
        if answerability == "full":
            answerability = "partial"
        data_note = _cross_domain_note(_xdom) if not data_note else data_note + " " + _cross_domain_note(_xdom)
        di["_cross_domain"] = [{"slot": s, "slot_family": sf, "source": src, "source_family": cf}
                               for (s, sf, src, cf) in _xdom]
    out = {
        "card_id": ci["card_id"],
        "$ctx": ci["group_id"] if ci["is_group_card"] else None,
        "render_slot": raw.get("render_slot") or "",
        "analytical_story": raw.get("analytical_story") or ci["story"]["analytical_story"],
        "swap_decision": swap,
        "exact_metadata": exact_metadata,
        "data_instructions": di,
        "controls": raw.get("controls"),
        "answerability": answerability,
        "data_note": data_note,
        "gap": gap,
        "conforms": conforms,
        "failure": None if conforms else {"stage": "llm" if llm_err else "emit",
                                          "reason": f"llm_{llm_err}" if llm_err
                                          else (failures[0] if failures else "unknown"),
                                          "detail": "; ".join(failures[:6])},
        "_applied_morphs": applied,
        "_undeclared_morphs": _undeclared,      # [A1] authored-but-undeclared metadata changes produce() reverted (telemetry)
        "_reemit_of": reemit_of,
        "_default_payload": _seedfree_default(dp),            # data-leaf paths + offline replay source for the DATA-fill (SEEDLESS)
    }
    out["_schema_issues"] = validate_layer2_card_output(out)
    # LOAD-BEARING SCHEMA GATE [META-08]: if the envelope still can't be completed after the deterministic backfill
    # (payload_shape/orientation/fields missing) the FE mapper has nothing to key on → honest-degrade rather than ship a
    # propless card marked answerable. A missing-shape issue flips answerability to 'partial' (no worse — the card still
    # renders its metadata frame, but the story is flagged as not fully data-bound).
    _shape_broken = any(("payload_shape" in i or "orientation" in i or "exact_metadata must be" in i)
                        for i in (out["_schema_issues"] or []))
    if _shape_broken and out["answerability"] == "full":
        out["answerability"] = "partial"
        out["data_note"] = out.get("data_note") or "data envelope incomplete (shape unresolved) — metadata-only render"
    return out


def run_card(run_id, card_id, l1a, l1b, *, already_chosen=None, shared_ctx_ref=None):
    already_chosen = already_chosen or set()
    ci = build_card_input(run_id, card_id, l1a, l1b, shared_ctx_ref=shared_ctx_ref)

    # PRE-EMIT RENDERABILITY [wasted-emit fix]: a KNOWN-unrenderable card (static catalog verdict in
    # config.feasibility.UNRENDERABLE_VERDICTS) had its first emit ALWAYS discarded — the force-swap replaced the card
    # and a second emit ran for the target. The forced decision needs NO AI input (verdict + pool + already_chosen are
    # all pre-known), so decide it BEFORE the first emit and emit ONCE, for the final card only. Pure reordering —
    # gate_force_renderable produces the identical decision it would have produced post-emit. [audit: run_card ordering]
    _current_verdict = (ci["catalog_row"].get("feasibility") or {}).get("verdict")
    from layer2.swap import gate_force_renderable as _force
    if _force.is_unrenderable(_current_verdict) and ci["swap_candidates"]:
        forced, _kept = _force.enforce({"action": "keep"}, verdict=_current_verdict,
                                       pool=ci["swap_candidates"], already_chosen=already_chosen)
        tgt = forced.get("swap_to_id")
        if forced.get("origin") == "swapped" and tgt and tgt != card_id:
            target_ci = build_swap_target_input(run_id, tgt, ci, l1b)
            return _finalize_with_gate_retry(target_ci, emit(target_ci), forced, reemit_of=card_id)
        # no unclaimed renderable replacement → fall through: emit for the kept card (honest, never fabricate)

    raw = emit(ci)

    # RENDERABILITY ENFORCER inputs: the CURRENT card's feasibility verdict + the swap pool (candidates.py filters it
    # to POOL_VERDICTS (render_real) + recoverable-default + registered renderer [META-05, FR-5]). If the current card
    # is UNRENDERABLE (config.feasibility.UNRENDERABLE_VERDICTS), swap_gate force-swaps it to a renderable candidate
    # not already claimed by another slot. A FORCED swap is stamped confidence=FORCED_SWAP_CONFIDENCE (>1.0) so the
    # parallel runner's settle post-pass (grounding.swap_settle, highest-confidence-first) never reverts a MANDATORY
    # swap in favor of another slot's optional stylistic swap on the same target. [user rule 1, META-04]
    swap = swap_gate(raw.get("swap_decision") or {"action": "keep"},
                     pool_ids=[c["card_id"] for c in ci["swap_candidates"]],
                     template_card_ids=ci["story"]["template_card_ids"], already_chosen=already_chosen,
                     page_card_ids=_page_card_ids(ci["page_key"]), current_card_id=card_id,
                     current_verdict=_current_verdict, pool=ci["swap_candidates"])

    # SWAP-TARGET RE-EMIT: the first emit authored the payload for `card_id`'s shape; the FINAL card is the swap
    # target, which has a DIFFERENT shape. Re-run the emit for the target (it inherits the slot's story) so the
    # payload matches the final card. The swap decision from pass 1 stands.
    tgt = swap.get("swap_to_id")
    if swap.get("origin") == "swapped" and tgt and tgt != card_id:
        target_ci = build_swap_target_input(run_id, tgt, ci, l1b)
        target_raw = emit(target_ci)
        return _finalize_with_gate_retry(target_ci, target_raw, swap, reemit_of=card_id)

    return _finalize_with_gate_retry(ci, raw, swap)


def _finalize_with_gate_retry(ci, raw, swap, *, reemit_of=None):
    """GATE-FAILURE RE-PROMPT [the biggest lost-value seam: hundreds of cards shipped degraded where one corrective
    re-emit would have fixed the emission]. When the finalized card does NOT conform and the failure is an EMIT-stage
    gate hit, re-emit ONCE with the EXACT gate issues appended to the user message (temp=0 + pinned seed means a blind
    retry is byte-identical — the injected feedback is what changes the completion). Keep whichever result conforms
    (retry preferred); telemetry rides `_gate_retry`. Bounded by the DB knob app_config llm.gate_retry (default 1);
    generic — no card ids, no per-card vocab. An 'llm'-stage failure is NOT re-prompted here (emit() already did the
    bounded transport retry)."""
    out = _finalize(ci, raw, swap, reemit_of=reemit_of)
    from config.app_config import cfg as _cfg
    retries = max(0, int(_cfg("llm.gate_retry", 1)))
    f = out.get("failure") or {}
    if out.get("conforms") or not retries or f.get("stage") != "emit" or not f.get("detail"):
        return out
    feedback = [s for s in (f.get("detail") or "").split("; ") if s]
    raw2 = emit(ci, feedback=feedback)
    out2 = _finalize(ci, raw2, swap, reemit_of=reemit_of)
    if out2.get("conforms"):
        out2["_gate_retry"] = "retried_fixed"
        return out2
    out["_gate_retry"] = "retried_not_fixed"
    return out
