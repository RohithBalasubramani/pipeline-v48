"""workers/ — DATA-source + window helpers reused by the host frame-fetch (sources/ems_backend_source + ems_window).
The server-side PARSE→FILL→STITCH path was removed: DATA now fills LIVE on the FRONTEND from the ems_backend frame via
each CMD V2 card's OWN mapper (run/layer2_all._fill emits fill_source='live-frontend'). NEVER touches exact_metadata."""
