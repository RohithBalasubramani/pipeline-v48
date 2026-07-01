"""Per-page WebSocket dispatchers and per-(type, page) strategies.

Each page is one Dispatcher class registered against a single URL pattern.
The Dispatcher loads the MFM, looks up the strategy for that MFM's type,
and runs the live/snapshot loop using the strategy's column list (or widget
catalogue, in the case of the Overview page).

Layout:

  consumers/
    _base.py                  BaseLiveStrategy + _BaseLiveDispatcher
    _history_base.py          BaseHistoryStrategy + _BaseHistoryDispatcher
    _overview_base.py         Widget primitives + _BaseOverviewDispatcher
    _fanout_base.py           BaseFanOutStrategy + _BaseFanOutDispatcher
    _common.py                Shared status-label callables

  Live (column-row, delta-queue):
    overview/                 OverviewDispatcher
    real_time_monitoring/     RealTimeMonitoringDispatcher
    voltage_current/          VoltageCurrentDispatcher
    energy_power/             EnergyPowerDispatcher
    power_quality_summary/    PowerQualitySummaryDispatcher
    distortion_harmonics/     DistortionHarmonicsDispatcher

  Fan-out (per-outgoing live):
    energy_distribution/      EnergyDistributionDispatcher

  History (date range + sampling):
    voltage_history/          VoltageHistoryDispatcher
    current_history/          CurrentHistoryDispatcher
    demand_profile/           DemandProfileDispatcher
    load_anomalies/           LoadAnomaliesDispatcher
    energy_power_history/     EnergyPowerHistoryDispatcher
    power_quality_history/    PowerQualityHistoryDispatcher
"""
from .overview              import OverviewDispatcher
from .real_time_monitoring  import RealTimeMonitoringDispatcher
from .voltage_current       import VoltageCurrentDispatcher
from .energy_power          import EnergyPowerDispatcher
from .energy_power_history  import EnergyPowerHistoryDispatcher
from .energy_distribution   import EnergyDistributionDispatcher
from .power_quality_summary import PowerQualitySummaryDispatcher
from .power_quality_history import PowerQualityHistoryDispatcher
from .distortion_harmonics  import DistortionHarmonicsDispatcher
from .voltage_history       import VoltageHistoryDispatcher
from .current_history       import CurrentHistoryDispatcher
from .demand_profile        import DemandProfileDispatcher
from .load_anomalies        import LoadAnomaliesDispatcher

__all__ = [
    'OverviewDispatcher',
    'RealTimeMonitoringDispatcher',
    'VoltageCurrentDispatcher',
    'EnergyPowerDispatcher',
    'EnergyPowerHistoryDispatcher',
    'EnergyDistributionDispatcher',
    'PowerQualitySummaryDispatcher',
    'PowerQualityHistoryDispatcher',
    'DistortionHarmonicsDispatcher',
    'VoltageHistoryDispatcher',
    'CurrentHistoryDispatcher',
    'DemandProfileDispatcher',
    'LoadAnomaliesDispatcher',
]
