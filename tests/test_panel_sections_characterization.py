"""tests/test_panel_sections_characterization.py — pins TODAY'S behavior of the deterministic bus-section
detectors (layer1b/resolve/asset_resolve.py panel_section / compare_sections) BEFORE the Tier-0 AI-first refactor
(deterministic_audit_20260714 L1B-1 / T0-9).

Two kinds of pins:
  · the CORRECT behavior the refactor must preserve (exact alias spellings resolve; non-section prompts stay None);
  · the KNOWN DEFECTS (elided spellings — 'compare pcc 1a and 1b' drops the second alias because _norm collapses
    the prompt to 'comparepcc1aand1b' which contains 'pcc1a' but NOT 'pcc1b') pinned as xfail(strict=True): the
    T0-9 AI section emission flips these to pass; strict=True makes that flip loud.

Offline: pcc_section_index is monkeypatched to the real live shape (normalized-alias keys) — no DB, no LLM.
[T0-8] the detectors moved to layer1b/resolve/panel_sections.py (asset_resolve re-exports them byte-compatibly);
this file patches + calls the new home."""
import pytest

import layer1b.resolve.panel_sections as AR


IDX = {
    # _norm() output keys, exactly what _pcc_section_index builds from cmd_catalog.pcc_panel_alias
    "pcc1a": ("PCC-Panel-1", "A"), "pcc1b": ("PCC-Panel-1", "B"),
    "panel1a": ("PCC-Panel-1", "A"), "panel1b": ("PCC-Panel-1", "B"),
    "pcc2a": ("PCC-Panel-2", "A"), "pcc2b": ("PCC-Panel-2", "B"),
    "panel2a": ("PCC-Panel-2", "A"), "panel2b": ("PCC-Panel-2", "B"),
}


@pytest.fixture(autouse=True)
def _pin_index(monkeypatch):
    monkeypatch.setattr(AR, "pcc_section_index", lambda: dict(IDX))


# ── panel_section: the single-section stamp ─────────────────────────────────────────────────────────────────────────

def test_single_section_alias_resolves():
    assert AR.panel_section("voltage for pcc-1b", "PCC-Panel-1") == "B"
    assert AR.panel_section("show pcc 1a current", "PCC-Panel-1") == "A"


def test_wrong_panel_name_is_none():
    assert AR.panel_section("voltage for pcc-1b", "PCC-Panel-2") is None


def test_unsectioned_mention_is_none():
    assert AR.panel_section("voltage for pcc panel 1", "PCC-Panel-1") is None


def test_both_sections_named_is_none_single():
    # both sections spelled out FULLY → the single-section stamp abstains (the compare path owns it)
    assert AR.panel_section("compare pcc-1a and pcc-1b", "PCC-Panel-1") is None


def test_empty_inputs_are_none():
    assert AR.panel_section("", "PCC-Panel-1") is None
    assert AR.panel_section("voltage for pcc-1b", None) is None


# ── compare_sections: the two-section compare fact ──────────────────────────────────────────────────────────────────

def test_full_spellings_compare_detected():
    assert AR.compare_sections("compare pcc-1a and pcc-1b", "PCC-Panel-1") == ["A", "B"]
    assert AR.compare_sections("compare pcc 1a and pcc 1b", "PCC-Panel-1") == ["A", "B"]


def test_single_alias_is_not_a_compare():
    assert AR.compare_sections("voltage for pcc-1b", "PCC-Panel-1") is None


def test_other_panels_aliases_dont_count():
    # 1a of panel 1 + 2b of panel 2 is NOT a section compare of panel 1
    assert AR.compare_sections("compare pcc-1a and pcc-2b", "PCC-Panel-1") is None


# ── KNOWN DEFECTS (the T0-9 AI section emission must flip these) ─────────────────────────────────────────────────────

@pytest.mark.xfail(strict=True, reason="elided second alias: 'comparepcc1aand1b' contains pcc1a but not pcc1b — "
                                       "the substring detector misses the compare (fixed by resolver.section_ai)")
def test_DEFECT_elided_compare_pcc_1a_and_1b():
    assert AR.compare_sections("compare pcc 1a and 1b", "PCC-Panel-1") == ["A", "B"]


@pytest.mark.xfail(strict=True, reason="spaced-out elided spelling 'pcc 1 a and 1 b' normalizes to pcc1aand1b — "
                                       "same miss (fixed by resolver.section_ai)")
def test_DEFECT_elided_spaced_compare():
    assert AR.compare_sections("compare pcc 1 a and 1 b", "PCC-Panel-1") == ["A", "B"]


def test_DEFECT_elided_compare_stamps_wrong_single_slice():
    # TODAY the elided compare falls through to panel_section which sees ONLY section A — the silent wrong-slice
    # the audit flagged. Pinned as-is (this documented misbehavior is what T0-9 retires; when the AI path is ON the
    # stamping site prefers the AI's 'both' and this function's answer becomes a validator input only).
    assert AR.panel_section("compare pcc 1a and 1b", "PCC-Panel-1") == "A"
