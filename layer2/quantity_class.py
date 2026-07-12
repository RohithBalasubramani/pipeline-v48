"""layer2/quantity_class.py — FACADE. The physical-quantity vocabulary HOME moved to domain/quantity_class.py
(ems_exec.measurable_resolve consumes the same vocabulary; parked here it made layer2↔ems_exec circular).

sys.modules aliasing (not re-exports) so `layer2.quantity_class` IS `domain.quantity_class` — every consumer keeps
working identically, including the seed tool reading `_*_DEFAULT` mirrors and the wall tests monkeypatching
`_unit_map`/`_name_map`/`_weak` (an attribute set through EITHER path lands on the ONE module object).
[cycle-kill 2026-07-12]"""
import sys

import domain.quantity_class as _home

sys.modules[__name__] = _home
