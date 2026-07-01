import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# `layer2` is ALSO a package at the grandparent backend/layer2/, and pytest prepends `backend` to
# sys.path[0] — shadowing our package. While ROOT is first here, pin `layer2` -> pipeline_v48/layer2
# in sys.modules so every later `import layer2.*` binds to THIS pipeline regardless of path order.
for _m in [m for m in list(sys.modules) if m == "layer2" or m.startswith("layer2.")]:
    _f = getattr(sys.modules[_m], "__file__", "") or ""
    if not os.path.abspath(_f).startswith(ROOT):
        del sys.modules[_m]
import layer2 as _layer2  # noqa: E402  (cache the correct package now, while ROOT is sys.path[0])
assert os.path.abspath(_layer2.__file__).startswith(ROOT), _layer2.__file__

import obs.ai_log as _ai  # noqa: E402  (install the LLM logger early)

_ai.set_run_id("pytest")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: exercises a live Qwen call (tolerant of fail-open)")
