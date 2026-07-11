"""validation/corpus/templates.py — the WORKFLOW TAXONOMY: every prompt category the pipeline supports, as templates
the generator permutes over the universe. Each category carries its EXPECTED outcome (checks/expectations.py judges
against it) — expectations use the response.parse outcome vocabulary:
cards | picker | knowledge | refused | empty | compare(N groups) | flexible unions ('cards|picker').

Class-appropriate metric vocabulary: a metric only pairs with classes that can plausibly serve it (fuel->DG,
pressure->Compressor/Dryer) so 'invalid' coverage is deliberate (its own category), never accidental."""
from __future__ import annotations

# metric -> classes it applies to (None = every electrical-metered class)
METRICS = {
    "voltage and current": None,
    "energy and power": None,
    "power factor": None,
    "power quality and harmonics": None,
    "load factor": None,
    "demand profile": None,
    "load anomalies": None,
    "real time monitoring": None,
    "efficiency": ("DG", "Chiller", "Transformer", "UPS"),
    "operations and runtime": ("DG",),
    "fuel efficiency": ("DG",),
    "thermal oil": ("Compressor", "Dryer"),
    "pressure element": ("Compressor", "Dryer"),
    "condenser performance": ("Chiller",),
    "overview": ("Chiller", "AHU", "AirWasher", "CoolingTower", "Pump", "Fan", "Dryer"),
}

TIME_WINDOWS = ["today", "yesterday", "over the last hour", "over the last 30 minutes", "over the last 7 days",
                "over the last 30 days", "this month", "this week"]

CONCEPTS = ["what is power factor", "explain THD", "explain apparent power", "how does a UPS work",
            "what is a cooling tower", "difference between kW and kVA", "how does a diesel generator work",
            "what causes voltage sag", "explain load factor", "what is reactive power"]

OFF_DOMAIN = ["what's the weather today", "who won the cricket match", "who is the prime minister of india",
              "recommend me a movie", "write a poem about the sea", "capital of france"]

INVALID = ["energy for DG-999", "voltage for ZZZ-Unknown-Plant-7", "power for Fake-UPS-77",
           "current for Transformer-99X"]

# category -> spec. count = generation budget per category (the generator downsamples deterministically).
CATEGORIES = {
    # grounded single-asset dashboards: <metric> for <UNIQUE asset name> (confident pin -> cards)
    "single_asset":      {"expect": "cards",         "count": 400},
    # the same, with a time window appended (historical coverage)
    "historical":        {"expect": "cards",         "count": 250},
    # panel-aggregate by alias ('energy for PCC-1A') + incomer/outgoing scope words
    "panel_aggregate":   {"expect": "cards",         "count": 60},
    # compare: 2/3/5 assets, same-class + mixed-class, alias + full-name spellings
    "compare_2":         {"expect": "compare:2",     "count": 40},
    "compare_3":         {"expect": "compare:3",     "count": 15},
    "compare_5":         {"expect": "compare:5|picker", "count": 6},
    "compare_mixed":     {"expect": "compare:2|picker", "count": 12},
    # ambiguity: bare homonym tokens / bare classes -> the honest picker
    "ambiguous":         {"expect": "picker",        "count": 40},
    # invalid asset names -> honest empty/picker, NEVER cards, NEVER a crash
    "invalid":           {"expect": "empty|picker|unavailable", "count": len(INVALID)},
    # alias/mutation robustness: alias-typed panels + mutated spellings of unique names
    "alias":             {"expect": "cards|picker",  "count": 40},
    "mutated":           {"expect": "cards|picker",  "count": 60},
    # knowledge + off-domain guardrails
    "knowledge":         {"expect": "knowledge",     "count": len(CONCEPTS)},
    "off_domain":        {"expect": "refused",       "count": len(OFF_DOMAIN)},
    # special views
    "sld":               {"expect": "cards",         "count": 8},
    "view_3d":           {"expect": "cards",         "count": 8},
    "narrative":         {"expect": "cards",         "count": 20},
    "sankey":            {"expect": "cards",         "count": 6},
    # mixed multi-intent requests (metric + window + summary in one prompt)
    "mixed":             {"expect": "cards|compare:2", "count": 20},
}
