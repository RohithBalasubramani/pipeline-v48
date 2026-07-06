"""F3 [per-leaf reason] — the whole-asset 'No data logged for this asset' reason may fire ONLY when the meter is
genuinely dark. When a meter HAS logged columns but a card's declared energy-counter metrics are dead, the blank is
PER-METRIC — name the metrics, never blame the asset. Non-live (neuract stubbed)."""
from __future__ import annotations

import ems_exec.data.neuract as nx
from host import server as S


class _StubMeter:
    def __init__(self, has_data):
        self.has_data = has_data

    def __enter__(self):
        self._pc, self._cl = nx.present_columns, nx.column_logged
        nx.present_columns = lambda t: frozenset({"active_power_total_kw", "energy_kwh"})
        nx.column_logged = lambda t, c: self.has_data and c == "active_power_total_kw"
        return self

    def __exit__(self, *a):
        nx.present_columns, nx.column_logged = self._pc, self._cl


def _card():
    return {"card_id": 1, "title": "Energy", "analytical_story": "s", "role_in_story": "r", "slot": "a", "size": "m"}


def _l2_all_blank():
    # Layer 2 declared two energy-counter metrics; the completed payload blanked BOTH (dead counters), power lives
    # elsewhere on the meter. n_real == 0 for THIS card.
    di = {"asset_name": "DG 2", "fields": [
        {"slot": "data.readings.activeEnergy.value", "label": "Active Energy", "column": "energy_kwh"},
        {"slot": "data.readings.reactiveEnergy.value", "label": "Reactive Energy", "column": "reactive_kvarh"}]}
    payload = {"data": {"readings": {
        "activeEnergy": {"value": "—", "unit": "kWh"},
        "reactiveEnergy": {"value": "—", "unit": "kVARh"}}}}
    return {"data_instructions": di, "payload": payload, "conforms": True}, payload


def test_live_meter_dead_counters_gets_per_metric_reason_not_whole_asset():
    l2, payload = _l2_all_blank()
    with _StubMeter(has_data=True):
        card = S._enrich_card(_card(), "energy-power", {}, l2, completed=payload, asset_table="dg_2_mfm")
    reason = (card["render"] or {}).get("reason") or ""
    assert card["render"]["verdict"] == "honest_blank"
    # NEVER the whole-asset claim when the meter has data
    assert "No data logged for" not in reason
    # names the dead metrics instead
    assert "Active Energy" in reason and "not logged" in reason.lower()


def test_truly_dark_meter_still_gets_whole_asset_reason():
    l2, payload = _l2_all_blank()
    with _StubMeter(has_data=False):
        card = S._enrich_card(_card(), "energy-power", {}, l2, completed=payload, asset_table="dg_2_mfm")
    reason = (card["render"] or {}).get("reason") or ""
    # a genuinely dark meter MAY carry the whole-asset reason (honest)
    assert "No data logged for" in reason or "not logged" in reason.lower()
