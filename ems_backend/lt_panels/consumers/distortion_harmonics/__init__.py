"""Distortion & Harmonics page — V/I-THD, harmonics, PF, K-factor."""
from .._base import _BaseLiveDispatcher, StubStrategy
from .lt_panel    import LtPanelDistortionHarmonics
from .transformer import TransformerDistortionHarmonics
from .ups         import UpsDistortionHarmonics


# APFC distortion analysis uses the same THD + PF + harmonic cols as LT,
# plus the APFC-specific compensation/resonance telemetry.
class ApfcDistortionHarmonics(LtPanelDistortionHarmonics):
    columns = LtPanelDistortionHarmonics.columns + [
        'apfc_pf_before', 'apfc_pf_after',
        'apfc_compensation_ratio_pct',
        'apfc_bank_utilization_pct',
        'apfc_resonance_risk_hz',
        'apfc_detuning_effectiveness_pct',
        'apfc_compensation_flag',
    ]


# PCC-named MFMs are typed lt_panel in the DB. Aliasing to the LT strategy
# lets them get real distortion data instead of being blocked by a stub
# (the dispatcher's category-first lookup would otherwise short-circuit
# on the stub before the type-code fallback could find LtPanelDistortionHarmonics).
class PccPanelDistortionHarmonics(LtPanelDistortionHarmonics): pass


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelDistortionHarmonics(StubStrategy): pass
class SubPanelDistortionHarmonics(StubStrategy): pass


class DistortionHarmonicsDispatcher(_BaseLiveDispatcher):
    PAGE_CODE = 'distortion-harmonics'
    STRATEGIES = {
        'lt_panel':    LtPanelDistortionHarmonics,
        'transformer': TransformerDistortionHarmonics,
        'ht_panel':    HtPanelDistortionHarmonics,
        'ups':         UpsDistortionHarmonics,
        'apfc':        ApfcDistortionHarmonics,
        'sub_panel':   SubPanelDistortionHarmonics,
        'pcc_panel':   PccPanelDistortionHarmonics,
    }
