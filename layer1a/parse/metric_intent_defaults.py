"""layer1a/parse/metric_intent_defaults.py — normalize metric to canonical vocab + clamp intent enum."""
from config.metrics import normalize_metric
from config import intents as _intents   # lazy module attrs — read per call so DB row edits reach the clamp live


def clamp_metric_intent(metric, intent):
    metric = normalize_metric(metric)
    default = _intents.INTENT_DEFAULT
    intent = (intent or default).strip().lower()
    if intent not in _intents.INTENT_VOCAB:
        intent = default
    return metric, intent
