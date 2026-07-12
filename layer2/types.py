"""layer2/types.py — annotation-only TypedDicts for the L2 boundary [typing F2]. total=False + runtime-inert;
the swap vocabulary home is layer2/swap/vocab.py, the di._* telemetry enumeration is layer2/telemetry.py, and the
runtime contract check stays layer2/schema.validate_layer2_card_output."""
from __future__ import annotations

from typing import Any, TypedDict


class SwapDecision(TypedDict, total=False):
    action: str                   # swap.vocab.ACTIONS: 'keep' | 'swap'
    origin: str                   # swap.vocab.ORIGINS: 'kept' | 'swapped' | 'must_swap'
    swap_to_id: int | None
    swap_to_title: str | None
    confidence: float | None
    criteria: str


class DataInstructions(TypedDict, total=False):
    payload_shape: str
    orientation: str
    fields: list[dict[str, Any]]  # the declared data slots (slot/kind/column/fn/metric/unit/label/agg/…)
    window: dict[str, Any]
    consumer: dict[str, Any]      # the ems_backend endpoint binding (endpoint/screen)
    # every `_*` key is telemetry — the enumerated family lives in layer2/telemetry.DI_TELEMETRY_KEYS


class Layer2CardInput(TypedDict, total=False):
    card_id: int
    story: dict[str, Any]         # the 1a card (analytical_story/profile/recipe/handling)
    catalog_row: dict[str, Any]   # recipe/contract/controls/feasibility/default_payload
    asset: dict[str, Any]
    group_id: str | None
    is_group_card: bool


class Layer2CardOutput(TypedDict, total=False):
    card_id: int
    render_slot: str
    analytical_story: str
    swap_decision: SwapDecision
    exact_metadata: dict[str, Any]
    data_instructions: DataInstructions
    controls: Any
    answerability: str            # validate/verdicts.ANSWERABILITY
    data_note: str | None
    gap: bool
    conforms: bool
    failure: dict[str, Any] | None   # {stage, reason, detail} — the ONE failure channel when conforms=False
    contract_problems: list[str]     # a.k.a. _schema_issues (transitional dual naming, typing F10)
