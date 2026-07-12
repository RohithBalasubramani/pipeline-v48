"""layer2/emit/metadata/asset_3d.py — FACADE. The 4-tier neuract 3D model resolver + viewer-preset merge HOME moved to
domain/asset_3d.py (the ems_exec 3D renderer consumes it directly; parked here it made layer2↔ems_exec circular).

sys.modules aliasing (not re-exports) so this module IS domain.asset_3d — the seed scripts and the equipment-3D tests
that monkeypatch module attributes keep working through either path. [cycle-kill 2026-07-12]"""
import sys

import domain.asset_3d as _home

sys.modules[__name__] = _home
