# tests/property — property-based invariant suite (hypothesis)

Randomized, generative tests over the V48 pipeline's invariants. Two tiers:

| Tier | What runs | LLM | Cases per run |
|---|---|---|---|
| **offline** (default) | deterministic seams with the LLM faked at each module's `call_qwen` binding and every DB read snapshotted once per session from the REAL rows | none | `PBT_EXAMPLES` (default 150) per property × ~25 properties ≈ **~4,000 randomized cases** |
| **live** (`-m live`) | sampled metamorphic checks against the real pinned-seed Qwen on :8200 (auto-skipped if unreachable) | real | `PBT_LIVE_EXAMPLES` (default 4) cases per test |

## Requirement → file map

| Invariant | Offline (deterministic) | Live (metamorphic) |
|---|---|---|
| Capitalization must not change page selection | `test_prop_page_key_resolution.py`, `test_prop_metric_normalization.py`, `test_prop_intent_clamp.py`, `test_prop_route_fail_closed.py` (P3) | `test_prop_live_route_invariance.py` |
| Whitespace must not change asset resolution | `test_prop_asset_norm_equivalence.py`, `test_prop_asset_name_echo_invariance.py` | `test_prop_live_asset_invariance.py` (L1) |
| Aliases must resolve identically | `test_prop_asset_alias_equivalence.py` (aka column + `pcc_panel_alias`) | `test_prop_live_asset_invariance.py` (L2) |
| Historical prompts → historical pages/windows | `test_prop_window_clamp.py` | `test_prop_live_historical_window.py` |
| Knowledge prompts never invoke dashboards | `test_prop_knowledge_gate_contract.py`, `test_prop_host_knowledge_terminal.py` (the fork: a knowledge kind returns terminally, `build_response` never runs) | `test_prop_live_knowledge_offdomain.py` (L1/L3) |
| Off-domain prompts always rejected | `test_prop_knowledge_gate_contract.py` (P2), `test_prop_host_knowledge_terminal.py` | `test_prop_live_knowledge_offdomain.py` (L2) |
| Resolver never fabricates (closure/fail-closed) | `test_prop_asset_fail_closed_fuzz.py`, `test_prop_route_fail_closed.py`, `test_prop_member_scope.py`, `test_prop_class_prior.py` | — |

## Running

```bash
cd backend/layer2/pipeline_v48

# offline tier (no LLM; needs the cmd_catalog/neuract DB for the one-time snapshots)
python -m pytest tests/property -q -m "not live"

# deeper soak — 1000 examples per property (~25k cases)
PBT_EXAMPLES=1000 python -m pytest tests/property -q -m "not live"

# live tier (needs :8200; ~2-5 min at the default budget)
python -m pytest tests/property -q -m live
PBT_LIVE_EXAMPLES=8 PBT_SEED=7 python -m pytest tests/property -q -m live
```

## Design rules

- **Mutants are equivalence-preserving by construction** (`gen.py`): `edge_mutants` = the `.strip().lower()` class,
  `norm_mutants` = the layer1b `_norm` class. The generator side can't produce a false failure; every red is a real
  normalization/plumbing regression (offline) or a real model instability (live).
- **The fake LLM is a holder dict** the test writes per example — the pipeline code under test is byte-identical to
  production; only each module's own `call_qwen` binding is monkeypatched.
- **Snapshots are real rows** read once per session (`conftest.py`) — full data fidelity, no per-example DB
  round-trips, no TTL-expiry flake mid-run.
- **Oracles are independent**: claimant sets for aliases are computed from the raw tables, never from resolver
  internals, so tests don't mirror the code they check.
- **Non-vacuity is asserted**: corpora sizes are checked (registry ≥ 20 unique names, alias corpus ≥ 5, ≥ 9 pages);
  an empty corpus skips loudly instead of passing silently.
