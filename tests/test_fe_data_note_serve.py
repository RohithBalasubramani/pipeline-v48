"""B1 [residual 'fe' — invisible proxy notes]: Layer 2's card-level `data_note` (the plain-words proxy/substitution
disclosure, e.g. r_44796d791a card 70's 'kWh shown as a proxy for run-hours') and its own `answerability` claim were
dropped by _enrich_card's whitelist — the note reached only the page-level notes.loop1, never the card the FE renders.
host/server.py now attaches BOTH as ADDITIVE card fields (_attach_l2_notes) and the FE renders the note beside the
gap-chip (registry.tsx GapInfo) + on the no-component placeholder (CmdCard). Non-live."""
from __future__ import annotations

import os

from host import server as S

_WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "host", "web", "src")


def _read(*rel):
    with open(os.path.join(_WEB, *rel), errors="replace") as f:
        return f.read()


# ── the serve boundary: _attach_l2_notes ────────────────────────────────────────────────────────────────────────────

def test_top_level_data_note_and_answerability_attached():
    cards = [{"card_id": 70, "render": {"verdict": "partial"}}]
    l2 = {70: {"data_note": "Showing kWh as a proxy for run-hours.", "answerability": "partial",
               "data_instructions": {}}}
    out = S._attach_l2_notes(cards, l2)
    assert out[0]["data_note"] == "Showing kWh as a proxy for run-hours."
    assert out[0]["l2_answerability"] == "partial"


def test_di_nested_note_fallback():
    # emit-variance location (r_44796d791a card 71): the model nested data_note INSIDE data_instructions
    cards = [{"card_id": 71}]
    l2 = {71: {"data_note": None, "answerability": "partial",
               "data_instructions": {"data_note": "Showing active energy as a proxy for run-hours."}}}
    out = S._attach_l2_notes(cards, l2)
    assert out[0]["data_note"] == "Showing active energy as a proxy for run-hours."


def test_top_level_note_wins_over_nested():
    cards = [{"card_id": 1}]
    l2 = {1: {"data_note": "top", "data_instructions": {"data_note": "nested"}, "answerability": "full"}}
    assert S._attach_l2_notes(cards, l2)[0]["data_note"] == "top"


def test_blank_or_nonstring_note_is_none_never_fabricated():
    cards = [{"card_id": 1}, {"card_id": 2}, {"card_id": 3}]
    l2 = {1: {"data_note": "   ", "answerability": "full"},
          2: {"data_note": {"not": "a string"}, "answerability": "none"},
          3: {}}
    out = S._attach_l2_notes(cards, l2)
    assert out[0]["data_note"] is None
    assert out[1]["data_note"] is None and out[1]["l2_answerability"] == "none"
    assert out[2]["data_note"] is None and out[2]["l2_answerability"] is None


def test_missing_l2_output_and_empty_inputs_are_safe():
    # a card with no L2 output carries None for both (honest); empty/None collections never raise
    out = S._attach_l2_notes([{"card_id": 9}], {})
    assert out[0]["data_note"] is None and out[0]["l2_answerability"] is None
    assert S._attach_l2_notes([], {1: {"data_note": "x"}}) == []
    assert S._attach_l2_notes(None, None) is None


def test_attach_is_additive_no_existing_field_moves():
    card = {"card_id": 5, "payload": {"a": 1}, "render": {"verdict": "render", "answerability": "full"}}
    before = dict(card)
    S._attach_l2_notes([card], {5: {"data_note": "n", "answerability": "partial"}})
    for k, v in before.items():
        assert card[k] == v                                    # nothing existing changed
    # l2_answerability is TELEMETRY — the derived render.answerability is untouched even when they disagree
    assert card["render"]["answerability"] == "full" and card["l2_answerability"] == "partial"


def test_build_response_wires_attach():
    import inspect
    src = inspect.getsource(S.build_response)
    assert "_attach_l2_notes(cards, l2)" in src


# ── the FE render seam (source-locked: the note must stay consumed, not just served) ────────────────────────────────

def test_registry_renders_data_note_beside_gap_chip():
    src = _read("cmd", "registry.tsx")
    assert "data_note" in src                                  # renderCmd reads the additive field
    assert "l2_answerability" in src
    # GapInfo carries the note (marker shows even with zero gap records) and withGaps threads it through every tier
    assert "note?: string | null" in src
    assert "!(note ?? \"\").trim()" in src or '!(note ?? "").trim()' in src
    assert src.count("dnote, l2ans") >= 7                      # all renderer tiers pass the note to withGaps


def test_placeholder_path_shows_data_note():
    src = _read("components", "CmdCard.tsx")
    assert "card.data_note" in src                             # no-component placeholder still discloses the proxy note


def test_types_declare_additive_fields():
    src = _read("types.ts")
    assert "data_note?: string | null" in src
    assert "l2_answerability?" in src
