"""layer1b/basket/column_basket.py — CARD-AGNOSTIC generous column basket (resolve_columns, recipe_fields=None). [spec section 2 L1b, #20]"""
import os
from llm.prompt_load import load as _prompt_load

from llm.client import call_qwen
from config.app_config import cfg
from config.metrics import prompt_metric_hint
from layer1b.basket.col_dict import col_dict, window_nonnull
from layer1b.basket.avg_phase import phase_sources
from llm.transient_retry import retry_transient_result
from layer1b.resolve.asset_candidates import feeder_table

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DB-driven basket guidance (cmd_catalog.app_config key 'layer1b.basket.quality_guidance'; this constant is the
# code-default fallback per the DB-driven-config pattern). WHY: the AI read 'real time monitoring' narrowly and dropped
# the derived QUALITY class (current_unbalance_pct, thd_*, *_deviation_pct) even though those columns were shown with
# has_data=Y — so quality cards served blank. The fix is CONTEXT, not code: tell the model the generous basket includes
# the quality columns measuring each in-scope quantity family. Edit the DB row to tune; no code change needed.
_QUALITY_GUIDANCE = (
    "The GENEROUS feasible basket MUST also include the derived QUALITY/health columns that MEASURE each quantity "
    "family the prompt covers — unbalance, per-phase deviation, spread, THD/compliance, and power-factor columns of "
    "that family (e.g. a current-family prompt includes current_unbalance_pct and the thd_current_* columns; a "
    "voltage-family prompt includes voltage_unbalance_pct and the thd_voltage_* columns). A broad monitoring / "
    "overview / status / dashboard prompt covers ALL quantity families present, so include the has_data=Y quality "
    "columns of every family. Quality columns belong in `feasible` (card-agnostic breadth); rank them in `probable` "
    "only when the prompt asks about quality."
)


def _load_prompt(name):
    return _prompt_load(_HERE, name)   # the ONE loader (llm/prompt_load, D8); errors="replace" house default


def build_basket(prompt, asset, intent="snapshot"):
    # need only a resolved data TABLE — col_dict reads its real columns directly (neuract is self-describing). The old
    # `mfm_type_id` requirement was stale (col_dict was once keyed by mfm_type over lt_parameter; it no longer is) and
    # the live app_devices registry leaves mfm_type_id=None (class carries the type), so requiring it emptied every basket.
    if not asset or not asset.get("table"):
        return {"tables": [], "columns": [], "probable": [], "n_columns": 0, "llm_failed": False}
    # GHOST short-circuit: a row the registry sync has already proven table-less (table_exists stamped False) can
    # never have columns — skip the doomed sample AND the pointless basket LLM call. Only an EXPLICIT False
    # short-circuits (legacy asset dicts without the key are unaffected); latest_nonnull's dark-table degrade stays
    # the generic backstop for the stale-true case (table dropped after the last sync). [audit 2026-07-14, 01 F1]
    if asset.get("table_exists") is False:
        return {"tables": [], "columns": [], "probable": [], "n_columns": 0, "llm_failed": False}
    table = asset["table"]
    # WINDOWED has_data [hardening]: the per-column Y/N shown to the basket AI covers the last N rows (DB knob
    # layer1b.has_data_window_rows), so an intermittent column that is merely null at the single latest sample isn't
    # dishonestly flagged N ('Prefer has_data=Y' then biased the AI away from a real column).
    hasdata = window_nonnull(table)
    # AGGREGATE PANEL only: when the panel's OWN table carries NO canonical ELECTRICAL columns but it HAS feeders,
    # build the basket from a representative feeder's schema so the Sankey/total cards' metrics (active_power_total_kw,
    # …) resolve instead of hallucinating. THE TRIGGER IS ELECTRICAL-NESS, NOT VALUES [feedbacks-stub fix]: the old
    # `not hasdata` gate assumed pcc_panel_N_feedbacks is value-empty — it is NOT (breaker/relay feedback BITS are
    # non-null), so the substitution never fired and the basket AI was honestly shown 34 relay columns for a
    # voltage/current prompt → feasible=[] probable=[] (live section-compare inspector, 2026-07-12). A canonical
    # electrical column is one the dictionary DESCRIBES (non-empty label/unit — describe() knows voltage_avg, not
    # tf_inc_2_acb_on_fb). A REAL meter (transformer/incomer) keeps its OWN columns — its table HAS electrical
    # columns, so it is never overridden. leaf → no feeders → unchanged.
    def _has_electrical(t):
        return any((c[1] or c[3]) for c in col_dict(t))       # any column with a dictionary label OR unit
    if asset.get("has_feeders") and asset.get("mfm_id") and not _has_electrical(table):
        ft = feeder_table(asset["mfm_id"])
        if ft:
            table = ft
            hasdata = window_nonnull(ft)
    metric = prompt_metric_hint(prompt)                     # rough prompt-derived hint (1b is parallel to 1a) [T0-6]
    cols = col_dict(table)                                  # dictionary built from the REAL consumer (neuract / CONSUMER_SCHEMA) columns
    lines = "\n".join(f"{c[0]} | {c[1]} | {c[2]} | {c[3]} | {'Y' if c[0] in hasdata else 'N'}" for c in cols)
    system = _load_prompt("column_system.md")
    guidance = cfg("layer1b.basket.quality_guidance", _QUALITY_GUIDANCE)
    user = (f"PROMPT: {prompt!r}\nMETRIC: {metric}\nINTENT: {intent}\n"
            + (f"GUIDANCE: {guidance}\n" if guidance else "")
            + f"\nCOLUMNS (column_name | label | kind | unit | has_data):\n{lines}\n\nJSON:")
    # stage='basket' names this call site in llm/obs failure telemetry (before: 84 outage entries bucketed stage='-')
    # and keys the per-stage timeout row (app_config llm.timeout.basket; base llm.timeout fallback — the same 120s the
    # old literal hardcoded, now a DB row). retry_transient mirrors asset_resolve: transient-only bounded retry (no-retry rule: a deterministic
    # timeout/truncation fails fast) so a
    # transient outage doesn't silently shrink the basket to the logged floor; llm_failed rides in the basket and is
    # surfaced via layer1b contract_problems (schema.validate_layer1b_output). [AI_QUALITY_BACKLOG item 15]
    # DECISION INSPECTOR: the meter's real column dictionary IS the option set — declared per attempt (call_qwen
    # clears the context on return) so the llm event's `decision` carries what the model chose FROM.
    from obs import llm_tap

    def _call():
        llm_tap.set_decision(kind="selection", candidate_kind="column",
                             candidates=[{"column": c[0], "label": c[1], "kind": c[2], "unit": c[3],
                                          "has_data": c[0] in hasdata} for c in cols],
                             table=table, metric_hint=metric)
        return call_qwen(system, user, stage="basket", on_error="marker")

    res, llm_failed = retry_transient_result(_call)

    realset = {c[0] for c in cols}
    by = {c[0]: c for c in cols}
    allcols = [c[0] for c in cols]                                        # every real metric column of this meter (no plumbing)
    # LOGGED FLOOR [SEAM 4]: the basket must ALWAYS carry the meter's REAL LOGGED columns so Layer 2 can bind every real
    # column ANY card on the routed page needs — the AI's `feasible` array alone dropped logged voltage/current on some
    # prompts (57 logged -> 28 basket), which then false-blanked cards for columns that ARE in the DB. The floor is every
    # logged column that is a genuine metric (kind != 'event' — a 0/1 flag like current_imbalance_event_active must NOT
    # ride in as a phase current, per describe's EVENT rule). Gated by a DB knob so the policy is editable, not code.
    include_floor = bool(cfg("layer1b.basket.include_logged_floor", True))
    floor = [c[0] for c in cols if include_floor and c[0] in hasdata and c[2] != "event"]
    feasible = [c for c in (res.get("feasible") or []) if c in realset]   # GENEROUS AI breadth (no hallucination)
    # UNION floor ∪ AI-feasible, floor first (guaranteed real columns), then any extra AI columns (may be genuinely-empty
    # but relevant — they stay has_data=false so downstream honest-blanks; never fabricated). Dedup, order-stable.
    seen, feasible_cols = set(), []
    for c in floor + feasible:
        if c not in seen:
            seen.add(c)
            feasible_cols.append(c)
    # BOUND [SEAM 4]: keep the basket bounded via a DB knob (default 400 — a neuract meter has ~63 metric cols, so this is
    # effectively uncapped for meters; it guards the ~190-col lt_panels tables). Logged floor columns are kept ahead of
    # empty AI-only columns, so a cap never drops a real logged column before an empty one.
    cap = int(cfg("layer1b.basket.max_columns", 400))
    feasible = feasible_cols[:cap] if cap and cap > 0 else feasible_cols
    # probable carries the AI's relevance CONFIDENCE (1.0=exact, 0.6-0.8=closest real stand-in) + substitute_for
    # (the asked-for concept a low-confidence column stands in for) so Layer 2 can best-effort fill + note substitutions.
    probable = []
    for p in (res.get("probable") or []):
        if not (isinstance(p, dict) and p.get("column") in realset):
            continue
        try:
            conf = float(p.get("confidence", 1.0))
        except (TypeError, ValueError):
            conf = 1.0
        probable.append({"column": p["column"], "label": p.get("label") or by[p["column"]][1],
                         "why": p.get("why") or "", "rank": p.get("rank"),
                         "confidence": max(0.0, min(1.0, conf)),
                         "substitute_for": (p.get("substitute_for") or None)})
    # AVG-FROM-PHASE derivability [SEAM 4]: a present-but-EMPTY avg column whose per-phase siblings ARE logged is not a
    # dead leaf — its value is the mean of the real phases. Flag it `derivable` (with the logged phase source columns) so
    # Layer 2 / the executor fills it from the phases instead of blanking. has_data stays FALSE (the avg column itself has
    # no rows — no fabrication); `derivable` is the recovery pointer. A genuinely-empty avg with no logged phases is not
    # flagged and stays honest-blank. DB knob gates the whole behavior.
    derive_avg = bool(cfg("layer1b.basket.derive_avg_from_phase", True))
    columns = []
    for col in feasible:
        has = col in hasdata
        c = {"table": table, "column": col, "label": by[col][1], "kind": by[col][2],
             "unit": by[col][3], "has_data": has}
        if derive_avg and not has:
            srcs = phase_sources(col, allcols, hasdata)
            if srcs:
                c["derivable"] = "avg_from_phase"
                c["derive_sources"] = srcs
        columns.append(c)
    return {"tables": [table], "columns": columns, "probable": probable,
            "n_columns": len(columns), "metric_hint": metric,
            # telemetry, NOT a gate: True = the basket AI was never heard (fail-open {} twice) — the basket is the
            # logged floor only. Surfaced as a contract problem so the failure is attributed, never silent. [item 15]
            "llm_failed": llm_failed}
