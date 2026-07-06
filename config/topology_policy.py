"""config/topology_policy.py — thin reader for the TOPOLOGY / IO-loss / trend knobs (the derivation-math bands).

Every threshold the ported feeder_energypower.py IO-resolution + core/derive.py trend logic introduces is an EDITABLE ROW
in cmd_catalog.data_quality_policy (keys under the `topology.` namespace) — NO magic number lives in derivations/*.py.
This module is the ONE accessor those pure fns read, so a reviewer flips the loss-plausibility band or the trend deadband
by editing a row, not code. Mirrors config.quality_policy's num()/txt() shape but WRAPS the reader so it FALLS BACK to the
code default with the DB down (data.db_client.q raises on connect failure). [#4/#12 derivation-math port]

Keys:
  topology.loss_plausible_min_pct  (0.0)   — lower bound of the trusted input↔output loss band; below → output_only
  topology.loss_plausible_max_pct  (10.0)  — upper bound; a bigger figure means the paired meter is not truly upstream
  topology.trend_deadband          (0.05)  — ±fraction deadband for trend_status (rising/stable/falling)
"""
from config import quality_policy as _qp


def _num(key, default):
    """quality_policy.num(key, default) but honest-degrade to `default` when the DB is unreachable (q() raises)."""
    try:
        return _qp.num(key, default)
    except Exception:
        return default


def loss_plausible_band_pct():
    """The (min, max) percent band within which an input↔output loss pairing is physically plausible. A computed
    loss_pct outside this band means the 'input' meter is not really upstream → the loss block is dropped for
    output_only (P1 #11 gate). Editable rows topology.loss_plausible_{min,max}_pct. Defaults (0.0, 10.0)."""
    lo = _num("topology.loss_plausible_min_pct", 0.0)
    hi = _num("topology.loss_plausible_max_pct", 10.0)
    return (lo, hi)


def trend_deadband():
    """The ±fraction deadband for trend_status — |Δ| within this fraction of |baseline| reads 'stable' (no spurious
    arrows). Editable row topology.trend_deadband. Default 0.05 (±5%)."""
    return _num("topology.trend_deadband", 0.05)
