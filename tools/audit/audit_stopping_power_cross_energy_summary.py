#!/usr/bin/env python3
"""Audit stopping-power reporting for unsupported cross-energy averaging.

The current stopping-power diagnostic has no per-energy uncertainty or covariance
model. A cross-energy arithmetic mean can therefore look like a combined closure
estimate even though no statistically defined combination exists. This tool
inspects the reporting source and fails closed when it finds that pattern.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

TOOL_VERSION = "1.0.0"
FORBIDDEN_LABEL = "mean point-estimate ratio"
SAFE_POLICY = "NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL"


class CrossEnergySummaryError(ValueError):
    """Raised when the source cannot be audited reliably."""


def _read_source_snapshot(path: Path) -> tuple[bytes, str]:
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise CrossEnergySummaryError(f"cannot read source {path}: {exc}") from exc
    try:
        return source_bytes, source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CrossEnergySummaryError(f"source {path} is not valid UTF-8: {exc}") from exc


def _statistics_mean_lines(tree: ast.AST) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and function.value.id == "statistics"
            and function.attr == "mean"
        ):
            lines.append(node.lineno)
    return sorted(lines)


def audit_source(path: Path) -> dict[str, object]:
    """Return a reproducible audit record for one Python reporting source."""
    path = Path(path)
    source_bytes, source_text = _read_source_snapshot(path)
    try:
        tree = ast.parse(source_text, filename=str(path))
    except SyntaxError as exc:
        raise CrossEnergySummaryError(f"cannot parse source {path}: {exc}") from exc

    mean_lines = _statistics_mean_lines(tree)
    label_lines = [
        line_no
        for line_no, line in enumerate(source_text.splitlines(), start=1)
        if FORBIDDEN_LABEL in line
    ]
    unsafe = bool(mean_lines and label_lines)
    findings: list[dict[str, object]] = []
    if unsafe:
        findings.append(
            {
                "finding_id": "UNWEIGHTED_CROSS_ENERGY_MEAN",
                "state": "FLAWED",
                "statistics_mean_lines": mean_lines,
                "report_label_lines": label_lines,
                "reason": (
                    "the report combines ratios from distinct energies with an "
                    "arithmetic mean while uncertainty_method is NOT_EVALUATED and "
                    "no covariance or weighting model is defined"
                ),
            }
        )

    return {
        "schema_version": 1,
        "tool": "tools/audit/audit_stopping_power_cross_energy_summary.py",
        "tool_version": TOOL_VERSION,
        "status": "FLAWED" if unsafe else "VALIDATED",
        "policy": SAFE_POLICY,
        "source_path": str(path),
        "source_bytes": len(source_bytes),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "statistics_mean_lines": mean_lines,
        "report_label_lines": label_lines,
        "unsupported_cross_energy_mean_present": unsafe,
        "findings": findings,
        "required_remediation": (
            "remove the cross-energy arithmetic mean; report individual energy "
            "points and descriptive bounds only until a preregistered uncertainty, "
            "covariance, and combination model is implemented"
        ),
        "literature_basis": {
            "identifier": "doi:10.6028/NIST.tn.1297",
            "supported_statement": (
                "measurement-result combination requires identified uncertainty "
                "components and an established documented propagation method"
            ),
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Python reporting source to audit")
    parser.add_argument("--output", type=Path, help="write machine-readable JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = audit_source(args.source)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except CrossEnergySummaryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(
        "CROSS-ENERGY SUMMARY AUDIT: "
        f"status={result['status']} sha256={result['source_sha256']} "
        f"policy={result['policy']}"
    )
    return 1 if result["unsupported_cross_energy_mean_present"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
