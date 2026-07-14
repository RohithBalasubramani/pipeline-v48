"""tests/test_layer1b_alias_rescue.py — T2.3 [alias reshape]: the digit-boundary alias match (T2.3-1) and the
flag-gated dictionary re-ask (T2.3-2). Previously UNCOVERED (characterization added here first).

T2.3-1: alias_in enforces a digit boundary so 'pcc1' no longer matches inside 'pcc10' — byte-identical on the live
alias set (panels 1-4). T2.3-2: on an all-panel-ambiguous outcome whose spelled aliases uniquely name ONE panel,
flag on re-asks the model with the dictionary fact and lets IT own the pin (how='alias-fact-ai'); a non-confirming
re-answer falls to the deterministic pin (how='alias-dictionary')."""
from unittest.mock import patch

import layer1b.resolve.panel_sections as PS
import layer1b.resolve.asset_resolve as AR


# ── T2.3-1: alias_in digit boundary ─────────────────────────────────────────────────────────────────────────────────

def test_alias_in_letter_terminated_still_matches():
    assert PS.alias_in("comparepcc1aand1b", "pcc1a") is True       # ends in 'a', next char 'a' → matches
    assert PS.alias_in("voltageforpcc1b", "pcc1b") is True


def test_alias_in_digit_run_boundary_blocks_collision():
    assert PS.alias_in("sectionsofpcc10", "pcc1") is False         # 'pcc1' inside 'pcc10' → digit run, blocked
    assert PS.alias_in("pcc1andmore", "pcc1") is True              # 'pcc1' then 'a' (non-digit) → matches


def test_alias_in_empty():
    assert PS.alias_in("", "pcc1") is False and PS.alias_in("pcc1", "") is False


# ── T2.3-2: the dictionary re-ask ───────────────────────────────────────────────────────────────────────────────────

# candidate rows: [id, name, table, mfm_type_id, load_group, class, has_data, has_feeders, never_wired, table_exists, aka]
CANDS = [["317", "PCC-Panel-1", "pcc_panel_1_feedbacks", "", "", "Panel", True, True, False, True, ""],
         ["318", "PCC-Panel-2", "pcc_panel_2_feedbacks", "", "", "Panel", True, True, False, True, ""]]
SEC_IDX = {"pcc1a": ("PCC-Panel-1", "A"), "pcc1b": ("PCC-Panel-1", "B")}


def _ambiguous_reply():
    # the observed flip-flop: the model goes ambiguous between the two panels
    return {"names": [], "confident": False, "candidates": ["PCC-Panel-1", "PCC-Panel-2"]}


def _run(prompt, reprompt_on, reask_reply=None):
    calls = {"n": 0}

    def fake_qwen(system, user, **kw):
        calls["n"] += 1
        return _ambiguous_reply() if calls["n"] == 1 else (reask_reply or {})

    flags = {"resolver.alias_reprompt": reprompt_on}
    with patch.object(AR, "call_qwen", fake_qwen), \
         patch.object(AR, "_pcc_alias_index", return_value={}), \
         patch.object(AR, "class_from_subject", return_value=None), \
         patch.object(PS, "pcc_section_index", lambda: dict(SEC_IDX)), \
         patch.object(AR, "_pcc_section_index", lambda: dict(SEC_IDX)), \
         patch("config.app_config.flag_on", lambda k: flags.get(k, False)):
        out = AR.resolve_asset(prompt, cands=CANDS)
    return out, calls["n"]


def test_flag_off_deterministic_pin_one_call():
    out, n = _run("compare pcc 1a and pcc 1b", reprompt_on=False)
    assert out["how"] == "alias-dictionary" and out["asset"]["name"] == "PCC-Panel-1"
    assert n == 1                                                  # no re-ask


def test_flag_on_reask_confirms_panel():
    out, n = _run("compare pcc 1a and pcc 1b", reprompt_on=True,
                  reask_reply={"names": ["PCC-Panel-1"], "confident": True})
    assert out["how"] == "alias-fact-ai" and out["asset"]["name"] == "PCC-Panel-1"
    assert out.get("alias_reprompt") == "confirmed" and n == 2     # one re-ask


def test_flag_on_reask_wrong_panel_falls_back():
    out, n = _run("compare pcc 1a and pcc 1b", reprompt_on=True,
                  reask_reply={"names": ["PCC-Panel-2"], "confident": True})  # model re-answers the WRONG panel
    assert out["how"] == "alias-dictionary" and out["asset"]["name"] == "PCC-Panel-1"
    assert out.get("alias_reprompt") == "fallback" and n == 2
