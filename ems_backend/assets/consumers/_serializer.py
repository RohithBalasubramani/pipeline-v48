def fallback(obj):
    """JSON serializer for datetime / Decimal fallbacks."""
    return str(obj)
