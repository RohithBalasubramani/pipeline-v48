"""ems_exec/executor/blank.py — FACADE. Home moved to lib/blank.py (shared below the layers; see that module).
sys.modules aliasing so both import paths are the SAME module object. [cycle-kill 2026-07-12]"""
import sys

import lib.blank as _home

sys.modules[__name__] = _home
