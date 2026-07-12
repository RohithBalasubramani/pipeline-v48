"""host/assemble.py — the serve-boundary CARD ASSEMBLY for ONE asset: run the parallel per-card NEURACT executor
(ems_exec.run_card) + enrich each Layer-2 card into the FE card shape. ONE concern, reused BYTE-COMPATIBLY by BOTH the
single-asset build_response AND every lane of the multi-asset build_response_multi (each lane calls it with its OWN
resolved asset → its own neuract table). This is a pure extraction of build_response's executor+enrich block,
parameterised by the target asset — nothing else changed. [atomic]
"""
from config import neuract_dsn as _neuract_dsn             # DB-driven neuract DSN (config accessor + code-default)
from host.enrich import _enrich_card                       # FE card build + blank-reason wording + emit-gap merge
from host.exec_cards import _run_cards                     # the parallel per-card executor fan-out


def assemble_cards(out, asset, date_window=None):
    """Fill + enrich EVERY Layer-2 card for `asset` (from its OWN neuract table). `out` = a run_pipeline lane result
    (carries layer1a / layer2 / validation / run_id / data_unavailable). `asset` = the resolved as_asset dict
    (name/table/class/mfm_id). Returns the FE card list — NOT yet L2-note-attached: the caller runs _attach_l2_notes so
    the source-locked wiring test (test_build_response_wires_attach) stays green and both paths attach identically.

    INFRA-OUTAGE / no resolved table → [] (honest page-level terminal), exactly as the inline block did before."""
    from obs.span import stage_span
    l1a = out.get("layer1a") or {}
    l2 = out.get("layer2") or {}                              # {card_id: Layer2CardOutput} — the payload source
    val = out.get("validation") or {}
    vcards = (val.get("payload") or {}).get("cards") or []
    val_by_id = {c.get("card_id"): c for c in vcards if isinstance(c, dict) and "card_id" in c}
    page_key = l1a.get("page_key")
    asset = asset or {}
    asset_table = asset.get("table")
    if out.get("data_unavailable") or not asset_table:
        # INFRA-OUTAGE / no resolved table — Layer 2 never reached ground truth (or has no meter to read). Emit ZERO
        # cards (honest terminal via data_unavailable + degrade.reason) rather than verdict-less 1a shells.
        with stage_span("executor", inputs={"page_key": page_key, "asset": asset.get("name")}) as sp:
            sp.set_degradation(data_unavailable=out.get("data_unavailable") or None,
                               no_asset_table=(not asset_table) or None)
            sp.set_outputs(cards=0)
        return []
    # OBS `executor` stage span: the whole parallel per-card fill (each fill is an `executor.card` child span)
    with stage_span("executor", inputs={"page_key": page_key, "asset": asset.get("name"),
                                        "asset_table": asset_table, "n_cards": len(l2),
                                        "date_window": date_window}) as sp:
        completed_by_id, status_by_id = _run_cards(l2, asset_table, db_link=_neuract_dsn.dsn(),
                                                   date_window=date_window, run_id=out.get("run_id"),
                                                   asset=asset, page_key=page_key,
                                                   metric=l1a.get("metric"), intent=l1a.get("intent"))
        n_fail = sum(1 for s in status_by_id.values() if not (s or {}).get("ok", True))
        sp.set_outputs(cards=len(status_by_id), completed=len(completed_by_id), failed=n_fail,
                       fail_whys=sorted({(s or {}).get("why") for s in status_by_id.values()
                                         if not (s or {}).get("ok", True)}))
        if n_fail:
            sp.set_degradation(failed_fills=n_fail)
    # OBS `renderer` stage span: the FE card build + per-leaf render verdict attachment
    with stage_span("renderer", inputs={"page_key": page_key, "n_cards": len(l1a.get("cards") or [])}) as sp:
        from host.exec_cards import _special_handling_map
        _handling = _special_handling_map([c.get("card_id") for c in (l1a.get("cards") or []) if c.get("card_id")])
        cards = [_enrich_card(c, page_key, val_by_id, l2.get(c.get("card_id")),
                              completed=completed_by_id.get(c.get("card_id")),
                              run_ok=(status_by_id.get(c.get("card_id")) or {}).get("ok", True),
                              run_why=(status_by_id.get(c.get("card_id")) or {}).get("why"),
                              asset_table=asset_table, asset=asset,   # asset → the per-card /api/frame refetch bundle [RC1]
                              handling=_handling.get(c.get("card_id")),   # panel_aggregate = date-navigable by construction
                              date_window=date_window)                    # '{period}' title token → the window label
                 for c in (l1a.get("cards") or [])]
        verdicts = {}
        for c in cards:
            v = ((c.get("render") or {}).get("verdict")) or "none"
            verdicts[v] = verdicts.get(v, 0) + 1
        sp.set_outputs(cards=len(cards), verdicts=verdicts,
                       with_payload=sum(1 for c in cards if c.get("has_payload")))
        sp.set_validation(verdicts=verdicts)
        if verdicts.get("honest_blank"):
            sp.set_degradation(honest_blank=verdicts.get("honest_blank"))
        return cards
