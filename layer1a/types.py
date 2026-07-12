"""layer1a/types.py — annotation-only TypedDicts for the 1a boundary [typing F2]. total=False + runtime-inert:
no validation, no behavior; the shapes document what build_layer1a_output/route actually emit so consumers stop
re-guessing dict keys defensively. Contract checks stay in layer1a/schema.validate_layer1a_output."""
from __future__ import annotations

from typing import Any, TypedDict


class RouteResult(TypedDict, total=False):
    page_key: str
    metric: str
    intent: str
    window: str | None            # prompt-derived preset key ('last-7-days') or None
    page_spec: dict[str, Any]     # the routed page_specs row
    routing: dict[str, Any]       # deterministic route telemetry (page_key_how, dropped_templates, …)


class Card1a(TypedDict, total=False):
    card_id: int
    title: str
    analytical_story: str
    role_in_story: str
    slot: str
    size: str
    profile: dict[str, Any]       # what the card IS / answers (swap reasoning)
    recipe: dict[str, Any]        # the DATA spec Layer 2 builds data_instructions from
    handling: dict[str, Any]      # how it is produced/rendered (data_fill_shape signal)


class Layer1aOutput(TypedDict, total=False):
    page_key: str
    page_title: str
    shell: str
    module: str | None
    metric: str
    intent: str
    window: str | None
    story: str
    routing: dict[str, Any]
    layout: dict[str, Any]
    cards: list[Card1a]
    groups: list[dict[str, Any]]
    contract_problems: list[str]  # non-gating validate_layer1a_output telemetry [typing F10]
