"""Private row-math helpers shared by the PQ derivers.

Pure functions over a single live row dict (column → value). No DB I/O,
no state. Return None when the inputs are absent.
"""
from __future__ import annotations

from .thresholds import ORDINAL


def _ord(n):
    if n is None:
        return None
    try:
        return ORDINAL.get(int(n), f'{int(n)}th')
    except (TypeError, ValueError):
        return None


def _max_thd_v(row):
    vs = [row.get(f'thd_voltage_{p}_pct') for p in ('r', 'y', 'b')]
    vs = [v for v in vs if v is not None]
    return max(vs) if vs else None


def _max_thd_i(row):
    vs = [row.get(f'thd_current_{p}_pct') for p in ('r', 'y', 'b')]
    vs = [v for v in vs if v is not None]
    return max(vs) if vs else None


def _avg_thd_v(row):
    vs = [row.get(f'thd_voltage_{p}_pct') for p in ('r', 'y', 'b')]
    vs = [v for v in vs if v is not None]
    return (sum(vs) / len(vs)) if vs else None


def _avg_thd_i(row):
    vs = [row.get(f'thd_current_{p}_pct') for p in ('r', 'y', 'b')]
    vs = [v for v in vs if v is not None]
    return (sum(vs) / len(vs)) if vs else None
