"""validation/corpus/store.py — the DB-DRIVEN template/vocab loader: prompt_category + prompt_template + prompt_vocab
rows from cmd_catalog, fail-open to the code-default mirror (templates.py — exactly the seeded rows) when the tables
are absent or the DB is down: a generation run behaves identically either way until someone EDITS a row [config → DB].
One read, process-cached, ascii-sanitized at the boundary (surrogate safety). Seed: db/seed_prompt_corpus.sql."""
from __future__ import annotations

from functools import lru_cache

from sweep.corpus.templates import defaults
from sweep.response import ascii_safe


@lru_cache(maxsize=1)
def store() -> dict:
    """{categories: {cat: {expect,budget}}, templates: [{tkey,category,template,expect,weight}],
    vocab: {kind: [{value,meta}]}, source: 'db'|'code-default'} — enabled rows only."""
    from data import db_client
    try:
        cats = {ascii_safe(r[0]): {"expect": ascii_safe(r[1]), "budget": int(r[2])}
                for r in db_client.q("cmd_catalog",
                                     "SELECT category, expect, budget FROM prompt_category WHERE enabled ORDER BY category")}
        tmpls = [{"tkey": ascii_safe(r[0]), "category": ascii_safe(r[1]), "template": ascii_safe(r[2]),
                  "expect": ascii_safe(r[3]) or None, "weight": int(r[4])}
                 for r in db_client.q("cmd_catalog",
                                      "SELECT tkey, category, template, expect, weight FROM prompt_template "
                                      "WHERE enabled ORDER BY tkey")]
        vocab: dict[str, list[dict]] = {}
        for r in db_client.q("cmd_catalog",
                             "SELECT kind, value, meta FROM prompt_vocab WHERE enabled ORDER BY kind, value"):
            vocab.setdefault(ascii_safe(r[0]), []).append({"value": ascii_safe(r[1]), "meta": ascii_safe(r[2])})
        if not cats or not tmpls:                      # tables exist but empty -> behave as unseeded
            return defaults()
        return {"categories": cats, "templates": tmpls, "vocab": vocab, "source": "db"}
    except Exception:                                  # tables absent / DB down -> code-default mirror (fail-open)
        return defaults()


def reload() -> None:
    """Drop the process cache (after seeding/editing rows in the same process)."""
    store.cache_clear()


def metrics_for(cls: str, vocab: dict) -> list[str]:
    """Metric surface forms applicable to an asset class ('' meta = every class; 'A+B' compare pairs get the ''-set)."""
    out = []
    for row in vocab.get("metric", []):
        classes = [c for c in (row["meta"] or "").split(",") if c]
        if not classes or cls in classes:
            out.append(row["value"])
    return out
