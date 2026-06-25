"""Run summary Matplotlib cache guard."""

from __future__ import annotations

from pathlib import Path


def test_run_summary_sets_mplconfigdir_before_import() -> None:
    text = Path("src/ccb_mc_validation/reporting/run_summary.py").read_text(encoding="utf-8")
    assert "MPLCONFIGDIR" in text
    assert "run_root / \".matplotlib\"" in text
    assert "os.environ.setdefault" in text
