"""validation/corpus/templates.py — the WORKFLOW TAXONOMY as the CODE-DEFAULT MIRROR of db/seed_prompt_corpus.sql:
every prompt category (+ expect + budget), template phrasing, and vocabulary lane the generator permutes. The LIVE
source is the cmd_catalog rows (prompt_category / prompt_template / prompt_vocab — edit rows, not this file); these
constants are ONLY the DB-down fallback, loaded through store.py (fail-open) [config → DB].

Expectations use the checks/expectations.py grammar: cards | picker | knowledge | refused | empty | unavailable |
compare:N | '|' unions. Class-appropriate metric vocabulary: a metric only pairs with classes that can plausibly serve
it (fuel->DG, pressure->Compressor/Dryer) so 'invalid' coverage is deliberate (its own category), never accidental."""
from __future__ import annotations

# category -> expected outcome + post-expansion case budget (the corpus-size dial; DB mirror: prompt_category)
DEFAULT_CATEGORIES = {
    "single_asset":    {"expect": "cards",                    "budget": 9000},
    "historical":      {"expect": "cards",                    "budget": 6000},
    "panel_aggregate": {"expect": "cards",                    "budget": 2500},
    "compare_2":       {"expect": "compare:2|picker",         "budget": 2000},
    "compare_3":       {"expect": "compare:3|picker",         "budget": 700},
    "compare_5":       {"expect": "compare:5|picker",         "budget": 250},
    "compare_mixed":   {"expect": "compare:2|picker",         "budget": 500},
    "ambiguous":       {"expect": "picker",                   "budget": 1500},
    "invalid":         {"expect": "empty|picker|unavailable", "budget": 400},
    "alias":           {"expect": "cards|picker",             "budget": 2000},
    "mutated":         {"expect": "cards|picker",             "budget": 2500},
    "knowledge":       {"expect": "knowledge",                "budget": 400},
    "off_domain":      {"expect": "refused",                  "budget": 300},
    "sld":             {"expect": "cards",                    "budget": 350},
    "view_3d":         {"expect": "cards",                    "budget": 350},
    "narrative":       {"expect": "cards",                    "budget": 1500},
    "sankey":          {"expect": "cards",                    "budget": 250},
    "mixed":           {"expect": "cards|compare:2",          "budget": 800},
}

# (tkey, category, template, expect-override|None, weight) — DB mirror: prompt_template
DEFAULT_TEMPLATES = [
    ("single_asset.metric_for_asset",  "single_asset",    "<metric> for <asset>",                 None, 3),
    ("single_asset.asset_metric",      "single_asset",    "<asset> <metric>",                     None, 2),
    ("single_asset.show_metric_of",    "single_asset",    "show me <metric> of <asset>",          None, 2),
    ("single_asset.whats_metric",      "single_asset",    "what's the <metric> for <asset>",      None, 1),
    ("single_asset.dashboard",         "single_asset",    "<metric> dashboard for <asset>",       None, 1),
    ("single_asset.how_is_on",         "single_asset",    "how is <asset> doing on <metric>",     None, 1),
    ("historical.metric_asset_window", "historical",      "<metric> for <asset> <window>",        None, 3),
    ("historical.window_first",        "historical",      "<window> <metric> for <asset>",        None, 1),
    ("historical.show_asset_window",   "historical",      "show <asset> <metric> <window>",       None, 1),
    ("historical.metric_window",       "historical",      "<metric> <window>",         "cards|picker", 1),
    ("panel_aggregate.metric_panel",   "panel_aggregate", "<metric> for <panel>",                 None, 3),
    ("panel_aggregate.scoped",         "panel_aggregate", "<metric> for <scope> <panel>",         None, 2),
    ("panel_aggregate.overview",       "panel_aggregate", "overview of <panel>",                  None, 1),
    ("compare_2.compare_and",          "compare_2",       "compare <asset1> and <asset2>",        None, 2),
    ("compare_2.compare_metric",       "compare_2",       "compare <asset1> and <asset2> <metric>", None, 2),
    ("compare_2.vs",                   "compare_2",       "<asset1> vs <asset2> <metric>",        None, 2),
    ("compare_2.which_higher",         "compare_2",       "which has higher <metric>, <asset1> or <asset2>", None, 1),
    ("compare_3.compare_and",          "compare_3",       "compare <asset1> and <asset2> and <asset3> <metric>", None, 1),
    ("compare_3.commas",               "compare_3",       "compare <asset1>, <asset2>, <asset3> <metric>", None, 1),
    ("compare_5.compare_and",          "compare_5",
     "compare <asset1> and <asset2> and <asset3> and <asset4> and <asset5> <metric>",             None, 1),
    ("compare_mixed.compare_and",      "compare_mixed",   "compare <asset1> and <asset2> <metric>", None, 1),
    ("ambiguous.dashboard_token",      "ambiguous",       "show me the dashboard for <token>",    None, 2),
    ("ambiguous.metric_class",         "ambiguous",       "<metric> for <class>",                 None, 2),
    ("ambiguous.bare_token",           "ambiguous",       "<token>",                              None, 1),
    ("invalid.metric_for",             "invalid",         "<metric> for <invalid>",               None, 2),
    ("invalid.bare",                   "invalid",         "<invalid> dashboard",                  None, 1),
    ("alias.metric_panel",             "alias",           "<metric> for <panel>",                 None, 2),
    ("alias.metric_short",             "alias",           "<metric> for <asset>",                 None, 2),
    ("mutated.metric_for",             "mutated",         "<metric> for <asset>",                 None, 1),
    ("knowledge.concept",              "knowledge",       "<concept>",                            None, 1),
    ("off_domain.prompt",              "off_domain",      "<offdomain>",                          None, 1),
    ("sld.for_panel",                  "sld",             "single line diagram for <panel>",      None, 2),
    ("sld.sld_of",                     "sld",             "sld of <panel>",                       None, 1),
    ("view_3d.of_panel",               "view_3d",         "3d view of <panel>",                   None, 2),
    ("view_3d.show_asset",             "view_3d",         "show <asset> in 3d",                   None, 1),
    ("narrative.summary_terse",        "narrative",       "summary <asset>",                      None, 2),
    ("narrative.give_summary",         "narrative",       "give me a summary of <asset>",         None, 2),
    ("narrative.performing",           "narrative",       "how is <asset> performing today",      None, 1),
    ("narrative.brief_report",         "narrative",       "brief report on <asset>",              None, 1),
    ("sankey.flow_panel",              "sankey",          "energy flow distribution for <panel>", None, 1),
    ("mixed.window_summary",           "mixed",           "<metric> for <asset> <window> and summarize anomalies", None, 1),
    ("mixed.metric_plus_summary",      "mixed",           "<metric> for <asset> and give me a summary", None, 1),
]

# kind -> [(value, meta)] — DB mirror: prompt_vocab (meta: metric -> classes csv, *_abbrev -> canonical, plural -> stem)
DEFAULT_VOCAB = {
    "metric": [
        ("voltage and current", ""), ("energy and power", ""), ("power factor", ""),
        ("power quality and harmonics", ""), ("load factor", ""), ("demand profile", ""),
        ("load anomalies", ""), ("real time monitoring", ""),
        ("efficiency", "DG,Chiller,Transformer,UPS"), ("operations and runtime", "DG"),
        ("fuel efficiency", "DG"), ("thermal oil", "Compressor,Dryer"), ("pressure element", "Compressor,Dryer"),
        ("condenser performance", "Chiller"), ("overview", "Chiller,AHU,AirWasher,CoolingTower,Pump,Fan,Dryer"),
    ],
    "window": [(w, "") for w in (
        "today", "yesterday", "over the last hour", "over the last 30 minutes", "over the last 7 days",
        "over the last 30 days", "this month", "this week", "last week", "last month", "past 24 hours", "since monday")],
    "conv_prefix": [(p, "") for p in (
        "can you show me", "please pull up", "hey, i need", "show me", "i want to see", "could you display",
        "give me", "let me see", "bring up", "pull up", "i'd like to check", "quickly show")],
    "conv_suffix": [(s, "") for s in (
        "please", "right now", "thanks", "asap", "on the main screen", "for the plant",
        "when you get a chance", "quickly")],
    "concept": [(c, "") for c in (
        "what is power factor", "explain THD", "explain apparent power", "how does a UPS work",
        "what is a cooling tower", "difference between kW and kVA", "how does a diesel generator work",
        "what causes voltage sag", "explain load factor", "what is reactive power")],
    "off_domain": [(o, "") for o in (
        "what's the weather today", "who won the cricket match", "who is the prime minister of india",
        "recommend me a movie", "write a poem about the sea", "capital of france")],
    "invalid_asset": [(i, "") for i in (
        "DG-999", "ZZZ-Unknown-Plant-7", "Fake-UPS-77", "Transformer-99X", "UPS-1000", "Chiller-77Z")],
    "scope_incomer": [(s, "") for s in ("incomer", "incoming", "supply side", "source side", "upstream")],
    "metric_abbrev": [("pf", "power factor"), ("thd", "harmonics"), ("volts", "voltage"), ("amps", "current"),
                      ("kwh", "energy"), ("rtm", "real time monitoring"), ("sld", "single line diagram")],
    "class_abbrev": [("tfr", "transformer"), ("xfmr", "transformer"), ("trafo", "transformer"),
                     ("genset", "generator"), ("pnl", "panel"), ("comp", "compressor")],
    "plural": [("transformers", "transformer"), ("panels", "panel"), ("chillers", "chiller"), ("pumps", "pump"),
               ("fans", "fan"), ("anomalies", "anomaly"), ("compressors", "compressor"), ("feeders", "feeder")],
}


def defaults() -> dict:
    """The store()-shaped fallback bundle (see store.py)."""
    cats = {c: dict(v) for c, v in DEFAULT_CATEGORIES.items()}
    tmpls = [{"tkey": t, "category": c, "template": s, "expect": e, "weight": w}
             for t, c, s, e, w in DEFAULT_TEMPLATES]
    vocab = {k: [{"value": v, "meta": m} for v, m in rows] for k, rows in DEFAULT_VOCAB.items()}
    return {"categories": cats, "templates": tmpls, "vocab": vocab, "source": "code-default"}
