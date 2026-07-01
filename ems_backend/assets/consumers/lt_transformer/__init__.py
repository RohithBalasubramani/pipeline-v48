"""LT Transformer asset pages (type-specific).

Widget-envelope tabs (chart + KPIs + monitor + heatmap, per-widget filters):
  Thermal & Life → lt-transformer-thermal
  Loss Analysis  → lt-transformer-loss
  Utilization    → lt-transformer-utilization
"""
from .thermal import LtTransformerThermalDispatcher
from .loss_analysis import LtTransformerLossAnalysisDispatcher
from .utilization import LtTransformerUtilizationDispatcher

__all__ = [
    'LtTransformerThermalDispatcher',
    'LtTransformerLossAnalysisDispatcher',
    'LtTransformerUtilizationDispatcher',
]
