# Multi-compare lane/fill parallelism — verification results (2026-07-14)

Flag-gated Stage A (per-asset fill fan-out) + Stage B (class-lane fan-out), per the approved plan. Single-asset spine
byte-untouched; both knobs default 0 = the sequential path.

## What shipped
- `run/harness.py`: `lane_salt` threaded to the reflect loop (single path byte-identical rids; multi lanes salted
  `class:<cls>:` so concurrent lanes can't collide on `ai_<rid>.jsonl`); Stage B phase-1 (sequential until a lane
  yields `shared_1a`) + phase-2 (remaining lanes via `run_parallel` when `multi_asset.lane_concurrency>1 and len>1`).
- `host/multi_asset.py` (committed ba53752): Stage A per-asset fill fan-out + compare_mode hoist behind
  `multi_asset.fill_concurrency`; order-preserving serial reassembly; first-in-order exception parity.
- `host/compare_overlay.py`: **pre-existing crash fix** — `merge_overlay` assumed `payload.period` is a dict, but a
  scalar card's `period` is a STRING label → `AttributeError: 'str' object has no attribute 'get'` 500'd EVERY overlay
  compare of these UPS/energy cards. Guarded `period` like its `stats`/`points` siblings (base + per-comparand). This
  is in committed HEAD (line 207), unrelated to parallelism — it blocked verification and breaks the compare feature.
- `db/seed_multi_parallel.sql`, `tests/test_multi_parallel.py` (16 cases), `tests/test_multi_asset.py` (fakes `**kw`).

## Verification

**Offline:** full non-live suite **1075 passed** (+16 new parallel tests, +52 compare/overlay/multi after the merge
fix); the 16 new tests pin order-determinism (sleep-staggered), first-in-order exception parity, compare_mode hoist,
Stage-B phase split + real overlap, data_unavailable-lane0, reflect-salt, single-group no-pool, sectioned compare.

**Live (same :8200 lifetime = greedy determinism):** the pipeline is NOT byte-deterministic run-to-run — the L2 emit
prompt carries a wall-clock anchor, so two SEQUENTIAL baseline runs of the SAME prompt already differ in emitted
values/prose (single-asset too). So neutrality was verified on the **structural fingerprint** (card count, the ordered
`(asset_id, render_card_id)` sequence — the load-bearing order — mode, data_unavailable, real-card count), which IS
stable run-to-run. Fixtures: P1 = 3-UPS same-class (overlay), P2 = UPS+DG cross-class (overlay), S1 = single (spine).

| run | P1 fp | P2 fp | S1 fp |
|---|---|---|---|
| base1 | 903ad9801826 | 10351ddb0f84 | d11705927dbd |
| base2 | 903ad9801826 | 10351ddb0f84 | d11705927dbd |
| Stage A (fill=3) | 903ad9801826 | 10351ddb0f84 | d11705927dbd |
| Stage B (fill=3,lane=2,adm 4/300) | 903ad9801826 | 10351ddb0f84 | d11705927dbd |

**All fingerprints identical** across baseline, Stage A, Stage B → parallelism changes nothing beyond the pre-existing
LLM value-wobble. No blanks, no timeouts, no reordering, correct per-asset tagging.

## Adoption decision
- **Stage A ADOPTED live** (`multi_asset.fill_concurrency=3`): proven neutral + safe, and it adds ZERO vLLM load
  (fills are executor/DB only), so it's safe regardless of concurrent GPU traffic. Win is modest on small compares
  (fills are cheap vs the ~20s L2 emit that dominates e2e) and grows with same-class asset count.
- **Stage B HELD OFF** (`multi_asset.lane_concurrency=0`): mechanism verified (the 3-class trace showed the DG +
  Transformer lanes running concurrently) and neutral, BUT the one heavy 3-class run hit an **emit timeout →
  hard_fails=1** (a card blanked) while a CONCURRENT SESSION's dashboard traffic was also hammering vLLM. That is the
  documented 2026-07-06 contention class. Stage B's SAFETY cannot be cleanly proven while another session shares the
  GPU. Also: Stage B only engages at **3+ distinct classes** (a 2-class compare's phase-2 has one lane → sequential),
  so its benefit is narrow. Re-verify in a quiet GPU window with `global_concurrency` tuned before adopting.
- Admission guard reverted to defaults (`global_concurrency=0`, `admission_wait_s=60`) — it was Stage-B prep; with
  Stage B off it isn't needed and reverting keeps single/multi LLM behavior exactly as before.

## Live knob state (cmd_catalog app_config)
`multi_asset.fill_concurrency=3` · `multi_asset.lane_concurrency=0` · `llm.global_concurrency=0` · `llm.admission_wait_s=60`
