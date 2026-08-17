#!/usr/bin/env python3
"""Fail-closed governance check for canonical Rmax claims.

This checker validates that the canonical detector-rate claim remains withheld
while its measurand/quality criterion is unresolved. It may emit clearly
labelled arithmetic sensitivities, but it never infers an accepted detector
rate from selected-pulse occupancy or a legacy duty factor.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

VERSION = "3.0.0"
POLICY = "RMAX_FAIL_CLOSED_NO_RATE_PROMOTION_FROM_OCCUPANCY_OR_DUTY_FACTOR"
TAU_CL011_NS = 124.79018394263471
LEGACY_DUTY_FACTOR = 0.38
FIVE_PERCENT_OVERLAP = 0.05
FIELDS = (
    "claim_id,chapter,section,claim_text,current_value,unit,stat_unc,syst_unc,"
    "total_unc,ci_low,ci_high,ci_level,ci_method,bootstrap_unit,n_events,n_runs,"
    "n_data,n_mc,numerator,denominator,p_value,effect_size,baseline_value,"
    "baseline_unc,delta_vs_baseline,delta_ci_low,delta_ci_high,truth_type,status,"
    "allowed_status_validated,source_report,source_script,source_data,source_config,"
    "source_manifest,figure_ids,table_ids,source_commit,link_validated,ci_status,"
    "blocked_by,supersedes,notes"
).split(",")


class InputError(ValueError):
    """Controlled malformed-input failure."""


def snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES_STRICT_UTF8",
    }


def parse_ledger(text: str) -> list[list[str]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows or rows[0] != FIELDS:
        raise InputError("claim ledger header is not the canonical 43-column schema")
    return rows


def unique_claim(rows: list[list[str]], claim_id: str) -> dict[str, str]:
    matches = [row for row in rows[1:] if row and row[0] == claim_id]
    if len(matches) != 1:
        raise InputError(f"expected exactly one {claim_id} row, found {len(matches)}")
    row = matches[0]
    if len(row) != len(FIELDS):
        raise InputError(
            f"{claim_id} row width {len(row)} does not match canonical {len(FIELDS)}"
        )
    return dict(zip(FIELDS, row))


def add_mismatch(
    issues: list[dict[str, Any]], field: str, expected: str, actual: str
) -> None:
    if actual != expected:
        issues.append(
            {
                "code": "LEDGER_FIELD_MISMATCH",
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def require_phrase(
    issues: list[dict[str, Any]], text: str, phrase: str, code: str
) -> None:
    if phrase not in text:
        issues.append({"code": code, "phrase": phrase})


def reject_phrase(
    issues: list[dict[str, Any]], text: str, phrase: str, code: str
) -> None:
    if phrase in text:
        issues.append({"code": code, "phrase": phrase})


def evaluate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    wiki_text, wiki_prov = snapshot(root / "WIKI.md")
    ledger_text, ledger_prov = snapshot(root / "docs/claim_ledger.csv")
    rows = parse_ledger(ledger_text)
    cl010 = unique_claim(rows, "CL-010")
    cl011 = unique_claim(rows, "CL-011")

    issues: list[dict[str, Any]] = []
    expected_cl010 = {
        "current_value": "",
        "unit": "MHz",
        "truth_type": "derived_model_conflicted",
        "status": "BLOCKED",
        "allowed_status_validated": "NO",
        "ci_status": "NOT_APPLICABLE_WITH_REASON",
        "blocked_by": "S-STAT-003",
    }
    for field, expected in expected_cl010.items():
        add_mismatch(issues, f"CL-010.{field}", expected, cl010[field])
    for phrase in (
        "accepted value is withheld",
        "does not identify event-arrival rate",
        "live exposure",
        "absolute Rmax",
    ):
        require_phrase(
            issues,
            cl010["notes"],
            phrase,
            "CL010_FAIL_CLOSED_NOTE_MISSING",
        )

    add_mismatch(issues, "CL-011.current_value", repr(TAU_CL011_NS), cl011["current_value"])
    add_mismatch(issues, "CL-011.unit", "ns", cl011["unit"])
    add_mismatch(issues, "CL-011.truth_type", "data_measurement", cl011["truth_type"])
    add_mismatch(issues, "CL-011.status", "DONE_DATA_ONLY", cl011["status"])

    for phrase in (
        "Rmax — pile-up tolerance (canonical) | withheld",
        "Rmax is withheld pending S-STAT-003",
        "No accepted numerical Rmax until S-STAT-003 resolves the criterion",
    ):
        require_phrase(issues, wiki_text, phrase, "WIKI_WITHHOLDING_STATEMENT_MISSING")
    for phrase in (
        "Rmax 2.92 MHz (data-derived, corroborates CL-010 3.05 MHz)",
        "3.05 MHz is measured (occupancy)",
        "Rmax from real-data occupancy",
    ):
        reject_phrase(issues, wiki_text, phrase, "WIKI_OVERAUTHORIZES_RMAX")

    tau_s = TAU_CL011_NS * 1.0e-9
    five_percent_rate_mhz = -math.log1p(-FIVE_PERCENT_OVERLAP) / tau_s / 1.0e6
    legacy_duty_arithmetic_mhz = LEGACY_DUTY_FACTOR / tau_s / 1.0e6

    return {
        "checker": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "governance_status": "PASS" if not issues else "FAIL",
        "scientific_acceptance": "BLOCKED",
        "accepted_rmax_mhz": None,
        "definitions": {
            "canonical_detector_rmax": (
                "WITHHELD: requires a preregistered detector/reconstruction quality criterion, "
                "an independently identified event-arrival exposure/rate model, and uncertainty"
            ),
            "poisson_overlap_sensitivity": "r = -ln(1-p)/tau under stationary independent arrivals",
            "legacy_duty_factor_arithmetic": "duty_factor/tau; historical arithmetic only, not a quality threshold",
        },
        "calculations": {
            "tau_cl011_ns": TAU_CL011_NS,
            "five_percent_overlap_probability": FIVE_PERCENT_OVERLAP,
            "five_percent_poisson_rate_mhz": five_percent_rate_mhz,
            "legacy_duty_factor": LEGACY_DUTY_FACTOR,
            "legacy_duty_factor_arithmetic_mhz": legacy_duty_arithmetic_mhz,
            "interpretation": (
                "These values are arithmetic/model sensitivities only. Neither selected-pulse occupancy "
                "nor the beam duty factor identifies an accepted detector Rmax."
            ),
        },
        "inputs": {"wiki": wiki_prov, "claim_ledger": ledger_prov},
        "issues": issues,
        "n_issues": len(issues),
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    for item in payload.get("inputs", {}).values():
        if Path(item["path"]).resolve() == path:
            raise InputError("output path aliases a checked input")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output-json", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = evaluate(args.root)
        if args.output_json:
            atomic_json(args.output_json, payload)
    except InputError as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload["governance_status"] == "PASS":
        print("PASS: Rmax public/ledger governance is internally consistent and remains scientifically BLOCKED.")
        return 0
    print("FAIL: Rmax governance is inconsistent or over-authorizing; scientific acceptance remains BLOCKED.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
