"""tests/test_sections_token_characterization.py — pins TODAY'S behavior of data/equipment/sections.py token()
BEFORE the Tier-0 registry-validation change (deterministic_audit_20260714 L2-07 / T0-5).

Pins the CORRECT contract (numbered panel + A/B → '<n><S>'; no number / bad letter → None) AND the KNOWN defect
shape: int() collapses leading-zero variants ('PCC-Panel-01' and 'PCC-Panel-1' both → '1A') and the synthesized
token is never checked against the registry (a panel with no such section still gets a token → silently filters to
zero members). T0-5 keeps the collapse-to-real-token behavior when the registry CONFIRMS it and returns None
otherwise; the pins marked DEFECT here get updated in that commit."""
import data.equipment.sections as SE


def test_basic_tokens():
    assert SE.token("PCC-Panel-1", "A") == "1A"
    assert SE.token("PCC-Panel-2", "b") == "2B"          # letter case-insensitive
    assert SE.token("PCC-Panel-4", "B") == "4B"


def test_no_trailing_number_is_none():
    assert SE.token("Panel", "A") is None
    assert SE.token("", "A") is None
    assert SE.token(None, "A") is None


def test_bad_section_letter_is_none():
    assert SE.token("PCC-Panel-1", "C") is None
    assert SE.token("PCC-Panel-1", "") is None
    assert SE.token("PCC-Panel-1", None) is None


def test_DEFECT_leading_zero_collapse():
    # int() strips the zero: two DIFFERENT panel spellings produce the SAME token — pinned as today's behavior;
    # T0-5 keeps this ONLY when the registry proves '1A' is the real token (unique hit), else honest None.
    assert SE.token("PCC-Panel-01", "A") == "1A"


def test_DEFECT_token_never_registry_checked():
    # A panel number with NO such section in equipment.mfm still synthesizes a token today (silently filters the
    # member roll-up to zero). T0-5 makes this return None (honest degrade) when the registry map is available.
    assert SE.token("PCC-Panel-99", "A") == "99A"
