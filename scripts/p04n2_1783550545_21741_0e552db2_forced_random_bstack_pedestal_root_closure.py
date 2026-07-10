#!/usr/bin/env python3
"""P04n2 runner for the claimed forced/random B-stack pedestal ROOT closure."""

from __future__ import annotations

from pathlib import Path

import p04n_1781101446_892_139c702a_forced_random_pedestal_validation as p04n


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    config = ROOT / "configs/p04n2_1783550545_21741_0e552db2_forced_random_bstack_pedestal_root_closure.json"
    import sys

    sys.argv = [sys.argv[0], "--config", str(config)]
    return p04n.main()


if __name__ == "__main__":
    raise SystemExit(main())
