"""Tests for deterministic close-intent governance workflow (#1218)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "gov"))
import run_close_intent_gates as g  # noqa: E402


def test_fixture_matrix_passes():
    report = g.run_fixture_matrix()
    assert report["status"] == "PASS", report["failures"]


def test_keyword_smoke_passes():
    report = g.run_keyword_smoke()
    assert report["status"] == "PASS", report["failures"]


def test_cli_passes_without_pr_text():
    assert g.main(["--skip-pr-text"]) == 0


def test_cli_blocks_autoclose_pr_text(tmp_path: Path):
    body = tmp_path / "body.md"
    body.write_text("Closes #1057\n", encoding="utf-8")
    assert g.main(["--pr-text-file", str(body)]) == 1
