#!/usr/bin/env python3
"""Require exact MV3 evidence to be bound to the public WIKI sections that use it."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "WIKI_MV3_EXACT_VALUES_MUST_BE_BOUND_TO_CANONICAL_SECTIONS"

DATA_TOKEN = "7051/306745 = 0.02298651974767315"
MC_TOKEN = "55619/249484 = 0.22293614019335908"
CHI2_TOKEN = "Pearson χ² = 204808.2179684494"
NDF_TOKEN = "ndf = 3"
CHI2_NDF_TOKEN = "χ²/ndf = 68269.40598948313"
BOUNDARY_TOKEN = "the diagnostic remains FLAWED"
BLOCKER = "BLK-MV3-LEGACY-001"


class ValidationError(ValueError):
    """Controlled malformed-input error."""


def read_utf8(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _unique_line(lines: list[str], prefix: str, code: str, issues: list[dict[str, Any]]) -> str:
    matches = [(index + 1, line) for index, line in enumerate(lines) if line.startswith(prefix)]
    if len(matches) != 1:
        issues.append({
            "code": code,
            "prefix": prefix,
            "expected_occurrences": 1,
            "actual_occurrences": len(matches),
            "line_numbers": [line_number for line_number, _ in matches],
        })
        return ""
    return matches[0][1]


def _section(text: str, heading: str, end_marker: str) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    end = text.find(end_marker, start + len(heading))
    return text[start:] if end < 0 else text[start:end]


def _require(
    value: str,
    tokens: tuple[str, ...],
    code: str,
    issues: list[dict[str, Any]],
) -> None:
    missing = [token for token in tokens if token not in value]
    if missing:
        issues.append({"code": code, "missing_tokens": missing})


def audit(wiki_path: Path) -> dict[str, Any]:
    text, provenance = read_utf8(wiki_path)
    lines = text.splitlines()
    issues: list[dict[str, Any]] = []

    canonical = _unique_line(
        lines,
        "| MV3 legacy B8 fractions / profile statistic |",
        "CANONICAL_ROW_OCCURRENCE",
        issues,
    )
    _require(
        canonical,
        (DATA_TOKEN, MC_TOKEN, CHI2_TOKEN, NDF_TOKEN, CHI2_NDF_TOKEN, "**FLAWED**"),
        "CANONICAL_ROW_MISMATCH",
        issues,
    )
    if "data 2.3%; MC 22.3%" in canonical:
        issues.append({"code": "CANONICAL_ROW_ROUNDED_ONLY"})

    impact = _unique_line(lines, "| Impact |", "MATERIAL_IMPACT_OCCURRENCE", issues)
    _require(
        impact,
        (
            "Exact tracked MV3 B8 counts and Pearson arithmetic",
            BOUNDARY_TOKEN,
            BLOCKER,
        ),
        "MATERIAL_IMPACT_MISMATCH",
        issues,
    )

    pid = _section(text, "### MV3 Impact on PID", "**[Full chapter:")
    _require(
        pid,
        (
            DATA_TOKEN,
            MC_TOKEN,
            CHI2_TOKEN,
            NDF_TOKEN,
            CHI2_NDF_TOKEN,
            BOUNDARY_TOKEN,
            BLOCKER,
        ),
        "PID_SECTION_MISMATCH",
        issues,
    )

    matrix = _unique_line(
        lines,
        "| MV3 | Legacy stopping-profile diagnostic |",
        "VALIDATION_MATRIX_OCCURRENCE",
        issues,
    )
    _require(
        matrix,
        ("**FLAWED**", "exact tracked counts/statistic", "strict stopping-depth"),
        "VALIDATION_MATRIX_MISMATCH",
        issues,
    )

    blocking = _unique_line(
        lines,
        "1. **MV3: Strict stopping-profile closure is absent**",
        "BLOCKING_ISSUE_OCCURRENCE",
        issues,
    )
    _require(
        blocking,
        (
            "exact fixed-source arithmetic is available",
            "geometry",
            "trigger and selection transfer",
            "covariance",
            "detector/model systematics",
        ),
        "BLOCKING_ISSUE_MISMATCH",
        issues,
    )

    gap = _unique_line(lines, "| GAP-01 |", "GAP01_OCCURRENCE", issues)
    _require(
        gap,
        ("FLAWED under BLK-MV3-LEGACY-001", "strict MV3 rerun"),
        "GAP01_MISMATCH",
        issues,
    )

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "wiki": provenance,
        "bound_sections": [
            "canonical_results_table",
            "material_budget_impact",
            "pid_mv3_section",
            "mc_validation_matrix",
            "mc_blocking_issue",
            "gap01",
        ],
        "issues": issues,
        "n_issues": len(issues),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = audit(args.wiki)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
