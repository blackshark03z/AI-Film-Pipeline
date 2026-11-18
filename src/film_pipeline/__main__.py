"""Run `python -m film_pipeline` via the installed CLI entrypoint."""
from __future__ import annotations

from film_pipeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
