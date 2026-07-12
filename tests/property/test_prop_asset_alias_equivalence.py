"""PROPERTY — "aliases must resolve identically": every human alias the resolver knows (the equipment-registry `aka`
column at row index 10 + cmd_catalog.pcc_panel_alias) must resolve to the SAME registry row as the canonical name.
  P1  every UNIQUELY-CLAIMED alias pins its owner row — and the owner's canonical name pins the same row (identity).
  P2  the same holds for ANY _norm-equal respelling of the alias ('PCC-1A' == 'pcc 1a' == 'Pcc_1A').
  P3  a COLLIDING alias (norm claimed by 2+ distinct rows, or shadowed by a canonical name) never confidently pins a
      row OUTSIDE its claimant set — honest ambiguity is legal, a silently wrong asset is not.
Claimant sets are computed from the RAW snapshot tables (not from resolver internals), so the oracle is independent.
"""
import pytest
from hypothesis import given, strategies as st

from tests.property.gen import norm_key, norm_mutants


@pytest.fixture(scope="session")
def alias_corpus(registry_snapshot):
    """{alias_norm: {'spelling', 'owners', 'canonical_rows'}} built from the raw aka column + pcc_panel_alias index.
    owners = rows that DECLARE the alias; canonical_rows = rows whose canonical NAME shares the norm (these shadow the
    alias — canonical resolution wins by design)."""
    cands = registry_snapshot["cands"]
    by_name = {c[1]: c for c in cands}
    cnorm = {}
    for c in cands:
        cnorm.setdefault(norm_key(c[1]), []).append(c)

    corpus = {}
    for c in cands:                                              # equipment aka column (index 10)
        if len(c) > 10 and c[10]:
            e = corpus.setdefault(norm_key(c[10]), {"spelling": str(c[10]), "owners": {}})
            e["owners"][str(c[0])] = c
    for alias_norm, panel_name in registry_snapshot["pcc_alias"].items():   # pcc_panel_alias (already normalized)
        row = by_name.get(panel_name)
        if row is not None:
            e = corpus.setdefault(alias_norm, {"spelling": alias_norm, "owners": {}})
            e["owners"][str(row[0])] = row
    for k, e in corpus.items():
        e["canonical_rows"] = {str(r[0]): r for r in cnorm.get(k, [])}
    return corpus


def _unique_entries(alias_corpus):
    """Aliases with exactly ONE claimant row overall (no canonical shadow, single owner) whose owner is pinnable."""
    out = []
    for k, e in alias_corpus.items():
        claim = dict(e["owners"])
        claim.update(e["canonical_rows"])
        if len(claim) == 1 and not e["canonical_rows"]:
            row = next(iter(claim.values()))
            if len(row) <= 9 or row[9]:                          # ghost owners can never pin — excluded by design
                out.append((k, e["spelling"], row))
    return out


def test_p1_every_unique_alias_pins_its_owner(resolve_offline, alias_corpus):
    entries = _unique_entries(alias_corpus)
    if not entries:
        pytest.skip("no uniquely-claimed aliases in the registry (equipment.alias knob off / nothing seeded)")
    assert len(entries) >= 5, f"suspiciously small alias corpus ({len(entries)}) — check the equipment.alias wiring"
    failures = []
    for _k, spelling, row in entries:
        resolve_offline["reply"] = {"names": [spelling], "confident": True}
        out = resolve_offline["resolve"](f"voltage for {spelling}")
        if out["asset"] is None or out["asset"]["mfm_id"] != int(row[0]):
            failures.append(f"alias {spelling!r}: expected mfm {row[0]} ({row[1]!r}), "
                            f"got {out['asset'] and out['asset']['mfm_id']} (how={out['how']})")
            continue
        resolve_offline["reply"] = {"names": [row[1]], "confident": True}
        ref = resolve_offline["resolve"](f"voltage for {row[1]}")
        if ref["asset"] is None or ref["asset"]["mfm_id"] != out["asset"]["mfm_id"]:
            failures.append(f"alias {spelling!r} and canonical {row[1]!r} resolve to DIFFERENT rows")
    assert not failures, "alias identity broken:\n" + "\n".join(failures)


@given(data=st.data())
def test_p2_alias_respellings_resolve_identically(resolve_offline, alias_corpus, data):
    entries = _unique_entries(alias_corpus)
    if not entries:
        pytest.skip("no uniquely-claimed aliases in the registry")
    _k, spelling, row = data.draw(st.sampled_from(entries))
    mutant = data.draw(norm_mutants(spelling))
    resolve_offline["reply"] = {"names": [mutant], "confident": True}
    out = resolve_offline["resolve"](f"voltage for {mutant}")
    assert out["asset"] is not None and out["asset"]["mfm_id"] == int(row[0]), (
        f"alias respelling {mutant!r} (of {spelling!r}) failed to pin its owner {row[1]!r}: "
        f"got {out['asset'] and out['asset']['mfm_id']} (how={out['how']})")


@given(data=st.data())
def test_p3_colliding_alias_never_pins_outside_claimants(resolve_offline, alias_corpus, data):
    colliding = []
    for k, e in alias_corpus.items():
        claim = set(e["owners"]) | set(e["canonical_rows"])
        if len(claim) > 1 or (e["canonical_rows"] and e["owners"] and set(e["owners"]) != set(e["canonical_rows"])):
            colliding.append((e["spelling"], claim))
    if not colliding:
        pytest.skip("no colliding aliases in this registry — nothing to check (good)")
    spelling, claim = data.draw(st.sampled_from(colliding))
    resolve_offline["reply"] = {"names": [spelling], "confident": True}
    out = resolve_offline["resolve"](f"voltage for {spelling}")
    if out["asset"] is not None:
        assert str(out["asset"]["mfm_id"]) in claim, (
            f"colliding alias {spelling!r} confidently pinned mfm {out['asset']['mfm_id']} OUTSIDE its claimants {claim}")
