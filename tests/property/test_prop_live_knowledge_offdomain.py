"""LIVE metamorphic PROPERTY — the knowledge gate against the REAL model:
  L1  conceptual electrical/mechanical questions come back kind='knowledge' with a real answer (never refused,
      never silently falling through to the card pipeline) — "knowledge prompts must never invoke dashboards"
      end-to-end, since a knowledge kind returns TERMINALLY at the host fork (see the offline plumbing property).
  L2  off-domain prompts (people/food/sport/poetry/geography) are ALWAYS kind='off_scope' with the refusal line.
  L3  asset/data prompts DEFER (kind='dashboard') — the gate never swallows a dashboard request into prose.
Seeded by PBT_SEED, scaled by PBT_LIVE_EXAMPLES.
"""
import os
import random

import pytest

pytestmark = pytest.mark.live

SEED = int(os.environ.get("PBT_SEED", "42"))
N = max(1, int(os.environ.get("PBT_LIVE_EXAMPLES", "4")))

KNOWLEDGE = [
    "what is power factor?",
    "explain total harmonic distortion",
    "how does a ups inverter work?",
    "why does a transformer need a tap changer?",
    "what does kvarh measure?",
    "what is the difference between kva and kw?",
]
OFF_DOMAIN = [
    "who is the president of the united states?",
    "best pizza place near me",
    "what was the latest cricket score?",
    "write a poem about the ocean",
    "what is the capital of france?",
    "recommend a good movie for tonight",
]
DASHBOARD = [
    "voltage and current for PCC-Panel-1",
    "dg fuel level today",
    "real-time monitoring of PCC-Panel-2",
]


def _sample(rng, pool, n):
    pool = list(pool)
    rng.shuffle(pool)
    return pool[:n]


def test_l1_knowledge_prompts_are_answered_not_dashboarded(qwen_live):
    from knowledge.ems import ask
    rng = random.Random(SEED)
    failures = []
    for p in _sample(rng, KNOWLEDGE, N):
        out = ask(p)
        if out["kind"] != "knowledge" or out["refused"] or not out["answer"].strip():
            failures.append(f"  {p!r}: kind={out['kind']!r} refused={out['refused']} answer_chars={len(out['answer'])}")
    assert not failures, "knowledge prompts mis-gated:\n" + "\n".join(failures)


def test_l2_off_domain_prompts_always_refused(qwen_live):
    from knowledge.ems import ask, refusal_line
    rng = random.Random(SEED + 1)
    failures = []
    for p in _sample(rng, OFF_DOMAIN, N):
        out = ask(p)
        if out["kind"] != "off_scope" or out["refused"] is not True or out["answer"] != refusal_line():
            failures.append(f"  {p!r}: kind={out['kind']!r} refused={out['refused']}")
    assert not failures, "off-domain prompts NOT refused:\n" + "\n".join(failures)


def test_l3_dashboard_prompts_defer(qwen_live):
    from knowledge.ems import ask
    rng = random.Random(SEED + 2)
    failures = []
    for p in _sample(rng, DASHBOARD, min(N, len(DASHBOARD))):
        out = ask(p)
        if out["kind"] != "dashboard":
            failures.append(f"  {p!r}: kind={out['kind']!r} (the gate must DEFER asset/data prompts)")
    assert not failures, "dashboard prompts swallowed by the knowledge gate:\n" + "\n".join(failures)
