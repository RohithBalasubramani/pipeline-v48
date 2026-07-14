"""tests/test_resolver_full_listing.py — T0-7 [AI-first]: the resolver.full_listing flag.

Off (default): the model sees the class_from_subject-narrowed listing — byte-identical legacy. On: the model sees
the FULL registry; the prior is kept ONLY for class_mismatch telemetry + the class-narrowed empty-fallback picker.
Offline: call_qwen captured, candidates faked, cfg/flag faked."""
from unittest.mock import patch

import layer1b.resolve.asset_resolve as AR


ROWS = [
    # [id, name, table, mfm_type_id, load_group, class, has_data, has_feeders, never_wired, table_exists, aka]
    ["1", "UPS-01", "gic_ups1", "", "GIC-01", "UPS", True, False, False, True, ""],
    ["2", "Transformer-01", "gic_tx1", "", "GIC-02", "Transformer", True, False, False, True, ""],
    ["3", "DG-1 MFM", "gic_dg1", "", "GIC-03", "DG", True, False, False, True, ""],
]


class _Recorder:
    def __init__(self, result):
        self.calls, self._result = [], result

    def __call__(self, system, user, **kw):
        self.calls.append({"system": system, "user": user, **kw})
        return self._result


def _resolve(prompt, flag_on, prior="UPS", llm_result=None):
    rec = _Recorder(llm_result or {"names": [], "confident": False, "candidates": []})
    with patch.object(AR, "class_from_subject", return_value=prior), \
         patch.object(AR, "_full_listing_on", return_value=flag_on), \
         patch.object(AR, "_pcc_alias_index", return_value={}), \
         patch.object(AR, "call_qwen", rec):
        out = AR.resolve_asset(prompt, cands=ROWS)
    return out, rec


def test_flag_off_listing_is_class_narrowed():
    _out, rec = _resolve("battery status", flag_on=False)
    user = rec.calls[0]["user"]
    assert "UPS-01" in user and "Transformer-01" not in user and "DG-1 MFM" not in user


def test_flag_on_listing_is_full_registry():
    _out, rec = _resolve("battery status", flag_on=True)
    user = rec.calls[0]["user"]
    assert "UPS-01" in user and "Transformer-01" in user and "DG-1 MFM" in user


def test_flag_on_keeps_class_prior_telemetry():
    out, _rec = _resolve("battery status", flag_on=True)
    assert out["class_prior"] == "UPS"                     # prior survives for class_mismatch telemetry


def test_flag_on_empty_fallback_stays_class_narrowed():
    # the model was never heard (llm_failed) with a prior set → empty_fallback receives the NARROWED rows
    seen = {}

    def fake_fallback(prompt, rows=None):
        seen["rows"] = rows
        return {"asset": None, "how": "ambiguous", "candidates": [], "candidate_list": rows or []}

    rec = _Recorder({"_llm_failed_marker": True})
    with patch.object(AR, "class_from_subject", return_value="UPS"), \
         patch.object(AR, "_full_listing_on", return_value=True), \
         patch.object(AR, "_pcc_alias_index", return_value={}), \
         patch.object(AR, "empty_fallback", fake_fallback), \
         patch.object(AR, "retry_transient_result", lambda call: ({}, True)), \
         patch.object(AR, "call_qwen", rec):
        AR.resolve_asset("battery status", cands=ROWS)
    assert [r[1] for r in (seen["rows"] or [])] == ["UPS-01"]   # narrowed, never the widened listing
