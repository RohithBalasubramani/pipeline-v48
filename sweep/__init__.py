"""validation/ — the V48 PIPELINE VALIDATION FRAMEWORK: continuously exercise every workflow of the prompt pipeline
(hundreds/thousands of generated prompts, parallel, throttled), capture per-stage logs, judge each outcome against its
category's expectation, compute coverage vs the cmd_catalog universe, detect regressions, and make every failure
replayable. NOT a benchmark, NOT a unit suite — a failure-mode exposer.

Modules (atomic — one concern each):
  config.py               knobs (API base, concurrency, timeouts, output dirs) — env + cmd_catalog-overridable
  response.py             the ONE /api/run response parser (every field gotcha lives here, nowhere else)
  corpus/universe.py      the cmd_catalog ground-truth universe (assets, classes, aliases, pages, cards)
  corpus/store.py         DB-driven template/vocab loader (prompt_category/prompt_template/prompt_vocab rows)
  corpus/templates.py     code-default mirror of the seeded rows (the workflow taxonomy; DB-down fallback)
  corpus/fill.py          slot engine: ground one template row over universe x vocab (explosion-safe)
  corpus/mutators/        mutation families (casing/spelling/abbrev/partial/plural/aliasing/conversational)
  corpus/mutate.py        mutation composer: per-case deterministic expansion + the classic mangle probe set
  corpus/generate.py      templates x universe x mutators -> corpus JSONL (category budgets = the size dial)
  runner.py               parallel prompt executor (configurable concurrency, auto-throttle, artifact capture)
  checks/expectations.py  per-category outcome judge (cards / picker / knowledge / refused / empty / compare-groups)
  checks/datesync.py      interactive date-sync checks (/api/frame reslice; history reload, snapshot unchanged)
  checks/determinism.py   same-prompt repeat comparison (page / cards / metadata / payload structure)
  coverage.py             achieved-vs-universe coverage matrix + uncovered-path report
  failures.py             failure collector (stage attribution + outputs/logs correlation by run_id)
  metrics.py              latency/percentile metrics
  report_json.py          deterministic machine-readable report
  report_html.py          self-contained human dashboard (summary, coverage, failure groups)
  replay.py               re-run any saved case with identical inputs (debugging)
  cli.py                  entrypoint: generate | run | report | replay | coverage

Run:  python -m sweep.cli generate            # build the corpus from the live universe
      python -m sweep.cli run --limit 200 --concurrency 3
      python -m sweep.cli report
      python -m sweep.cli replay <case_id>
"""
