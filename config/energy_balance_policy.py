"""config/energy_balance_policy.py — the ONE store for the feeder fan-out energy-balance / Sankey-conservation knobs.

Ported from CMD_V2 backend2 panels/consumers/energydist.py (`_build` :224-347, `_cap_util` :71-78). The PCC-panel
energy-accounting view splits the incomer↔outgoing kWh gap into (a) *unmetered distribution* — modeled as its OWN
balancing Sankey node so inflow == outflow — vs (b) genuine measurement *loss*, and raises an over-metering 'Review'
badge when Σoutgoing over-reads Σincoming by more than a threshold. Every scalar in that logic is an EDITABLE ROW here;
NO magic number lives in energy_distribution/pcc_panel.py.

DB home: cmd_catalog.data_quality_policy under the `energy_balance.` namespace (one row per knob), read via
num('energy_balance.<key>', default). Mirrors config/bands.py: pure-stdlib fallback dict, lazy DB read that never
raises, so the accessor works with the DB DOWN (returns the code default). [#5 feeder fan-out energy-balance + Sankey]
"""

# ── code-default fallbacks (mirror backend2 energydist.py constants) — used verbatim when the DB row / DB is absent ────
_SCALAR_DEFAULTS = {
    # Σoutgoing over Σincoming by more than this fraction of measured input → over-metering, 'Review' badge.
    # backend2 energydist.py:241  `over_metered = gap > measured * 0.02`.
    "energy_balance.over_metered_frac": 0.02,
    # Surface the unmetered remainder as its own consumer row + balancing Sankey node only when it exceeds this
    # fraction of measured input (below it is rounding noise). backend2 energydist.py:284/311 `unmetered > measured*0.01`.
    "energy_balance.unmetered_surface_frac": 0.01,
    # Loss above this % of measured input reads 'above the expected band' → 'review' badge.
    # backend2 energydist.py:20/123/337 EXPECTED_LOSS_BAND_PCT.
    "energy_balance.expected_loss_band_pct": 3.0,
    # assumed power factor turning nameplate kVA → kW for capacity. backend2 energydist.py:28 `_PF`.
    "energy_balance.assumed_pf": 0.9,
}

# text knobs (physical column names) — editable so a schema rename is a row edit, not a code change.
_TXT_DEFAULTS = {
    # cumulative reactive-energy import counter; apparent energy is derived √(kWh² + kVArh²) over the SAME window,
    # NOT read as a counter. backend2 energydist.py:207/212. V48 seed_parameters.py measured metric M10.
    "energy_balance.reactive_energy_col": "reactive_energy_import_kvarh",
}


# ── DB-backed accessors (fall back to the code defaults above when the row / DB is absent) ────────────────────────────

def num(key, default=None):
    """The scalar `energy_balance.<...>` knob (over-metering fraction / unmetered-surface fraction / expected-loss band
    / assumed PF), or its code default. Reads cmd_catalog.data_quality_policy (via config.policy_read — the one shared
    reader); falls back to _SCALAR_DEFAULTS[key] (else `default`) with the DB DOWN."""
    from config import policy_read as _pr
    return _pr.num(key, _SCALAR_DEFAULTS.get(key, default))


def txt(key, default=None):
    """The text `energy_balance.<...>` knob (e.g. the reactive-energy counter column), or its code default. Reads
    cmd_catalog.data_quality_policy (via config.policy_read); falls back to _TXT_DEFAULTS[key] (else `default`) with
    the DB DOWN."""
    from config import policy_read as _pr
    return _pr.txt(key, _TXT_DEFAULTS.get(key, default))
