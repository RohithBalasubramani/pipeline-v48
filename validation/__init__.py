"""validation/ — the V48 PIPELINE VALIDATION FRAMEWORK: continuously exercise every workflow of the prompt pipeline
(hundreds/thousands of generated prompts, parallel, throttled), capture per-stage logs, judge each outcome against its
category's expectation, compute coverage vs the cmd_catalog universe, detect regressions, and make every failure
replayable. NOT a benchmark, NOT a unit suite — a failure-mode exposer.

Modules (atomic — one concern each):
  config.py               knobs (API base, concurrency, timeouts, output dirs) — env + cmd_catalog-overridable
  response.py             the ONE /api/run response parser (every field gotcha lives here, nowhere else)
  corpus/universe.py      the cmd_catalog ground-truth universe (assets, classes, aliases, pages, cards)
  corpus/templates.py     per-category prompt templates (the workflow taxonomy)
  corpus/generate.py      template x universe permutation generator -> corpus JSONL
  corpus/mutate.py        spelling/case/spacing/punctuation mutators for alias-robustness coverage
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

Run:  python -m validation.cli generate            # build the corpus from the live universe
      python -m validation.cli run --limit 200 --concurrency 3
      python -m validation.cli report
      python -m validation.cli replay <case_id>
"""
