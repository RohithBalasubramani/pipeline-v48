"""config/defs/metrics.py — ATOMIC config declaration for the `metrics` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'metrics.aliases', "default": '{"power factor": "pf", "reactive power": "pf", "powerfactor": "pf", "harmonic distortion": "thd", "harmonics": "thd", "total harmonic distortion": "thd", "distortion": "thd", "power quality": "thd", "pq": "thd", "voltage/current": "voltage", "current/voltage": "voltage", "voltage and current": "voltage", "amps": "current", "ampere": "current", "amperage": "current", "amperes": "current", "volt": "voltage", "volts": "voltage", "kv": "voltage", "kw": "power", "kva": "power", "kilowatt": "power", "load": "power", "demand": "power", "supply": "power", "kwh": "energy", "consumption": "energy", "kwh consumption": "energy", "temp": "temperature", "thermal": "temperature", "heat": "temperature", "freq": "frequency", "hz": "frequency"}', "data_type": 'json'},
    {"key": 'metrics.default', "default": 'power', "data_type": 'text'},
    {"key": 'metrics.vocab', "default": '["current", "voltage", "power", "energy", "thd", "pf", "frequency", "temperature"]', "data_type": 'json'},
]
