"""layer1a/route.py — the 1a storytelling-router LLM call: prompt -> page_key + metric + intent. [spec section 2 L1a, #19]

Routes ONLY among the pages enabled in config/available_pages.py (the add/remove provision).

FAIL-CLOSED (hardening): an LLM outage / unparseable response / invalid page_key RAISES instead of silently routing to
the first shell-sorted page (the old keys[0] fallback landed EVERY failed prompt on the DG engine-cooling page with
metric=power). The raised message carries the 'llm transport/parse failure' fingerprint run/degrade_gate.py matches,
so the pipeline surfaces the honest data_unavailable terminal instead of a confident misroute.
"""
import os

from llm.client import call_qwen
from config.app_config import cfg
from config.metrics import METRIC_VOCAB
from config.available_pages import filter_to_available
from layer1a.catalog_compress import merge_story
from layer1a.db_reads.page_specs import read_page_specs
from layer1a.db_reads.card_titles import read_card_titles
from layer1a.db_reads.page_feasibility import read_page_feasibility
from layer1a.parse.page_key_fallback import resolve_page_key
from layer1a.parse.template_feasibility_gate import filter_renderable_templates
from layer1a.parse.metric_intent_defaults import clamp_metric_intent
from layer1a.parse.window_default import clamp_window
from layer1a.route_schema import route_answer_schema

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_prompt(name):
    with open(os.path.join(_HERE, "prompts", name)) as f:
        return f.read()


def _candidate_block(specs, titles):
    # per-page card-title evidence cap: DB knob (the two most card-rich panel pages measure 255/197 chars — the old
    # hardcoded 160 cut their tail cards mid-word, exactly the evidence a near-tie route needs). [hardening: titles cap]
    cap = int(cfg("route.card_titles_max", 400))
    # COMPRESSED CATALOG [AI_QUALITY_BACKLOG item 21 / D5]: ONE line per page — page_key + title VERBATIM (recall
    # untouched), then the purpose/theme/answers prose collapsed to ONE deduplicated story (they were 3 restatements =
    # ~10.4K of the 14.7K-char user message, x27 router calls/sweep). Shell boilerplate stays deduped by the ONE
    # '## SHELL' header per group. archetype is a per-shell layout tag the routing rules never key on — shown only when
    # the DB knob turns it back on.
    show_arch = bool(cfg("route.catalog_archetype", False))
    shell_hdr = _load_prompt("shell_grouping.md").strip()          # the '## SHELL: {shell}' grouping header template
    lines, shell = [], None
    for s in specs:
        if s["shell"] != shell:
            shell = s["shell"]
            lines.append("\n" + shell_hdr.replace("{shell}", shell or "(none)"))
        story = merge_story(s["purpose"], s["theme"], s["answers"])
        lines.append(f"- {s['page_key']} | {s['title']}"
                     + (f" [{s['archetype']}]" if show_arch and s["archetype"] else "")
                     + (f" | story: {story}" if story else "")
                     + f" | cards: {titles.get(s['page_key'], '')[:cap]}")
    return "\n".join(lines)


def route(prompt, db="cmd_catalog", feedback=None, exclude_page_key=None):
    specs = filter_to_available(read_page_specs(db))   # <-- only available pages
    if not specs:
        raise RuntimeError("no available pages (config/available_pages.py) match the live DB")
    # RENDERABILITY GATE (whole-template drop-and-reselect): disqualify any candidate template whose fraction of
    # UNRENDERABLE cards (card_feasibility.verdict in drop/no_data) >= cfg feasibility.template_max_unrenderable_frac,
    # so the router CHOOSES ANOTHER eligible template. NOT per-card pruning — a KEPT template passes ALL its cards and
    # Layer 2 force-swaps the few unrenderable ones. All disqualified -> fall back to the least-unrenderable (never nothing).
    feas_counts = read_page_feasibility([s["page_key"] for s in specs], db)
    specs, dropped = filter_renderable_templates(specs, feas_counts)
    # RE-ROUTE EXCLUSION (mechanical, not prose-only): on reflect feedback the previously-failed page is REMOVED from
    # the candidate list, so the model CANNOT silently re-pick the same page. [hardening: reflect loop]
    excluded = None
    if exclude_page_key and any(s["page_key"] == exclude_page_key for s in specs) and len(specs) > 1:
        specs = [s for s in specs if s["page_key"] != exclude_page_key]
        excluded = exclude_page_key
    titles = read_card_titles(db)
    keys = [s["page_key"] for s in specs]
    # the metric/intent enum lines are generated from the SAME DB-driven vocab config/metrics.py + config/intents.py
    # read, so the prompt can never drift from the vocabulary the clamp enforces. [hardening: metric vocab drift]
    system = (_load_prompt("system.md")
              .replace("{{METRIC_VOCAB}}", ", ".join(METRIC_VOCAB))
              .replace("{{INTENT_VOCAB}}", " | ".join(cfg("intents.vocab", ["trend", "distribution", "snapshot", "table", "events"]))))
    user = "PAGES:\n" + _candidate_block(specs, titles) + f"\n\nPROMPT: {prompt!r}\n"
    if feedback:                                        # reflect-loop: the prior template couldn't be answered → re-route
        user += "\n" + _load_prompt("reroute_clause.md").strip().replace("{feedback}", str(feedback)) + "\n"
    user += "JSON:"
    # ROUTING DETERMINISM [L1a non-deterministic-page defect]: enum-CONSTRAIN the emission (vLLM structured output) to
    # the EXACT candidate page_key list + the metric/intent vocab. Greedy temp-0 + pinned seed keeps the RNG stable,
    # but a NEAR-TIE route can still flip run-to-run under batch load (concurrent batch composition changes the FP
    # reduction order) AND land in the fuzzy resolve_page_key recovery (segment/substring) whose winner differs by
    # which candidate barely wins. Forcing page_key ∈ keys removes that recovery branch entirely (the grammar can only
    # emit a valid verbatim key → how='verbatim' always), so the same prompt yields the same page. Wired FLAG-GATED
    # through json_schema= behind llm.guided_json.route (DEFAULT OFF, db/seed_route_guided_json.sql), mirroring the 1b
    # asset-resolver seam (json_schema=asset_answer_schema()): flag OFF → route_answer_schema returns None → call_qwen's
    # json_schema kwarg is inert → the request is BYTE-IDENTICAL to today (json_object). stage='route' also applies the
    # per-stage timeout so a slow batch can't flip to the fail-closed path.
    _intent_vocab = list(cfg("intents.vocab", ["trend", "distribution", "snapshot", "table", "events"]))
    r = call_qwen(system, user, stage="route",
                  json_schema=route_answer_schema(keys, METRIC_VOCAB, _intent_vocab))
    if not r:
        # fail-closed: call_qwen is fail-open ({} on ANY transport/parse error) — never emit a keys[0] route for it.
        # The message carries an outage fingerprint (run/degrade_gate.py) → honest data_unavailable terminal.
        raise RuntimeError("layer1a route: llm transport/parse failure (empty response from call_qwen :8200) — "
                           "fail-closed, refusing the arbitrary keys[0] fallback")
    page_key, how = resolve_page_key(r.get("page_key"), keys)
    if page_key is None:
        raise RuntimeError(f"layer1a route: model page_key {r.get('page_key')!r} is not resolvable "
                           f"({how}) against the candidate list — fail-closed, no arbitrary fallback"
                           + (f" (excluded reroute page: {excluded!r})" if excluded else ""))
    metric, intent = clamp_metric_intent(r.get("metric"), r.get("intent"))
    window = clamp_window(r.get("window"))
    spec = next(s for s in specs if s["page_key"] == page_key)
    return {"page_key": page_key, "metric": metric, "intent": intent, "window": window, "page_spec": spec,
            # telemetry (stage-logged by run/harness.py): which fallback fired + what the gate/exclusion did.
            # `window` is ALSO carried inside routing so build_layer1a_output forwards it verbatim (harness fallback).
            "routing": {"page_key_how": how, "dropped_templates": dropped, "excluded_page_key": excluded,
                        "raw_page_key": r.get("page_key"), "window": window}}


def route_to(page_key, metric, intent, db="cmd_catalog", *, reason=None):
    """DETERMINISTIC targeted route to a SPECIFIC live page (NO routing LLM call) — the granularity-reconcile re-route:
    the mirror page_key is already decided (layer1a.parse.granularity_reconcile), metric/intent carry over from the
    original route. Assembles the SAME route_result shape (page_spec + telemetry) so run_1a_to can rebuild stories/
    layout for the mirror. Raises if the page_key is not a live/available page (fail-closed — never fabricate a spec)."""
    specs = filter_to_available(read_page_specs(db))
    spec = next((s for s in specs if s["page_key"] == page_key), None)
    if spec is None:
        raise RuntimeError(f"route_to: {page_key!r} is not a live/available page — cannot reconcile granularity")
    metric, intent = clamp_metric_intent(metric, intent)
    return {"page_key": page_key, "metric": metric, "intent": intent, "page_spec": spec,
            "routing": {"page_key_how": "granularity_reconcile", "dropped_templates": [], "excluded_page_key": None,
                        "raw_page_key": page_key, "reconcile_reason": reason}}
