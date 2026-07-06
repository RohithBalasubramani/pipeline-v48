# ITEM 18 — morph-map vs full-emit: OFFLINE A/B over the logged corpus

Generated 2026-07-06T16:33:17.265089+00:00 by tools/morphmap_ab.py (pure replay — no live LLM calls, no pipeline wiring; layer2/build.py + layer2/emit/emit.py untouched).

## Corpus
- ai_r_*.jsonl files scanned: **562** (outputs/logs + outputs/_log_archive/**)
- L2 full-emit records found: **6366** (dedup dropped 0)
- completions parseable: **6362** (99.9%); lost to the full contract's size/transport: truncated **4**, no_json **0**, parse **0**
- skipped (card has no stored payload_stripped skeleton — the no-default contract path): **531**
- byte-compared emits: **5831** across 70 distinct cards

## Regime A — producer equivalence (morphs = the _morphed-DECLARED paths)
- byte-identical to the reproduced live enforce result: **5831/5831** (100.0%)
- zero mismatches ⇒ `morphmap/producer.apply` is BYTE-EQUIVALENT to the live produce→gate→enforce path on identical declared intent.

## Regime B — expressed intent (morphs = every authored leaf that differs from the default)
- byte-identical: **1906/5831** (32.7%)
- differing: **3925** — each difference is a leaf the AI AUTHORED off-default but did NOT declare in `_morphed`, so the full-emit contract silently REVERTED it (the A1 silent-no-op corruption); under morph-map, naming the path IS the declaration, so that intent ships (still through the same gates — chrome/data-leaf/locked morphs are still rejected).

## Corruption the full-emit contract caused (that morph-map structurally avoids)
- records with authored-but-UNDECLARED metadata changes (intent silently reverted): **4669** records / **113438** leaf paths
    - outputs/logs/ai_r_075d05bffb.jsonl ts=2026-07-06T16:13:31.441073 card=13 undeclared=48 e.g. ['flow.vm.legend[0].items[0].label', 'flow.vm.legend[0].items[1].label', 'flow.vm.legend[2].items[0].color', 'flow.vm.legend[2].items[0].label']
    - outputs/logs/ai_r_44796d791a.jsonl ts=2026-07-06T16:28:47.470331 card=71 undeclared=23 e.g. ['duty.points[0].label', 'duty.points[1].label', 'duty.points[2].label', 'duty.points[3].label']
    - outputs/logs/ai_r_44796d791a.jsonl ts=2026-07-06T18:17:35.844168 card=53 undeclared=11 e.g. ['backupHistory.maxY', 'backupHistory.xLabels[0]', 'backupHistory.xLabels[1]', 'backupHistory.xLabels[2]']
    - outputs/logs/ai_r_44796d791a.jsonl ts=2026-07-06T18:17:49.766296 card=69 undeclared=3 e.g. ['data.maxLine.label', 'data.maxLine.value', 'data.expectedMax']
    - outputs/logs/ai_r_44796d791a.jsonl ts=2026-07-06T18:17:57.768217 card=71 undeclared=23 e.g. ['duty.points[0].label', 'duty.points[1].label', 'duty.points[2].label', 'duty.points[3].label']
    - outputs/logs/ai_r_44796d791a.jsonl ts=2026-07-06T18:18:14.537779 card=45 undeclared=1 e.g. ['health.data.insightVocab.awaitingVoltage']
    - outputs/logs/ai_r_82157379cd.jsonl ts=2026-07-06T16:21:15.032718 card=38 undeclared=2 e.g. ['data.thresholds[0].label', 'data.thresholds[1].label']
    - outputs/logs/ai_r_82157379cd.jsonl ts=2026-07-06T16:21:16.719165 card=37 undeclared=4 e.g. ['data.thresholds[0].label', 'data.thresholds[0].value', 'data.thresholds[1].label', 'data.thresholds[1].value']
    - outputs/logs/ai_r_82157379cd.jsonl ts=2026-07-06T19:08:08.040399 card=38 undeclared=4 e.g. ['data.thresholds[0].label', 'data.thresholds[0].value', 'data.thresholds[1].label', 'data.thresholds[1].value']
    - outputs/logs/ai_r_82157379cd.jsonl ts=2026-07-06T19:08:11.238509 card=37 undeclared=4 e.g. ['data.thresholds[0].label', 'data.thresholds[0].value', 'data.thresholds[1].label', 'data.thresholds[1].value']
    - outputs/logs/ai_r_82157379cd.jsonl ts=2026-07-06T21:57:26.898853 card=14 undeclared=1 e.g. ['card.view.markerLabel.unit']
    - outputs/logs/ai_r_82157379cd.jsonl ts=2026-07-06T21:57:29.712124 card=17 undeclared=1 e.g. ['demand.range']
    - … (+4657 more records)
- whole emissions LOST to completion size (truncated/unparseable): **4** — the ENTIRE payload (metadata AND every morph) shipped as a degraded default. A morph-map completion is a fraction of the size (see below), so the identical token budget could not have truncated at the same point.
    - outputs/_log_archive/logs_pre_20260705_002155/ai_r_30bbfb4c02.jsonl ts=2026-07-04T18:00:22.744485 card=5 kind=truncated prompt_tok=46758 completion_tok=18778
    - outputs/_log_archive/logs_pre_20260705_002155/ai_r_f9787f915f.jsonl ts=2026-07-03T20:31:59.852447 card=5 kind=truncated prompt_tok=46438 completion_tok=19098
    - outputs/_log_archive/logs_pre_20260705_002155/ai_r_f9787f915f.jsonl ts=2026-07-03T20:34:18.072187 card=5 kind=truncated prompt_tok=46589 completion_tok=18947
    - outputs/_log_archive/logs_pre_20260705_002155/ai_r_f9787f915f.jsonl ts=2026-07-03T20:37:39.211799 card=5 kind=truncated prompt_tok=46490 completion_tok=19046
- records whose authored metadata carried INVENTED keys (dropped identically by both contracts): **1707**

## Completion-size reduction (the morph-map win)
- exact_metadata block (as emitted, incl. _morphed) → morphs-only map: 9,879,571 → 4,583,600 chars = **53.6% smaller**
- WHOLE completion (envelope simulated with `morphs` replacing `exact_metadata`): 28,907,487 → 23,500,767 chars = **18.7% smaller** (median per-emit reduction 17.9%)
- corpus completion tokens on compared emits: 14,680,929 — a proportional token cut ≈ 2,745,851 tokens saved across the corpus (char-ratio estimate)

## Verdict inputs (user condition: adopt ONLY if provably equal-or-better)
- EQUAL: regime A byte-equivalence above (same declared intent ⇒ same bytes through the same imported gates).
- BETTER: (a) the silent-no-op class disappears by construction (regime B / undeclared counts); (b) the completion shrinks by the % above, directly attacking the truncated/timeout loss class; (c) nothing to retype ⇒ no omission/drift risk on the ~untouched leaves.
- NOT wired live: adoption remains behind app_config `emit.morphmap_mode` (DEFAULT 'off', db/seed_morphmap_flag.sql); the live seam is post-certification work.
