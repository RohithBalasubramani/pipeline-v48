"""Energy & Power page — KPIs, today's energy, input vs output."""
from .._base import _BaseLiveDispatcher, StubStrategy
from .lt_panel    import LtPanelEnergyPower
from .transformer import TransformerEnergyPower
from .pcc_panel   import PccPanelEnergyPower
from .ups         import UpsEnergyPower


# APFC: same E&P tiles as LT + APFC-specific savings/penalty columns.
class ApfcEnergyPower(LtPanelEnergyPower):
    columns = LtPanelEnergyPower.columns + [
        'apfc_savings_per_month',
        'apfc_penalty_avoided_per_month',
        'apfc_pf_before',
        'apfc_pf_after',
        'apfc_compensation_ratio_pct',
    ]


# ── Stubs — TODO: spec from user ─────────────────────────────────────────
class HtPanelEnergyPower(StubStrategy): pass
class SubPanelEnergyPower(StubStrategy): pass


class EnergyPowerDispatcher(_BaseLiveDispatcher):
    PAGE_CODE = 'energy-power'
    STRATEGIES = {
        'lt_panel':    LtPanelEnergyPower,
        'transformer': TransformerEnergyPower,
        'ht_panel':    HtPanelEnergyPower,
        'ups':         UpsEnergyPower,
        'apfc':        ApfcEnergyPower,
        'sub_panel':   SubPanelEnergyPower,
        'pcc_panel':   PccPanelEnergyPower,
    }
