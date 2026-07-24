#!/usr/bin/env python3
"""Validate public MV3 wording against exact tracked summary and ledger rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
EXPECTED_LEDGER_COLUMNS = 43
POLICY = "WIKI_MV3_MUST_REPORT_EXACT_TRACKED_SUMMARY_WITH_FLAWED_BOUNDARY"
REQUIRED_CLAIMS = ("CL-019", "CL-020", "CL-021")


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


def parse_ledger(text: str) -> dict[str, dict[str, str]]:
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise ValidationError("claim ledger is empty")
    header = [value.strip() for value in rows[0]]
    if len(header) != EXPECTED_LEDGER_COLUMNS:
        raise ValidationError(
            f"claim ledger header has {len(header)} columns; "
            f"expected {EXPECTED_LEDGER_COLUMNS}"
        )
    parsed: dict[str, dict[str, str]] = {}
    widths: dict[str, int] = {}
    for row_number, fields in enumerate(rows[1:], start=2):
        if not fields or not any(value.strip() for value in fields):
            continue
        claim_id = fields[0].strip()
        if claim_id in widths:
            raise ValidationError(f"duplicate claim_id {claim_id}")
        widths[claim_id] = len(fields)
        if len(fields) == EXPECTED_LEDGER_COLUMNS:
            parsed[claim_id] = {
                key: value.strip() for key, value in zip(header, fields, strict=True)
            }
    for claim_id in REQUIRED_CLAIMS:
        width = widths.get(claim_id)
        if width is None:
            raise ValidationError(f"required claim {claim_id} is absent")
        if width != EXPECTED_LEDGER_COLUMNS:
            raise ValidationError(
                f"required claim {claim_id} has {width} columns; "
                f"expected {EXPECTED_LEDGER_COLUMNS}"
            )
    return parsed


def parse_summary(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"MV3 summary is invalid JSON: {exc}") from exc
    try:
        mc_counts = payload["mc"]["counts"]
        data_counts = payload["data"]["all"]["counts"]
        mc_total = int(payload["mc"]["n_above_threshold"])
        data_total = int(payload["data"]["all"]["n_events"])
        stored_mc_b8 = float(payload["mc"]["fractions"]["B8"])
        stored_data_b8 = float(payload["data"]["all"]["fractions"]["B8"])
        stored_chi2 = float(payload["chi2_mc_vs_data_all"])
        stored_ndf = int(payload["chi2_ndf"])
        stored_chi2_ndf = float(payload["chi2_per_ndf"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"MV3 summary schema is incomplete: {exc}") from exc

    labels = ("B2", "B4", "B6", "B8")
    try:
        mc = {label: int(mc_counts[label]) for label in labels}
        data = {label: int(data_counts[label]) for label in labels}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"MV3 count schema is incomplete: {exc}") from exc
    if any(value < 0 for value in (*mc.values(), *data.values())):
        raise ValidationError("MV3 counts must be nonnegative")
    if sum(mc.values()) != mc_total or sum(data.values()) != data_total:
        raise ValidationError("MV3 count totals do not match stored denominators")
    if mc_total <= 0 or data_total <= 0:
        raise ValidationError("MV3 denominators must be positive")

    mc_fraction = mc["B8"] / mc_total
    data_fraction = data["B8"] / data_total
    mc_fractions = {label: mc[label] / mc_total for label in labels}
    expected = {label: data_total * mc_fractions[label] for label in labels}
    chi2 = math.fsum(
        (data[label] - expected[label]) ** 2 / expected[label] for label in labels
    )
    ndf = len(labels) - 1
    chi2_ndf = chi2 / ndf

    exact_checks = {
        "mc_fraction_matches_summary": mc_fraction == stored_mc_b8,
        "data_fraction_matches_summary": data_fraction == stored_data_b8,
        "chi2_matches_summary": chi2 == stored_chi2,
        "ndf_matches_summary": ndf == stored_ndf,
        "chi2_ndf_matches_summary": chi2_ndf == stored_chi2_ndf,
    }
    return {
        "mc_counts": mc,
        "data_counts": data,
        "mc_total": mc_total,
        "data_total": data_total,
        "mc_b8_fraction": mc_fraction,
        "data_b8_fraction": data_fraction,
        "chi2": chi2,
        "ndf": ndf,
        "chi2_ndf": chi2_ndf,
        "exact_checks": exact_checks,
    }


def audit(wiki_path: Path, ledger_path: Path, summary_path: Path) -> dict[str, Any]:
    wiki_text, wiki_provenance = read_utf8(wiki_path)
    ledger_text, ledger_provenance = read_utf8(ledger_path)
    summary_text, summary_provenance = read_utf8(summary_path)
    ledger = parse_ledger(ledger_text)
    summary = parse_summary(summary_text)
    issues: list[dict[str, Any]] = []

    for name, passed in summary["exact_checks"].items():
        if not passed:
            issues.append({"code": "SUMMARY_ARITHMETIC_MISMATCH", "check": name})

    expected_ledger = {
        "CL-019": {
            "current_value": repr(summary["mc_b8_fraction"]),
            "numerator": str(summary["mc_counts"]["B8"]),
            "denominator": str(summary["mc_total"]),
            "status": "GATED",
            "blocked_by": "BLK-MV3-LEGACY-001",
        },
        "CL-020": {
            "current_value": repr(summary["data_b8_fraction"]),
            "numerator": str(summary["data_counts"]["B8"]),
            "denominator": str(summary["data_total"]),
            "status": "GATED",
            "blocked_by": "BLK-MV3-LEGACY-001",
        },
        "CL-021": {
            "current_value": repr(summary["chi2_ndf"]),
            "status": "FLAWED",
            "blocked_by": "BLK-MV3-LEGACY-001",
        },
    }
    for claim_id, expected_fields in expected_ledger.items():
        for field, expected_value in expected_fields.items():
            actual = ledger[claim_id][field]
            if actual != expected_value:
                issues.append({
                    "code": "LEDGER_SUMMARY_MISMATCH",
                    "claim_id": claim_id,
                    "field": field,
                    "expected": expected_value,
                    "actual": actual,
                })

    exact_tokens = {
        "data_count_fraction": (
            f"7051/306745 = {summary['data_b8_fraction']!r}"
        ),
        "mc_count_fraction": (
            f"55619/249484 = {summary['mc_b8_fraction']!r}"
        ),
        "chi2": f"Pearson χ² = {summary['chi2']!r}",
        "ndf": f"ndf = {summary['ndf']}",
        "chi2_ndf": f"χ²/ndf = {summary['chi2_ndf']!r}",
        "acceptance_boundary": "the diagnostic remains FLAWED",
        "blocker": "BLK-MV3-LEGACY-001",
    }
    for name, token in exact_tokens.items():
        if token not in wiki_text:
            issues.append({"code": "MISSING_EXACT_WIKI_TOKEN", "name": name, "token": token})

    forbidden = (
        "the reported χ²/ndf label is not reconstructable",
        "without the underlying χ², ndf, bin variances, covariance, or exact counts",
        "Recover exact counts/statistic",
        "exact statistic/count provenance remain unresolved",
        "MV3 geometry FAIL (χ²/ndf = 68,269)",
    )
    for phrase in forbidden:
        if count := wiki_text.count(phrase):
            issues.append({
                "code": "STALE_MV3_ABSENCE_NARRATIVE",
                "phrase": phrase,
                "occurrences": count,
            })

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "wiki": wiki_provenance,
        "claim_ledger": ledger_provenance,
        "mv3_summary": summary_provenance,
        "reconstructed": summary,
        "required_claims": list(REQUIRED_CLAIMS),
        "exact_wiki_tokens": exact_tokens,
        "forbidden_stale_phrases": list(forbidden),
        "issues": issues,
        "n_issues": len(issues),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiki", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = audit(args.wiki, args.ledger, args.summary)
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
