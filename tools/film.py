"""Thin compatibility entrypoint forwarding to ``film_pipeline.cli``."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "src").is_dir() and str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.cli import (  # noqa: E402, F401
    GENERATORS_FILE_HELP,
    _emit,
    _generators,
    _motion,
    _narration,
    _run,
    main,
    scaffold,
)

if __name__ == "__main__":
    raise SystemExit(main())
