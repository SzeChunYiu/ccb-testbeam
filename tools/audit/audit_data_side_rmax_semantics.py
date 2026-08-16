#!/usr/bin/env python3
"""Audit whether the data-side occupancy study over-authorizes an Rmax claim."""
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

VERSION = "1.0.0"
POLICY = "OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE"
FIELDS = (
    "claim_id,chapter,section,claim_text,current_value,unit,stat_unc,syst_unc,"
    "total_unc,ci_low,ci_high,ci_level,ci_method,bootstrap_unit,n_events,n_runs,"
    "n_data,n_mc,numerator,denominator,p_value,effect_size,baseline_value,"
    "baseline_unc,delta_vs_baseline,delta_ci_low,delta_ci_high,truth_type,status,"
    "allowed_status_validated,source_report,source_script,source_data,source_config,"
    "source_manifest,figure_ids,table_ids,source_commit,link_validated,ci_status,"
    "blocked_by,supersedes,notes"
).split(",")

TAU_CL011_NS = 124.79018394263471
MU_LEGACY = 0.38
FORMER_TAU_NS = 130.0


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
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def parse_rows(text: str, label: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid CSV in {label}: {exc}") from exc


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


def require_text(
    issues: list[dict[str, Any]], text: str, phrase: str, code: str, location: str
) -> None:
    if phrase not in text:
        issues.append({"code": code, "location": location, "phrase": phrase})


def reject_text(
    issues: list[dict[str, Any]], text: str, phrase: str, code: str, location: str
) -> None:
    if phrase in text:
        issues.append({"code": code, "location": location, "phrase": phrase})


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    ledger_text, ledger_prov = snapshot(root / "docs/claim_ledger.csv")
    script_text, script_prov = snapshot(root / "scripts/studies/data_side_real_beam.py")
    report_text, report_prov = snapshot(root / "reports/studies/data_side/REPORT.md")

    rows = parse_rows(ledger_text, "docs/claim_ledger.csv")
    if not rows or rows[0] != FIELDS:
        raise InputError("claim ledger header is not the canonical 43-column schema")
    cl010 = unique_claim(rows, "CL-010")
    cl011 = unique_claim(rows, "CL-011")

    issues: list[dict[str, Any]] = []
    expected_cl010 = {
        "current_value": "",
        "unit": "MHz",
        "stat_unc": "",
        "syst_unc": "",
        "total_unc": "",
        "truth_type": "derived_model_conflicted",
        "status": "BLOCKED",
        "allowed_status_validated": "NO",
        "source_report": "reports/mv5_pileup_1782678353/REPORT.md",
        "source_script": "scripts/mv5_pileup_study.py",
        "source_data": "reports/mv5_pileup_1782678353/mv5_pileup_summary.json",
        "ci_status": "NOT_APPLICABLE_WITH_REASON",
        "blocked_by": "S-STAT-003",
        "supersedes": "4.22 MHz",
    }
    for field, expected in expected_cl010.items():
        add_mismatch(issues, f"CL-010.{field}", expected, cl010[field])

    for phrase in (
        "0.38 is the beam duty factor",
        "rmax_from_failure_ceiling_mhz=null",
        "3.20 MHz",
    ):
        require_text(
            issues,
            cl010["notes"],
            phrase,
            "CL010_QUARANTINE_NOTE_MISSING",
            "docs/claim_ledger.csv:CL-010",
        )

    add_mismatch(issues, "CL-011.current_value", repr(TAU_CL011_NS), cl011["current_value"])
    add_mismatch(issues, "CL-011.unit", "ns", cl011["unit"])
    add_mismatch(issues, "CL-011.truth_type", "data_measurement", cl011["truth_type"])
    add_mismatch(issues, "CL-011.status", "DONE_DATA_ONLY", cl011["status"])
    add_mismatch(issues, "CL-011.blocked_by", "BLK-S10B-001", cl011["blocked_by"])

    prohibited_script = (
        "Rmax from real occupancy",
        "tau_eff_ns = ACQ_WINDOW_NS - 30.0",
        "Rmax_data_derived_Hz",
        "Rmax(data-derived)",
        "Rmax_derived=",
    )
    for phrase in prohibited_script:
        reject_text(
            issues,
            script_text,
            phrase,
            "SCRIPT_OVERAUTHORIZES_RMAX",
            "scripts/studies/data_side_real_beam.py",
        )

    required_script = (
        '"rmax_authorized": False',
        '"rmax_status": "BLOCKED"',
        '"tau_eff_cl011_ns": TAU_CL011_NS',
        '"mu_max_legacy_convention": MU_LEGACY',
        '"model_sensitivity_only_mhz"',
        "Rmax withheld",
    )
    for phrase in required_script:
        require_text(
            issues,
            script_text,
            phrase,
            "SCRIPT_FAIL_CLOSED_CONTRACT_MISSING",
            "scripts/studies/data_side_real_beam.py",
        )

    prohibited_report = (
        "Rmax from real-data occupancy",
        "Rmax (data-derived",
        "corroborates the canonical 3.05 MHz",
        "grounded in the measured real-data occupancy",
        "**DONE_DATA_ONLY** (data-derived corroboration)",
        "| Rmax | 2.92 MHz (derived)",
    )
    for phrase in prohibited_report:
        reject_text(
            issues,
            report_text,
            phrase,
            "REPORT_OVERAUTHORIZES_RMAX",
            "reports/studies/data_side/REPORT.md",
        )

    required_report = (
        "Rmax is withheld",
        "does not measure event-arrival rate",
        "legacy duty-factor convention",
        "3.045111305987686 MHz",
        "S-STAT-003",
        "CL-010 remains BLOCKED",
    )
    for phrase in required_report:
        require_text(
            issues,
            report_text,
            phrase,
            "REPORT_FAIL_CLOSED_SCOPE_MISSING",
            "reports/studies/data_side/REPORT.md",
        )

    exact_model_mhz = MU_LEGACY / (TAU_CL011_NS * 1.0e-9) / 1.0e6
    former_model_mhz = MU_LEGACY / (FORMER_TAU_NS * 1.0e-9) / 1.0e6
    if not math.isclose(exact_model_mhz, 3.045111305987686, rel_tol=0, abs_tol=1e-15):
        raise AssertionError("unexpected binary64 model sensitivity")

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "scientific_acceptance": "BLOCKED",
        "accepted_rmax_mhz": None,
        "measured_occupancy_role": "DESCRIPTIVE_SELECTED_PULSE_MULTIPLICITY_ONLY",
        "independent_calculations": {
            "legacy_mu_convention": MU_LEGACY,
            "cl011_tau_ns": TAU_CL011_NS,
            "model_sensitivity_only_mhz": exact_model_mhz,
            "former_130ns_model_mhz": former_model_mhz,
            "former_minus_exact_mhz": former_model_mhz - exact_model_mhz,
            "former_relative_difference_percent": 100.0
            * (former_model_mhz - exact_model_mhz)
            / exact_model_mhz,
            "interpretation": (
                "Both rates are model/convention calculations. Selected-pulse occupancy "
                "does not identify mu_max, live exposure, or an absolute arrival rate."
            ),
        },
        "inputs": {
            "ledger": ledger_prov,
            "data_side_script": script_prov,
            "data_side_report": report_prov,
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path = path.resolve()
    for item in payload.get("inputs", {}).values():
        if Path(item["path"]).resolve() == path:
            raise InputError("output path aliases an audited input")
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
        payload = audit(args.root)
        if args.output_json:
            atomic_json(args.output_json, payload)
    except InputError as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
