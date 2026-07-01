"""layer1a/parse/page_key_fallback.py — verbatim page_key check + substring near-miss -> first page fallback."""


def resolve_page_key(pk, keys):
    if pk in keys:
        return pk
    if pk:
        m = next((k for k in keys if str(pk).lower() in k.lower()), None)
        if m:
            return m
    return keys[0]
