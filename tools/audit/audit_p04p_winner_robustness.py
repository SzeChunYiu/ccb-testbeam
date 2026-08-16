#!/usr/bin/env python3
"""Audit whether the P04p winner survives an uncertainty-aware coverage gate."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "COVERAGE_GATE_MUST_USE_PREDECLARED_UNCERTAINTY_RULE"
DEFAULT_COVERAGE_THRESHOLD = 0.50
RANK_FIELDS = (
    "accepted_charge_res68_frac",
    "accepted_timing_abs68_ns",
    "calibration_ece",
)


class P04pAuditError(ValueError):
    """Controlled input or schema error."""


def _read_json_snapshot(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise P04pAuditError(f"cannot read {path}: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise P04pAuditError(f"{path} is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise P04pAuditError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise P04pAuditError("result JSON must contain an object")
    return payload, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _finite_number(value: Any, field: str, method: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise P04pAuditError(f"{method}.{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise P04pAuditError(f"{method}.{field} must be finite")
    return number


def _parse_methods(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_methods = payload.get("harm_methods")
    if not isinstance(raw_methods, list) or not raw_methods:
        raise P04pAuditError("harm_methods must be a non-empty list")

    methods: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_methods):
        if not isinstance(raw, dict):
            raise P04pAuditError(f"harm_methods[{index}] must be an object")
        method = raw.get("method")
        if not isinstance(method, str) or not method.strip():
            raise P04pAuditError(f"harm_methods[{index}].method must be non-empty")
        method = method.strip()
        if method in seen:
            raise P04pAuditError(f"duplicate method {method}")
        seen.add(method)

        interval = raw.get("accepted_coverage_ci95")
        if not isinstance(interval, list) or len(interval) != 2:
            raise P04pAuditError(
                f"{method}.accepted_coverage_ci95 must contain two values"
            )
        coverage = _finite_number(raw.get("accepted_coverage"), "accepted_coverage", method)
        ci_low = _finite_number(interval[0], "accepted_coverage_ci95[0]", method)
        ci_high = _finite_number(interval[1], "accepted_coverage_ci95[1]", method)
        if not (0.0 <= ci_low <= coverage <= ci_high <= 1.0):
            raise P04pAuditError(
                f"{method}.accepted_coverage and CI must satisfy "
                "0 <= low <= point <= high <= 1"
            )

        row = {
            "method": method,
            "accepted_coverage": coverage,
            "accepted_coverage_ci95": [ci_low, ci_high],
        }
        for field in RANK_FIELDS:
            row[field] = _finite_number(raw.get(field), field, method)
        methods.append(row)
    return methods


def _rank(methods: list[dict[str, Any]], eligibility_field: str, threshold: float) -> list[str]:
    eligible = [row for row in methods if row[eligibility_field] >= threshold]
    eligible.sort(key=lambda row: tuple(row[field] for field in RANK_FIELDS))
    return [str(row["method"]) for row in eligible]


def audit_payload(
    payload: dict[str, Any],
    coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD,
) -> dict[str, Any]:
    if not math.isfinite(coverage_threshold) or not 0.0 < coverage_threshold < 1.0:
        raise P04pAuditError("coverage threshold must be finite and between 0 and 1")
    if payload.get("study") != "P04p":
        raise P04pAuditError("result JSON must identify study P04p")

    reported_winner = payload.get("winner")
    if not isinstance(reported_winner, str) or not reported_winner.strip():
        raise P04pAuditError("winner must be a non-empty string")
    reported_winner = reported_winner.strip()
    selection = payload.get("winner_selection")
    if not isinstance(selection, str) or not selection.strip():
        raise P04pAuditError("winner_selection must be a non-empty string")

    methods = _parse_methods(payload)
    by_name = {str(row["method"]): row for row in methods}
    if reported_winner not in by_name:
        raise P04pAuditError("reported winner is absent from harm_methods")

    point_rows = [dict(row, gate_value=row["accepted_coverage"]) for row in methods]
    robust_rows = [
        dict(row, gate_value=row["accepted_coverage_ci95"][0]) for row in methods
    ]
    point_rank = _rank(point_rows, "gate_value", coverage_threshold)
    robust_rank = _rank(robust_rows, "gate_value", coverage_threshold)
    point_winner = point_rank[0] if point_rank else None
    robust_winner = robust_rank[0] if robust_rank else None

    issues: list[dict[str, Any]] = []
    if point_winner != reported_winner:
        issues.append(
            {
                "code": "REPORTED_WINNER_NOT_REPRODUCIBLE",
                "reported_winner": reported_winner,
                "recomputed_point_estimate_winner": point_winner,
            }
        )
    if "coverage_gate_uncertainty_policy" not in payload:
        issues.append(
            {
                "code": "COVERAGE_GATE_UNCERTAINTY_POLICY_MISSING",
                "detail": (
                    "winner selection uses a hard coverage threshold but the result "
                    "does not declare whether point or interval coverage controls eligibility"
                ),
            }
        )
    if robust_winner is None:
        issues.append(
            {
                "code": "NO_METHOD_MEETS_CI_LOWER_BOUND_GATE",
                "coverage_threshold": coverage_threshold,
            }
        )
    elif robust_winner != reported_winner:
        issues.append(
            {
                "code": "WINNER_CHANGES_UNDER_CI_LOWER_BOUND_GATE",
                "reported_winner": reported_winner,
                "ci_lower_bound_winner": robust_winner,
                "coverage_threshold": coverage_threshold,
            }
        )

    rows = []
    for row in sorted(methods, key=lambda item: str(item["method"])):
        point_eligible = row["accepted_coverage"] >= coverage_threshold
        robust_eligible = row["accepted_coverage_ci95"][0] >= coverage_threshold
        rows.append(
            {
                **row,
                "point_estimate_eligible": point_eligible,
                "ci_lower_bound_eligible": robust_eligible,
            }
        )

    return {
        "auditor": "audit_p04p_winner_robustness.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "study": "P04p",
        "coverage_threshold": coverage_threshold,
        "reported_winner": reported_winner,
        "reported_winner_selection": selection,
        "recomputed_point_estimate_rank": point_rank,
        "ci_lower_bound_rank": robust_rank,
        "recomputed_point_estimate_winner": point_winner,
        "ci_lower_bound_winner": robust_winner,
        "winner_stable_to_ci_lower_bound_gate": reported_winner == robust_winner,
        "methods": rows,
        "issues": issues,
        "n_issues": len(issues),
        "interpretation": (
            "This is a model-selection robustness audit. It does not designate the "
            "CI-lower-bound winner as canonical unless that rule is preregistered."
        ),
    }


def audit(path: Path, coverage_threshold: float = DEFAULT_COVERAGE_THRESHOLD) -> dict[str, Any]:
    payload, provenance = _read_json_snapshot(path)
    result = audit_payload(payload, coverage_threshold=coverage_threshold)
    result["result_json"] = provenance
    return result


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_svg(path: Path, payload: dict[str, Any]) -> None:
    rows = sorted(payload["methods"], key=lambda row: row["accepted_coverage"])
    width = 980
    left = 250
    right = 50
    top = 85
    row_h = 52
    plot_w = width - left - right
    height = top + row_h * len(rows) + 95
    threshold = float(payload["coverage_threshold"])

    def x(value: float) -> float:
        return left + value * plot_w

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">P04p coverage-gate winner robustness</title>',
        '<desc id="desc">Accepted coverage point estimates and run-bootstrap 95 percent '
        'intervals. The reported point-gate winner changes under a '
        'lower-confidence-bound gate.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="30" font-family="sans-serif" font-size="21" '
        'font-weight="bold">P04p winner is not stable to the coverage-uncertainty rule</text>',
        '<text x="24" y="55" font-family="sans-serif" font-size="13">'
        'Synthetic rendering of committed result metrics; not detector-response data.</text>',
        f'<line x1="{x(threshold):.1f}" y1="68" x2="{x(threshold):.1f}" '
        f'y2="{top + row_h * len(rows) - 10}" stroke="black" stroke-width="2"/>',
        f'<text x="{x(threshold) + 6:.1f}" y="78" font-family="sans-serif" '
        f'font-size="12">coverage gate {threshold:.2f}</text>',
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        method = html.escape(str(row["method"]))
        low, high = row["accepted_coverage_ci95"]
        point = row["accepted_coverage"]
        reported = row["method"] == payload["reported_winner"]
        robust = row["method"] == payload["ci_lower_bound_winner"]
        marker = "reported winner" if reported else ("CI-gate sensitivity winner" if robust else "")
        parts.extend(
            [
                f'<text x="24" y="{y + 19}" font-family="monospace" '
                f'font-size="13">{method}</text>',
                f'<line x1="{x(low):.1f}" y1="{y + 14}" x2="{x(high):.1f}" '
                f'y2="{y + 14}" stroke="black" stroke-width="3"/>',
                f'<line x1="{x(low):.1f}" y1="{y + 8}" x2="{x(low):.1f}" '
                f'y2="{y + 20}" stroke="black"/>',
                f'<line x1="{x(high):.1f}" y1="{y + 8}" x2="{x(high):.1f}" '
                f'y2="{y + 20}" stroke="black"/>',
                f'<circle cx="{x(point):.1f}" cy="{y + 14}" r="5" fill="white" '
                f'stroke="black" stroke-width="2"/>',
                f'<text x="{x(high) + 8:.1f}" y="{y + 19}" font-family="sans-serif" '
                f'font-size="11">{point:.3f} [{low:.3f}, {high:.3f}] {html.escape(marker)}</text>',
            ]
        )
    axis_y = top + row_h * len(rows)
    parts.append(
        f'<line x1="{left}" y1="{axis_y}" x2="{left + plot_w}" y2="{axis_y}" stroke="black"/>'
    )
    for value in [0.0, 0.25, 0.50, 0.75, 1.0]:
        parts.extend(
            [
                f'<line x1="{x(value):.1f}" y1="{axis_y}" x2="{x(value):.1f}" '
                f'y2="{axis_y + 6}" stroke="black"/>',
                f'<text x="{x(value):.1f}" y="{axis_y + 23}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="11">{value:.2f}</text>',
            ]
        )
    parts.extend(
        [
            f'<text x="{left + plot_w / 2:.1f}" y="{axis_y + 45}" text-anchor="middle" '
            'font-family="sans-serif" font-size="13">accepted coverage</text>',
            f'<text x="24" y="{height - 20}" font-family="sans-serif" font-size="12">'
            f'Policy: {html.escape(payload["policy"])}; status: {payload["status"]}; '
            f'reported winner: {html.escape(str(payload["reported_winner"]))}; '
            'CI-gate sensitivity winner: '
            f'{html.escape(str(payload["ci_lower_bound_winner"]))}</text>',
            '</svg>',
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_json", type=Path)
    parser.add_argument("--coverage-threshold", type=float, default=DEFAULT_COVERAGE_THRESHOLD)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.result_json, coverage_threshold=args.coverage_threshold)
    except P04pAuditError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        _write_json(args.output, result)
    if args.svg:
        _write_svg(args.svg, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
