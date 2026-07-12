"""LIVE metamorphic PROPERTY — "historical prompts must always produce historical pages": against the REAL router,
a prompt asking about a PAST period must come back with the matching historical TIME_WINDOWS preset — never the
'live' window and never the real-time-monitoring page family — and an explicitly live/now prompt must not be forced
into a multi-day historical window.
  L1  exact-vocabulary past phrases ('last 7 days', 'last 24 hours', "today's") map to their preset, and the routed
      page is NOT a real-time-monitoring page.
  L2  paraphrased past phrases (weaker oracle) still never yield window='live' nor a real-time-monitoring page.
  L3  explicit live/now prompts never yield a multi-day historical window.
Seeded by PBT_SEED, scaled by PBT_LIVE_EXAMPLES.
"""
import os
import random

import pytest

pytestmark = pytest.mark.live

SEED = int(os.environ.get("PBT_SEED", "42"))
N = max(1, int(os.environ.get("PBT_LIVE_EXAMPLES", "4")))

ASSETS = ["PCC-Panel-1", "PCC-Panel-2"]
EXACT = [
    ("energy consumption for {a} over the last 7 days", "last-7-days"),
    ("power trend for {a} over the last 24 hours", "last-24h"),
    ("today's energy for {a}", "today"),
]
PARAPHRASE = [
    "how much energy did {a} use over the past week",
    "power drawn by {a} during the previous 24 hours",
    "yesterday's consumption for {a}",
]
LIVE_NOW = [
    "live power right now for {a}",
    "what is {a} drawing at this very moment",
]
MULTI_DAY = {"last-7-days"}


def test_l1_exact_past_phrases_map_to_their_preset(qwen_live):
    from layer1a.route import route
    rng = random.Random(SEED)
    cases = [(t, w, rng.choice(ASSETS)) for t, w in EXACT][:N] or [(EXACT[0][0], EXACT[0][1], ASSETS[0])]
    failures = []
    for template, expected, asset in cases:
        r = route(template.format(a=asset))
        if r["window"] != expected:
            failures.append(f"  {template.format(a=asset)!r}: window={r['window']!r}, expected {expected!r}")
        if r["page_key"].endswith("/real-time-monitoring"):
            failures.append(f"  {template.format(a=asset)!r}: routed to the REAL-TIME page {r['page_key']!r}")
    assert not failures, "historical prompts lost their historical window/page:\n" + "\n".join(failures)


def test_l2_paraphrased_past_never_live(qwen_live):
    from layer1a.route import route
    rng = random.Random(SEED + 1)
    failures = []
    for template in PARAPHRASE[:N]:
        p = template.format(a=rng.choice(ASSETS))
        r = route(p)
        if r["window"] == "live" or r["page_key"].endswith("/real-time-monitoring"):
            failures.append(f"  {p!r}: window={r['window']!r} page={r['page_key']!r}")
    assert not failures, "past-tense prompts landed on live window/page:\n" + "\n".join(failures)


def test_l3_live_now_prompts_never_multiday_historical(qwen_live):
    from layer1a.route import route
    rng = random.Random(SEED + 2)
    failures = []
    for template in LIVE_NOW[:N]:
        p = template.format(a=rng.choice(ASSETS))
        r = route(p)
        if r["window"] in MULTI_DAY:
            failures.append(f"  {p!r}: window={r['window']!r}")
    assert not failures, "live/now prompts were forced into a multi-day window:\n" + "\n".join(failures)
