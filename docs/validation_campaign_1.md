# Validation Campaign 1 — the framework's first live cycle (2026-07-12)

The V48 validation framework (`validation/`, `python -m validation.cli`) ran its first full
generate → run → judge → coverage → replay cycle against the live stack. This document is the
campaign record: what ran, every defect it exposed, and each defect's disposition.

## What ran

| Session | Cases | Result |
|---|---|---|
| `smoke_1` — 36 stratified (2 × 18 categories) | all workflows | **33/36 pass** (2 honest-degraded); p50 58s, p95 256s |
| `compare_recheck` — 12 compare-lane cases | compare 2/3/5-way, mutations | 6/12 pre-fix → **all 6 failures root-caused; fixes proven by replay** |
| `datesync` sweep — 10 responses, 38 history cards | interactive date-sync | **37 reslice + 1 honest as-of-latest, 0 violations** |
| Replays — all 6 compare failures re-run post-fix | before/after proof | 3 full compares (5–6 groups), 2 honest pickers, 1 → prompt-rule re-replay |

Corpus: **30,747 cases** (DB-driven: `prompt_category` / `prompt_template` / `prompt_vocab`,
byte-deterministic regeneration; budgets are DB rows). Coverage from the 36-case smoke alone:
20.4% pages / 27.4% cards / 100% categories, with honest uncovered lists.

## Defects exposed → dispositions

### Pipeline defects (fixed + replay-proven)
1. **Punctuation-heavy compare names silently degraded to single** — `_span_regex` token gaps
   (`[-_ ]*`) stopped at the first `(`/`[`/`+`. Fix: `_SEP = [^a-zA-Z0-9]{0,4}` (`bba3ac0`).
2. **Phantom-alias infix detection** — 'Chiller **Panel-1** Main INC' contains the PCC alias
   `panel-1`; a 5-chiller compare detected 9 rows (4 phantom panels), whose empty sub-resolutions
   killed the compare. Fix: span-subsumption in `named_full_rows` (`cf1590c`).
   **Replay proof: chiller 5-way = compare, 5 groups, 15 cards, 0 errors.**
3. **Kept-name mutilation** — an OTHER row's pattern could strip text *inside* the kept name
   ('Chiller Panel-2 Main INC' → 'Chiller Main Inc'). Fix: sentinel-mask the kept span
   (`cf1590c`). **Replay proof: BPDB 5-way = 6 groups / 24 cards; HHF lowercase 5-way = 5 groups.**
4. **The pump 3-way — a six-layer excavation** (one corpus case, six independent seams hardened,
   each exposed only after the previous fix; every layer committed):
   1. client timeout at 420s → compare-lane 900s (`cf1590c`)
   2. resolver substituted a lexical neighbor ('Cooling Pumps' → 'Air Compressor Panel') →
      ★ no-substitution rule (`d516f7f`)
   3. concurrent sub-resolves each re-ran the ~250-table candidate probe; two flap-errored →
      ONE shared probe (`f68ff38`)
   4. model hedged AMBIGUOUS on the explicitly-named NO-DATA row → verbatim-name-is-never-a-homonym
      rule (`6ccb58f`)
   5. the natural-compare gate bailed SILENTLY → decision telemetry (`c92d4db`)
   6. a named-but-DARK member's single-path picker-affordance flipped it ambiguous → how='no_data'
      counts CONFIDENT; the dark lane joins the compare and honest-blanks (`8cb3ff3`)
   **Final replay (round 8, isolated :8771): `decision=compare rows=3 confident=3` →
   compare, 3 groups, 9 cards, 0 payload errors. CLOSED.**
   (Rounds 6–7 died to a real :5433 outage + parallel-session server restarts — bonus live
   certification of the honest data_unavailable terminal, telemetry naming the exact cause.)

### Framework defects (fixed)
5. **Client timeouts manufactured failures** — two "failures" were 420.1s client timeouts on
   multi-asset runs the server completed. Fix: `COMPARE_TIMEOUT_S=900` per-category
   (`config.timeout_for`, runner + replay) (`cf1590c`, `a1b8c16`).
6. **Page coverage silently zero** — the parser read `cards[0].page_key`; page identity lives on
   the top-level `page` object (`fceba4e`).
7. **No-data picker mislabeled 'cards'** — `asset_no_data` + candidates now classifies as
   `picker` (the FE opens the picker over any cards); compare expects accept `|picker` — dark-asset
   /homonym compares honestly land there while silent single-pin still fails (`ffe3faa`).
8. **Head-slice `--limit`** starved category coverage → stratified round-robin (`bba3ac0`).

### Honest behaviors confirmed (not defects)
- **Dark-meter compares** → the no-data picker with alternatives (replays 1 & 6: Solar Incomer-1).
- **Bare-homonym compares** ('UPS-01 and UPS-02') → 10-candidate picker, never auto-pin.
- **RC9 as-of-latest** scalar/KPI cards legitimately don't reslice with the date window.
- **Self-compare pair** ('pcc-1 vs pcc-panel-1') — an old-generator artifact; the DB-driven corpus
  produces 0 (3,450 compare cases scanned).
- Off-domain refused, invalid assets graceful, knowledge answered without dashboards — all green.

## Performance observation (not a defect)
A 5-way panel compare issued **~11k SQL queries** (member fan-out re-reads per card per lane).
Correct but heavy (~5–15 min per run). If wide compares should feel snappy, a per-run member-frame
cache would collapse this. Deferred.

## Operational notes
- vLLM contention: /api/run lane hard-capped at 3 (framework default 2); /api/frame is no-LLM (lane 8).
- The `ai_log._RUN_ID` global race pollutes per-run AI logs under concurrent runs (known P3);
  stage-log attribution during parallel validation runs is best-effort.
- Registry mirror re-synced during the campaign (22,883 rows / 8 tables; `table_exists` verified
  truthful — a suspected stale flag was actually a wrong-search-path probe).

## How to re-run
```bash
python -m validation.cli generate                       # corpus from the live universe (deterministic)
python -m validation.cli run --limit 36 --concurrency 2 # stratified smoke
python -m validation.cli run --category compare_2 --category compare_3 --limit 12
python -m validation.cli datesync --session <sid>
python -m validation.cli replay <case_id> --session <sid>
python -m validation.cli report --session <sid>         # report.json + report.html
```
