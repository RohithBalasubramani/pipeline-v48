# fab_guards Full Audit — Rework/Retire/Keep (2026-07-16)

Executes the approved plan. Shadow-mode fleet audit (mode=report, 19 pages) + guard-corpus cert replay.

## Fleet shadow verdict (report mode, before adoption)
Of all gap causes across 19 pages, the **four fab_guards causes fired as**:
- CLASS 1 epoch_ms_leak: **0**
- CLASS 2 null_column_reading: **0**
- CLASS 3 no_source_value: **0**
- CLASS 4 unstripped_seed: **33** — freshness.tone/label/status badges (cards 36/37/38) + legendValue (51/53/67) + 1 PQ.
  All fabrication-SAFE (the seed never ships); the real fix is freshness-badge + F5 legendValue DERIVATION, out of guard scope.

The C2/C3 fires that the 7-day telemetry recorded (card-15 panel family + card-46/40 under-derivation) are **already zero** —
the earlier twin-redirect, F7 aggregate-from-phases, and exempt_roster_slots fixes eliminated every one. So the C3-retirement
gate ("0 true-positive fires across the fleet") is empirically MET.

## Adopted (live, verify-then-adopt)
- `fab_guards.null_column_writer_aware = on` — CLASS 2 stands down on panel-aggregate fills (values from the member roll-up,
  not asset_table); defense-in-depth generalizing exempt_roster_slots. 0 fleet impact today, prevents future panel FPs.
- `fab_guards.no_source = off` — the numeric CLASS 3 branch RETIRED. Its true positives are pre-covered by the L2 honest-blank
  walls (cert-covered by wall_corpus_replay) + the executor present_cols None-return; its only distinct surface (post-fill
  strays) produced 100% false positives historically and 0 fires now. The live-literal STRING charter stays on its own valve.
- `fab_guards.mode` returned to `enforce`.

## Acceptance (all green)
- A/B before(current flags) vs after(target flags) on 4 hotspot pages: **0 lost-data leaves**, no strays introduced; card 15 real.
- SSR gate: 13/13 cards, 0 throws. Offline suite: 1425 passed (3 guard test files now pinned to enforce mode).
- guard_corpus_replay: 12 fixtures + 5 knob scenarios pinned to outputs/guard_replay_baseline.json (the new cert anchor —
  fab_guards had ZERO coverage in wall_corpus_replay / the sweep judge before this).

## Kept / staged
- CLASS 1 + CLASS 4 KEPT (C4 authoritative raw-vs-stripped wall; every fire = a latent strip bug → freshness/legendValue
  derivation follow-ups). restore_chrome KEPT.
- FULL numeric-C3 CODE DELETION + sweep fabrication_scan wiring (sweep/response.py:42) STAGED for a follow-up soak.

## Instruments (new)
- tools/fab_guards_shadow_replay.py — fleet report-mode audit → VERDICTS.md + verdicts.json (+ --diff before/after).
- tools/guard_corpus_replay.py + outputs/guard_replay_baseline.json — deterministic guard cert replay.
- sweep/checks/fabrication_scan.py — served-payload epoch/seed backstop (standalone; wire at sweep/response.py:42).
