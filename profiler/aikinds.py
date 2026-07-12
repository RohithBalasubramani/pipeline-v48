"""profiler/aikinds.py — fingerprint an AI-log record's call kind from its system prompt.

ai_*.jsonl records carry no stage tag; the system prompt (request.messages[0].content)
is stable per call site (10 kinds observed across all 12,238 historical records).
Order matters: first match wins. Each kind maps to the profiler stage it belongs to.
"""

# (needle in messages[0].content, kind, stage)
FINGERPRINTS = [
    ("STORYTELLING ROUTER", "l1a_route", "page_selection"),
    ("L1 ASSET RESOLVER", "l1b_resolve", "asset_resolution"),
    ("COLUMN RESOLVER", "l1b_basket", "asset_resolution"),
    ("ANALYTICAL STORY", "stories", "story_selection"),
    ("LAYER 2", "l2_emit", "layer2_card"),
    ("EMS ASSISTANT gate", "knowledge_gate", "knowledge_gate"),
    ("EMS KNOWLEDGE ASSISTANT", "knowledge_answer", "knowledge_gate"),
    ("industrial EMS command center", "knowledge_router", "knowledge_gate"),
    ("AI SUMMARY line", "insight_summary", "ai_other"),
]
FALLBACK = ("unknown", "ai_other")


def classify(system_content):
    s = system_content or ""
    for needle, kind, stage in FINGERPRINTS:
        if needle in s:
            return kind, stage
    return FALLBACK
