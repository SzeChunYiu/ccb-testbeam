#!/usr/bin/env python3
"""Generate the canonical paper-grade CCB wiki figure set."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ccb_plotting.wiki_figures import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
