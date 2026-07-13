"""host/enrich.py — the FE CARD BUILD at the serve boundary: fold the executor's completed payload + Layer-2 output +
the post-fill render verdict into the ONE card dict the frontend renders, with the honest blank-reason wording
(per-leaf gap sentences → per-metric → whole-asset last resort) and the emit-gap merge. One concern; host/server
re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

from validate import render_verdict as _rverdict   # the ONE post-fill verdict (see the retirement note in git history)
from host.payload_store import _skeleton_payload, _raw_default_payload
from layer1b.resolve.member_scope import OUTGOING


def _gap_note(gaps, budget=300):
    """Join the executor's per-leaf honest-gap sentences into ONE reason line — deduped, WHOLE sentences only (never a
    mid-sentence slice), disclosing how many further leaves carry a reason. None when no gap carries a sentence."""
    notes = list(dict.fromkeys(g.get("reason") for g in (gaps or []) if g.get("reason")))
    if not notes:
        return None
    take = [notes[0]]
    for s in notes[1:]:
        if len("; ".join(take + [s])) > budget:
            break
        take.append(s)
    extra = len(notes) - len(take)
    return "; ".join(take) + (f" (+{extra} more)" if extra else "")


def _no_data_reason(asset_name):
    """The LAST-RESORT blank reason (no per-leaf gap record survived) — the editable cmd_catalog.reason_template
    'no_data' row, never a dangling hardcoded sentence. Code-default only on a DB outage."""
    try:
        from config.reason_templates import reason as _reason
        return _reason("no_data", asset=asset_name or "this asset")
    except Exception:
        return "no live data logged"


def _asset_has_logged_data(asset_table):
    """Does this resolved meter carry ANY logged column at all? The F3 honesty guard: the whole-asset 'No data logged
    for this asset' reason may fire ONLY when the meter is genuinely dark (every column NULL / no rows). When even ONE
    column is logged, a card that blanked did so PER-METRIC (its declared columns are dead) — never whole-asset. Cheap:
    one bounded scan of the present columns for any non-null. False (→ allow the whole-asset reason) on any error."""
    try:
        from ems_exec.data import neuract as _nx
        cols = list(_nx.present_columns(asset_table))
        for c in cols:                                            # short-circuits on the first logged column (cached)
            if _nx.column_logged(asset_table, c):
                return True
        return False
    except Exception:
        return False


def _per_metric_blank_reason(data_instructions, asset_name):
    """A PER-METRIC blank reason when the card blanked but its meter HAS data (F3): name the declared metrics/columns
    that produced no live value, via the editable cmd_catalog.reason_template 'structurally_null' row — never the
    whole-asset 'no data logged' claim. Falls back to the generic per-metric sentence on a DB outage."""
    metrics = []
    for f in ((data_instructions or {}).get("fields") or []):
        if isinstance(f, dict):
            m = f.get("label") or f.get("metric") or f.get("column") or f.get("slot")
            if m and m not in metrics:
                metrics.append(str(m))
    label = ", ".join(metrics[:4]) + (f" (+{len(metrics) - 4} more)" if len(metrics) > 4 else "") if metrics else "these metrics"
    try:
        from config.reason_templates import reason as _reason
        return _reason("structurally_null", metric=label)
    except Exception:
        return f"{label} not logged by this meter."


def _graft_card_title(payload, card_title):
    """DEFENSE-IN-DEPTH [metadata-stripping]: a card must NEVER render NAMELESS. When the served payload's own title
    leaf is blank (None/''/'—') but cmd_catalog carries the card's title (card.title, e.g. 'Power & Energy
    (Real-Time)'), graft card.title in. CHROME-ONLY, never a reading: only an EXISTING `title` key is filled (the
    payload shape is never grown), a non-blank payload title always wins, and the graft source is catalog metadata.
    Checks the canonical homes in order: payload.data.title then payload.title. Mutates + returns `payload`; never
    raises (fail-open on the served payload). [atomic]"""
    try:
        if not card_title or not isinstance(payload, dict):
            return payload
        for holder in (payload.get("data"), payload):
            if isinstance(holder, dict) and "title" in holder:
                if holder.get("title") in (None, "", "—"):
                    holder["title"] = str(card_title)
                return payload                                # first title home wins (a real title is never clobbered)
    except Exception:
        pass
    return payload


def _merge_emit_gaps(gaps, emit_gaps, payload):
    """Fold Layer 2's di._emit_gaps per-leaf reason records into the executor's gap list (serve boundary). Deduped by
    slot (both `x` and `data.x` address forms); a record whose leaf resolves in the served payload and is NOT blank is
    dropped (reasons describe the SERVED payload only); an unresolvable slot is kept (unverifiable ≠ stale, mirroring
    fill._prune_stale_gaps). Never raises."""
    out = list(gaps or [])
    if not emit_gaps:
        return out or None
    try:
        from ems_exec.executor.fill import _blank_val, _has_path, _leaf_at

        def _norm(slot):
            s = str(slot or "")
            return s[5:] if s.startswith("data.") else s

        seen = {_norm(g.get("slot")) for g in out if isinstance(g, dict)}
        for g in emit_gaps:
            if not isinstance(g, dict) or _norm(g.get("slot")) in seen:
                continue
            slot = g.get("slot")
            resolved, leaf = False, None
            for cand in (slot, f"data.{slot}" if slot else None):
                if cand and _has_path(payload or {}, cand):
                    resolved, leaf = True, _leaf_at(payload or {}, cand)
                    break
            if resolved and not _blank_val(leaf):
                continue                                     # the leaf filled real → the emit-time reason is stale
            seen.add(_norm(slot))
            out.append(g)
    except Exception:
        pass
    return out or None


_PERIOD_LABELS = {"today": "Today", "yesterday": "Yesterday", "this-week": "This Week", "this-month": "This Month",
                  "last-7-days": "Last 7 Days", "last-30-days": "Last 30 Days", "last-24-hours": "Last 24 Hours",
                  "custom-range": "Custom Range"}


def _period_label(date_window):
    """The human window label a '{period}' title token renders as — the OPERATIVE window's range prettified, 'Today'
    when no window is set (the page's resting read is today/latest). Never raises."""
    try:
        rng = str((date_window or {}).get("range") or "").strip().lower().replace("_", "-")
        return _PERIOD_LABELS.get(rng) or (rng.replace("-", " ").title() if rng else "Today")
    except Exception:
        return "Today"


def _sub_period(text, label):
    """Substitute a literal '{period}' template token in a chrome string ('Event Timeline at {period}') — the token is
    CARD METADATA the AI/coherence passes never fill, so it rendered literally/blank. Chrome-only, never a reading."""
    if isinstance(text, str) and "{period}" in text:
        return text.replace("{period}", label)
    return text


def _fill_period_labels(payload, label):
    """Set `<subtree>.period.label` to the operative window label ('Today' / 'Last 7 Days') — the CMD_V2 in-card title
    is `pres.titlePrefix + connector + period.label`, so this label IS the time period the header shows, and the host
    (which knows the window) OWNS it. Fills an empty label (the seed-strip resets it to ''), AND overwrites a label the
    AI wrongly authored as the SECTION-COMPARE string (a ' vs ' heading like '1A vs 1B' — period.label is the TIME
    window, not the comparison; the host title already prepends '· 1A vs 1B', so an AI '1A vs 1B' here doubled it to
    '… · 1A vs 1B at 1A vs 1B'). A REAL time label (a bucket the executor wrote) has no ' vs ' and is left untouched.
    CHROME ONLY, never a reading. In-place, fail-open."""
    def _is_authoritative(v):                                     # empty, or the AI's section-vs corruption
        return v in ("", None) or (isinstance(v, str) and " vs " in v)
    try:
        stack = [payload]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                per = node.get("period")
                if isinstance(per, dict) and "label" in per and _is_authoritative(per.get("label")):
                    per["label"] = label
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    except Exception:
        pass
    return payload


def _enrich_card(card, page_key, val_by_id, l2_out, completed=None, run_ok=True, run_why=None, endpoint_override=None,
                 asset_table=None, asset=None, handling=None, date_window=None):
    """Build the FE card. The `payload` is the COMPLETED CMD_V2 payload from ems_exec.run_card (`completed`) — real
    neuract leaves + honest-blank else, seed numbers stripped. If Layer 2 emitted nothing (no exact_metadata) the
    executor was skipped and payload is None (the FE shows it not-rendered — honest, not masked). On an accepted swap the
    FINAL card is the swap target: render_card_id follows swap_to_id (the payload is already the target's shape).

    The render VERDICT (render|partial|honest_blank) is DERIVED HERE from the completed payload's real-vs-blank data
    leaves (`validate.render_verdict.compute`) — NO Layer 3, NO frame re-gate. `run_ok`/`run_why` is the executor's fetch-reason
    channel (True/'ok' on a fill, False+why on a neuract/executor error) [ER-6].

    `endpoint_override` (asset-dashboard): retained for FE compatibility — it re-points this card's declared `endpoint`
    field to the page screen. The DATA no longer flows through any endpoint (run_card reads neuract directly); endpoint is
    now purely an informational label + the date-nav key. None → the normal Layer 2 endpoint."""
    cid = card.get("card_id")
    l2 = l2_out or {}
    swap = l2.get("swap_decision") or {"action": "keep"}
    render_card_id = swap.get("swap_to_id") or cid           # the card actually drawn (swap target if swapped)
    payload = completed if completed is not None else l2.get("payload")
    # STRUCTURE-PRESERVING SKELETON [per-leaf-degradation]: Layer 2 skipped (asset_no_data / asset_pending) or emitted no
    # exact_metadata → payload is None → the FE would show the GENERIC placeholder for EVERY card. Instead serve the
    # card's harvested honest-blank skeleton (all data leaves nulled, chrome intact) so the FE draws its REAL component in
    # its own empty state. GENERIC (keyed by render identity); a card with no skeleton keeps the machine-reason blank.
    skeleton_blank = False
    if payload is None:
        skel = _skeleton_payload(render_card_id)
        if skel is not None:
            payload, skeleton_blank = skel, True
    consumer = (l2.get("data_instructions") or {}).get("consumer") or {}
    endpoint = endpoint_override or consumer.get("endpoint")  # informational label + date-nav key (data comes from run_card)

    # POST-FILL RENDER VERDICT [validate/render_verdict]: ONE provenance-grounded pass — declared-field real/blank +
    # the roster interpreter's own recipe-driven telemetry (roster_stats) + a leaf_classify net that counts UNDECLARED
    # numeric leaves (panel fields=[] 0.0 leftovers / surviving Storybook seeds) as blank. ONE pop_all strips EVERY
    # reserved telemetry key before the verdict's leaf scan (telemetry_keys.py owns the enumeration — the old
    # two-pops-in-the-right-order sequence was the drift trap: a new reserved key one consumer forgot to pop was
    # silently counted as a blank data leaf). [typing F9]
    from ems_exec.executor import telemetry_keys as _tkeys
    _reserved = _tkeys.pop_all(payload)
    roster_stats = _reserved["roster_stats"]
    gaps = _reserved["gaps"]                                 # per-leaf honest-gap reason records (telemetry, never a FE prop)
    # EMIT-GAP MERGE [cards 19/25/63 render.gaps=null family]: Layer 2's completeness reconcile writes per-leaf
    # 'unbound_by_emit' records to di._emit_gaps, but a special-renderer card (narrative_ai / fuel telemetry) never
    # passes through fill(), so those reasons never reached render.gaps — the payload shipped blank leaves REASONLESS.
    # Merge them here at the ONE serve boundary: only records whose leaf is STILL blank in the served payload (a
    # filled-real leaf must never carry a stale reason; an unresolvable slot is kept — unverifiable ≠ stale).
    gaps = _merge_emit_gaps(gaps, (l2.get("data_instructions") or {}).get("_emit_gaps"), payload)
    payload_error = l2.get("exception") or (l2.get("failure") or {}).get("detail")
    _v = _rverdict.compute(payload or {}, l2.get("data_instructions"), roster_stats,
                           has_payload=payload is not None, skeleton_blank=skeleton_blank, payload_error=payload_error)
    n_real, n_data, verdict = _v["n_real"], _v["n_data"], _v["verdict"]
    # HONEST-DASH display policy [host/display_dash.py]: AFTER the leaf accounting above (a dash must never count as a
    # real data leaf), unit-adjacent type-proven scalar nulls become '—' so tiles render the honest dash, not 'null'.
    # For a served skeleton (L2 skipped → no _default_payload) the type-proof reference is the card's RAW harvested default.
    from host.display_dash import apply as _dash
    _dash_ref = l2.get("_default_payload") or (_raw_default_payload(render_card_id) if skeleton_blank else None)
    payload = _dash(payload, _dash_ref)
    # TITLE GRAFT [defense-in-depth, metadata-stripping]: whatever upstream pass stripped the payload's title leaf
    # (an over-eager seed scrub / emit strip), the served card must never render NAMELESS — refill a blank existing
    # title leaf from cmd_catalog's card.title. Chrome only (after the leaf accounting: a title never counts as data).
    payload = _graft_card_title(payload, card.get("title"))
    reason = None
    if verdict != "render":
        asset_name = (l2.get("data_instructions") or {}).get("asset_name") or ""
        # the executor's per-leaf honest-gap sentences (DB reason_template rows), deduped + joined — the EXPLAINED blank
        gap_note = _gap_note(gaps)
        # F3 [per-leaf reason, never whole-asset when the asset has data]: the whole-asset 'No data logged for this
        # asset' sentence may fire ONLY when the meter is genuinely dark. When the meter HAS logged columns but THIS
        # card's declared metrics produced nothing, the blank is PER-METRIC — name the metrics, never blame the asset.
        zero_real_reason = None
        if n_real == 0:
            whole_asset_reason = (
                _no_data_reason(asset_name) if (asset_table is None or not _asset_has_logged_data(asset_table))
                else _per_metric_blank_reason(l2.get("data_instructions"), asset_name))
            zero_real_reason = payload_error or gap_note or whole_asset_reason
        reason = (run_why if not run_ok else None) or (
            zero_real_reason if n_real == 0 else (gap_note or "some metrics have no live data"))

    _fill_period_labels(payload, _period_label(date_window))    # empty in-card 'at {label}' chrome ← window label
    return {
        "card_id": cid,
        "render_card_id": render_card_id,
        "title": _sub_period(card.get("title"), _period_label(date_window)),
        "story": card.get("analytical_story"),
        "role": card.get("role_in_story"),
        "slot": card.get("slot"),
        "size": card.get("size"),
        "payload": payload,                                  # the ems_exec-COMPLETED CMD_V2 payload (FE renders directly)
        "endpoint": endpoint,                                # informational label + per-card date-nav key
        # date-navigable = the endpoint's history flag OR a panel_aggregate card (its member fan-out is window-driven
        # BY CONSTRUCTION — the endpoint label marks the live/history SCREEN split, not executor capability).
        "is_history": bool(consumer.get("is_history")) or handling == "panel_aggregate",
        # INTERACTIVE DATE RE-FETCH bundle [RC1]: everything /api/frame needs to re-fill THIS card for a new window that
        # the consumer/payload does NOT carry — the RENDERED card identity, the resolved neuract table + asset name (the
        # panel member fan-out resolves its lt_mfm id from these, NOT consumer.mfm_id — a different id-space), the panel
        # reading side, and the harvested chrome-safe default. Served ONLY for date-navigable (is_history) cards so a
        # snapshot card (date control disabled) never bloats the response. The FE posts card.payload as exact_metadata.
        "refetch": ({"render_card_id": render_card_id, "asset_table": asset_table,
                     "asset_name": (asset or {}).get("name"),
                     "member_scope": (asset or {}).get("member_scope") or OUTGOING,
                     "_default_payload": l2.get("_default_payload")}
                    if (consumer.get("is_history") or handling == "panel_aggregate") else None),
        "swap": swap,
        "conforms": l2.get("conforms"),
        "fill_source": "ems_exec",                           # DATA filled server-side by the per-card NEURACT executor
        "fill_ok": run_ok,
        "fill_why": run_why,
        "data_instructions": l2.get("data_instructions"),
        "validation": val_by_id.get(cid),
        "has_payload": payload is not None,
        "payload_error": payload_error,
        # ── RENDER channel — verdict DERIVED from the completed payload's real/blank data leaves (NO Layer 3) ────────
        "render": {
            "verdict": verdict,                              # render | partial | honest_blank
            # ANSWERABILITY: single source of truth = render_verdict.compute (agrees with `verdict`). full ONLY when
            # ≥1 real leaf AND every data leaf is real; some-but-not-all real → partial; zero real over ≥1 leaf → none.
            "answerability": _v["answerability"],
            "reason": reason,                                # honest machine/human reason for a blank/partial
            "coverage_note": None,                           # aggregation deferred (panel leaves honest-blank per-card)
            "date_control": "enabled" if (consumer.get("is_history") or handling == "panel_aggregate") else "disabled",
            "slots": None,                                   # per-slot channel retired with Layer 3
            "gaps": gaps or None,                            # per-leaf honest-gap records [{slot, cause, metric, reason}]
            "leaf_stats": {"real": n_real, "data": n_data, "undeclared": _v["n_undeclared"]},  # filled / total / undeclared-blank
            "watermark": "live",                             # every shown numeric is a live neuract read or honest-blank
        },
        "frame_status": {"endpoint": endpoint, "ok": bool(run_ok), "why": (run_why or "ok")},  # ER-6 honest fetch-reason
    }
