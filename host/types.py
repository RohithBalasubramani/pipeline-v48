"""host/types.py — the FE card boundary shape (the TS PipelineResult.cards[] element mirrors this) [typing F2].
total=False + runtime-inert; host/web/src/types.ts is the TS twin — keep the two in sync by hand (they cross a JSON
boundary, so there is no import relationship to enforce it)."""
from __future__ import annotations

from typing import Any, TypedDict


class FECard(TypedDict, total=False):
    card_id: int
    render_card_id: int           # follows swap_to_id on an accepted swap (the payload is the target's shape)
    title: str
    payload: dict[str, Any] | None    # the COMPLETED CMD_V2 payload (None = executor skipped, FE shows not-rendered)
    render: dict[str, Any]            # {verdict, n_real, n_data, reason?, gaps?} — telemetry, never a render gate
    data_note: str | None
    endpoint: str | None
    answerability: str
    swap: dict[str, Any] | None
    controls: Any
