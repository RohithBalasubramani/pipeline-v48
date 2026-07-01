"""UPS asset pages (type-specific).

Each tab is its own dispatcher bound to ASSET_TYPE='ups' — no per-type
STRATEGIES map, because these pages exist only for UPS assets. The shared
`overview` page lives under consumers/overview/, not here.

Tabs (columns sourced from the UPS-assets timeseries spec):
  Battery & Autonomy   → ups-battery-autonomy   (14 cols)
  Source & Transfer    → ups-source-transfer    (12 cols)
  Output Load/Capacity → ups-output-capacity     (7 cols)
"""
from .battery_autonomy import UpsBatteryAutonomyDispatcher
from .source_transfer import UpsSourceTransferDispatcher
from .output_capacity import UpsOutputCapacityDispatcher

__all__ = [
    'UpsBatteryAutonomyDispatcher',
    'UpsSourceTransferDispatcher',
    'UpsOutputCapacityDispatcher',
]
