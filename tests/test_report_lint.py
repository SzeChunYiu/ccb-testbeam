"""Report lint diagnostics tests."""

from __future__ import annotations

import math

from ccb_mc_validation.reporting.diagnostics import lint_report


def test_lint_catches_nan_metric() -> None:
    report = lint_report(metrics={"auc": math.nan, "purity": 0.91})
    assert not report.ok
    assert any(f.rule == "nan_metric" for f in report.findings)


def test_lint_catches_todo_and_absolute_path() -> None:
    text = "See /Users/billy/Desktop/projects/ccb-testbeam/reports/foo\nTODO fix this\n"
    report = lint_report(text=text)
    rules = {f.rule for f in report.findings}
    assert "todo_marker" in rules
    assert "absolute_path" in rules


def test_lint_clean_report() -> None:
    text = "| metric | value |\n| --- | --- |\n| `auc` | 0.95 |\n"
    report = lint_report(text=text, metrics={"auc": 0.95})
    assert report.ok
