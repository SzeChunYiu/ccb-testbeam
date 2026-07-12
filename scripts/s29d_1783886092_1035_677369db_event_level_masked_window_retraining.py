#!/usr/bin/env python3
"""Ticket-specific S29d event-level masked-window retraining runner."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts/s29d_1783828885_13013_75ac144c_event_level_masked_window_retraining.py"
CONFIG = ROOT / "configs/s29d_1783886092_1035_677369db_event_level_masked_window_retraining.json"
TICKET = "1783886092.1035.677369db"
WORKER = "testbeam-laptop-1"


def load_base():
    spec = importlib.util.spec_from_file_location("s29d_event_level_masked_window_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["s29d_event_level_masked_window_base"] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    base = load_base()
    base.CONFIG = CONFIG
    base.TICKET = TICKET
    base.WORKER = WORKER
    base.main()


if __name__ == "__main__":
    main()
