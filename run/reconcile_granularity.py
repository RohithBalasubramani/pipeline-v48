"""run/reconcile_granularity.py — the harness STEP that applies the post-resolution granularity safety-net (single
purpose). Layer 1a routes the shell from prompt TEXT (parallel with 1b, so blind to the asset's has_feeders); if the
routed page's SHELL granularity contradicts the RESOLVED asset (single meter on a panel-aggregate shell, or vice
versa), re-route 1a to the correct-granularity MIRROR page (same analytical tail) BEFORE Layer 2, so the page's cards
can actually populate. Deterministic + DB-driven (layer1a.parse.granularity_reconcile owns the shell/tail policy);
never raises — a reconcile hiccup must not sink an otherwise-fine page. Only fires on a CONFIDENT mismatch."""
from obs.errfmt import fmt_exc as _fmt_exc   # the ONE exception string [EH F4]
from layer1a.parse.granularity_reconcile import mirror_page_key, target_shell
from layer1a.db_reads.page_specs import read_page_specs
from config.available_pages import filter_to_available
from layer1a.build import run_1a_to
from obs.stage import stage
from obs.failures import record as record_failure


def apply(out, prompt, db, run_id):
    """If 1a's routed shell contradicts 1b's resolved asset granularity, rebuild 1a onto the mirror page. Mutates
    out['layer1a'] in place and records telemetry. No-op (returns out unchanged) when there is nothing to reconcile."""
    l1a, l1b = out.get("layer1a") or {}, out.get("layer1b") or {}
    if not l1a or not l1b:
        return out
    asset = l1b.get("asset") or {}
    if not asset:
        return out                                    # no resolved asset (ambiguous/empty) — nothing to reconcile against
    has_feeders = asset.get("has_feeders")
    asset_class = asset.get("class")
    routed_key = l1a.get("page_key")
    routed_shell = l1a.get("shell")
    try:
        specs = filter_to_available(read_page_specs(db))
        mirror = mirror_page_key(routed_key, routed_shell, has_feeders, specs, asset_class)
    except Exception as e:
        stage(run_id, "granularity_reconcile", ERROR=_fmt_exc(e))
        return out
    if not mirror:
        # TELEMETRY ONLY [T0-3]: mirror_page_key() returns None BOTH when the granularity already matches AND when a
        # REAL mismatch exists but no correct-granularity mirror page is available in the live specs — the latter used
        # to vanish silently (no stage record, no failure). Distinguish them here so a missing mirror is observable;
        # the decision path is untouched (the router's choice stands, exactly as before).
        try:
            want, mismatch = target_shell(routed_shell, has_feeders, asset_class)
            if mismatch and (has_feeders is not None or asset_class):
                stage(run_id, "granularity_reconcile", skipped="no_mirror", was=routed_key,
                      shell=routed_shell, want=want, has_feeders=has_feeders)
                record_failure("granularity_reconcile", "no_mirror", run_id=run_id,
                               detail=(f"routed {routed_key!r} ({routed_shell!r}) wants the {want!r} granularity "
                                       f"(has_feeders={has_feeders}, class={asset_class!r}) but no mirror page exists"))
        except Exception:
            pass
        return out
    why = (f"asset {asset.get('name')!r} has_feeders={has_feeders} but the routed page {routed_key!r} is the "
           f"{'panel-aggregate' if not has_feeders else 'single-meter'} granularity — reconciled to {mirror!r}")
    try:
        out["layer1a"] = run_1a_to(prompt, mirror, l1a.get("metric"), l1a.get("intent"), db, reason=why)
        out["notes"].setdefault("reconcile", why)
        stage(run_id, "granularity_reconcile", was=routed_key, now=mirror,
              has_feeders=has_feeders, cards=len((out["layer1a"] or {}).get("cards") or []))
    except Exception as e:
        # keep the original route rather than sink the page — reconcile is a safety-net, not a hard gate
        stage(run_id, "granularity_reconcile", ERROR=_fmt_exc(e), intended=mirror)
    return out
