"""Category resolution for dispatcher → strategy lookup.

Dispatchers normally pick a strategy by `mfm.mfm_type.code` (transformer,
lt_panel, ht_panel, ups, apfc, sub_panel). Some MFMs belong to a *named*
sub-category that's recognised by name prefix instead — e.g. a PCC Panel is
typed `lt_panel` in the DB but its presentation differs.

`resolve_category(mfm)` returns the lookup key the dispatcher should use:

  - 'pcc_panel'     — name starts with "PCC Panel" (case-insensitive)
  - <mfm_type.code> — fallback for everything else

Dispatchers should look up `STRATEGIES[category]` first; if that's missing,
fall back to `STRATEGIES[mfm.mfm_type.code]` so categories that aren't
configured for a given page transparently inherit the underlying type's
behaviour.
"""
import re

# (prefix, category_key) pairs — checked in order, first match wins.
# Add more rows here when a new named category is introduced.
_PREFIX_CATEGORIES: list[tuple[str, str]] = [
    ('pcc panel', 'pcc_panel'),
]


def resolve_category(mfm) -> str:
    """Return the dispatcher lookup key for this MFM. The name is normalized (separators → single space) so the
    prefix matches regardless of punctuation — 'PCC-Panel-1', 'PCC_Panel_1' and 'PCC Panel 1 A' all → 'pcc_panel'."""
    name = re.sub(r'[^a-z0-9]+', ' ', (mfm.name or '').lower()).strip()
    for prefix, category in _PREFIX_CATEGORIES:
        if name.startswith(prefix):
            return category
    return mfm.mfm_type.code


def lookup_strategy(strategies: dict[str, type], mfm):
    """Resolve `category → STRATEGIES[category]`, falling back to mfm_type.code.

    Returns (StrategyCls, category_used) or (None, requested_category) if
    nothing matched (so the dispatcher can decide how to surface the error).
    """
    category = resolve_category(mfm)
    cls = strategies.get(category)
    if cls is not None:
        return cls, category
    fallback_key = mfm.mfm_type.code
    if fallback_key != category:
        cls = strategies.get(fallback_key)
        if cls is not None:
            return cls, fallback_key
    return None, category
