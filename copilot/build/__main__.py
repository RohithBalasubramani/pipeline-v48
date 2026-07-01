"""Package entrypoint so `python3 -m build` / `python3 build/` rebuilds the index
(the atomised replacement for the old `python3 build.py`)."""
from .cli import main

if __name__ == "__main__":
    main()
