"""PROPERTY — resolve_asset NEVER fabricates, for ARBITRARY model emissions (offline: registry snapshot-pinned,
resolver LLM holder-faked):
  P1  outcome closure: how ∈ {AI, no_data, ambiguous, empty, user-choice}; every pinned/candidate id EXISTS in the
      registry; a confident pin only happens on a truthy `confident`; how='AI' implies a renderable (non-ghost,
      data-bearing) asset — the no_data gate and the ghost rule are unbypassable.
  P2  junk names (norm-disjoint from every canonical name AND alias) NEVER pin — fuzzy recovery is ambiguous-only.
  P3  a transport-dead LLM ({} twice) degrades to the browse picker (candidates offered), never a silent empty.
  P4  a pinned picker round-trip (asset_id_override) is honored EXACTLY, without consulting the LLM at all; a bogus
      override falls through to resolution instead of crashing.
"""
from hypothesis import assume, given, strategies as st

from tests.property.gen import norm_key, st_junk

HOWS = {"AI", "no_data", "ambiguous", "empty", "user-choice"}


def _reply_strategy(names):
    name_like = st.one_of(st_junk, st.sampled_from(names))
    return st.one_of(
        st.just({}),
        st.fixed_dictionaries({}, optional={
            "names": st.lists(name_like, max_size=4),
            "confident": st.one_of(st.booleans(), st.none(), st.integers(0, 1), st.just("yes"), st.just("")),
            "candidates": st.lists(name_like, max_size=6),
        }),
    )


@given(data=st.data())
def test_p1_outcome_closure(resolve_offline, registry_snapshot, data):
    cands = registry_snapshot["cands"]
    ids = {str(c[0]) for c in cands}
    ghosts = {str(c[0]) for c in cands if len(c) > 9 and not c[9]}
    reply = data.draw(_reply_strategy([c[1] for c in cands]))
    resolve_offline["reply"] = reply
    out = resolve_offline["resolve"](data.draw(st_junk))

    assert out["how"] in HOWS
    if out.get("asset"):
        assert str(out["asset"]["mfm_id"]) in ids, f"pinned an id OUTSIDE the registry: {out['asset']['mfm_id']}"
    for c in out.get("candidates") or []:
        assert str(c["mfm_id"]) in ids, f"candidate id OUTSIDE the registry: {c['mfm_id']}"
    if out["how"] == "AI":
        assert bool(reply.get("confident", False)), "confident pin without a truthy `confident`"
        assert out["asset"]["has_data"], "how='AI' shipped a data-empty asset past the no_data gate"
        assert str(out["asset"]["mfm_id"]) not in ghosts, "pinned a ghost (table_exists=False) row"


@given(data=st.data())
def test_p2_unresolvable_names_never_pin(resolve_offline, registry_snapshot, data):
    cands = registry_snapshot["cands"]
    known = {norm_key(c[1]) for c in cands if c[1]}
    known |= {norm_key(c[10]) for c in cands if len(c) > 10 and c[10]}
    known |= set(registry_snapshot["pcc_alias"])
    names = data.draw(st.lists(st_junk, min_size=1, max_size=3))
    assume(all(norm_key(n) and norm_key(n) not in known for n in names))
    resolve_offline["reply"] = {"names": names, "confident": True}
    out = resolve_offline["resolve"]("show me something")
    assert out["how"] == "ambiguous" and out["asset"] is None, (
        f"unresolvable names {names!r} produced how={out['how']!r} asset={out['asset']!r} — junk must never pin")


def test_p3_dead_llm_degrades_to_browse_picker(resolve_offline):
    resolve_offline["reply"] = {"_llm_error": "http"}            # every transient-retry attempt comes back dead
    out = resolve_offline["resolve"]("voltage of the main panel")
    assert out["how"] == "ambiguous" and out["candidates"], "LLM outage must surface the browse picker, not a dead end"
    assert out["llm_failed"] is True


@given(data=st.data())
def test_p4_pinned_override_honored_exactly(resolve_offline, registry_snapshot, data):
    row = data.draw(st.sampled_from(registry_snapshot["cands"]))
    resolve_offline["calls"] = 0
    resolve_offline["reply"] = {"names": ["IRRELEVANT"], "confident": True}
    out = resolve_offline["resolve"]("anything at all", asset_id_override=row[0])
    assert out["how"] in ("user-choice", "no_data")
    assert str(out["asset"]["mfm_id"]) == str(row[0]), "picker pin was not honored exactly"
    assert resolve_offline["calls"] == 0, "pinned round-trip must skip the resolution LLM entirely"


@given(bogus=st_junk)
def test_p4_bogus_override_falls_through(resolve_offline, registry_snapshot, bogus):
    assume(bogus not in {str(c[0]) for c in registry_snapshot["cands"]})
    resolve_offline["reply"] = {}
    out = resolve_offline["resolve"]("x", asset_id_override=bogus)
    assert out["how"] in HOWS                                    # never a KeyError/crash on an unknown pin
