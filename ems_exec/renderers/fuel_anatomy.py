"""ems_exec/renderers/fuel_anatomy.py — the FUEL-TANK-ANATOMY renderer (card 63, DG fuel-efficiency).

Renders OUTSIDE the per-card column-fill executor: card 63 mounts CMD_V2's 3D FuelTankAnatomy (its OWN three.js Canvas
— the GLB is a frontend asset), and the backend supplies ONLY the tank telemetry numbers the tank is filled from, plus
the display prose. The shape is the CARD'S OWN skeleton (not a hardcoded channel list):

    { snapshot: { …every key the card_payloads skeleton declares… },   ← telemetry numbers; null today (domain gap)
      display }                                                          ← the prose title/subtitle/channel-detail

STRUCTURE-PRESERVING [card-63 canonical fix]: the snapshot keys are ENUMERATED FROM the card's own harvested skeleton
(exact_metadata.snapshot, else _default_payload.snapshot) — NOT a hardcoded 3-tuple. The CMD_V2 FuelSnapshot carries 5
keys {fuelLevel, fuelRate, fuelTemp, autonomy, efficiency} and fuelTankDisplay.ts calls s.autonomy.toFixed(1) /
s.efficiency.toFixed(0) UNCONDITIONALLY, so dropping a skeleton key both violates structure-preservation AND would crash
the component on `.toFixed(undefined)`. Enumerating from the skeleton guarantees EVERY declared key is present (null when
unbound), so the emitted payload is always valid against the component's own contract. `display` likewise preserves its
skeleton STRUCTURE (title/subtitle/channelDetail/aiText) with every value honest-blanked to null — never dropped to {}.

DOMAIN GAP (the reality this renderer encodes): fuel level / rate / temp / autonomy / efficiency are DIESEL-GENERATOR
domain telemetry the neuract logging DB does NOT carry (no fuel columns / no run log). So every number honest-BLANKS to
null WITH a per-leaf reason on the executor's honest-gap channel (fill.GAPS_KEY). We never fabricate the numbers.

DATA = NEURACT ONLY. HONEST-DEGRADE: every telemetry number → null (+ reason); `display` → structure-preserved-nulled.
DB-DRIVEN: the fuel-column mapping is a config knob (config.schema_map.fuel_columns) so the instant neuract grows real
fuel telemetry, an editable row lights this up with ZERO code change — until then it honest-blanks. The GLB is a frontend
asset; this backend renderer never touches it. [atomic; one concern; NEVER fabricate domain telemetry; NO hardcoded
channel list, NO hardcoded card id]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from ems_exec.executor.fill import GAPS_KEY

# no class claim: this renderer is reached by SHAPE (an asset_3d card whose own skeleton carries a telemetry snapshot —
# _is_telemetry_3d in the package __init__), never by handling_class, so it registers nothing.
HANDLING_CLASSES = ()


def render(asset, card, ctx):
    """The {snapshot, display} payload for the fuel-tank-anatomy card.

    ``asset`` = 1b's resolved asset dict; ``card`` = the card def row (carries exact_metadata + _default_payload);
    ``ctx`` = {asset_table, mfm_id, db_link, window, page_key}. The snapshot keys are ENUMERATED from the card's own
    skeleton and each is filled from a CONFIGURED neuract column if one exists, else null WITH a per-leaf gap reason (the
    DG-telemetry domain gap). ``display`` preserves its skeleton structure with every value honest-blanked. NEVER
    fabricated, NEVER a dropped key."""
    ctx = ctx or {}
    card = card or {}
    asset_table = ctx.get("asset_table") or (asset or {}).get("table")

    skeleton = _skeleton(card)                                   # the card's OWN harvested shape ({snapshot, display, …})
    snap_skel = skeleton.get("snapshot") if isinstance(skeleton.get("snapshot"), dict) else {}
    channels = list(snap_skel.keys())                           # ENUMERATED from the skeleton — never a hardcoded tuple

    cols = _fuel_columns()                                       # {channel: neuract_column} — {} today (honest gap)
    present = _nx.present_columns(asset_table) if asset_table else frozenset()
    want = [cols[c] for c in channels if cols.get(c)]
    latest = _nx.latest(asset_table, want) if (asset_table and want) else {}

    snapshot, gaps = {}, []
    for ch in channels:
        col = cols.get(ch)
        val = latest.get(col) if (col and col in present) else None
        # HONEST-BLANK: no configured column, or the column isn't physically on this meter → null + a per-leaf reason.
        snapshot[ch] = val
        if val is None:
            gaps.append(_gap_for(ch, col, present, asset, asset_table))

    payload = {
        "snapshot": snapshot,                                   # every skeleton key present; null where unbound
        # display: CHROME survives verbatim (title/subtitle-class digit-free strings), harvested PROSE that embeds a
        # seed measurement (narrative keys / digit-bearing strings) honest-blanks — each blank WITH a per-leaf reason.
        "display": _display_honest(skeleton.get("display"), gaps),
    }
    if gaps:
        payload[GAPS_KEY] = gaps                                # host pops these → render.gaps (per-leaf reason channel)
    return payload


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _skeleton(card):
    """The card's OWN harvested shape — the L2 exact_metadata skeleton (preferred, it IS the card's props), else the
    raw harvested default payload, else {}. This is the ONE source the snapshot keys + display structure enumerate
    from, so this renderer never invents a channel or a display field the card doesn't declare."""
    for k in ("exact_metadata", "payload", "skeleton"):
        v = card.get(k)
        if isinstance(v, dict):
            return v
    dp = card.get("_default_payload")
    return dp if isinstance(dp, dict) else {}


def _narrative_keys():
    """The narrative-slot key vocabulary (quality_policy 'narrative_slots' row — the SAME set the build-time strip
    scrubs), lowercased. Fail-open to the strip's code default so the two never diverge."""
    try:
        from grounding.default_assemble import _narrative_slots
        return _narrative_slots()
    except Exception:
        return {"insight", "text", "summary", "note", "caption", "subtitle", "message", "headline",
                "description", "detail", "commentary", "aitext"}


def _display_honest(display, gaps, _path="display"):
    """STRUCTURE-PRESERVING honest display [card-63 chrome-restore + reasons-always, 2026-07-06]:
      · a DIGIT-FREE, non-narrative string is DESIGN CHROME ('Fuel Tank Anatomy', 'height fill') — kept VERBATIM
        (the old blanket-null shipped the card untitled);
      · a NARRATIVE-keyed string (quality_policy narrative_slots: aiText/subtitle/…) or ANY digit-bearing string
        ('Day tank at 60% … 107 L/hr' — a harvested seed measurement in prose) honest-blanks to null;
      · EVERY blank leaf (nulled here, already-'' from the strip, lists) gets a per-leaf gap record — the DG fuel
        domain gap, cause column_absent ('fuel telemetry (<key>) not measured by this meter').
    Never drops a key; None skeleton → None. Never raises beyond the caller's guard."""
    if not isinstance(display, dict):
        return None
    narrative = _narrative_keys()
    out = {}
    for k, v in display.items():
        child = f"{_path}.{k}"
        if isinstance(v, dict):
            out[k] = _display_honest(v, gaps, _path=child)
        elif isinstance(v, list):
            out[k] = []
            gaps.append(_display_gap(child, k))
        elif isinstance(v, str):
            if str(k).lower() in narrative or any(ch.isdigit() for ch in v):
                out[k] = None                                   # prose composed from unmeasured fuel telemetry
                gaps.append(_display_gap(child, k))
            elif not v.strip():
                out[k] = v                                      # already strip-blanked chrome — keep + reason
                gaps.append(_display_gap(child, k))
            else:
                out[k] = v                                      # digit-free chrome survives byte-identical
        elif v is None:
            out[k] = None
            gaps.append(_display_gap(child, k))
        else:
            out[k] = v                                          # a non-string display literal is chrome — untouched
    return out


def _display_gap(slot, key):
    metric = f"fuel telemetry ({key})"
    try:
        from config.reason_templates import reason as _reason
        sentence = _reason("column_absent", metric=metric)
    except Exception:
        sentence = "column_absent"
    return {"slot": slot, "cause": "column_absent", "metric": metric, "column": None, "fn": None, "reason": sentence}


def _gap_for(channel, col, present, asset, asset_table):
    """One per-leaf honest-gap record for a blanked fuel channel. column_absent when no neuract column is configured or
    the configured column isn't on this meter (the DG fuel domain gap). Reason = the editable cmd_catalog.reason_template
    row; never raises, never fabricates."""
    metric = col or channel
    cause = "column_absent"
    try:
        from config.reason_templates import reason as _reason
        sentence = _reason(cause, metric=metric)
    except Exception:
        sentence = cause
    return {"slot": f"snapshot.{channel}", "cause": cause, "metric": metric, "column": col, "fn": None,
            "reason": sentence}


def _fuel_columns():
    """{channel: neuract_column} for the fuel channels — the editable config.schema_map.fuel_columns() row (fail-open to
    {}). {} today because neuract carries no fuel telemetry → every channel honest-blanks; an admin row lights it up with
    zero code change once the columns exist. NEVER guesses a column name."""
    try:
        from config import schema_map as _sm
        got = _sm.fuel_columns()                                # optional accessor; absent → AttributeError → {}
        return got if isinstance(got, dict) else {}
    except Exception:
        return {}
