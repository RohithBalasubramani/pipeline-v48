"""host/exec_cards.py — the PARALLEL per-card executor fan-out: fill every Layer-2 card's payload from NEURACT via
ems_exec.run_card (special-renderer kinds via run_special), per-card, in parallel, under one wall-clock budget, with
the honest per-card fetch-reason channel [ER-6/8]. One concern; host/server drives build_response through this.
[atomic]
"""
from __future__ import annotations
from obs.errfmt import fmt_exc as _fmt_exc   # the ONE exception string [EH F4]

import os
import time

from config.app_config import cfg
from ems_exec.serve import run as ems_exec_run              # per-card NEURACT executor (run_card)
from host.payload_store import _raw_default_payload
from layer1b.resolve.member_scope import OUTGOING

# Wall-clock ceiling for the WHOLE parallel per-card executor fan-out (all cards together). A single cold/slow neuract
# read used to (×N cards) drop the whole page; PARALLEL + a budget means a slow card degrades to ok=False+why='executor
# budget exceeded' (its payload is the honest-blanked skeleton) instead of sinking every other card. [ER-8]
# Read lazily per fan-out (not frozen at import) so editing the row takes effect on the next request.
def _exec_budget_s():
    return cfg("ems_exec.card_budget_s", float(os.environ.get("V48_EXEC_BUDGET_S", "45")))


def _date_window_for(consumer, date_window):
    """The (start,end)/None window run_card reads. History cards honor the user's date_window; non-history cards read the
    latest logged range (None). run_card accepts a (start,end) tuple, a {start,end} dict, or None.

    RC2/RC4 [interactive date-nav]: the everyday-preset FE emitters send a RANGE-ONLY window ({range:'today' |
    'last-7-days' | 'yesterday' | …, start:None, end:None}); with no concrete span the read falls to full/latest and the
    date pick does nothing. Resolve the span HERE — the ONE seam shared by the initial /api/run fan-out and the
    interactive /api/frame re-fetch — mirroring the working prompt-path _window_from_preset (reuse the executor's own
    window_policy._range_start so host + exec can never disagree). An explicit start+end (custom-range / the panel
    emitter) passes through untouched."""
    if not date_window:
        return None
    if not (consumer or {}).get("is_history"):
        return None                                          # snapshot card → latest row regardless of the FE date bar
    dw = date_window
    if isinstance(dw, dict) and dw.get("range") and not (dw.get("start") and dw.get("end")):
        dw = _resolve_range_span(dw)
    return dw                                                # {range,start,end,sampling} dict — run_card reads start/end


def _resolve_range_span(dw):
    """Fill start/end for a RANGE-ONLY preset (dw['range'] present, start/end absent). Calendar/lookback ranges via
    window_policy._range_start anchored at site-now; 'yesterday' is the one range whose END is NOT now — it anchors at
    midnight-today (start = that − 1 day) so it never leaks into today's partial day. Unknown range → left untouched
    (honest; the read stays latest). Returns a NEW dict; never raises."""
    try:
        from datetime import timedelta
        from config.windows import site_tz
        from ems_exec.executor.window_policy import _range_start
        from ems_exec.executor.derived import _site_calendar_start
        from replay.clock import now as _replay_now             # frozen to the original instant during a replay
        now = _replay_now(site_tz())
        rng = str(dw.get("range")).strip().lower().replace("_", "-")
        if rng == "yesterday":
            end = _site_calendar_start(now, "day")            # midnight today (site tz)
            start = end - timedelta(days=1)                   # midnight yesterday
        else:
            end = now
            start = _range_start(rng, end)                    # None → unknown range → leave dw as-is (honest)
        if start is not None and end is not None:
            out = dict(dw)
            out["start"] = start.isoformat()
            out["end"] = end.isoformat()
            return out
    except Exception:
        pass
    return dw


# the shipped special classes — the FAIL-OPEN fallback only; the live set derives from the renderer registry below.
_SPECIAL_KINDS_FALLBACK = ("asset_3d", "topology_sld", "narrative_ai", "panel_aggregate")


def _special_kinds():
    """The handling classes that render via run_special — derived from the renderer registry ITSELF (ems_exec.renderers.
    special_kinds() = discovered HANDLING_CLASSES ∪ the DB-driven roster kinds), so a new renderer module / roster-kind
    row extends the host split with NO edit here. Fail-open to the shipped four; never raises."""
    try:
        from ems_exec.renderers import special_kinds
        return special_kinds()
    except Exception:
        return _SPECIAL_KINDS_FALLBACK


def _special_handling_map(card_ids):
    """{card_id: handling_class} for cards whose handling_class is a SPECIAL renderer kind (asset_3d / topology_sld /
    narrative_ai) — those render via ems_exec.renderers.run_special (a GLB envelope / widgets.sld / widgets.ai_summary),
    NOT the column-fill run_card. Non-special / absent cards are omitted (they use run_card). DB read; never raises."""
    if not card_ids:
        return {}
    try:
        from layer2.catalog.card_handling import handling_classes   # THE batch card_handling read (D11)
        special = set(_special_kinds())
        return {cid: hc for cid, hc in handling_classes(card_ids).items() if hc in special}
    except Exception:
        return {}


def _registry_mfm_id(asset):
    """The neuract registry (lt_mfm.id) for the resolved 1b asset — bridges 1b's row-number id-space to the lt_mfm
    membership registry (which run_special's topology/narrative use) via name/table. Falls back to the 1b id, then
    None (run_special then honest-degrades to empty widgets). Never raises."""
    if not isinstance(asset, dict):
        return None
    try:
        from registries import neuract as _reg
        for key in (asset.get("name"), asset.get("table")):
            if key:
                m = _reg.meter_by(key)
                if m and m.get("id") is not None:
                    return m.get("id")
    except Exception:
        pass
    return asset.get("mfm_id") or asset.get("id")


try:
    from replay import hooks as _replay_hooks                  # record/replay seam (fail-open; None → bare calls)
except Exception:
    _replay_hooks = None


def fill_one_card(**kw):
    """The public per-card fill — semantics in _fill_one_card_raw. REPLAY SEAM [replay/hooks.py]: records each card's
    RESOLVED operative window + completed payload (the executor-stage diff anchor). Record-only — a replay re-runs
    the executor on tape-served SQL."""
    if _replay_hooks is None:
        return _fill_one_card_raw(**kw)
    return _replay_hooks.exec_card(_fill_one_card_raw, **kw)


def _fill_one_card_raw(*, cid, render_card_id, handling_class, exact_metadata, data_instructions, asset_table,
                       db_link=None, window=None, requested_window=None, default_payload=None, mfm_id=None,
                       asset_name=None, member_scope=OUTGOING, section=None, page_key=None, metric=None, intent=None):
    """Fill ONE card's payload from NEURACT — the SHARED seam used by BOTH the parallel page fan-out (_run_cards._fill)
    AND the interactive /api/frame per-card date re-fetch. Dispatches run_special for a SPECIAL handling_class
    (asset_3d / topology_sld / narrative_ai / panel_aggregate) else run_card. This dispatch is the reason /api/frame
    must go through here: a panel-overview trend card is handling_class=panel_aggregate and is_history=true, so a
    run_card-only re-fetch would silently replace its member-summed data with wrong single-table data. [RC1]

    `window` = the OPERATIVE (start,end)/None read window (None for a snapshot/non-history card → latest row);
    `requested_window` = what the FE asked REGARDLESS of is_history (kept for honest narrative window labels). Never
    raises up here (run_card / run_special honest-degrade)."""
    if handling_class in _special_kinds():                   # asset_3d / topology_sld / narrative_ai / panel_aggregate / …
        from ems_exec.renderers import run_special
        a = {"mfm_id": mfm_id, "name": asset_name, "table": asset_table, "member_scope": member_scope,
             "section": section}                            # bus-section view [sections]: None = whole panel
        # panel_aggregate fills the card's OWN skeleton from the member-aggregated row; topology/narrative/asset_3d build
        # widgets from scratch and ignore the extra keys. shape_ref = the RAW harvested default for the RENDERED card
        # (the shape oracle fill()/fab_guards need so the panel path does not over-blank order/layout metadata).
        ctx = {"asset_table": asset_table, "mfm_id": mfm_id, "db_link": db_link,
               "window": window, "requested_window": requested_window, "page_key": page_key,
               "metric": metric, "intent": intent, "member_scope": member_scope, "section": section}
        card = {"card_id": cid, "render_card_id": render_card_id, "card_handling": handling_class,
                "exact_metadata": exact_metadata, "data_instructions": data_instructions,
                "_default_payload": default_payload, "shape_ref": _raw_default_payload(render_card_id)}
        out = run_special(handling_class, a, card, ctx)
        return out if out is not None else exact_metadata    # None → fall back to the metadata skeleton (honest)
    # column-fill path — shape_ref = the RAW harvested default (shape oracle for the post-fill axis/scale/normalize
    # passes). Values are NEVER copied from it (zero-fabrication stands).
    return ems_exec_run.run_card(exact_metadata, data_instructions, asset_table, db_link=db_link, window=window,
                                 default_payload=default_payload,
                                 shape_ref=_raw_default_payload(render_card_id), card_id=render_card_id)


def _run_cards(l2, asset_table, db_link=None, date_window=None, run_id="-", asset=None, page_key=None,
               metric=None, intent=None):
    """Fill EVERY Layer-2 card's payload from NEURACT via ems_exec.run_card — PER-CARD, IN PARALLEL, with a wall-clock
    budget. Returns (completed_by_id, status_by_id): completed_by_id={card_id: completed CMD_V2 payload}; status_by_id=
    {card_id: {ok, why}} the honest fetch-reason channel [ER-6]. Feeder + asset + panel cards ALL go through run_card
    (panel-aggregate leaves simply honest-blank — aggregation deferred). run_card never raises; a per-card timeout is an
    honest {ok:False, why='executor budget exceeded'} whose payload is the honest-blanked skeleton (no seed leak).
    [ems_exec per-card; ER-6/8 parallel+budget]"""
    from obs.stage import stage
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FTimeout
    completed_by_id, status_by_id = {}, {}
    tasks = {cid: o for cid, o in (l2 or {}).items()
             if isinstance(o, dict) and not o.get("exception") and o.get("exact_metadata") is not None}
    if not tasks:
        return completed_by_id, status_by_id

    special = _special_handling_map(list(tasks.keys()))       # {card_id: kind} for the SPECIAL renderer cards
    reg_mfm = _registry_mfm_id(asset)                         # the lt_mfm.id for topology/narrative membership
    asset_name = (asset or {}).get("name")
    section = (asset or {}).get("section")                    # bus-section view [sections]: 'pcc-1b' -> 'B', else None
    member_scope = (asset or {}).get("member_scope") or OUTGOING  # PANEL READING DIRECTION [panel_overview]: the
    # incomer-vs-outgoing side the prompt asked for (stamped by layer1b/resolve/member_scope). Threaded to the
    # panel_aggregate renderer so its member fan-out sums the RIGHT side (default 'outgoing' → behaviour unchanged).

    t_start = {}                                              # per-card fill start — the `ms` on each exec stage record

    def _fill(cid, o):
        t_start[cid] = time.time()
        di = o.get("data_instructions") or {}
        kind = special.get(cid)
        # panel_aggregate fills are WINDOW-DRIVEN BY CONSTRUCTION (the member fan-out accepts any span) — their
        # date-navigability must not ride the ems_backend endpoint LABEL (consumer.is_history), which marks the
        # live/history SCREEN split, not executor capability. [panel-events date-nav]
        if kind == "panel_aggregate" and date_window:
            window = date_window
        else:
            window = _date_window_for(di.get("consumer") or {}, date_window)
        rid = (o.get("swap_decision") or {}).get("swap_to_id") or cid  # the RENDERED card's identity (swap target)
        # ONE shared seam for every card kind (dispatches run_special vs run_card) — see fill_one_card. `requested_window`
        # carries what the FE asked REGARDLESS of is_history (honest narrative label + future windowed-facts) while
        # `window` is the OPERATIVE read window; `metric`/`intent` let the narrator lead with the asked-about quantity.
        # OBS: one `executor.card` span per fill — its neuract reads attribute to it; runs on the pool thread under
        # the copied context, so it nests under the `executor` parent span.
        from obs.span import stage_span
        with stage_span("executor.card", card_id=cid,
                        inputs={"render_card_id": rid, "handling": special.get(cid),
                                "asset_table": asset_table, "window": window}) as sp:
            payload = fill_one_card(cid=cid, render_card_id=rid, handling_class=kind,
                                    exact_metadata=o.get("exact_metadata"), data_instructions=di,
                                    asset_table=asset_table,
                                    db_link=db_link, window=window, requested_window=date_window,
                                    default_payload=o.get("_default_payload"), mfm_id=reg_mfm,
                                    asset_name=asset_name, member_scope=member_scope, section=section, page_key=page_key,
                                    metric=metric, intent=intent)
            sp.set_outputs(filled=payload is not None)
            return payload

    import contextvars

    def _ms(cid):                                               # per-card fill wall so far (admin dashboard exec latency)
        return int((time.time() - t_start.get(cid, time.time())) * 1000)

    deadline = time.time() + _exec_budget_s()
    # ER-8 wall-clock budget — REAL as of 2026-07-12. The old form was `with ThreadPoolExecutor(...) as ex:` +
    # `for fut in as_completed(futs):` (NO timeout): as_completed only yields COMPLETED futures, so the `_FTimeout`
    # branch was unreachable and the `with` exit joined every worker — the budget never fired and one black-holed
    # neuract read (a :5433 tunnel flap) blocked the whole /api/run response indefinitely. Now: a TOTAL timeout on
    # as_completed raises the moment the budget is spent; unfinished cards honest-blank as 'executor budget exceeded';
    # and we shutdown(wait=False, cancel_futures=True) so a straggler is ABANDONED (its DB read is bounded by the
    # connect_timeout/keepalives on the pooled door) instead of re-blocking the response.
    ex = ThreadPoolExecutor(max_workers=max(2, min(len(tasks), 8)))
    # OBS: copy the caller's context per task so the trace + `executor` parent span hop into the pool threads
    futs = {ex.submit(contextvars.copy_context().run, _fill, cid, o): cid for cid, o in tasks.items()}
    try:
        for fut in as_completed(futs, timeout=max(0.0, deadline - time.time())):
            cid = futs[fut]
            try:
                completed_by_id[cid] = fut.result()             # already complete (as_completed yielded it) → immediate
                status_by_id[cid] = {"ok": True, "why": "ok"}
                stage(run_id, "exec", card=cid, ok=True, ms=_ms(cid))
            except Exception as e:                              # run_card never raises, but stay honest if it ever does
                status_by_id[cid] = {"ok": False, "why": _fmt_exc(e)}
                stage(run_id, "exec", card=cid, ok=False, why=_fmt_exc(e), ms=_ms(cid))
    except _FTimeout:
        pass                                                    # budget spent — unfinished cards handled in `finally`
    finally:
        for fut, cid in futs.items():                           # every card that did NOT finish within the budget
            if cid in status_by_id:
                continue
            # BUDGET RACE [OBS-5]: a future can COMPLETE between as_completed's timeout raise and this sweep — its
            # real payload is already in the future. Harvest it (result() returns immediately on a done future)
            # instead of discarding fetched data as budget-exceeded; a raised task stays on the failure path.
            if fut.done() and not fut.cancelled():
                try:
                    completed_by_id[cid] = fut.result()
                    status_by_id[cid] = {"ok": True, "why": "ok"}
                    stage(run_id, "exec", card=cid, ok=True, ms=_ms(cid))
                except Exception as e:
                    status_by_id[cid] = {"ok": False, "why": _fmt_exc(e)}
                    stage(run_id, "exec", card=cid, ok=False, why=_fmt_exc(e), ms=_ms(cid))
                continue
            fut.cancel()
            status_by_id[cid] = {"ok": False, "why": "executor budget exceeded"}
            stage(run_id, "exec", card=cid, ok=False, why="executor budget exceeded", ms=_ms(cid))
        ex.shutdown(wait=False, cancel_futures=True)            # do NOT join stragglers (see budget note above)
    return completed_by_id, status_by_id
