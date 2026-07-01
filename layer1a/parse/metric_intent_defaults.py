"""layer1a/parse/metric_intent_defaults.py — normalize metric to canonical vocab + clamp intent enum."""
from config.metrics import normalize_metric
from config.intents import INTENT_DEFAULT, INTENT_VOCAB


def clamp_metric_intent(metric, intent):
    metric = normalize_metric(metric)
    intent = (intent or INTENT_DEFAULT).strip().lower()
    if intent not in INTENT_VOCAB:
        intent = INTENT_DEFAULT
    return metric, intent
