"""fuel_anatomy (card 63 CANONICAL fix) — pure unit tests (no DB row required, no LLM, no host).

Asserts the two defects the FIXER swept are gone GENERICALLY:
  1. STRUCTURE-PRESERVATION: the emitted snapshot carries EVERY key the card's own skeleton declares (the 5-key
     FuelSnapshot {fuelLevel,fuelRate,fuelTemp,autonomy,efficiency}), null where unbound — autonomy + efficiency are
     NEVER dropped (the old _CHANNELS 3-tuple hardcode); `display` preserves its structure honest-blanked, not None/{}.
  2. NO HARDCODED CARD ID / CHANNEL LIST: the dispatch routes to fuel_anatomy by the SHAPE of the card's skeleton (a
     top-level `snapshot` object), and the renderer enumerates channels from that skeleton — a DIFFERENT snapshot shape
     (extra/fewer keys) is honored verbatim, proving no card-63 / no 3-tuple assumption survives.
  3. PER-LEAF REASONS: every nulled channel carries an honest-gap record (slot/cause/reason), never a silent null.
  4. NEVER FABRICATES: with no neuract table (or no configured fuel columns) every telemetry number honest-blanks to
     null — never a seed 60% / 107 L·hr."""
from __future__ import annotations

from ems_exec.renderers import _resolve, fuel_anatomy
from ems_exec.executor.fill import GAPS_KEY

# the real card-63 skeleton (FuelSnapshot 5 keys + the display prose), values stripped like payload_stripped
_SKELETON = {
    "snapshot": {"autonomy": 0.0, "fuelRate": 0.0, "fuelTemp": 0.0, "fuelLevel": 0.0, "efficiency": 0.0},
    "display": {"title": "Fuel Tank Anatomy", "aiText": "x", "subtitle": "",
                "channelDetail": {"flow": "a", "level": "b", "temperature": "c"}},
}


def _card(skeleton, cid=63):
    return {"card_id": cid, "render_card_id": cid, "card_handling": "asset_3d",
            "exact_metadata": skeleton, "_default_payload": skeleton}


def test_dispatch_routes_telemetry_3d_to_fuel_anatomy_by_shape_not_id():
    # a snapshot-carrying asset_3d card → fuel_anatomy (NOT the GLB asset_3d resolver), by shape not card id
    assert _resolve("asset_3d", _card(_SKELETON)).__name__.endswith("fuel_anatomy")
    # the SAME shape under a DIFFERENT card id still routes to fuel_anatomy (no hardcoded id)
    assert _resolve("asset_3d", _card(_SKELETON, cid=999)).__name__.endswith("fuel_anatomy")


def test_dispatch_glb_asset3d_still_routes_to_asset3d():
    # a GLB card carries no harvested snapshot skeleton → the generic GLB resolver, unchanged
    glb = {"card_id": 60, "card_handling": "asset_3d", "exact_metadata": None, "_default_payload": None}
    assert _resolve("asset_3d", glb).__name__.endswith("asset_3d")


def test_structure_preserving_snapshot_all_keys_present_null_when_unbound():
    out = fuel_anatomy.render({"name": "DG-1", "table": None}, _card(_SKELETON), {"asset_table": None})
    # EVERY skeleton key present — autonomy + efficiency NOT dropped (the old 3-tuple bug)
    assert set(out["snapshot"].keys()) == set(_SKELETON["snapshot"].keys())
    assert set(out["snapshot"].keys()) >= {"autonomy", "efficiency"}
    # honest-blank: every telemetry number null (no fabricated seed), never a dropped key
    assert all(v is None for v in out["snapshot"].values())


def test_display_structure_preserved_chrome_kept_prose_blanked_with_reasons():
    """RESIDUAL-2 card-63 contract [2026-07-06]: display CHROME survives verbatim (digit-free, non-narrative strings
    like the title — the old blanket-null shipped the card UNTITLED), while narrative-keyed prose (aiText/subtitle)
    and digit-bearing strings (seed measurements in text) honest-blank — and EVERY blank display leaf carries a
    per-leaf gap reason."""
    out = fuel_anatomy.render({"name": "DG-1", "table": None}, _card(_SKELETON), {"asset_table": None})
    d = out["display"]
    assert isinstance(d, dict) and set(d.keys()) == set(_SKELETON["display"].keys())
    assert d["title"] == "Fuel Tank Anatomy"                       # digit-free chrome KEPT (never an untitled card)
    assert d["aiText"] is None and d["subtitle"] is None           # narrative prose honest-blanked
    assert isinstance(d["channelDetail"], dict)                    # nested structure preserved
    assert set(d["channelDetail"].keys()) == {"flow", "level", "temperature"}
    assert d["channelDetail"] == {"flow": "a", "level": "b", "temperature": "c"}   # digit-free chrome survives
    gaps = out.get(GAPS_KEY) or []
    slots = {g["slot"] for g in gaps}
    assert {"display.aiText", "display.subtitle"} <= slots         # every blanked display leaf is REASONED
    assert all(g.get("reason") for g in gaps)


def test_display_digit_bearing_prose_blanks_with_reason():
    """A display string embedding a NUMBER ('5.6 hr autonomy' — a harvested seed measurement in prose) honest-blanks
    with a per-leaf reason even under a non-narrative key; its digit-free siblings survive."""
    skel = {"snapshot": {"fuelLevel": 0.0},
            "display": {"title": "Fuel Tank Anatomy",
                        "channelDetail": {"flow": "5.6 hr autonomy", "level": "height fill"}}}
    out = fuel_anatomy.render({"name": "DG-1", "table": None}, _card(skel), {"asset_table": None})
    d = out["display"]
    assert d["channelDetail"]["flow"] is None                      # seed measurement prose blanked
    assert d["channelDetail"]["level"] == "height fill"            # digit-free chrome kept
    slots = {g["slot"] for g in (out.get(GAPS_KEY) or [])}
    assert "display.channelDetail.flow" in slots


def test_every_null_channel_carries_a_per_leaf_reason():
    out = fuel_anatomy.render({"name": "DG-1", "table": None}, _card(_SKELETON), {"asset_table": None})
    gaps = out.get(GAPS_KEY) or []
    slots = {g["slot"] for g in gaps}
    for k in _SKELETON["snapshot"]:
        assert f"snapshot.{k}" in slots, f"channel {k} nulled without a per-leaf reason"
    assert all(g.get("reason") for g in gaps)                      # never a silent null


def test_enumerates_channels_from_skeleton_not_a_hardcoded_tuple():
    # a card whose snapshot declares a DIFFERENT key set → the renderer honors it verbatim (no 3-tuple assumption)
    custom = {"snapshot": {"levelPct": 0.0, "reserveHours": 0.0}, "display": {"title": "x"}}
    out = fuel_anatomy.render({"name": "X", "table": None}, _card(custom), {"asset_table": None})
    assert set(out["snapshot"].keys()) == {"levelPct", "reserveHours"}
    assert all(v is None for v in out["snapshot"].values())
