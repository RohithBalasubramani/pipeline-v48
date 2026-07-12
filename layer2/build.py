"""layer2/build.py — Layer 2 GENERAL per-card entry (contract 5). One fan-out unit:
assemble input -> AI emit {swap, exact_metadata(morphs), data_instructions} -> deterministic gates -> Layer2CardOutput.
On an ACCEPTED swap, RE-EMIT for the swapped-in card (it has a different shape) — the payload always matches the FINAL
card. AI DECIDES (swap + morphs + recipe); deterministic code SUPPORTS (copy defaults, gate, assemble). [spec §2 L2]"""
from validate import verdicts as _verdicts   # the ONE verdict vocab home [typing F5]
import re

from layer2.card_input import build_card_input, build_swap_target_input
from layer2.emit.emit import emit
from layer2.emit.metadata.producer import produce, metadata_reference, undeclared_morphs
from layer2.emit.morphmap.producer import apply as morphmap_apply
from layer2.emit.instructions.consumer_binding import build as consumer_build
from layer2.resolve.column_override import apply as override_columns
from layer2.swap.decide import gate as swap_gate
from layer2.gates import (gate_exact_metadata, gate_data_instructions, gate_roster, enforce_exact_metadata,
                          enforce_free_metadata)
from layer2.schema import validate_layer2_card_output
from data.db_client import q


def _page_card_ids(page_key):
    return [int(x[0]) for x in q("cmd_catalog",
            f"SELECT DISTINCT card_id FROM page_layout_cards WHERE page_key=$a${page_key}$a$ AND card_id IS NOT NULL") if x and x[0]]


# ── extracted single-purpose passes (atomic rule) — re-exported byte-compatibly (tests + tools import from here) ──
from layer2.window_backfill import (                                    # noqa: F401
    _lookback_delta, _range_delta, _window_anchor, _slots_declared_range, _calendar_start, _backfill_default_window)
from layer2.reconcile_slots import _reconcile_slots                     # noqa: F401
from layer2.cross_domain import (                                       # noqa: F401
    _fn_quantity_map, _cross_domain_fields, _cross_domain_note, _blank_cross_domain_leaves)
from layer2.metadata_resolve import resolve_exact_metadata              # noqa: F401  (extracted produce→gate→enforce)


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


def _finalize(ci, raw, swap, *, reemit_of=None):
    """OBS wrapper — `metadata_resolution` stage span around the gates + exact_metadata production + consumer-binding
    step (runs 1-2x per card: first pass + optional gate-retry; each pass is its own span under the card span)."""
    from obs.span import stage_span
    with stage_span("metadata_resolution", card_id=ci.get("card_id"),
                    inputs={"reemit_of": reemit_of, "swap_action": (swap or {}).get("action")}) as sp:
        out = _finalize_inner(ci, raw, swap, reemit_of=reemit_of)
        sp.set_outputs(conforms=out.get("conforms"), answerability=out.get("answerability"), gap=out.get("gap"),
                       applied_morphs=len(out.get("_applied_morphs") or []),
                       undeclared_morphs=len(out.get("_undeclared_morphs") or []),
                       schema_issues=len(out.get("_schema_issues") or []),
                       failure=(out.get("failure") or {}).get("reason"))
        if out.get("gap") or not out.get("conforms"):
            sp.set_degradation(gap=out.get("gap") or None, nonconforming=(not out.get("conforms")) or None,
                               data_note=out.get("data_note"))
        return out


def _finalize_inner(ci, raw, swap, *, reemit_of=None):
    """Produce the Layer2CardOutput for the FINAL card (ci) from its AI emit (raw) + the resolved swap decision."""
    basket = ci["column_basket"]
    dp = ci["catalog_row"].get("default_payload")
    # METADATA RESOLUTION — the morph-map vs full produce→gate→enforce machinery (layer2/metadata_resolve.py). Returns
    # the same locals the inline block did; `failures` is seeded with the metadata-stage failures and kept appending to.
    exact_metadata, applied, _undeclared, ok_m, llm_err, failures = resolve_exact_metadata(raw, dp)

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
    di, ov_notes = override_columns(di, basket, data_note=raw.get("data_note"), applied_morphs=applied,
                                    is_group_card=ci["is_group_card"],
                                    default_payload=(dp["payload"] if dp else None))
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
    # DETERMINISTIC: attach the consumer-driving params so the DATA-fill helper drove the legacy EMS WS dispatcher
    di["consumer"] = consumer_build(cr, ci.get("asset"), ci["page_key"], window=di.get("window"), ai_spec=di.get("fetch"))
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
    # PER-LEAF PAYLOAD_ERROR PARTITION [deterministic robustness — degrade PER-LEAF, verdicts are telemetry, never a
    # card gate]. gate_data_instructions returns TWO kinds of issue and used to treat BOTH as a card-blocking
    # payload_error (conforms=False), even though a single malformed/unbindable FIELD already HONEST-BLANKS at fill
    # (fn=None → nothing derives; column=None → nothing binds; const value=None → nothing renders): the card still
    # mounts its real component and every SIBLING leaf fills.
    #   (a) FIELD-LEVEL per-leaf issues — shaped 'fields[i] …' ('kind=derived without fn', 'kind=bucketed missing a
    #       resolved column', 'kind=const without a value', 'kind=event without edge', a hallucinated-column flag): one
    #       field that self-heals to a blank. These are TELEMETRY (di._per_leaf_gaps + a data_note), NOT failures, and
    #       they do NOT gate conforms — mirrors the roster-aware partition above (audit PASSED cards 62/72/77/59/54 as
    #       honest degradation; the payload_error was a telemetry mislabel).
    #   (b) CARD-STRUCTURAL issues — anything WITHOUT the 'fields[' prefix ('data_instructions.fields is empty', a bad
    #       $ctx-on-non-group flag, an envelope/shape defect): a real card conformance error. These STAY failures and
    #       KEEP conforms=False. A genuinely fields-required card with empty fields still fails honestly.
    # ok_d is RECOMPUTED over only the card-structural issues, so conforms stays True when only per-leaf field issues
    # remain. Generic — no card ids/vocab; keyed purely on the 'fields[' issue shape the gate itself emits.
    _field_issues = [i for i in d_issues if str(i).startswith("fields[")]
    _struct_issues = [i for i in d_issues if not str(i).startswith("fields[")]
    ok_d = not _struct_issues
    if _field_issues:
        di["_per_leaf_gaps"] = (di.get("_per_leaf_gaps") or []) + list(_field_issues)
    failures += _struct_issues          # only card-structural data issues are card-blocking failures
    failures += r_issues                # roster telemetry AFTER gate issues — the failure reason stays a real gate hit

    # DETERMINISTIC COMPLETENESS RECONCILE — slot-catalog coverage diff (telemetry + the per-leaf 'unbound_by_emit'
    # reason records fill.py merges into the honest-gap channel). Never a render gate.
    _reconcile_slots(di, dp["payload"] if dp else None, basket, fields_optional=_fields_optional,
                     data_note=_declared_note)

    # NO-OP MORPH-REJECTION PARTITION [per-leaf robustness, mirrors the field partition above]: a morph the AI DECLARED
    # on a path that is NOT a real metadata leaf ('… is not a real metadata leaf'), or declared but sent no value for
    # ('… declared morphed but no value in exact_metadata'), is a NO-OP — produce()/morphmap_apply already shipped the
    # byte-identical DEFAULT for that path, so it NEVER rendered anything different (card 42's non-leaf morphs). Move it
    # to telemetry (di._noop_morphs) so it can't become the card's failure.detail/payload_error. This does NOT partition
    # a GENUINE metadata defect that reverted: a 'reverted to default: …' (a byte-identity/chrome violation the enforce
    # pass had to undo) and a 'morph rejected: …: DATA leaf …' / '…: morph value is chrome …' (an attempt to inject a
    # seed data value or chrome) STAY failures — the default shipping there is a self-heal of a real violation, not a
    # harmless no-op. Keyed purely on the two no-op reason suffixes produce()/morphmap_apply emit (no card ids/vocab).
    def _is_noop_morph(s):
        s = str(s)
        return s.startswith("morph rejected:") and (
            s.endswith("morph path is not a real metadata leaf")
            or s.endswith("declared morphed but no value in exact_metadata"))
    _noop_morphs = [f for f in failures if _is_noop_morph(f)]
    if _noop_morphs:
        failures = [f for f in failures if not _is_noop_morph(f)]
        di["_noop_morphs"] = (di.get("_noop_morphs") or []) + list(_noop_morphs)

    conforms = ok_m and ok_d and bool(exact_metadata) and not llm_err
    # BEST-EFFORT / ANSWERABILITY: the AI reports whether it could answer the card's story with REAL columns —
    # "full" (exact), "partial" (rendered via a real substitute, + data_note), or "none" (a genuine GAP that the
    # orchestrator may re-route on). gap drives the reflect-loop; data_note (loop-1 note) is saved for the user.
    # ★ NO FAIL-OPEN [A4]: an emit that DECLARES no answerability (top-level or nested) defaults to "partial" —
    # the absence of a declaration is NOT a declaration of full (the old absence→"full" default stamped ~10% of
    # emits fully-answered by code). Same for an invalid token. An LLM-transport failure degrades identically.
    answerability = _declared_answer or "partial"
    if answerability not in _verdicts.ANSWERABILITY:
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
    # PER-LEAF FIELD-GAP note [payload_error partition]: a field that self-heals to a blank (derived-without-fn /
    # bucketed-no-column / const-without-value / hallucinated column — di._per_leaf_gaps) is a per-leaf degradation, not
    # a full answer nor a card block. Surface a user-facing note + soften answerability; the card renders, that leaf
    # blanks, every sibling fills. Never a gap/re-route, never a payload_error.
    if di.get("_per_leaf_gaps"):
        data_note = data_note or ("one or more leaves could not be bound for this card on this asset — those leaves "
                                  "render an honest blank (per-leaf reasons attached), every other leaf fills")
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
    # physical domain than its slot (a current column under a voltage-THD leaf; an energy fn in a 'years' leaf; the
    # card-72 apparent_power_total_kva under an energy `apparentMvah` leaf) is a wrong-KIND stand-in. A wrong-QUANTITY
    # reading is NOT real data (a POWER value cannot be a true ENERGY reading no matter how it is relabelled), so per the
    # zero-fabrication mandate the leaf must HONEST-BLANK — not merely carry a telemetry note while the wrong number still
    # renders. Promote the old telemetry-only pass to a PER-LEAF BLANKING pass: drop each flagged field's column/fn to
    # None + reroute to the frame path (identical to resolve/column_override.apply's slot-quantity guard), so ONLY the
    # wrong-domain leaves blank while every sibling field still fills — NEVER a card-block. Keep the telemetry record
    # (di['_cross_domain']) + the honest note + force ≥partial. Generic + DB-driven (config.metrics.quantity_family); a
    # genuine SAME-domain proxy (cfam == sfam, the R7 rule already honored in _cross_domain_fields) is never flagged, so
    # it is never blanked here. This is the honesty backstop for a substitute the prompt tried to prevent.
    _xdom = _cross_domain_fields(di)
    if _xdom:
        if answerability == "full":
            answerability = "partial"
        data_note = _cross_domain_note(_xdom) if not data_note else data_note + " " + _cross_domain_note(_xdom)
        di["_cross_domain"] = [{"slot": s, "slot_family": sf, "source": src, "source_family": cf}
                               for (s, sf, src, cf) in _xdom]
        di["_cross_domain_blanked"] = _blank_cross_domain_leaves(di, _xdom)   # per-LEAF honest-blank (telemetry: count)
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
    """OBS wrapper — one `layer2_card_ai.card` span per card; the emit LLM call(s), catalog reads, swap gate and
    metadata_resolution child spans all attribute to it."""
    from obs.span import stage_span
    with stage_span("layer2_card_ai.card", card_id=card_id) as sp:
        out = _run_card_inner(run_id, card_id, l1a, l1b, already_chosen=already_chosen,
                              shared_ctx_ref=shared_ctx_ref)
        sw = out.get("swap_decision") or {}
        sp.set_outputs(swap=sw.get("action"), swap_to=sw.get("swap_to_id"), origin=sw.get("origin"),
                       conforms=out.get("conforms"), answerability=out.get("answerability"),
                       gap=out.get("gap"), gate_retry=out.get("_gate_retry"),
                       endpoint=((out.get("data_instructions") or {}).get("consumer") or {}).get("endpoint"))
        sp.set_confidence(swap_confidence=sw.get("confidence"), ai_confidence=sw.get("ai_confidence"),
                          answerability=out.get("answerability"))
        if out.get("gap") or not out.get("conforms"):
            sp.set_degradation(gap=out.get("gap") or None, nonconforming=(not out.get("conforms")) or None,
                               failure=(out.get("failure") or {}).get("reason"), data_note=out.get("data_note"))
        return out


def _run_card_inner(run_id, card_id, l1a, l1b, *, already_chosen=None, shared_ctx_ref=None):
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
    # the AI's OWN per-asset render verdict [#1 dataless swap]: answerability='none' = this card is WHOLLY unfillable for
    # THIS asset (every leaf honest-blanks — a Fuel Tank on a DG with no fuel column). The static catalog verdict can't
    # know that; the gate treats it like an unrenderable verdict and force-swaps to a fillable candidate (or honestly
    # keeps when the whole page is a data dead-end). Same robust extraction as _finalize (top-level OR nested envelope).
    _di = raw.get("data_instructions") if isinstance(raw.get("data_instructions"), dict) else {}
    _answer = raw.get("answerability") or _di.get("answerability")
    swap = swap_gate(raw.get("swap_decision") or {"action": "keep"},
                     pool_ids=[c["card_id"] for c in ci["swap_candidates"]],
                     template_card_ids=ci["story"]["template_card_ids"], already_chosen=already_chosen,
                     page_card_ids=_page_card_ids(ci["page_key"]), current_card_id=card_id,
                     current_verdict=_current_verdict, pool=ci["swap_candidates"], answerability=_answer)

    # SWAP-TARGET RE-EMIT: the first emit authored the payload for `card_id`'s shape; the FINAL card is the swap
    # target, which has a DIFFERENT shape. Re-run the emit for the target (it inherits the slot's story) so the
    # payload matches the final card. The swap decision from pass 1 stands.
    tgt = swap.get("swap_to_id")
    if swap.get("origin") == "swapped" and tgt and tgt != card_id:
        target_ci = build_swap_target_input(run_id, tgt, ci, l1b)
        target_raw = emit(target_ci)
        # DATALESS REVERT-GUARD [#1]: a forced dataless swap must land on a card THIS asset can actually FILL. The pool is
        # only CATALOG-render_real; the target's per-asset fillability is unknown until it re-emits. If the target ALSO
        # declares itself wholly unfillable (answerability in DATALESS_ANSWERABILITY — a whole-page data dead-end, e.g. a
        # fuel page on a fuel-less DG where every candidate is empty), swapping empty→empty just loses the ORIGINAL's
        # honest data_note. Revert: keep the original card (honest-blank + its declared reason), never fabricate.
        if swap.get("forced_dataless"):
            _tdi = target_raw.get("data_instructions") if isinstance(target_raw.get("data_instructions"), dict) else {}
            _tans = target_raw.get("answerability") or _tdi.get("answerability")
            if _force.is_dataless(_tans):
                keep = {**swap, "action": "keep", "origin": "kept", "swap_to_id": None, "swap_to_title": None,
                        "forced_renderable": False, "forced_kept_unrenderable": True, "reverted_dataless_swap": True,
                        "confidence": swap.get("ai_confidence")}
                return _finalize_with_gate_retry(ci, raw, keep)
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
