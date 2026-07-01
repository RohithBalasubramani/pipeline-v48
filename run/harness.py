"""run/harness.py — V48 entrypoint: fire Layer 1a ∥ Layer 1b on the prompt, join into the Layer-2 input, run Layer 2
per card (1a+1b → 2), then the render-guarantee PRE->L3->POST seam per card (the 3rd/last AI layer). When Layer 2
reports an answerability GAP, REFLECT: re-route 1a once with feedback and re-run. Best-effort substitutions + the
re-route are explained in saved NOTES (loop1/loop2). [spec: 1a∥1b; L2; PRE-grounding->L3; degrade-loop]"""
import os
import obs.ai_log as ai_log
from run.parallel import run_parallel
from run.run_id import make_run_id
from run.layer2_all import run_2_all
from run.layer3_all import run_3_all
from run.reflect import build_feedback, build_loop2_note
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
    """NON-AI validation (annotate-only, never blocks). Run on the CURRENT 1a + 1b."""
    try:
        out["validation"] = run_validate(out["layer1a"], out["layer1b"], db)
        stage(run_id, "validate", verdict=(out["validation"] or {}).get("verdict"))
    except Exception as e:
        out["errors"]["validation"] = f"{type(e).__name__}: {e}"
        record("validation", "layer-exception", detail=str(e), run_id=run_id)
        stage(run_id, "validate", ERROR=f"{type(e).__name__}: {e}")


def _run_layer3(out, rid):
    """The render-guarantee PRE->L3->POST seam: build each card's deterministic fact-sheet (grounding kit), fire the ONE
    L3 AI verdict per card (parallel), then POST-fetch+verify+assemble the render envelope. Annotate-only — a per-card
    L3 exception honest-blanks THAT card, never sinks the page. Skippable via V48_SKIP_LAYER3=1."""
    if os.environ.get("V48_SKIP_LAYER3") == "1":
        return
    try:
        l3 = run_3_all(rid, out["layer1a"], out["layer1b"], out.get("layer2") or {})
    except Exception as e:
        out["errors"]["layer3"] = f"{type(e).__name__}: {e}"
        record("layer3", "layer-exception", detail=str(e), run_id=rid)
        stage(rid, "layer3", ERROR=f"{type(e).__name__}: {e}")
        return
    out["layer3"] = l3
    stage(rid, "layer3", cards=len(l3),
          render=sum(1 for e in l3.values() if (e or {}).get("render_verdict") == "render"),
          partial=sum(1 for e in l3.values() if (e or {}).get("render_verdict") == "partial"),
          blank=sum(1 for e in l3.values() if (e or {}).get("render_verdict") == "honest_blank"))


def _reflect_loop(out, prompt, db, run_id):
    """Layer 2; on answerability GAPS (a card with NO real column/substitute), re-route 1a ONCE with feedback and
    re-run. Saves the first pass's best-effort/substitution notes (loop1) + a persistent-gap note (loop2). After Layer 2
    settles (answered OR re-route exhausted), fire the render-guarantee PRE->L3->POST seam once on the final layout."""
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
        pass_notes = [{"card_id": cid, "title": _title(out["layer1a"], cid),
                       "answerability": o.get("answerability"), "note": o.get("data_note")}
                      for cid, o in l2.items() if (o or {}).get("data_note")]
        if attempt == 1:
            out["notes"]["loop1"] = pass_notes
        stage(rid, "layer2", cards=len(l2),
              conform=sum(1 for o in l2.values() if (o or {}).get("conforms")),
              partial=sum(1 for o in l2.values() if (o or {}).get("answerability") == "partial"),
              gaps=len(gaps),
              swaps=sum(1 for o in l2.values() if ((o or {}).get("swap_decision") or {}).get("origin") == "swapped"))
        if not gaps:
            _run_layer3(out, rid)                               # answered → PRE->L3->POST on the final layout
            return                                              # answered (full or best-effort partial) → done
        if attempt < _MAX_ATTEMPTS:
            stage(rid, "reflect", loop=attempt, gaps=len(gaps), reroute_from=(out["layer1a"] or {}).get("page_key"))
            try:
                out["layer1a"] = run_1a(prompt, db, feedback=build_feedback(out["layer1a"], out["layer1b"], gaps))
                _validate(out, db, rid)
                stage(rid, "1a", page=(out["layer1a"] or {}).get("page_key"), reroute=True,
                      cards=len((out["layer1a"] or {}).get("cards") or []))
            except Exception as e:
                out["errors"]["reroute"] = f"{type(e).__name__}: {e}"
                out["notes"]["loop2"] = f"Could not re-route after the data gap: {e}"
                return
        else:                                                   # exhausted the re-route → persistent gap (loop-2 note)
            out["notes"]["loop2"] = build_loop2_note(out["layer1a"], gaps)
            stage(rid, "reflect", loop=attempt, gaps=len(gaps), unresolved=True)
            _run_layer3(out, rid)                               # still render the best-effort layout (honest-blank gaps)


def run_pipeline(prompt, *, asset_id=None, db=None, run_id=None):
    db = db or CMD_CATALOG
    run_id = run_id or make_run_id(prompt)
    ai_log.set_run_id(run_id)
    stage(run_id, "PROMPT", text=repr(prompt), asset_id=asset_id)

    results = run_parallel({
        "layer1a": lambda: run_1a(prompt, db),
        "layer1b": lambda: run_1b(prompt, asset_id=asset_id),
    })

    out = {"prompt": prompt, "run_id": run_id, "asset_id": asset_id,
           "layer1a": None, "layer1b": None, "validation": None, "layer2": None, "layer3": None,
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
        stage(run_id, "1a", page=l1a.get("page_key"), primitive=(l1a.get("layout") or {}).get("layout_primitive"),
              cards=len(l1a.get("cards") or []), metric=l1a.get("metric"), intent=l1a.get("intent"))
    if out["layer1b"] is not None:
        a = l1b.get("asset") or {}
        stage(run_id, "1b", asset=(a.get("name") if a else None), mfm_id=a.get("mfm_id"),
              candidates=len(l1b.get("candidate_list") or []), basket_cols=(l1b.get("column_basket") or {}).get("n_columns"))

    if out["layer1a"] is not None and out["layer1b"] is not None:
        _validate(out, db, run_id)

        # VALIDATION GATE (CHILLED) — validation SURFACES (FE dot/pill) but does NOT block on incidental gaps. It gates
        # ONLY when the page has ZERO usable data (the basket had real columns but EVERY one failed) — a genuine can't-
        # render. Anything with ≥1 usable column renders BEST-EFFORT so the pipeline always ANSWERS one way or the other
        # and the user can prompt-engineer with what's there. [user: validation a little chilled; always answer]
        _ds = ((out["validation"] or {}).get("data") or {}).get("summary") or {}
        out["validation_blocked"] = (_ds.get("n_columns", 0) > 0 and _ds.get("n_pass", 0) == 0)

        # ASSET-RESOLUTION GATE — Layer 2 runs ONLY when 1b PINNED an asset WITH DATA (how AI/user-choice) AND validation
        # passed. The other outcomes STOP here and the frontend handles them: how='no_data' -> a 'no data for <asset>'
        # notice; validation_blocked -> the asset-picker POPUP ('this asset can't render <page>'); ambiguous/empty ->
        # the asset-picker POPUP (user picks, caller RE-RUNS).
        how = (out["layer1b"] or {}).get("how")
        out["asset_no_data"] = (how == "no_data")
        asset_pinned = (how in {"AI", "user-choice"} and bool((out["layer1b"] or {}).get("asset"))
                        and not out["validation_blocked"])
        out["asset_pending"] = (not asset_pinned and not out["asset_no_data"])
        stage(run_id, "asset_gate", pinned=asset_pinned, how=how, no_data=out["asset_no_data"],
              validation_blocked=out["validation_blocked"], verdict=(out["validation"] or {}).get("verdict"),
              decision=("→ Layer 2" if asset_pinned else
                        ("NO-DATA → notice (Layer 2 NOT run)" if out["asset_no_data"]
                         else ("VALIDATION-FAIL → picker (Layer 2 NOT run)" if out["validation_blocked"]
                               else "PENDING → asset popup (Layer 2 NOT run)"))))

        # LAYER 2 + DEGRADE→REFLECT loop (skippable via V48_SKIP_LAYER2=1).
        if asset_pinned and os.environ.get("V48_SKIP_LAYER2") != "1":
            _reflect_loop(out, prompt, db, run_id)

    record_notes(run_id, out["notes"])                          # persist loop1/loop2 notes for later user-facing explain
    return out
