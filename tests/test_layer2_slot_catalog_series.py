"""★ slot_catalog series-of-objects expansion — the chrome-loss root-cause fix (sweep 15 / card 76).

A card whose data series is a list-of-OBJECTS with DOMAIN-specific numeric point keys (timeline.points →
{hotspotC, oilC, loadPct, windingC, efficiencyPct, slot}) must expand to PER-ELEMENT scalar leaves
(points[i].hotspotC …) so the AI binds each sub-field and the executor fills a per-key scalar — NEVER a lone
`timeline.points` container slot the AI clobbers with a flat list (which loses every default point dict = 8 lost
chrome keys, the C3 FAIL). PURE-CHROME object series (chart.series/{width,dash,warn,decimals}) must instead STAY a
single collapsed container (no fillable leaf) so we never try to bind a measured column to a style token.

Data-shape + DB-driven: the fillable numeric keys come from vocab.element_value_keys (preferred) else EVERY numeric
element key minus vocab.element_chrome_keys — no per-card code, no per-key allowlist edit. Non-live: reads the real
card_payloads defaults from cmd_catalog (no LLM, no :5433).
"""
import json

import pytest

from data.db_client import q
from layer2.emit.slot_catalog import build_slot_catalog


def _payload(story_id):
    rows = q("cmd_catalog", f"SELECT payload FROM card_payloads WHERE story_id = $a${story_id}$a$ LIMIT 1")
    if not rows:
        pytest.skip(f"card_payloads has no story {story_id!r}")
    p = rows[0][0]
    return json.loads(p) if isinstance(p, str) else p


def _slots(story_id, prefix):
    cat = build_slot_catalog(_payload(story_id), None)
    return [e["slot"] for e in cat if e["slot"].startswith(prefix)]


def test_domain_object_series_expands_per_element():
    """timeline.points (transformer thermal-life) expands to per-element numeric leaves; the lone container is GONE."""
    slots = _slots("assets-transformer-thermal-life-cards--thermal-timeline", "timeline.points")
    assert "timeline.points" not in slots, "the whole series container must NOT be a fillable slot (clobber risk)"
    assert any(s.startswith("timeline.points[*].") for s in slots), "must expand to per-element leaves"
    # each real thermal quantity got its OWN fillable leaf (so a per-leaf honest-blank keeps the point-dict shape)
    for key in ("hotspotC", "oilC", "loadPct", "windingC", "efficiencyPct"):
        assert f"timeline.points[*].{key}" in slots, f"missing per-element leaf for {key}"


def test_pure_chrome_object_series_stays_collapsed():
    """chart.series/{width,dash,warn,decimals,trip} is design chrome — it must NOT expand into fillable data leaves."""
    slots = _slots("assets-diesel-generator-engine-cooling-cards--thermal-timeline", "chart.series")
    # the container may appear as a single non-expanded series entry, but NEVER a per-element style-token leaf
    assert not any(s.startswith("chart.series[") for s in slots), \
        f"chrome style tokens must not expand into fillable leaves: {slots}"


def test_regulation_points_expands():
    """A second domain series (transformer tap RTCC voltage-regulation) also expands per measured key."""
    slots = _slots("assets-transformer-tap-rtcc-cards--voltage-regulation", "regulation.points")
    assert "regulation.points" not in slots
    assert any(s.endswith("].voltageKv") for s in slots)
    assert any(s.endswith("].tap") for s in slots)
