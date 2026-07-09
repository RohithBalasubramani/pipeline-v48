"""host/exec_cards.py — the PARALLEL per-card executor fan-out: fill every Layer-2 card's payload from NEURACT via
ems_exec.run_card (special-renderer kinds via run_special), per-card, in parallel, under one wall-clock budget, with
the honest per-card fetch-reason channel [ER-6/8]. One concern; host/server drives build_response through this.
[atomic]
"""
from __future__ import annotations

import os
import time

from config.app_config import cfg
from ems_exec.serve import run as ems_exec_run              # per-card NEURACT executor (run_card)
from host.payload_store import _raw_default_payload

# Wall-clock ceiling for the WHOLE parallel per-card executor fan-out (all cards together). A single cold/slow neuract
# read used to (×N cards) drop the whole page; PARALLEL + a budget means a slow card degrades to ok=False+why='executor
# budget exceeded' (its payload is the honest-blanked skeleton) instead of sinking every other card. [ER-8]
_EXEC_BUDGET_S = cfg("ems_exec.card_budget_s", float(os.environ.get("V48_EXEC_BUDGET_S", "45")))


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
        from datetime import datetime, timedelta
        from config.windows import site_tz
        from ems_exec.executor.window_policy import _range_start
        from ems_exec.executor.derived import _site_calendar_start
        now = datetime.now(site_tz())
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


_SPECIAL_KINDS = ("asset_3d", "topology_sld", "narrative_ai", "panel_aggregate")


def _special_handling_map(card_ids):
    """{card_id: handling_class} for cards whose handling_class is a SPECIAL renderer kind (asset_3d / topology_sld /
    narrative_ai) — those render via ems_exec.renderers.run_special (a GLB envelope / widgets.sld / widgets.ai_summary),
    NOT the column-fill run_card. Non-special / absent cards are omitted (they use run_card). DB read; never raises."""
    if not card_ids:
        return {}
    try:
        from data.db_client import q
        ids = ",".join(str(int(c)) for c in card_ids)
        rows = q("cmd_catalog", f"SELECT card_id, handling_class FROM card_handling WHERE card_id IN ({ids})")
        return {int(r[0]): r[1] for r in (rows or []) if r and r[1] in _SPECIAL_KINDS}
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


def fill_one_card(*, cid, render_card_id, handling_class, exact_metadata, data_instructions, asset_table,
                  db_link=None, window=None, requested_window=None, default_payload=None, mfm_id=None,
                  asset_name=None, member_scope="outgoing", page_key=None, metric=None, intent=None):
    """Fill ONE card's payload from NEURACT — the SHARED seam used by BOTH the parallel page fan-out (_run_cards._fill)
    AND the interactive /api/frame per-card date re-fetch. Dispatches run_special for a SPECIAL handling_class
    (asset_3d / topology_sld / narrative_ai / panel_aggregate) else run_card. This dispatch is the reason /api/frame
    must go through here: a panel-overview trend card is handling_class=panel_aggregate and is_history=true, so a
    run_card-only re-fetch would silently replace its member-summed data with wrong single-table data. [RC1]

    `window` = the OPERATIVE (start,end)/None read window (None for a snapshot/non-history card → latest row);
    `requested_window` = what the FE asked REGARDLESS of is_history (kept for honest narrative window labels). Never
    raises up here (run_card / run_special honest-degrade)."""
    if handling_class in _SPECIAL_KINDS:                     # asset_3d / topology_sld / narrative_ai / panel_aggregate
        from ems_exec.renderers import run_special
        a = {"mfm_id": mfm_id, "name": asset_name, "table": asset_table, "member_scope": member_scope}
        # panel_aggregate fills the card's OWN skeleton from the member-aggregated row; topology/narrative/asset_3d build
        # widgets from scratch and ignore the extra keys. shape_ref = the RAW harvested default for the RENDERED card
        # (the shape oracle fill()/fab_guards need so the panel path does not over-blank order/layout metadata).
        ctx = {"asset_table": asset_table, "mfm_id": mfm_id, "db_link": db_link,
               "window": window, "requested_window": requested_window, "page_key": page_key,
               "metric": metric, "intent": intent, "member_scope": member_scope}
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
    member_scope = (asset or {}).get("member_scope") or "outgoing"  # PANEL READING DIRECTION [panel_overview]: the
    # incomer-vs-outgoing side the prompt asked for (stamped by layer1b/resolve/member_scope). Threaded to the
    # panel_aggregate renderer so its member fan-out sums the RIGHT side (default 'outgoing' → behaviour unchanged).

    def _fill(cid, o):
        di = o.get("data_instructions") or {}
        window = _date_window_for(di.get("consumer") or {}, date_window)
        rid = (o.get("swap_decision") or {}).get("swap_to_id") or cid  # the RENDERED card's identity (swap target)
        # ONE shared seam for every card kind (dispatches run_special vs run_card) — see fill_one_card. `requested_window`
        # carries what the FE asked REGARDLESS of is_history (honest narrative label + future windowed-facts) while
        # `window` is the OPERATIVE read window; `metric`/`intent` let the narrator lead with the asked-about quantity.
        return fill_one_card(cid=cid, render_card_id=rid, handling_class=special.get(cid),
                             exact_metadata=o.get("exact_metadata"), data_instructions=di, asset_table=asset_table,
                             db_link=db_link, window=window, requested_window=date_window,
                             default_payload=o.get("_default_payload"), mfm_id=reg_mfm, asset_name=asset_name,
                             member_scope=member_scope, page_key=page_key, metric=metric, intent=intent)

    deadline = time.time() + _EXEC_BUDGET_S
    with ThreadPoolExecutor(max_workers=max(2, min(len(tasks), 8))) as ex:
        futs = {ex.submit(_fill, cid, o): cid for cid, o in tasks.items()}
        for fut in as_completed(futs):
            cid = futs[fut]
            remaining = max(0.0, deadline - time.time())
            try:
                completed_by_id[cid] = fut.result(timeout=remaining or 0.01)
                status_by_id[cid] = {"ok": True, "why": "ok"}
                stage(run_id, "exec", card=cid, ok=True)
            except _FTimeout:
                status_by_id[cid] = {"ok": False, "why": "executor budget exceeded"}
                stage(run_id, "exec", card=cid, ok=False, why="executor budget exceeded")
            except Exception as e:                              # run_card never raises, but stay honest if it ever does
                status_by_id[cid] = {"ok": False, "why": f"{type(e).__name__}: {e}"}
                stage(run_id, "exec", card=cid, ok=False, why=f"{type(e).__name__}: {e}")
    return completed_by_id, status_by_id
