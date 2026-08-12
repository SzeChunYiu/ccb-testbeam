"""Tests for scientific merge-close keyword gate (#1218)."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools" / "gov"))
import check_merge_close_keywords as c  # noqa: E402


def test_blocks_closes_keyword():
    findings = c.scan_text("This PR Closes #1057 after partial work.", {})
    assert findings and findings[0]["issue"] == 1057


def test_allows_does_not_close():
    findings = c.scan_text("This PR does not close #1057; follow-up required.", {})
    assert findings == []


def test_cli_blocks(tmp_path: Path):
    f = tmp_path / "body.md"
    f.write_text("Closes #1057\n", encoding="utf-8")
    assert c.main(["--repo-root", str(REPO), "--text-file", str(f)]) == 1


def test_cli_allows_with_explicit_allow(tmp_path: Path):
    f = tmp_path / "body.md"
    f.write_text("Closes #1057\n", encoding="utf-8")
    assert c.main(["--repo-root", str(REPO), "--text-file", str(f), "--allow-close", "1057"]) == 0
