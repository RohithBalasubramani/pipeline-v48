"""PROPERTY — layer1b.resolve.class_from_subject (the class prior that narrows the resolver's listing):
  P1  closure: ANY prompt yields a class that exists in the live registry, or None — never a phantom class.
  P2  a single unambiguous class token narrows to THAT class, in any casing, wrapped in any neutral words.
  P3  tokens from TWO different classes yield None — the prior never silently picks a side (the DG→UPS root cause).
  P4  case invariance: the prior is identical for a prompt and its upper-cased twin.
  P5  word-boundary rule: gluing alphanumerics onto a token defeats it ('upstream' must not hit the 'ups' token).
"""
from hypothesis import assume, given, strategies as st

from tests.property.gen import edge_mutants, st_junk


def _vocab(CS, registry_snapshot):
    """(known classes, {cls: [unique tokens]}, safe fillers) from the live hint policy + registry snapshot."""
    known = {c[5] for c in registry_snapshot["cands"] if c[5]}
    hints = CS._hints()
    all_kws = [k for spec in hints.values() for key in ("tokens", "concepts") for k in (spec or {}).get(key, []) if k]
    # tokens that hit EXACTLY one class in the deciding (tokens) pass — the only ones with a deterministic winner
    uniq = {}
    for cls, spec in hints.items():
        if cls not in known:
            continue
        for tok in (spec or {}).get("tokens", []):
            hit = [c for c, s in hints.items()
                   if c in known and any(CS._hit(f" {tok.lower()} ", t) for t in (s or {}).get("tokens", []))]
            if hit == [cls]:
                uniq.setdefault(cls, []).append(tok)
    safe = [w for w in ("please", "show", "the", "of", "for", "report", "overview", "status", "chart",
                        "trend", "daily", "summary", "site", "plant")
            if not any(CS._hit(f" {w} ", k) for k in all_kws)]
    return known, uniq, safe


@given(prompt=st.one_of(st.none(), st_junk))
def test_p1_closure(class_prior_offline, registry_snapshot, prompt):
    known = {c[5] for c in registry_snapshot["cands"] if c[5]}
    got = class_prior_offline.class_from_subject(prompt)
    assert got is None or got in known


@given(data=st.data())
def test_p2_single_token_narrows_to_its_class(class_prior_offline, registry_snapshot, data):
    known, uniq, safe = _vocab(class_prior_offline, registry_snapshot)
    assume(uniq and safe)
    cls = data.draw(st.sampled_from(sorted(uniq)))
    tok = data.draw(st.sampled_from(uniq[cls]))
    variant = data.draw(edge_mutants(tok))
    pre = data.draw(st.lists(st.sampled_from(safe), max_size=3))
    post = data.draw(st.lists(st.sampled_from(safe), max_size=3))
    prompt = " ".join(pre + [variant] + post)
    assert class_prior_offline.class_from_subject(prompt) == cls, f"{prompt!r} did not narrow to {cls}"


@given(data=st.data())
def test_p3_two_class_tokens_never_narrow(class_prior_offline, registry_snapshot, data):
    _known, uniq, safe = _vocab(class_prior_offline, registry_snapshot)
    assume(len(uniq) >= 2)
    a, b = data.draw(st.sampled_from([(x, y) for x in sorted(uniq) for y in sorted(uniq) if x < y]))
    prompt = " ".join([data.draw(st.sampled_from(uniq[a])), data.draw(st.sampled_from(safe)),
                       data.draw(st.sampled_from(uniq[b]))])
    assert class_prior_offline.class_from_subject(prompt) is None, (
        f"{prompt!r} names classes {a} AND {b} but the prior still narrowed")


@given(prompt=st_junk)
def test_p4_case_invariance(class_prior_offline, prompt):
    assert (class_prior_offline.class_from_subject(prompt)
            == class_prior_offline.class_from_subject(prompt.upper()))


@given(data=st.data())
def test_p5_glued_token_is_not_a_hit(class_prior_offline, registry_snapshot, data):
    _known, uniq, _safe = _vocab(class_prior_offline, registry_snapshot)
    assume(uniq)
    cls = data.draw(st.sampled_from(sorted(uniq)))
    tok = data.draw(st.sampled_from(uniq[cls]))
    glued = f"x{tok}9"                                            # alnum on both sides — the boundary must reject it
    assert class_prior_offline.class_from_subject(glued) != cls or any(
        class_prior_offline._hit(f" x{tok.lower()}9 ", t)
        for s in class_prior_offline._hints().values() for t in (s or {}).get("tokens", []))
