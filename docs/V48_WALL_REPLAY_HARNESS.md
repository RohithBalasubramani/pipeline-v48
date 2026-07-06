# V48 Wall Corpus-Replay Harness

**Tool:** `tools/wall_corpus_replay.py` · **Baseline artifacts:** `outputs/wall_replay_baseline.{json,md}`
**Backlog:** implements the WALL CORPUS-REPLAY HARNESS mandate + rides `outputs/AI_QUALITY_BACKLOG.md` item 22
(cast-integrity sibling: `tests/test_config_cast_integrity.py`).

## What it is

The **acceptance harness for every future wall change** (`layer2/gates.py`, `layer2/quantity_class.py`,
`quantity.*` / `consts.*` / `gates.*` app_config rows).

**Standard: all fabrications caught, zero legit binds harmed.**

It loads EVERY archived + fresh Layer-2 emit ever logged (`outputs/_log_archive/**/ai_r_*.jsonl` +
`outputs/logs/ai_r_*.jsonl`), parses each response's `data_instructions` (unparseable → counted + skipped),
reconstructs each run's column basket from the logged user message's DB SCHEMA block (all three historical header
dialects; an empty block = a real empty basket; a `+N more` truncation trailer is stamped so its rule-(i) blanks are
treated as replay artifacts), and replays every emit through the CURRENT deterministic walls — `gate_roster` then
`gate_data_instructions` (which runs `enforce_honest_blank`), in `layer2/build.py` ordering. The gates are imported
read-only; the tool never edits them.

## What it reports

- **per-rule blanks** — which wall blanked how many fields across how many emits:
  `rule_i_membership` (column/base-column absent from the basket, nameplate denominator empty, validate-FAIL),
  `rule_ii_reuse_smear`, `rule_iii_quantity_wall`, `rule_iiib_axis_coherence`, `rule_iiic_expectation`,
  `rule_iiid_boundary`, `rule_iv_const_source`;
- **suspected FALSE POSITIVES** — every blanked bind whose column quantity MATCHES its slot's quantity
  (same/compatible `layer2.quantity_class` class), flagged for human/agent review (full list in the JSON;
  `wall_replay.md_fp_cap` rows in the md);
- **bypass counts** — `$ctx`-sourced fields (total / kept / blanked / kept-with-off-basket-column),
  group-card emits, rule-(i) const/frame/time exemptions;
- gate/roster issue class counts, per-card rollups, corpus/skip accounting.

## How to run

```bash
cd pipeline_v48
PYTHONPATH=. python3.11 tools/wall_corpus_replay.py                       # full corpus → outputs/wall_replay_baseline.{json,md}
PYTHONPATH=. python3.11 tools/wall_corpus_replay.py --fresh-only          # outputs/logs only (smoke)
PYTHONPATH=. python3.11 tools/wall_corpus_replay.py --out-json /tmp/a.json --out-md /tmp/a.md   # candidate run
```

Config rows (cmd_catalog `app_config`, code-default fallback): `wall_replay.corpus_globs` (json),
`wall_replay.md_fp_cap` (int, default 60), `wall_replay.rule_examples_cap` (int, default 3).

## Acceptance procedure for a wall change

1. Before merging a gates/quantity-vocab change, run the tool to a scratch path.
2. Diff `per_rule`, `bypass`, and `false_positive_suspects` against the committed
   `outputs/wall_replay_baseline.json`.
3. Every NEW blank must be a real fabrication; every VANISHED blank must be an intended release; the FP-suspect
   list must not grow with quantity-matching binds. Then regenerate + commit the baseline.

Note the corpus is live-growing (concurrent sweeps append to `outputs/logs/`) — compare per-rule *composition*
on the shared corpus slice, or pin `--max-files` / archive-only globs when an exact A/B is needed.

## Replay-fidelity caveats (all conservative)

- The basket is the prompt's DB SCHEMA lines (incl. the `✗ FAILED-VALIDATION` verdict marker) — an OVERSIZED
  compacted prompt shows a capped basket, so those emits' rule-(i) blanks are flagged `replay_artifact`, never
  counted as catches.
- `exact_metadata` sibling-unit/label evidence uses the AI's raw skeleton (live path passes the
  `enforce_exact_metadata`-healed one); nameplate presence is unknown in the prompt → treated PRESENT, identical
  to the live basket (which carries no nameplate fold either).
