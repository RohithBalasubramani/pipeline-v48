"""tests/test_sections_token_characterization.py — pins the behavior of data/equipment/sections.py token()
across the Tier-0 registry-validation change (deterministic_audit_20260714 L2-07 / T0-5, now SHIPPED).

Pins the CORRECT contract (numbered panel + A/B → '<n><S>'; no number / bad letter → None) plus the two former
DEFECT shapes, updated to the new expectations: int()'s leading-zero collapse is kept ONLY when the registry
CONFIRMS the collapsed token (unique hit), and a synthesized token with NO such section in equipment.mfm is now
honest None instead of silently filtering the member roll-up to zero. The FIXED pins monkeypatch _section_map (no
DB); the contract pins below run against whatever map is live — they hold on the real registry (1A/2B/4B are real
tokens) AND door-dark (empty map → legacy synthesis), so they stay environment-independent."""
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


def test_FIXED_leading_zero_collapse(monkeypatch):
    # FIXED (T0-5): int() still strips the zero, but ONLY because the registry proves '1A' is the real token
    # (unique hit among the as-written + zero-stripped candidates) — no longer an unchecked collapse.
    monkeypatch.setattr(SE, "_section_map", lambda: {"t1": "1A", "t2": "1B"})
    assert SE.token("PCC-Panel-01", "A") == "1A"


def test_FIXED_token_registry_checked(monkeypatch):
    # FIXED (T0-5): a panel number with NO such section in equipment.mfm now returns honest None (was '99A' — a
    # synthesized token that silently filtered the member roll-up to zero) when the registry map is available.
    monkeypatch.setattr(SE, "_section_map", lambda: {"t1": "1A", "t2": "1B"})
    assert SE.token("PCC-Panel-99", "A") is None
