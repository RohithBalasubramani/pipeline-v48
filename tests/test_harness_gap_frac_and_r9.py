"""tests/test_harness_gap_frac_and_r9.py — T1-6 (reflect gap-fraction weighting) + T1-7 (R9 data_unavailable terminal).

T1-6: _gap_frac is count-mode by default (byte-identical) and area-weighted under reflect.gap_weight='area' so one
huge failed card can cross the reflect floor a 1-of-N count never would.
T1-7 (R9): a CONFIDENTLY resolved asset whose basket validation fails WHOLESALE (n_columns>0, n_pass=0) routes to
the honest data_unavailable terminal instead of the dead-end picker; an ambiguous/no_data outcome is unaffected."""
from unittest.mock import patch

import run.harness as H


# ── T1-6: _gap_frac ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_gap_frac_count_mode_default():
    l2 = {1: object(), 2: object(), 3: object()}
    trigger = [l2[1]]
    with patch.object(H, "cfg", lambda k, d=None: d):                # default 'count'
        assert H._gap_frac(trigger, l2) == 1 / 3


def test_gap_frac_area_mode_weights_by_grid():
    a, b, c = object(), object(), object()
    l2 = {1: a, 2: b, 3: c}
    sizes = {1: {"width_px": 1200, "height_px": 800},                # huge card (960k)
             2: {"width_px": 100, "height_px": 100},                 # tiny
             3: {"width_px": 100, "height_px": 100}}
    with patch.object(H, "cfg", lambda k, d=None: "area" if k == "reflect.gap_weight" else d), \
         patch("layer2.catalog.card_grid_size.read", lambda cid: sizes.get(cid)):
        frac = H._gap_frac([a], l2)                                  # the HUGE card failed
    # count-mode would be 1/3=0.33 (below the 0.34 floor); area-mode is ~0.98 (crosses it)
    assert frac > 0.9


def test_gap_frac_area_missing_size_weight_one():
    a, b = object(), object()
    l2 = {1: a, 2: b}
    with patch.object(H, "cfg", lambda k, d=None: "area" if k == "reflect.gap_weight" else d), \
         patch("layer2.catalog.card_grid_size.read", lambda cid: None):   # no size → weight 1 → back to count
        assert H._gap_frac([a], l2) == 0.5


# ── T1-7: R9 data_unavailable terminal ──────────────────────────────────────────────────────────────────────────────

def _drive(how, n_columns, n_pass, monkeypatch):
    """Run the harness with mocked 1a/1b/validate; return the out dict."""
    l1a = {"page_key": "p/x", "page_title": "X", "layout": {}, "cards": [{"card_id": 1}], "routing": {}}
    asset = {"mfm_id": 11, "name": "GIC-01-N3-UPS-01"} if how not in ("ambiguous", "empty") else None
    l1b = {"asset": asset, "how": how, "candidate_list": [] if asset else [{"mfm_id": 12}], "column_basket": {}}
    calls = {"l2": 0}
    monkeypatch.setattr(H, "run_1a", lambda prompt, db, **kw: l1a)
    monkeypatch.setattr(H, "run_1b", lambda prompt, asset_id=None: l1b)
    def fake_validate(out, db, rid):
        out["validation"] = {"verdict": "warn", "data": {"summary": {"n_columns": n_columns, "n_pass": n_pass}}}
    monkeypatch.setattr(H, "_validate", fake_validate)
    monkeypatch.setattr("run.reconcile_granularity.apply", lambda *a, **k: None)   # local import inside the harness
    monkeypatch.setattr(H, "_preflight_reroute", lambda *a, **k: None)
    monkeypatch.setattr(H, "run_2_all", lambda rid, a, b: calls.__setitem__("l2", calls["l2"] + 1) or {})
    out = H.run_pipeline("real time monitoring for GIC-01-N3-UPS-01")
    return out, calls


def test_r9_confident_resolve_wholesale_block_is_data_unavailable(monkeypatch):
    out, calls = _drive("AI", n_columns=3, n_pass=0, monkeypatch=monkeypatch)
    assert out.get("data_unavailable") is True
    assert out.get("asset_pending") is False
    assert (out.get("degrade") or {}).get("reason")                 # machine-readable reason present
    assert calls["l2"] == 0                                          # Layer 2 not run


def test_r9_ambiguous_still_goes_to_picker(monkeypatch):
    # an ambiguous outcome has no pinned asset/basket → not wholesale-blocked; R9 (asset_resolved only) never fires,
    # the genuine "which asset?" picker opens.
    out, calls = _drive("ambiguous", n_columns=0, n_pass=0, monkeypatch=monkeypatch)
    assert not out.get("data_unavailable")
    assert out.get("asset_pending") is True                         # the picker lane, unchanged
    assert calls["l2"] == 0


def test_r9_partial_validation_still_renders(monkeypatch):
    # n_pass>0 (some columns usable) is NOT wholesale-blocked → Layer 2 runs, no terminal
    out, calls = _drive("AI", n_columns=3, n_pass=2, monkeypatch=monkeypatch)
    assert not out.get("data_unavailable")
    assert calls["l2"] == 1
