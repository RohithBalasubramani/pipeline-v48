"""profiler/ — latency profiler for the V48 pipeline.

One single-purpose file per concern:
  spans.py    in-process span collector (contextvar run scope, thread-safe)
  attach.py   monkeypatch instrumentation over the real pipeline stage entry points
  logmine.py  mine historical outputs/logs/pipeline_*.jsonl + ai_*.jsonl into samples
  stats.py    avg / median / p95 / p99 / min / max / worst-cases over samples
  report.py   markdown report writer
  charts.py   matplotlib PNG charts
  live.py     live profiling harness (prompt corpus -> run_pipeline under attach)
  cli.py      python -m profiler.cli  mine | live | all

Stages measured: knowledge_gate, asset_resolution, page_selection, story_selection,
layer2, executor, validation, rendering — plus cross-cutting database and ai time.
"""
