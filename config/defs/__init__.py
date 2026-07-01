"""config/defs/ — per-concern atomic config declarations. ALL_DEFS = every concern's CONFIG, flattened with
its section, for the seed + any consumer that needs the full set. [atomic DB-config barrel]"""
from config.defs import card_grid_size as _card_grid_size
from config.defs import cards_intent as _cards_intent
from config.defs import ems_backend as _ems_backend
from config.defs import flags as _flags
from config.defs import gates as _gates
from config.defs import intents as _intents
from config.defs import metrics as _metrics
from config.defs import payload_shapes as _payload_shapes
from config.defs import routes as _routes
from config.defs import swap as _swap
from config.defs import validation as _validation
from config.defs import windows as _windows

ALL_DEFS = [
    *[dict(d, section='card_grid_size') for d in _card_grid_size.CONFIG],
    *[dict(d, section='cards_intent') for d in _cards_intent.CONFIG],
    *[dict(d, section='ems_backend') for d in _ems_backend.CONFIG],
    *[dict(d, section='flags') for d in _flags.CONFIG],
    *[dict(d, section='gates') for d in _gates.CONFIG],
    *[dict(d, section='intents') for d in _intents.CONFIG],
    *[dict(d, section='metrics') for d in _metrics.CONFIG],
    *[dict(d, section='payload_shapes') for d in _payload_shapes.CONFIG],
    *[dict(d, section='routes') for d in _routes.CONFIG],
    *[dict(d, section='swap') for d in _swap.CONFIG],
    *[dict(d, section='validation') for d in _validation.CONFIG],
    *[dict(d, section='windows') for d in _windows.CONFIG],
]
