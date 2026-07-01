"""config/defs/ems_backend.py — ATOMIC config declaration for the `ems_backend` concern: the operational knobs the
pipeline-side data-fill worker (workers/fill/sources/ems_backend_source.py) + host frame-fetch (host/server.py) use to
reach V48's ems_backend WS dispatcher. These are genuine site-tunable ceilings/retries (NOT the WS host/port wiring,
which stays structural in config/ems_backend.py). cfg() reads them from cmd_catalog.app_config; seed_app_config.py
upserts from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'ems_backend.connect_timeout_s', "default": 8, "data_type": 'number'},    # WS connect timeout
    {"key": 'ems_backend.frame_timeout_s', "default": 60, "data_type": 'number'},     # per-frame snapshot CEILING (big-panel aggregate fan-out)
    {"key": 'ems_backend.fetch_attempts', "default": 3, "data_type": 'int'},          # transient-flake retry count
    {"key": 'ems_backend.retry_backoff_s', "default": 0.4, "data_type": 'number'},    # per-attempt backoff (grows ×attempt)
    {"key": 'ems_backend.frame_budget_s', "default": 45, "data_type": 'number'},      # host total parallel deadline for ALL page frame fetches
]
