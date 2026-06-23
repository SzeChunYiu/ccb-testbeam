"""Report linting and validation diagnostics."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass
class LintFinding:
    """Single lint finding in a report artifact."""

    rule: str
    message: str
    line: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "message": self.message, "line": self.line}


@dataclass
class LintReport:
    """Aggregated lint results."""

    findings: list[LintFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": [finding.as_dict() for finding in self.findings]}


_TODO_RE = re.compile(r"\bTODO\b", re.IGNORECASE)
_ABS_PATH_RE = re.compile(r"(?<![\w./])(?:/Users/|/home/|/projects/)[^\s`]+")
_NAN_METRIC_RE = re.compile(r"\|\s*`[^`]+`\s*\|\s*NaN\s*\|", re.IGNORECASE)


def lint_report(
    report_path: str | Path | None = None,
    *,
    metrics: Mapping[str, Any] | None = None,
    text: str | None = None,
) -> LintReport:
    """Lint a report for TODO markers, NaN metrics, and absolute paths."""
    findings: list[LintFinding] = []

    body = text
    if body is None and report_path is not None:
        body = Path(report_path).read_text(encoding="utf-8")

    if metrics:
        for key, value in metrics.items():
            if isinstance(value, float) and math.isnan(value):
                findings.append(
                    LintFinding(
                        rule="nan_metric",
                        message=f"metric {key!r} is NaN",
                    )
                )

    if body:
        for line_no, line in enumerate(body.splitlines(), start=1):
            if _TODO_RE.search(line):
                findings.append(
                    LintFinding(rule="todo_marker", message="TODO marker found", line=line_no)
                )
            for match in _ABS_PATH_RE.finditer(line):
                findings.append(
                    LintFinding(
                        rule="absolute_path",
                        message=f"absolute path reference: {match.group(0)}",
                        line=line_no,
                    )
                )
            if _NAN_METRIC_RE.search(line):
                findings.append(
                    LintFinding(rule="nan_metric_table", message="NaN metric in table", line=line_no)
                )

    return LintReport(findings=findings)


def require_clean_report(*args: Any, **kwargs: Any) -> LintReport:
    """Run :func:`lint_report` and raise if findings are present."""
    from ccb_mc_validation.exceptions import ReportValidationError

    report = lint_report(*args, **kwargs)
    if not report.ok:
        messages = "; ".join(f.message for f in report.findings)
        raise ReportValidationError(messages)
    return report
