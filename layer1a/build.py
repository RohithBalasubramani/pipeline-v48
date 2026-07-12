"""layer1a/build.py — compose Layer 1a end to end: route -> per-card stories -> page layout -> partition -> Layer1aOutput. [spec section 2 L1a, contract 2]

OBS: the two AI decisions are wrapped as stage spans HERE (the composition boundary, not inside route/story code):
`page_selection` = the route (page_key/metric/intent/window pick), `story_selection` = the per-card story writing +
layout/partition assembly. Confidence = the deterministic route telemetry (page_key_how), not a model score (the
router emits none)."""
from layer1a.route import route, route_to
from layer1a.story_builder import build_stories
from layer1a.db_reads.page_layout import read_page_layout
from layer1a.schema import build_layer1a_output
from obs.span import stage_span
from layer1a.partition.group_detect import detect_groups


def _assemble(prompt, rr, db):
    with stage_span("story_selection", inputs={"page_key": rr.get("page_key"), "metric": rr.get("metric"),
                                               "intent": rr.get("intent")}) as sp:
        cards = build_stories(prompt, rr["page_key"], rr["metric"], rr["intent"], db)
        layout = read_page_layout(rr["page_key"], db)
        raw_groups, _standalone, dims = detect_groups(rr["page_key"], cards, db)
        groups = [
            {"group_id": f"{rr['page_key']}::g{i}", "card_ids": g, "coupling": dims}
            for i, g in enumerate(raw_groups)
        ]
        sp.set_outputs(n_cards=len(cards or []), card_ids=[c.get("card_id") for c in (cards or [])],
                       n_groups=len(groups),
                       n_storyless=sum(1 for c in (cards or []) if not c.get("analytical_story")))
        out = build_layer1a_output(rr, cards, layout, groups)
        # CONTRACT CHECK, non-gating [typing F10]: validate_layer1a_output existed + was unit-tested but had NO
        # production caller — 1a was the only silently-unchecked layer (1b attaches contract_problems, L2/validate
        # attach _schema_issues). Same key + same per-leaf-degradation posture as 1b: problems are TELEMETRY the
        # harness/sweeps read, never a gate. Never raises (a validator error must not take routing down).
        try:
            from layer1a.schema import validate_layer1a_output
            from layer1a.db_reads.page_specs import read_page_specs
            out["contract_problems"] = validate_layer1a_output(
                out, [s.get("page_key") for s in (read_page_specs(db) or [])])
        except Exception:
            out.setdefault("contract_problems", [])
        return out


def run_1a(prompt, db="cmd_catalog", feedback=None, exclude_page_key=None):
    with stage_span("page_selection", inputs={"prompt": prompt, "reroute": bool(feedback),
                                              "exclude_page_key": exclude_page_key}) as sp:
        rr = route(prompt, db, feedback=feedback, exclude_page_key=exclude_page_key)
        _rt = rr.get("routing") or {}
        sp.set_outputs(page_key=rr.get("page_key"), metric=rr.get("metric"), intent=rr.get("intent"),
                       window=rr.get("window"))
        sp.set_confidence(page_key_how=_rt.get("page_key_how"),
                          dropped_templates=len(_rt.get("dropped_templates") or []))
    return _assemble(prompt, rr, db)


def run_1a_to(prompt, page_key, metric, intent, db="cmd_catalog", *, reason=None):
    """Rebuild Layer 1a for a SPECIFIC page (granularity-reconcile mirror) — deterministic route_to (no routing LLM),
    then the SAME stories/layout/partition assembly. metric/intent carry over from the original route."""
    with stage_span("page_selection", inputs={"prompt": prompt, "pinned_page_key": page_key,
                                              "reason": reason}) as sp:
        rr = route_to(page_key, metric, intent, db, reason=reason)
        sp.set_outputs(page_key=rr.get("page_key"), metric=rr.get("metric"), intent=rr.get("intent"))
        sp.set_confidence(page_key_how="deterministic-mirror")
    return _assemble(prompt, rr, db)
