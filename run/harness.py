"""run/harness.py — V48 entrypoint: fire Layer 1a ∥ Layer 1b on the prompt, join into the Layer-2 input, run Layer 2
per card (1a+1b → 2). When Layer 2 HARD-fails a card (emit exception/timeout/non-conforming), REFLECT: re-route 1a once
with feedback and re-run. An honest answerability GAP (conforming emit, per-leaf reasons) is a VALID TERMINAL — noted,
never re-routed (DB knob reflect.reroute_on; 'any_gap' restores the legacy gap-trigger). Best-effort substitutions + the
re-route are explained in saved NOTES (loop1/loop2). [spec: 1a∥1b; L2; degrade-loop]

LAYER 3 IS RETIRED (archived at archive/layer3_archive_20260702.tar.gz — do NOT reuse). The harness now stops at
Layer 2: it produces {1a, 1b, layer2} and passes them through. The per-card DATA fill happens at the HOST via
ems_exec.serve.run.run_card (host/server.py) — real neuract leaves + honest-blank else, NO ws/mfm frame-fetch,
NO Layer 3 payload-cleaner. `V48_SKIP_LAYER3` is gone (L3 is always-off / removed). [ems_exec swap]"""
import copy
import os
import obs.ai_log as ai_log
from run.parallel import run_parallel
from run.run_id import make_run_id
from run.layer2_all import run_2_all
from run.reflect import build_feedback, build_loop2_note, build_honest_terminal_note
from config.app_config import cfg
from layer1a.build import run_1a
from layer1b.build import run_1b
from validate.build import run_validate
from config.databases import CMD_CATALOG  # canonical metadata DB name (edit in config/)
from obs.failures import record
from obs.notes import record as record_notes
from obs.stage import stage          # end-to-end pipeline log → stderr (host log) + outputs/logs/pipeline_<run_id>.jsonl

_MAX_ATTEMPTS = 2                     # attempt 1 + ONE re-route (loop 1 → loop 2 note). Matches the 2-loop design.


def _title(l1a, cid):
    for c in ((l1a or {}).get("cards") or []):
        if c.get("card_id") == cid:
            return c.get("title")
    return None


def _validate(out, db, run_id):
    """THE pre-Layer-2 validation pass (PASS 1 of the two-pass contract — see validate/build.py). Annotate-only on a
    NON-outage exception; an outage-shaped failure is re-inspected by the degrade gate (fail-open hole closed)."""
    try:
        out["validation"] = run_validate(out["layer1a"], out["layer1b"], db)
        stage(run_id, "validate", verdict=(out["validation"] or {}).get("verdict"),
              expected_gap_frac=(out["validation"] or {}).get("expected_gap_frac"))
    except Exception as e:
        out["errors"]["validation"] = f"{type(e).__name__}: {e}"
        record("validation", "layer-exception", detail=str(e), run_id=run_id)
        stage(run_id, "validate", ERROR=f"{type(e).__name__}: {e}")


def _preflight_reroute(out, prompt, db, run_id):
    """PRE-L2 EXPECTED-GAP RE-ROUTE [moved from post-emit]: run_validate already knows (deterministically) which cards
    are topology-infeasible on the resolved asset. When the roll-up crosses the SAME reflect.min_gap_frac knob the
    post-L2 reflect uses, re-route 1a ONCE — BEFORE the N-emit fan-out that used to burn a full LLM pass just to
    discover the page was infeasible. Below the threshold the (few) infeasible cards honest-blank per-leaf with their
    note. A no_data asset never re-routes (no data on ANY page)."""
    v = out.get("validation") or {}
    gaps = v.get("expected_gaps") or []
    if not gaps or out.get("asset_no_data"):
        return
    min_frac = float(cfg("reflect.min_gap_frac", 0.34))
    if v.get("expected_gap_frac", 0.0) < min_frac:
        return
    # SAME REROUTE-TRIGGER POLICY as the post-L2 reflect (DB knob reflect.reroute_on, default 'hard_failure'):
    # an EXPECTED gap is by construction an HONEST gap (a quantity the asset does not measure) — never a hard emit
    # failure — so under the default policy the routed page is KEPT and those cards honest-blank per-leaf with their
    # reason (the emit's feasibility backstop notes them). 'any_gap' restores the legacy pre-emit re-route.
    policy = str(cfg("reflect.reroute_on", "hard_failure")).strip().lower()
    if policy != "any_gap":
        stage(run_id, "preflight_reroute", gaps=len(gaps), gap_frac=v.get("expected_gap_frac"),
              skipped=f"reroute_on={policy}", honest_terminal=True)
        return
    prev_page = (out["layer1a"] or {}).get("page_key")
    stage(run_id, "preflight_reroute", gaps=len(gaps), gap_frac=v.get("expected_gap_frac"), reroute_from=prev_page)
    try:
        fake_gaps = [{"card_id": g.get("card_id"), "data_note": g.get("reason")} for g in gaps]
        out["layer1a"] = run_1a(prompt, db, feedback=build_feedback(out["layer1a"], out["layer1b"], fake_gaps),
                                exclude_page_key=prev_page)
        _validate(out, db, run_id)
        out["notes"]["loop1"] = (out["notes"].get("loop1") or []) + [
            {"card_id": g.get("card_id"), "title": g.get("title"), "answerability": "none",
             "note": f"pre-L2: {g.get('reason')}"} for g in gaps]
        stage(run_id, "1a", page=(out["layer1a"] or {}).get("page_key"), reroute="preflight",
              cards=len((out["layer1a"] or {}).get("cards") or []))
    except Exception as e:
        out["errors"]["preflight_reroute"] = f"{type(e).__name__}: {e}"


def _reflect_loop(out, prompt, db, run_id, no_reroute=False):
    """Layer 2; on HARD emit failures (exception/timeout/non-conforming envelope), re-route 1a ONCE with feedback and
    re-run. Saves the first pass's best-effort/substitution notes (loop1) + a persistent-gap note (loop2). Layer 2 is
    the LAST pipeline stage — the per-card DATA fill runs at the HOST via ems_exec.run_card (NO Layer 3).

    REROUTE-TRIGGER POLICY (DB knob `reflect.reroute_on`, code default 'hard_failure'):
      'hard_failure' — a card whose emit CONFORMS and is honest-blank WITH reasons (answerability='none') is a VALID
                       TERMINAL, not a failure to route around [per-leaf degradation mandate]. Only a card with NO
                       valid emit at all (conforms=False: emit exception / LLM timeout / gate-failing envelope)
                       triggers the re-route. (Sweep-#3 r_d7be9457fc: 'ups source transfer' routed CORRECTLY to
                       source-transfer, cards 54/55 emitted clean honest-none — and the old any-gap policy DISCARDED
                       the right page for output-load-capacity. The NOTE survives; the discard does not.)
      'any_gap'      — legacy behavior (honest answerability-none gaps re-route too); DB-tunable rollback, no code edit.

    `no_reroute` (a no_data asset): STILL run Layer 2 to emit the per-leaf-null skeleton, but NEVER re-route — the asset
    has no data on ANY page, so a re-route only thrashes. The gapped cards honest-blank per-leaf on the requested page."""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        rid = run_id if attempt == 1 else make_run_id(prompt, salt=f"loop{attempt}")
        if attempt > 1:
            ai_log.set_run_id(rid)
        try:
            l2 = run_2_all(rid, out["layer1a"], out["layer1b"])
        except Exception as e:
            out["errors"]["layer2"] = f"{type(e).__name__}: {e}"
            record("layer2", "layer-exception", detail=str(e), run_id=rid)
            stage(rid, "layer2", ERROR=f"{type(e).__name__}: {e}")
            return
        out["layer2"] = l2
        gaps = [o for o in l2.values() if (o or {}).get("gap")]
        # HARD failure = the card has NO valid emit at all (per-card exception envelope from run_2_all, LLM
        # timeout/transport error, or a gate-failing envelope → conforms=False). An honest gap (conforms=True,
        # answerability='none' + per-leaf reasons) is NOT in this set — it IS the answer.
        hard_fails = [o for o in l2.values() if not (o or {}).get("conforms")]
        pass_notes = [{"card_id": cid, "title": _title(out["layer1a"], cid),
                       "answerability": o.get("answerability"), "note": o.get("data_note")}
                      for cid, o in l2.items() if (o or {}).get("data_note")]
        if attempt == 1:
            out["notes"]["loop1"] = pass_notes
        stage(rid, "layer2", cards=len(l2),
              conform=sum(1 for o in l2.values() if (o or {}).get("conforms")),
              partial=sum(1 for o in l2.values() if (o or {}).get("answerability") == "partial"),
              gaps=len(gaps), hard_fails=len(hard_fails),
              swaps=sum(1 for o in l2.values() if ((o or {}).get("swap_decision") or {}).get("origin") == "swapped"))
        # REROUTE-TRIGGER POLICY (DB knob reflect.reroute_on; see the function docstring): default triggers ONLY on
        # hard failures; 'any_gap' restores the legacy honest-gap trigger. Generic — no card/page vocabulary.
        policy = str(cfg("reflect.reroute_on", "hard_failure")).strip().lower()
        trigger = gaps if policy == "any_gap" else hard_fails
        if not gaps and not trigger:
            return                                              # answered (full or best-effort partial) → done; host fills data
        if no_reroute:
            # a NO-DATA asset: the skeleton is emitted (per-leaf-null), but there is no data on ANY page to re-route to —
            # leave every card honest-blank per-leaf on the requested page instead of thrashing the router.
            out["notes"]["loop2"] = (f"asset has no logged data ({len(gaps)} of {len(l2)} cards gapped); page rendered "
                                     f"as an honest per-leaf-null skeleton, NOT re-routed (no data on any page).")
            stage(rid, "reflect", loop=attempt, gaps=len(gaps), skipped="no_data_asset")
            return
        if not trigger:
            # HONEST TERMINAL [reflect.reroute_on='hard_failure']: every emit CONFORMS and the gapped cards carry their
            # per-leaf reasons — that is the PROPER output, not a defect to route around. KEEP the routed page and its
            # cards; save the user-facing reflect NOTE (the explanation survives, the destructive re-route does not).
            out["notes"]["loop2"] = build_honest_terminal_note(out["layer1a"], gaps)
            stage(rid, "reflect", loop=attempt, gaps=len(gaps), honest_terminal=True, reroute_on=policy)
            return
        # TRIGGER-FRACTION GATE (DB knob reflect.min_gap_frac): ONE spurious trigger card must not re-route a whole
        # healthy page — below the threshold the affected cards honest-blank PER-LEAF (per-leaf degradation mandate) and
        # the run records why, instead of the historical 1-of-N whole-page re-route. [hardening: reflect loop trigger]
        gap_frac = len(trigger) / max(len(l2), 1)
        min_frac = float(cfg("reflect.min_gap_frac", 0.34))
        if gap_frac < min_frac:
            out["notes"]["loop2"] = (f"{len(trigger)} of {len(l2)} cards "
                                     f"{'have data gaps' if policy == 'any_gap' else 'hard-failed their emit'} "
                                     f"(frac {gap_frac:.2f} < reflect.min_gap_frac {min_frac:.2f}); "
                                     f"left honest-blank per-leaf, page NOT re-routed.")
            stage(rid, "reflect", loop=attempt, gaps=len(gaps), hard_fails=len(hard_fails),
                  gap_frac=round(gap_frac, 2), skipped="below_min_gap_frac")
            return
        if attempt < _MAX_ATTEMPTS:
            prev_page = (out["layer1a"] or {}).get("page_key")
            stage(rid, "reflect", loop=attempt, gaps=len(gaps), hard_fails=len(hard_fails),
                  reroute_on=policy, reroute_from=prev_page)
            try:
                # exclude_page_key: the failed page is MECHANICALLY dropped from the reroute candidates (not prose-only)
                out["layer1a"] = run_1a(prompt, db, feedback=build_feedback(out["layer1a"], out["layer1b"], trigger),
                                        exclude_page_key=prev_page)
                _validate(out, db, rid)
                stage(rid, "1a", page=(out["layer1a"] or {}).get("page_key"), reroute=True,
                      cards=len((out["layer1a"] or {}).get("cards") or []))
            except Exception as e:
                out["errors"]["reroute"] = f"{type(e).__name__}: {e}"
                out["notes"]["loop2"] = f"Could not re-route after the data gap: {e}"
                return
        else:                                                   # exhausted the re-route → persistent gap (loop-2 note)
            out["notes"]["loop2"] = build_loop2_note(out["layer1a"], gaps or trigger)
            stage(rid, "reflect", loop=attempt, gaps=len(gaps), unresolved=True)  # host still fills best-effort layout


def run_pipeline(prompt, *, asset_id=None, db=None, run_id=None, layer1a=None):
    db = db or CMD_CATALOG
    run_id = run_id or make_run_id(prompt)
    ai_log.set_run_id(run_id)
    stage(run_id, "PROMPT", text=repr(prompt), asset_id=asset_id)

    # SHARED-TEMPLATE LANE [multi-asset author-once-per-class]: a compare lane (run_pipeline_multi) INJECTS the already-
    # routed 1a so the template is chosen ONCE for the whole compare. The lane then runs 1b ALONE against that shared page
    # and the page is LOCKED — reconcile / preflight / reflect re-routes are suppressed below so EVERY asset renders the
    # SAME template. layer1a=None (the single-asset path) is byte-identical: 1a routes normally + every re-route runs.
    _shared_template = layer1a is not None
    results = run_parallel({
        "layer1a": (lambda: layer1a) if _shared_template else (lambda: run_1a(prompt, db)),
        "layer1b": lambda: run_1b(prompt, asset_id=asset_id),
    })

    out = {"prompt": prompt, "run_id": run_id, "asset_id": asset_id,
           "layer1a": None, "layer1b": None, "validation": None, "layer2": None,
           "notes": {"loop1": [], "loop2": None}, "errors": {}}
    for name in ("layer1a", "layer1b"):
        r = results[name]
        if isinstance(r, Exception):
            out["errors"][name] = f"{type(r).__name__}: {r}"
            record(name, "layer-exception", detail=str(r), run_id=run_id)
            stage(run_id, name, ERROR=f"{type(r).__name__}: {r}")
        else:
            out[name] = r

    # INFRA-OUTAGE honest terminal — if 1a/1b failed because a LIVE data source is unreachable (tunnel down / connection
    # refused / timeout), turn the swallowed layer-exception into the honest `data_unavailable` gate + a DB-driven reason,
    # so the page is an honest terminal instead of silent verdict-less cards claiming ok=True. [render-guarantee root-cause]
    from run.degrade_gate import apply as _apply_degrade_gate
    _apply_degrade_gate(out)
    if out.get("data_unavailable"):
        stage(run_id, "degrade", kind="data_unavailable", layer=(out.get("degrade") or {}).get("layer"))

    l1a, l1b = out["layer1a"] or {}, out["layer1b"] or {}
    if out["layer1a"] is not None:
        _rt = l1a.get("routing") or {}
        stage(run_id, "1a", page=l1a.get("page_key"), primitive=(l1a.get("layout") or {}).get("layout_primitive"),
              cards=len(l1a.get("cards") or []), metric=l1a.get("metric"), intent=l1a.get("intent"),
              page_key_how=_rt.get("page_key_how"), dropped_templates=_rt.get("dropped_templates") or [])
    if out["layer1b"] is not None:
        a = l1b.get("asset") or {}
        stage(run_id, "1b", asset=(a.get("name") if a else None), mfm_id=a.get("mfm_id"),
              candidates=len(l1b.get("candidate_list") or []), basket_cols=(l1b.get("column_basket") or {}).get("n_columns"),
              how=l1b.get("how"), class_prior=l1b.get("class_prior"), class_mismatch=l1b.get("class_mismatch"),
              contract_problems=l1b.get("contract_problems") or [])

    if out["layer1a"] is not None and out["layer1b"] is not None:
        # GRANULARITY RECONCILE (post-resolution safety-net): 1a routed the shell from prompt TEXT, blind to the asset's
        # has_feeders; if the routed page's granularity contradicts the resolved asset (single meter on a panel-aggregate
        # shell, or vice versa), re-route to the correct-granularity MIRROR page BEFORE validate/Layer 2. [routing #07]
        from run.reconcile_granularity import apply as _reconcile_granularity
        if not _shared_template:                          # shared-template lane keeps the ONE routed page (locked)
            _reconcile_granularity(out, prompt, db, run_id)   # may swap out["layer1a"] to the correct-granularity mirror

        _validate(out, db, run_id)

        # FAIL-OPEN HOLE CLOSED [audit: validator exception]: an OUTAGE-shaped validate failure (tunnel drop during the
        # pandas probe) is the same honest data_unavailable terminal as a 1a/1b outage — NOT a silent zero-validation
        # Layer-2 run. A non-outage validate exception stays annotate-only (the degrade gate doesn't match it).
        _apply_degrade_gate(out)
        if out.get("data_unavailable"):
            stage(run_id, "degrade", kind="data_unavailable", layer="validation")
            record_notes(run_id, out["notes"])
            return out

        # PRE-L2 EXPECTED-GAP RE-ROUTE — the deterministic topology-infeasibility roll-up from run_validate re-routes
        # BEFORE the Layer-2 fan-out (was discovered post-emit in reflect, burning a full N-emit pass). [audit HIGH]
        out["asset_no_data"] = ((out["layer1b"] or {}).get("how") == "no_data")
        if not _shared_template:                          # shared-template lane: never re-route (the page is locked)
            _preflight_reroute(out, prompt, db, run_id)   # may swap out["layer1a"] + re-validate

        # VALIDATION GATE (CHILLED) — validation SURFACES (FE dot/pill) but does NOT block on incidental gaps. It gates
        # ONLY when the page has ZERO usable data (the basket had real columns but EVERY one failed) — a genuine can't-
        # render. Anything with ≥1 usable column renders BEST-EFFORT so the pipeline always ANSWERS one way or the other
        # and the user can prompt-engineer with what's there. [user: validation a little chilled; always answer]
        _ds = ((out["validation"] or {}).get("data") or {}).get("summary") or {}
        out["validation_blocked"] = (_ds.get("n_columns", 0) > 0 and _ds.get("n_pass", 0) == 0)

        # ASSET-RESOLUTION GATE — Layer 2 runs whenever 1b RESOLVED an asset by NAME (how AI/user-choice/no_data), so
        # every card gets its structure-preserving metadata skeleton (real component, per-leaf-null). PER-LEAF DEGRADATION
        # [render-guarantee mandate]: a `no_data` asset (named + class-known, table empty) is just the extreme "every leaf
        # blank" case — it is NOT a reason to SKIP Layer 2. Skipping left every card payload:None → the FE fell to a
        # generic <HonestBlank> placeholder (tier 5) and NO card rendered its real CMD_V2 component (pages 01-05 defect).
        # Running Layer 2 emits the byte-identical stripped skeleton (data leaves null) so each card mounts its own empty
        # component. `asset_no_data` stays as TELEMETRY (the FE greys the dark asset + shows the honest no-data notice),
        # NOT a Layer-2 skip. Only the GENUINELY-UNRESOLVED outcomes (ambiguous/empty = asset_pending) or a validation
        # block stop before Layer 2 — those are real "which asset?" questions the picker must answer first.
        how = (out["layer1b"] or {}).get("how")           # asset_no_data already set (pre-flight) — how==no_data
        asset_resolved = (how in {"AI", "user-choice", "no_data"} and bool((out["layer1b"] or {}).get("asset")))
        asset_pinned = (asset_resolved and not out["validation_blocked"])   # asset resolved by name AND page renderable
        out["asset_pending"] = (not asset_resolved and not out["validation_blocked"])
        stage(run_id, "asset_gate", pinned=asset_pinned, how=how, no_data=out["asset_no_data"],
              validation_blocked=out["validation_blocked"], verdict=(out["validation"] or {}).get("verdict"),
              decision=("→ Layer 2 (no-data skeleton)" if (asset_pinned and out["asset_no_data"]) else
                        ("→ Layer 2" if asset_pinned else
                         ("VALIDATION-FAIL → picker (Layer 2 NOT run)" if out["validation_blocked"]
                          else "PENDING → asset popup (Layer 2 NOT run)"))))

        # LAYER 2 + DEGRADE→REFLECT loop (skippable via V48_SKIP_LAYER2=1). Runs for a no_data asset too — emitting the
        # per-leaf-null skeleton — but a no_data page has NO real columns anywhere, so the reflect loop's re-route (which
        # exists to find a page this asset's data CAN answer) is pointless: there is no data on any page. Suppress the
        # re-route for a no_data asset so it lands on the requested page's honest empty skeleton instead of thrashing.
        if asset_pinned and os.environ.get("V48_SKIP_LAYER2") != "1":
            _reflect_loop(out, prompt, db, run_id, no_reroute=(out["asset_no_data"] or _shared_template))
            # POST-SETTLE PAYLOAD REFRESH [report-staleness, annotate-only]: swaps can change the FINAL card set after
            # the pre-L2 report scored the 1a selection — re-score payload supply-vs-demand keyed by final render id.
            if out.get("layer2") and out.get("validation"):
                try:
                    from validate.build import payload_final
                    out["validation"]["payload_final"] = payload_final(
                        out["layer2"], (out["layer1a"] or {}).get("page_key"),
                        (out["validation"] or {}).get("data") or {"columns": [], "summary": {}})
                except Exception as e:
                    out["errors"]["payload_final"] = f"{type(e).__name__}: {e}"
            # HONEST PAGE NOTE [no_data skeleton]: a no_data page renders every card's REAL component with per-leaf-null
            # leaves (structure preserved), so it must not look like a normal answered page. Record the honest reason and
            # the onward-pick count so the run is self-explaining even when the emit reported no per-card gaps.
            if out["asset_no_data"] and not (out["notes"] or {}).get("loop2"):
                _a = (out["layer1b"] or {}).get("asset") or {}
                _alts = len((out["layer1b"] or {}).get("candidate_list") or [])
                out["notes"]["loop2"] = (f"{_a.get('name') or 'the resolved asset'} has no logged data — every card "
                                         f"renders its real component with per-leaf-null leaves (honest empty). "
                                         f"{_alts} data-bearing alternative(s) offered in the picker.")

    record_notes(run_id, out["notes"])                          # persist loop1/loop2 notes for later user-facing explain
    return out


def run_pipeline_multi(prompt, assets, *, db=None):
    """MULTI-ASSET COMPARE [author-once-per-class]: resolve N assets → N groups of cards in ONE run. 1a routes the
    template ONCE (the first class establishes it; every later class LOCKS to it via the layer1a injection); Layer 2
    authors the card recipe ONCE PER DISTINCT CLASS — a same-class compare ("UPS-01 vs UPS-02") is ONE authoring, and
    every same-class asset reuses that recipe (it binds by column NAME, portable across sibling meters). The per-asset
    DATA fill + honest-blank happen at the HOST executor (host/assemble.assemble_cards) reusing the class recipe — NOT
    per-asset Layer 2. `assets` = the resolved as_asset dicts (host resolves the picker's asset_ids). Returns
    {layer1a, run_id, groups:[{class, lane, assets}]}: `lane` is a full run_pipeline result whose layer2 IS the class
    recipe, `assets` the same-class members that reuse it. ONE asset → ONE group == the single-asset pipeline verbatim."""
    db = db or CMD_CATALOG
    run_id = make_run_id(prompt)
    by_class = {}
    for a in (assets or []):
        by_class.setdefault((a or {}).get("class") or "?", []).append(a)
    groups, shared_1a = [], None
    for cls, members in by_class.items():
        rep = members[0] or {}
        lane = run_pipeline(prompt, asset_id=rep.get("mfm_id"), db=db,
                            run_id=make_run_id(prompt, salt=f"class:{cls}"),
                            layer1a=(copy.deepcopy(shared_1a) if shared_1a is not None else None))
        if shared_1a is None:
            shared_1a = lane.get("layer1a")                     # the FIRST class ROUTES the template; the rest lock to it
        groups.append({"class": cls, "lane": lane, "assets": members})
    return {"layer1a": shared_1a, "run_id": run_id, "groups": groups}
