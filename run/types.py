"""run/types.py — the harness PipelineResult contract [typing F2]: the `out` dict run_pipeline builds IS the
orchestrator state every consumer (host/server, sweeps, tests) reads. total=False + runtime-inert."""
from __future__ import annotations

from typing import Any, TypedDict


class PipelineResult(TypedDict, total=False):
    prompt: str
    run_id: str
    asset_id: int | None
    layer1a: dict[str, Any] | None    # Layer1aOutput
    layer1b: dict[str, Any] | None    # Layer1bOutput
    validation: dict[str, Any] | None  # ValidationReport
    layer2: dict[str, Any] | None      # {render_id: Layer2CardOutput}
    window: str | None                 # the prompt-derived preset forwarded to the host date default
    asset_no_data: bool
    asset_pending: bool
    validation_blocked: bool
    data_unavailable: bool
    degrade: dict[str, Any] | None
    notes: list[str]
    errors: dict[str, Any]
