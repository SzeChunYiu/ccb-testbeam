#!/usr/bin/env python3
"""Ticket #2519/S60a residual pulse-shape timing atlas runner."""

from __future__ import annotations

import sys
from pathlib import Path

import ticket_2501_s55a_phase_conditioned_timing as base


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "ticket_2519_s60a_template_residual_pulse_shape_timing_atlas.json"


if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--config", str(CONFIG)]
    raise SystemExit(base.main())
