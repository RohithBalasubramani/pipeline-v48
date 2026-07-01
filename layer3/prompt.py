"""layer3/prompt.py — the L3 prompt (system + user) built from the fact-sheet. NAMES + BOOLEANS + REASON ONLY.

The contract: L3 owns EXACTLY four semantic calls — final feasibility VERDICT, SUBSTITUTE choice among PRE-verified
grounded alternatives, human REASON/COVERAGE sentences, and DATE_CONTROL enable/disable. Nothing else. The AI never
emits a rendered number; it only NAMES a real column/fn/reason (deterministic POST fetches + verifies).

The list of valid machine reason CAUSE keys is read from config/reason_templates (cmd_catalog.reason_template) — NOT
hardcoded — so the reason vocabulary is an editable table and the AI is told the exact keys it may use. [contract L3]
"""
import json

from config import reason_templates as _reasons


SYSTEM = """You are Layer 3 of a render-guarantee pipeline: the FINAL feasibility VERDICT for ONE dashboard card.

You are given a self-contained FACT-SHEET of NAMES and BOOLEANS only. It contains NO rendered numbers — every data
value has been stripped to the placeholder "<value>". Deterministic code has already probed the live database and
pre-verified which columns/fns/assets are PRESENT. Your job is to decide, for this ONE card:

  1. render_verdict  — can the card render with REAL data?  one of: render | partial | honest_blank
       render        = every open slot binds to a present column OR a grounded substitute.
       partial       = some slots render real, others honest-blank (mixed) — the card still shows real content.
       honest_blank  = no open slot can render real data → show an honest empty card with a reason.
  2. slot_decisions  — for EACH open slot, one decision:
       bind       — use the slot's pre-verified present column  (set bind_column to a name FROM the sheet)
       substitute — use one of the slot's grounded ALTERNATIVES (set substitute_fn OR substitute_column to a name
                    that appears in that slot's `alternatives` list — NEVER invent a name)
       blank      — no present column and no grounded alternative → set blank_reason to a CAUSE KEY (see list)
  3. reason         — ONE short human sentence for the card's overall state (why blank / why partial / all good).
  4. coverage_note  — for an AGGREGATE card, a short human note like "N of M feeders reporting"; else null.
  5. answerability  — full | partial | none  (mirror the render_verdict granularity).
  6. date_control   — enabled | disabled. Enable ONLY if endpoint.date_navigable is true AND endpoint.is_history is
                      true. If the domain has no history variant, DISABLE it (a live-snapshot date control is a no-op).
  7. suppress_default_leaves — a list of payload leaf PATHS (from default_leaf_paths) that carry fabricated/seed
                      values and MUST be force-blanked because no live data backs them (e.g. a slot you set to blank).

HARD RULES — you will be rejected and re-run if you break any:
  - Output STRICT JSON only. No prose outside the JSON.
  - NEVER output a number, a metric reading, a rendered value, or the "<value>" placeholder as a decision.
  - bind_column MUST be a column NAME that appears in the slot's facts (requested_column or pre_bound_column).
  - substitute_fn / substitute_column MUST be a NAME from that slot's `alternatives` list. If a slot has no
    alternatives and no present column, you MUST choose `blank`.
  - blank_reason and reason cause-refs MUST be one of the allowed CAUSE KEYS listed below.
  - Do NOT bind a slot the sheet marks present=false. Do NOT invent slots, columns, fns, or assets.
  - If schema.meaningful is false, the card cannot render live data → verdict honest_blank with the meaningful_reason.
"""


def _cause_keys():
    """The editable machine-cause vocabulary (cmd_catalog.reason_template) — the ONLY blank_reason keys L3 may emit."""
    return sorted(_reasons.all_templates().keys())


def build_user(factsheet):
    """The user message: the fact-sheet (names/flags/placeholders only) + the exact JSON output contract."""
    keys = _cause_keys()
    out_contract = {
        "render_verdict": "render|partial|honest_blank",
        "reason": "<one short human sentence>",
        "coverage_note": "<short note or null>",
        "answerability": "full|partial|none",
        "date_control": "enabled|disabled",
        "slot_decisions": [
            {
                "slot": "<slot name from open_slots>",
                "decision": "bind|substitute|blank",
                "bind_column": "<present column name, or null>",
                "substitute_fn": "<fn name from alternatives, or null>",
                "substitute_column": "<column name from alternatives, or null>",
                "blank_reason": "<one cause key, or null>",
                "fidelity_note": "<short note or null>",
            }
        ],
        "suppress_default_leaves": ["<payload leaf path from default_leaf_paths>"],
    }
    lines = [
        "FACT-SHEET (names + booleans only; every value is '<value>'):",
        json.dumps(factsheet, indent=1, default=str),
        "",
        "ALLOWED CAUSE KEYS (for blank_reason and reason references) — use ONLY these:",
        ", ".join(keys),
        "",
        "Return EXACTLY this JSON shape (fill every open slot in slot_decisions):",
        json.dumps(out_contract, indent=1),
    ]
    return "\n".join(lines)
