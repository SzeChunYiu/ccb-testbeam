#!/usr/bin/env python3
"""S55a/#2497 residual-shape atlas wrapper."""

from __future__ import annotations

from pathlib import Path

import s51a_2454_waveform_shape_time_identifiability_atlas as s51a


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "2497_s55a_residual_shape_atlas.json"


if __name__ == "__main__":
    s51a.main_args = None
    import sys

    sys.argv = [sys.argv[0], "--config", str(CONFIG)]
    s51a.main()
