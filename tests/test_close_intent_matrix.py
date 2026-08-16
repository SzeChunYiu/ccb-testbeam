"""Hostile fixture matrix for close-intent completion gates (#1218)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "gov"))
import validate_close_intent as v  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures" / "gov" / "close_intent"

EXPECT = {
    "01_acceptance_complete_pass.json": "PASS",
    "02_unresolved_autoclose_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "03_successor_transfer_pass.json": "PASS",
    "04_missing_successor_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "05_successor_omits_blocker_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "06_superseded_pass.json": "PASS",
    "07_pr_text_conflict_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "08_issue_atom_mismatch_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "09_partial_no_close_pass.json": "PASS",
}


@pytest.mark.parametrize("name,expected", sorted(EXPECT.items()))
def test_close_intent_fixture(name: str, expected: str):
    manifest = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    result = v.validate_manifest(manifest)
    assert result["status"] == expected, result
