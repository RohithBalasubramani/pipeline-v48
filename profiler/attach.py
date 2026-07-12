"""profiler/attach.py — monkeypatch the V48 pipeline for live latency spans.

MUST be installed before any pipeline consumer module is imported: every hot call
site binds names via `from X import f` at module top, so install() imports each
DEFINING module, wraps its functions in place, and only then imports the consumers
(run.harness, host.assemble, host.server, ...) so their bindings resolve to the
wrappers. verify() asserts the load-bearing consumer bindings actually took —
a silent miss would just under-report a stage, so it's checked, not assumed.

Wrap map (from outputs/notes/latency_profiler_map.md, verified 2026-07-12):
  stage spans   knowledge.ems.ask, layer1a.build.run_1a/run_1a_to,
                layer1b.build.run_1b, layer1a.story_builder.build_stories,
                run.layer2_all.run_2_all, layer2.build.run_card,
                validate.build.run_validate, validate.render_verdict.compute,
                host.exec_cards._run_cards + fill_one_card, ems_exec.serve.run.run_card,
                host.enrich._enrich_card, host.assemble.assemble_cards,
                run.harness.run_pipeline
  ai            llm.client.call_qwen (stage-tagged), ems_exec.renderers._insight._post
  database      data.db_client.q + pg_connect, ems_exec.data.neuract._run,
                data.neuract_live._db.rows/dicts, validate.payload_lookup.*

Per-card wrappers execute inside the ThreadPool worker that runs the card, so
setting spans.current_stage there attributes nested DB/AI calls correctly without
touching the bare ex.submit() sites.
"""
import functools
import importlib

from profiler import spans


def _wrap(module, fn_name, stage, *, set_current=False, meta_fn=None):
    orig = getattr(module, fn_name)
    if getattr(orig, "_prof_wrapped", False):
        return orig

    @functools.wraps(orig)
    def wrapper(*a, **kw):
        meta = {}
        try:
            if meta_fn:
                meta = meta_fn(a, kw) or {}
            if stage in ("database", "ai"):
                meta.setdefault("at", spans.current_stage.get())
        except Exception:
            meta = {}
        with spans.span(stage, set_current=set_current, **meta):
            return orig(*a, **kw)

    wrapper._prof_wrapped = True
    wrapper._prof_orig = orig
    setattr(module, fn_name, wrapper)
    return wrapper


def install():
    """Import-order-sensitive: defining modules first, consumers last."""
    # -- cross-cutting choke points (must precede EVERY consumer import) --
    llm_client = importlib.import_module("llm.client")
    _wrap(llm_client, "call_qwen", "ai",
          meta_fn=lambda a, kw: {"kind": kw.get("stage") or "?"})

    db_client = importlib.import_module("data.db_client")
    _wrap(db_client, "q", "database",
          meta_fn=lambda a, kw: {"db": f"psql:{a[0] if a else kw.get('db', '?')}"})
    _wrap(db_client, "pg_connect", "database", meta_fn=lambda a, kw: {"db": "pg_connect"})

    neuract_ts = importlib.import_module("ems_exec.data.neuract")
    _wrap(neuract_ts, "_run", "database", meta_fn=lambda a, kw: {"db": "neuract_ts"})

    neuract_meta = importlib.import_module("data.neuract_live._db")
    _wrap(neuract_meta, "rows", "database", meta_fn=lambda a, kw: {"db": "neuract_meta"})
    _wrap(neuract_meta, "dicts", "database", meta_fn=lambda a, kw: {"db": "neuract_meta"})

    payload_lookup = importlib.import_module("validate.payload_lookup")
    _wrap(payload_lookup, "card_payloads_for", "database", meta_fn=lambda a, kw: {"db": "card_payloads"})
    _wrap(payload_lookup, "card_payloads_home", "database", meta_fn=lambda a, kw: {"db": "card_payloads"})

    insight = importlib.import_module("ems_exec.renderers._insight")
    _wrap(insight, "_post", "ai", meta_fn=lambda a, kw: {"kind": "insight_post"})

    # -- stage entry points (defining modules; consumers bind these on import) --
    knowledge = importlib.import_module("knowledge.ems")
    _wrap(knowledge, "ask", "knowledge_gate", set_current=True)

    story_builder = importlib.import_module("layer1a.story_builder")
    _wrap(story_builder, "build_stories", "story_selection", set_current=True)

    l1a_build = importlib.import_module("layer1a.build")   # binds build_stories wrapper
    _wrap(l1a_build, "run_1a", "page_selection", set_current=True)
    if hasattr(l1a_build, "run_1a_to"):
        _wrap(l1a_build, "run_1a_to", "page_selection", set_current=True,
              meta_fn=lambda a, kw: {"note": "granularity_reconcile"})

    l1b_build = importlib.import_module("layer1b.build")
    _wrap(l1b_build, "run_1b", "asset_resolution", set_current=True)

    l2_build = importlib.import_module("layer2.build")
    _wrap(l2_build, "run_card", "layer2_card", set_current=True,
          meta_fn=lambda a, kw: {"card": kw.get("card_id")})

    l2_all = importlib.import_module("run.layer2_all")     # binds layer2.build.run_card wrapper
    _wrap(l2_all, "run_2_all", "layer2", set_current=True)

    v_build = importlib.import_module("validate.build")
    _wrap(v_build, "run_validate", "validation", set_current=True)

    v_verdict = importlib.import_module("validate.render_verdict")
    _wrap(v_verdict, "compute", "validation_verdict", set_current=True)

    exec_run = importlib.import_module("ems_exec.serve.run")
    _wrap(exec_run, "run_card", "executor_core", set_current=True,
          meta_fn=lambda a, kw: {"card": kw.get("card_id")})

    enrich = importlib.import_module("host.enrich")
    _wrap(enrich, "_enrich_card", "rendering_card", set_current=True)

    exec_cards = importlib.import_module("host.exec_cards")   # binds enrich pieces
    _wrap(exec_cards, "_run_cards", "executor", set_current=True,
          meta_fn=lambda a, kw: {"n_cards": len(a[0]) if a and hasattr(a[0], "__len__") else None})
    _wrap(exec_cards, "fill_one_card", "executor_card", set_current=True,
          meta_fn=lambda a, kw: {"card": kw.get("cid")})

    assemble = importlib.import_module("host.assemble")       # binds _run_cards/_enrich_card wrappers
    _wrap(assemble, "assemble_cards", "assembly_total", set_current=True)

    harness = importlib.import_module("run.harness")          # binds run_1a/run_1b/run_2_all/run_validate wrappers
    _wrap(harness, "run_pipeline", "pipeline_total", set_current=True)

    multi = importlib.import_module("host.multi_asset")       # binds assemble/resolve wrappers
    _wrap(multi, "natural_compare_ids", "asset_resolution", set_current=True,
          meta_fn=lambda a, kw: {"note": "natural_compare"})

    server = importlib.import_module("host.server")           # binds run_pipeline + fill_one_card wrappers
    return server


def verify(server):
    """Assert every load-bearing consumer binding is the wrapper (import-order proof)."""
    harness = importlib.import_module("run.harness")
    assemble = importlib.import_module("host.assemble")
    l2_all = importlib.import_module("run.layer2_all")
    l1a_build = importlib.import_module("layer1a.build")
    emit = importlib.import_module("layer2.emit.emit")
    checks = {
        "run.harness.run_1a": harness.run_1a,
        "run.harness.run_1b": harness.run_1b,
        "run.harness.run_2_all": harness.run_2_all,
        "run.harness.run_validate": harness.run_validate,
        "run.layer2_all.run_card": l2_all.run_card,
        "layer1a.build.build_stories": l1a_build.build_stories,
        "layer2.emit.emit.call_qwen": emit.call_qwen,
        "host.assemble._run_cards": assemble._run_cards,
        "host.assemble._enrich_card": assemble._enrich_card,
        "host.server.fill_one_card": server.fill_one_card,
        "host.server.run_pipeline": server.run_pipeline,
    }
    missed = [name for name, fn in checks.items() if not getattr(fn, "_prof_wrapped", False)]
    if missed:
        raise RuntimeError(f"profiler bindings missed (import-order bug): {missed}")
