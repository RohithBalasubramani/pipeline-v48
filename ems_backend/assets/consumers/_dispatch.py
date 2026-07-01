"""Category resolution for dispatcher → strategy lookup.

Dispatchers normally pick a strategy by `asset.asset_type.code` (chiller,
ahu, pump, compressor, sub_asset). Some assets may belong to a *named*
sub-category recognised by name prefix instead — e.g. a packaged HVAC plant
typed `chiller` but presented differently.

`resolve_category(asset)` returns the lookup key the dispatcher should use:

  - a derived category — when the asset name starts with a registered prefix
  - <asset_type.code> — fallback for everything else

Dispatchers should look up `STRATEGIES[category]` first; if missing, fall
back to `STRATEGIES[asset.asset_type.code]` so categories not configured for
a page transparently inherit the underlying type's behaviour.
"""

# (prefix, category_key) pairs — checked in order, first match wins.
# Empty by default; add rows here to introduce a derived category without a
# schema change (mirrors lt_panels' pcc_panel mechanism). Example:
#   _PREFIX_CATEGORIES = [('hvac plant', 'hvac_plant')]
_PREFIX_CATEGORIES: list[tuple[str, str]] = []


def resolve_category(asset) -> str:
    """Return the dispatcher lookup key for this asset."""
    name = (asset.name or '').strip().lower()
    for prefix, category in _PREFIX_CATEGORIES:
        if name.startswith(prefix):
            return category
    return asset.asset_type.code


def lookup_strategy(strategies: dict[str, type], asset):
    """Resolve `category → STRATEGIES[category]`, falling back to asset_type.code.

    Returns (StrategyCls, category_used) or (None, requested_category) if
    nothing matched (so the dispatcher can decide how to surface the error).
    """
    category = resolve_category(asset)
    cls = strategies.get(category)
    if cls is not None:
        return cls, category
    fallback_key = asset.asset_type.code
    if fallback_key != category:
        cls = strategies.get(fallback_key)
        if cls is not None:
            return cls, fallback_key
    return None, category
