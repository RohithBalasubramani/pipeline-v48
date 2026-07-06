# fe_contract — the FE-OWNED hook integration CONTRACT (NOT code V48 writes)

The hook (useRealTimeMonitoringData-style) is OWNED BY THE FRONTEND. V48 emits `{exact_metadata, data_instructions}` + the filled DATA; the FE hook owns live state, interactivity, and interdependency (the useState cells + handlers) and recomputes per-card payloads via useMemo. This folder is the CONTRACT V48 must satisfy, not files V48 ships.
