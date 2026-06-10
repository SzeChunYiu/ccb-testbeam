#!/usr/bin/env python3
"""Run the 1781020163.1162.0da302da S03e blind transfer study."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(script_dir))
    import s03e_blind_sample_i_to_ii_transfer as study

    config = "configs/s03e_1781020163_1162_0da302da_blind_sample_i_to_ii_transfer.yaml"
    sys.argv = [str(Path(__file__)), "--config", config]
    return study.main()


if __name__ == "__main__":
    raise SystemExit(main())
