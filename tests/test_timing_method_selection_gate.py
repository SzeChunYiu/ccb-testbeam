"""Same-sample timing method selection must stay non-authorising (#1062)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import validate_timing_method_selection as v  # noqa: E402


def test_exploratory_minimum_pass():
    result = {
        "method_selection": {
            "policy": "SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY",
            "authorising": False,
        },
        "best_pair_sigma68_authorising": False,
    }
    assert v.validate(result)["status"] == "PASS"


def test_authorising_same_sample_blocked():
    result = {
        "method_selection": {
            "policy": "SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY",
            "authorising": True,
        },
        "best_pair_sigma68_authorising": True,
        "claim": {"authorising": True, "uses_same_sample_minimum": True},
    }
    assert v.validate(result)["status"] == "BLOCKED"
