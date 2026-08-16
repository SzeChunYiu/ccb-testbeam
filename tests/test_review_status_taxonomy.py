"""Tests for review-status taxonomy (#990)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "audit"))
import validate_review_status_taxonomy as v


def test_chapters_have_no_unqualified_nature_badges():
    assert v.validate(REPO) == []
