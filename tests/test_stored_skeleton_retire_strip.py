"""Retire runtime strip_to_placeholders (OUTCOME 2): the stored card_payloads.payload_stripped is the single seedless
source of truth, so no request-time card re-derives it. Pure unit tests (no DB, no LLM).

Covers the three runtime seams the strip retirement touched:
  · producer/user_message read the STORED skeleton directly; a NULL payload_stripped FAILS LOUDLY (run the builder).
  · the no-default emit path folds its ONE data-leaf+clock scrub into gates.enforce_free_metadata (no strip caller).
  · the executor graft blanks its RAW-default container via blank_data_leaves (data-leaf placeholders, no seed).
strip_to_placeholders itself STAYS (the builder needs it) — these assert it has ZERO runtime callers by exercising the
replacements that stand in its place."""
from __future__ import annotations

import pytest

from grounding.default_assemble import strip_to_placeholders, blank_data_leaves
from layer2.emit.metadata.producer import produce, _metadata_default
from layer2.gates import enforce_free_metadata

_SEEDED = {"snapshot": {"activePowerAvgKw": 389.2, "unit": "kW", "source": "mock",
                        "note": "Active power loss is 43.0 kW", "ts": "13:14:10"},
           "history": [{"label": "Apr 15", "value": 68}, {"label": "16", "value": 71}],
           "statusColors": {"low": "#eee"}}


def test_producer_emit_skeleton_equals_stored_payload_stripped_not_a_restrip():
    # the emit skeleton IS the STORED payload_stripped VERBATIM (deep-copied), never a re-strip of the raw default.
    stored = strip_to_placeholders(_SEEDED)                       # what the BUILDER persists (build-time only)
    em, applied, rejected = produce(_SEEDED, {}, [], stored)
    assert applied == [] and rejected == []
    assert em == stored == _metadata_default(_SEEDED, stored)     # byte-for-byte the stored column, no re-derivation


def test_missing_stored_payload_stripped_fails_loudly():
    # a card with NO stored skeleton must FAIL LOUDLY (run scripts/build_stripped_payloads.py) — never a silent strip.
    with pytest.raises(ValueError):
        produce(_SEEDED, {}, [], None)
    with pytest.raises(ValueError):
        _metadata_default(_SEEDED, None)


def test_no_seed_survives_a_live_shaped_emit():
    # every seed leaf in the stored skeleton is a typed placeholder / scrubbed — no demo number, mock marker, or clock.
    stored = strip_to_placeholders(_SEEDED)
    em, _, _ = produce(_SEEDED, {}, [], stored)
    assert em["snapshot"]["activePowerAvgKw"] == 0.0             # demo number → typed-zero placeholder
    assert em["snapshot"]["source"] == ""                        # 'mock' provenance marker scrubbed
    assert em["snapshot"]["note"] == ""                          # fabricated-metric narrative scrubbed
    assert em["snapshot"]["ts"] == ""                            # clock label scrubbed
    assert em["snapshot"]["unit"] == "kW"                        # chrome kept byte-identical
    assert em["statusColors"] == {"low": "#eee"}                 # chrome kept byte-identical


def test_no_default_emit_scrub_folds_into_enforce_free_metadata():
    # the no-default branch (no stored skeleton) scrubs the AI's free-authored emit via enforce_free_metadata — the
    # SAME transform the builder persists, so seeds/clocks never ship even without a harvested default.
    scrubbed = enforce_free_metadata({"snapshot": {"activePowerAvgKw": 389.2, "unit": "kW", "ts": "13:14:10"}})
    assert scrubbed["snapshot"]["activePowerAvgKw"] == 0.0
    assert scrubbed["snapshot"]["ts"] == ""
    assert scrubbed["snapshot"]["unit"] == "kW"


def test_graft_blanks_data_leaves_keeps_chrome_no_seed():
    # the executor graft imports a RAW-default container SEED-FREE: scalar→0, array→[], series value zeroed, chrome kept.
    out = blank_data_leaves({"series": [{"value": 5.4, "label": "R"}], "peakKw": 412.0,
                             "ticks": [1, 2, 3], "unit": "kW"})
    assert out["series"] == [{"value": 0.0, "label": "R"}]        # per-element value zeroed, label chrome kept
    assert out["peakKw"] == 0.0                                   # scalar seed → typed-zero placeholder
    assert out["ticks"] == []                                     # numeric array → typed-empty
    assert out["unit"] == "kW"                                    # chrome kept byte-identical
