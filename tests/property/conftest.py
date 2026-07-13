"""tests/property/conftest.py — infrastructure for the property-based suite (fixtures only). [atomic]

TIERS
  offline (default run) — hundreds of randomized cases per property against the DETERMINISTIC seams (parse clamps,
    page-key fail-closed resolution, name/alias normalization, knowledge-gate plumbing, the host fork). The LLM is
    faked at each module's own `call_qwen` binding via a holder dict the test writes per example; every DB read on the
    exercised path is snapshotted ONCE per session from the REAL cmd_catalog/neuract rows — full data fidelity with no
    per-example round-trips and no TTL-expiry flake.
  live (-m live) — sampled metamorphic checks against the REAL pinned-seed Qwen on :8200 (llm.seed + temperature 0
    make the same prompt reproducible), auto-skipped when :8200 is unreachable. Scaled by PBT_LIVE_EXAMPLES.

ENV KNOBS
  PBT_EXAMPLES        hypothesis max_examples per offline property (default 150 → the whole tier runs thousands of
                      randomized cases; raise for a deeper soak, e.g. PBT_EXAMPLES=1000)
  PBT_LIVE_EXAMPLES   generated cases per live test (default 4)
  PBT_SEED            seed for the live-tier random generators (default 42; change to explore new mutants)
"""
import os

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile(
    "pbt",
    max_examples=int(os.environ.get("PBT_EXAMPLES", "150")),
    deadline=None,                       # session-snapshot warm-up + cfg cache refills blow the 200ms default
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,   # the suite-wide autouse cache-reset fixture is function-scoped
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,           # 'junk that collides with no real name/key' filters are assume-heavy
    ],
)
settings.load_profile("pbt")

PBT_SEED = int(os.environ.get("PBT_SEED", "42"))
LIVE_N = max(1, int(os.environ.get("PBT_LIVE_EXAMPLES", "4")))


# ── session snapshots (ONE real DB read each; real rows, zero per-example round-trips) ──────────────────────────────
# OUTAGE GUARD [audit TC-5 2026-07-12]: these snapshots are the offline tier's ONLY live-service dependency
# (cmd_catalog :5432 + the neuract :5433 value probe). On a machine without the tunnel they used to ERROR the whole
# "offline" tier (a wall of psycopg2 errors — the fake-red T8 warned about); a session-fixture pytest.skip() instead
# skips exactly the snapshot-dependent tests, honestly and machine-readably. DBs up → behavior byte-identical.

@pytest.fixture(scope="session")
def page_snapshot():
    """The 1a routing catalog exactly as route() reads it: raw specs, availability-filtered specs + keys, card
    titles, feasibility counts, and the POST-renderability-gate candidate keys (what the router can actually emit)."""
    from config.available_pages import filter_to_available
    from layer1a.db_reads.page_specs import read_page_specs
    from layer1a.db_reads.card_titles import read_card_titles
    from layer1a.db_reads.page_feasibility import read_page_feasibility
    from layer1a.parse.template_feasibility_gate import filter_renderable_templates
    try:
        raw = read_page_specs()
        avail = filter_to_available(raw)
        keys = [s["page_key"] for s in avail]
        feas = read_page_feasibility(keys)
        titles = read_card_titles()
    except Exception as e:
        pytest.skip(f"cmd_catalog (:5432) unreachable — page-snapshot property tests skipped: {type(e).__name__}: {e}")
    eff, _dropped = filter_renderable_templates(list(avail), feas)
    return {"raw": raw, "avail": avail, "keys": keys, "titles": titles, "feas": feas,
            "eff_keys": [s["page_key"] for s in eff]}


@pytest.fixture(scope="session")
def registry_snapshot():
    """The 1b asset registry exactly as resolve_asset() reads it: candidate rows (with aka aliases at index 10), the
    PCC-panel alias index, and the value-bearing table set the candidate dedup consults."""
    from layer1b.resolve.asset_candidates import asset_candidates
    from layer1b.resolve.asset_resolve import _pcc_alias_index
    from layer1b.resolve.has_data import tables_with_values
    try:
        cands = asset_candidates()
        live = tables_with_values([c[2] for c in cands if c[2] and (len(c) <= 9 or c[9])])
        pcc_alias = _pcc_alias_index()
    except Exception as e:
        pytest.skip(f"cmd_catalog (:5432) / neuract (:5433) unreachable — registry-snapshot property tests "
                    f"skipped: {type(e).__name__}: {e}")
    return {"cands": cands, "pcc_alias": pcc_alias, "live_tables": set(live)}


# ── offline harnesses (holder-driven fake LLM at each module's own call_qwen binding) ───────────────────────────────

@pytest.fixture()
def route_offline(monkeypatch, page_snapshot):
    """layer1a.route with its catalog reads snapshot-pinned and call_qwen holder-faked. Set holder['reply'] per
    example; route() then behaves EXACTLY as if the router model emitted that JSON."""
    import layer1a.route as R
    holder = {"reply": {}}
    monkeypatch.setattr(R, "read_page_specs", lambda db="cmd_catalog": list(page_snapshot["raw"]))
    monkeypatch.setattr(R, "filter_to_available", lambda specs: list(page_snapshot["avail"]))
    monkeypatch.setattr(R, "read_card_titles", lambda db="cmd_catalog": page_snapshot["titles"])
    monkeypatch.setattr(R, "read_page_feasibility", lambda keys, db="cmd_catalog": page_snapshot["feas"])
    monkeypatch.setattr(R, "call_qwen", lambda system, user, **kw: holder["reply"])
    holder["route"] = R.route
    return holder


@pytest.fixture()
def resolve_offline(monkeypatch, registry_snapshot):
    """layer1b resolve_asset with the registry/alias/value reads snapshot-pinned and call_qwen holder-faked (every
    transient-retry attempt sees the same holder['reply']; a {'_llm_error': ...} marker therefore exercises the
    llm_failed degrade path — bare {} is now an honest 'model chose to emit nothing')."""
    import layer1b.resolve.asset_resolve as AR
    import layer1b.resolve.class_from_subject as CS
    import layer1b.resolve.empty_fallback as EF
    import layer1b.resolve.ambiguous_candidates as AC
    cands, live = registry_snapshot["cands"], registry_snapshot["live_tables"]
    holder = {"reply": {}, "calls": 0}

    def fake_llm(system, user, **kw):
        holder["calls"] += 1
        return holder["reply"]

    monkeypatch.setattr(AR, "asset_candidates", lambda: cands)
    monkeypatch.setattr(CS, "asset_candidates", lambda: cands)
    monkeypatch.setattr(EF, "asset_candidates", lambda: cands)
    monkeypatch.setattr(EF, "reason", lambda cause, **kw: "no data")             # reason_template is a per-call DB read
    monkeypatch.setattr(AR, "_pcc_alias_index", lambda: dict(registry_snapshot["pcc_alias"]))
    monkeypatch.setattr(AC, "tables_with_values", lambda tables, k=None: {t for t in tables if t in live})
    monkeypatch.setattr(AR, "call_qwen", fake_llm)
    holder["resolve"] = AR.resolve_asset
    return holder


@pytest.fixture()
def class_prior_offline(monkeypatch, registry_snapshot):
    """class_from_subject with its registry read snapshot-pinned (the module under test, returned for direct use)."""
    import layer1b.resolve.class_from_subject as CS
    monkeypatch.setattr(CS, "asset_candidates", lambda: registry_snapshot["cands"])
    return CS


@pytest.fixture()
def knowledge_offline(monkeypatch):
    """knowledge.ems with call_qwen holder-faked. holder['raise']=True simulates a transport-layer exception;
    holder['calls'] counts gate invocations (the pinned-repost property asserts the gate is SKIPPED)."""
    import knowledge.ems as KE
    holder = {"reply": {}, "raise": False, "calls": 0}

    def fake_llm(system, user, **kw):
        holder["calls"] += 1
        if holder["raise"]:
            raise RuntimeError("simulated transport failure")
        return holder["reply"]

    monkeypatch.setattr(KE, "call_qwen", fake_llm)
    return holder


@pytest.fixture()
def host_offline(monkeypatch, knowledge_offline):
    """host/server.handle_run with the card pipeline replaced by a counting sentinel, the multi-asset preflight
    neutralized, response dumping + obs stage rows no-op'd, and the knowledge gate driven by knowledge_offline."""
    import host.server as HS
    import host.multi_asset as MA
    import obs.stage as OS
    calls = {"pipeline": 0}

    def fake_build_response(prompt, asset_id=None, date_window=None):
        calls["pipeline"] += 1
        return {"ok": True, "prompt": prompt, "_sentinel": "pipeline", "asset_id": asset_id}

    monkeypatch.setattr(HS, "build_response", fake_build_response)
    monkeypatch.setattr(HS, "_dump_response", lambda resp: None)
    monkeypatch.setattr(MA, "build_response_multi",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("multi-asset path must not run")))
    monkeypatch.setattr(OS, "stage", lambda *a, **k: None)
    return {"gate": knowledge_offline, "calls": calls, "handle_run": HS.handle_run}


# ── live tier ────────────────────────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def qwen_live():
    """Skip the live metamorphic tier when the pinned-seed Qwen on :8200 is unreachable (never a false red)."""
    import urllib.request
    from llm.config import LLM_URL
    probe = LLM_URL.rsplit("/chat/completions", 1)[0] + "/models"
    try:
        urllib.request.urlopen(probe, timeout=5)
    except Exception as e:
        pytest.skip(f"live Qwen unreachable at {probe} — live property tier skipped: {e}")
