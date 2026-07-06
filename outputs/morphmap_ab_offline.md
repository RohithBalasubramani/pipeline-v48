# ITEM 18 — morph-map vs full-emit: OFFLINE A/B over the logged corpus

Generated 2026-07-06T20:36:41.884517+00:00 by tools/morphmap_ab.py (pure replay — no live LLM calls, no pipeline wiring; layer2/build.py + layer2/emit/emit.py untouched).

## Corpus
- ai_r_*.jsonl files scanned: **609** (outputs/logs + outputs/_log_archive/**)
- L2 full-emit records found: **401** (dedup dropped 0)
- completions parseable: **400** (99.8%); lost to the full contract's size/transport: truncated **0**, no_json **0**, parse **0**
- skipped (card has no stored payload_stripped skeleton — the no-default contract path): **2**
- byte-compared emits: **398** across 58 distinct cards

## Regime A — producer equivalence (morphs = the _morphed-DECLARED paths)
- byte-identical to the reproduced live enforce result: **398/398** (100.0%)
- zero mismatches ⇒ `morphmap/producer.apply` is BYTE-EQUIVALENT to the live produce→gate→enforce path on identical declared intent.

## Regime B — expressed intent (morphs = every authored leaf that differs from the default)
- byte-identical: **361/398** (90.7%)
- differing: **37** — each difference is a leaf the AI AUTHORED off-default but did NOT declare in `_morphed`, so the full-emit contract silently REVERTED it (the A1 silent-no-op corruption); under morph-map, naming the path IS the declaration, so that intent ships (still through the same gates — chrome/data-leaf/locked morphs are still rejected).

## Corruption the full-emit contract caused (that morph-map structurally avoids)
- records with authored-but-UNDECLARED metadata changes (intent silently reverted): **59** records / **540** leaf paths
    - outputs/logs/ai_r_075d05bffb.jsonl ts=2026-07-06T16:13:31.441073 card=13 undeclared=48 e.g. ['flow.vm.legend[0].items[0].label', 'flow.vm.legend[0].items[1].label', 'flow.vm.legend[2].items[0].color', 'flow.vm.legend[2].items[0].label']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T16:23:43.538228 card=47 undeclared=9 e.g. ['snapshot.h5.limitPct', 'snapshot.h5.scaleMaxPct', 'snapshot.h7.limitPct', 'snapshot.h7.scaleMaxPct']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:03:31.408525 card=47 undeclared=9 e.g. ['snapshot.h5.limitPct', 'snapshot.h5.scaleMaxPct', 'snapshot.h7.limitPct', 'snapshot.h7.scaleMaxPct']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:03:45.104113 card=49 undeclared=1 e.g. ['loadImpact.views.pf-angle.series[0].label']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:03:50.989320 card=47 undeclared=9 e.g. ['snapshot.h5.limitPct', 'snapshot.h5.scaleMaxPct', 'snapshot.h7.limitPct', 'snapshot.h7.scaleMaxPct']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:21:24.972949 card=21 undeclared=12 e.g. ['distribution.period.panels[0].panel', 'distribution.period.panels[0].table', 'distribution.period.panels[1].panel', 'distribution.period.panels[1].table']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:21:37.488371 card=22 undeclared=29 e.g. ['table.pres.columns[2].id', 'table.pres.columns[2].header.label', 'table.pres.columns[3].id', 'table.pres.columns[4].header.label']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:21:52.509841 card=27 undeclared=16 e.g. ['signature.period.panels[0].panel', 'signature.period.panels[0].table', 'signature.period.panels[1].panel', 'signature.period.panels[1].table']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:21:58.439195 card=25 undeclared=21 e.g. ['summary.period.panels[0].panel', 'summary.period.panels[0].table', 'summary.period.panels[1].panel', 'summary.period.panels[1].table']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:22:02.101202 card=20 undeclared=28 e.g. ['trend.pres.stackSeries[2].color', 'trend.pres.stackSeries[3].color', 'trend.period.label', 'trend.period.panels[0].id']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:22:02.912566 card=26 undeclared=9 e.g. ['table.period.panels[0].table', 'table.period.panels[1].table', 'table.period.panels[2].table', 'table.period.panels[3].table']
    - outputs/logs/ai_r_1bc17049b9.jsonl ts=2026-07-06T22:22:14.737902 card=19 undeclared=1 e.g. ['summary.mode']
    - … (+47 more records)
- whole emissions LOST to completion size (truncated/unparseable): **0** — the ENTIRE payload (metadata AND every morph) shipped as a degraded default. A morph-map completion is a fraction of the size (see below), so the identical token budget could not have truncated at the same point.
- records whose authored metadata carried INVENTED keys (dropped identically by both contracts): **13**

## Completion-size reduction (the morph-map win)
- exact_metadata block (as emitted, incl. _morphed) → morphs-only map: 629,125 → 48,589 chars = **92.3% smaller**
- WHOLE completion (envelope simulated with `morphs` replacing `exact_metadata`): 2,035,766 → 1,447,668 chars = **28.9% smaller** (median per-emit reduction 28.6%)
- corpus completion tokens on compared emits: 991,633 — a proportional token cut ≈ 286,465 tokens saved across the corpus (char-ratio estimate)

## Verdict inputs (user condition: adopt ONLY if provably equal-or-better)
- EQUAL: regime A byte-equivalence above (same declared intent ⇒ same bytes through the same imported gates).
- BETTER: (a) the silent-no-op class disappears by construction (regime B / undeclared counts); (b) the completion shrinks by the % above, directly attacking the truncated/timeout loss class; (c) nothing to retype ⇒ no omission/drift risk on the ~untouched leaves.
- NOT wired live: adoption remains behind app_config `emit.morphmap_mode` (DEFAULT 'off', db/seed_morphmap_flag.sql); the live seam is post-certification work.
