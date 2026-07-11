#!/usr/bin/env python3
"""Ticket 1783751737.13450.49786d24 energy-closure benchmark wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s17b_0000000010_1_truthenergy as base


def main() -> None:
    if len(sys.argv) == 1:
        sys.argv.extend(["--config", "configs/1783751737_13450_49786d24_shape_saturation_energy.yaml"])
    base.main()


if __name__ == "__main__":
    main()
