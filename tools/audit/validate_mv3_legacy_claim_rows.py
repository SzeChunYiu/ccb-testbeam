#!/usr/bin/env python3
"""Validate source-backed governance for legacy MV3 stopping-profile claim rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "LEGACY_MV3_PROFILE_REQUIRES_EXACT_COUNTS_AND_FAIL_CLOSED_RERUN"
EXPECTED_COLUMNS = 43
CLAIM_IDS = ("CL-019", "CL-020", "CL-021")
SOURCE_COMMIT = "3c5ff5cf587c8ca9cefda20cb220ba29effd2170"
SOURCE_REPORT = "reports/mv3_stopping_v3_1782679272/REPORT.md"
BLOCKER = "BLK-MV3-LEGACY-001"
MC_TRACKS = 249_484
DATA_EVENTS = 306_745
MC_B8 = 0.223
DATA_B8 = 0.023
CHI2_NDF_LABEL = 68_269.4


class Mv3ClaimError(ValueError):
    """Controlled input or schema error."""


def _snapshot(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise Mv3ClaimError(f"cannot read {path}: {exc}") from exc
    return raw, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _decode(raw: bytes, path: Path) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Mv3ClaimError(f"{path} is not valid UTF-8") from exc


def _load_ledger(text: str) -> tuple[list[str], dict[str, list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise Mv3ClaimError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows:
        raise Mv3ClaimError("claim ledger is empty")
    header = rows[0]
    selected: dict[str, list[str]] = {}
    for row in rows[1:]:
        if row and row[0] in CLAIM_IDS:
            if row[0] in selected:
                raise Mv3ClaimError(f"duplicate claim row {row[0]}")
            selected[row[0]] = row
    missing = [claim_id for claim_id in CLAIM_IDS if claim_id not in selected]
    if missing:
        raise Mv3ClaimError(f"missing required claim rows: {', '.join(missing)}")
    return header, selected


def _reported_contract(report: str) -> dict[str, Any]:
    mc_match = re.search(r"MC tracks above threshold:\s*(\d+)", report)
    data_match = re.search(r"Data events:\s*(\d+)", report)
    chi_match = re.search(r"χ²/ndf\s*=\s*([0-9.]+)", report)
    b8_match = re.search(
        r"\|\s*B8\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|",
        report,
    )
    table_rows = re.findall(
        r"\|\s*B[2468]\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|",
        report,
    )
    if not all((mc_match, data_match, chi_match, b8_match)) or len(table_rows) != 4:
        raise Mv3ClaimError("legacy report does not match the audited MV3 contract")
    mc_values = [float(row[0]) for row in table_rows]
    data_values = [float(row[1]) for row in table_rows]
    return {
        "mc_tracks_above_threshold": int(mc_match.group(1)),
        "data_events": int(data_match.group(1)),
        "chi2_ndf_label": float(chi_match.group(1)),
        "b8_mc_fraction": float(b8_match.group(1)),
        "b8_data_fraction": float(b8_match.group(2)),
        "mc_fraction_sum": math.fsum(mc_values),
        "data_fraction_sum": math.fsum(data_values),
        "exact_per_stave_counts_present": False,
        "separate_chi2_ndf_p_value_present": False,
    }


def _remediation_contract(source: str) -> dict[str, bool]:
    compact = " ".join(source.split()).lower()
    return {
        "requires_sample_label": "records['sample_label']" in source,
        "requires_per_layer_mask": (
            "records['layer_hits']" in source and "records['edep_per_layer']" in source
        ),
        "blocks_without_inputs": "studystatus.blocked" in compact,
        "removes_event_parity_proxy": "event-parity proxy removed" in compact,
        "removes_stop_layer_occupancy_proxy": "stop_layer proxy" in compact,
    }


def _rounding_count_range(value: float, denominator: int) -> dict[str, Any]:
    lower_fraction = value - 0.0005
    upper_fraction = value + 0.0005
    minimum = math.ceil(lower_fraction * denominator)
    maximum = math.ceil(upper_fraction * denominator) - 1
    return {
        "reported_fraction": value,
        "denominator": denominator,
        "rounding_decimals": 3,
        "possible_numerator_min": minimum,
        "possible_numerator_max": maximum,
        "possible_numerator_count": maximum - minimum + 1,
    }


def _expect(
    issues: list[dict[str, Any]],
    condition: bool,
    code: str,
    detail: str,
    claim_id: str | None = None,
) -> None:
    if condition:
        return
    issue: dict[str, Any] = {"code": code, "detail": detail}
    if claim_id is not None:
        issue["claim_id"] = claim_id
    issues.append(issue)


def validate(ledger_path: Path, report_path: Path, remediation_path: Path) -> dict[str, Any]:
    ledger_raw, ledger_prov = _snapshot(ledger_path)
    report_raw, report_prov = _snapshot(report_path)
    remediation_raw, remediation_prov = _snapshot(remediation_path)
    header, rows = _load_ledger(_decode(ledger_raw, ledger_path))
    report_contract = _reported_contract(_decode(report_raw, report_path))
    remediation_contract = _remediation_contract(_decode(remediation_raw, remediation_path))
    issues: list[dict[str, Any]] = []

    _expect(issues, len(header) == EXPECTED_COLUMNS, "HEADER_WIDTH", "header must have 43 fields")
    _expect(
        issues,
        report_contract["mc_tracks_above_threshold"] == MC_TRACKS,
        "MC_TRACKS",
        "legacy report MC-track count changed",
    )
    _expect(
        issues,
        report_contract["data_events"] == DATA_EVENTS,
        "DATA_EVENTS",
        "legacy report data-event count changed",
    )
    _expect(
        issues,
        report_contract["b8_mc_fraction"] == MC_B8,
        "MC_B8",
        "legacy report MC B8 fraction changed",
    )
    _expect(
        issues,
        report_contract["b8_data_fraction"] == DATA_B8,
        "DATA_B8",
        "legacy report data B8 fraction changed",
    )
    _expect(
        issues,
        report_contract["chi2_ndf_label"] == CHI2_NDF_LABEL,
        "CHI2_LABEL",
        "legacy report chi2/ndf label changed",
    )
    for key, present in remediation_contract.items():
        _expect(issues, present, "REMEDIATION_CONTRACT", f"missing remediation contract: {key}")

    index = {name: pos for pos, name in enumerate(header)}
    expected = {
        "CL-019": {
            "claim_text": "Legacy MV3 v3 rounded B8 fraction in thresholded MC",
            "current_value": "0.223",
            "n_data": "",
            "n_mc": str(MC_TRACKS),
            "truth_type": "legacy_thresholded_mc_summary",
            "status": "GATED",
            "ci_status": "NOT_RECONSTRUCTABLE_ROUNDED_FRACTION_EXACT_COUNT_OMITTED",
        },
        "CL-020": {
            "claim_text": "Legacy MV3 v3 rounded B8 fraction in selected data",
            "current_value": "0.023",
            "n_data": str(DATA_EVENTS),
            "n_mc": "",
            "truth_type": "legacy_selected_data_summary",
            "status": "GATED",
            "ci_status": "NOT_RECONSTRUCTABLE_ROUNDED_FRACTION_EXACT_COUNT_OMITTED",
        },
        "CL-021": {
            "claim_text": "Legacy MV3 v3 reported profile chi2/ndf label",
            "current_value": "68269.4",
            "n_data": str(DATA_EVENTS),
            "n_mc": str(MC_TRACKS),
            "truth_type": "legacy_data_mc_profile_diagnostic",
            "status": "FLAWED",
            "ci_status": "NOT_RECONSTRUCTABLE_CHI2_NDF_P_VALUE_AND_BIN_ERRORS_OMITTED",
        },
    }
    note_fragments = {
        "CL-019": (
            "rounded to three decimals",
            "omits exact per-stave counts",
            "no binomial confidence interval",
            "not an accepted production stopping-profile measurement",
        ),
        "CL-020": (
            "rounded to three decimals",
            "omits exact per-stave counts",
            "no binomial confidence interval",
            "not an accepted production stopping-profile measurement",
        ),
        "CL-021": (
            "does not provide the underlying chi2",
            "data fractions sum to 1.001",
            "stop_layer occupancy inference",
            "not a calibrated goodness-of-fit statistic",
        ),
    }

    for claim_id, row in rows.items():
        _expect(
            issues,
            len(row) == EXPECTED_COLUMNS,
            "ROW_WIDTH",
            f"row has {len(row)} columns rather than 43",
            claim_id,
        )
        if len(row) != EXPECTED_COLUMNS:
            continue
        values = {name: row[pos] for name, pos in index.items()}
        for field, expected_value in expected[claim_id].items():
            _expect(
                issues,
                values[field] == expected_value,
                f"FIELD_{field.upper()}",
                f"{field} mismatch",
                claim_id,
            )
        for field in (
            "stat_unc",
            "syst_unc",
            "total_unc",
            "ci_low",
            "ci_high",
            "ci_level",
            "numerator",
            "denominator",
            "p_value",
        ):
            _expect(
                issues,
                values[field] == "",
                "UNSUPPORTED_QUANTITATIVE_FIELD",
                f"{field} must remain empty",
                claim_id,
            )
        expected_method = (
            "reported_fixed_profile_statistic_label"
            if claim_id == "CL-021"
            else "reported_fraction_rounded_3dp"
        )
        _expect(
            issues,
            values["ci_method"] == expected_method,
            "CI_METHOD",
            "method label mismatch",
            claim_id,
        )
        _expect(
            issues,
            values["allowed_status_validated"] == "NO",
            "ALLOWED",
            "legacy claim must not be authorized",
            claim_id,
        )
        _expect(
            issues,
            values["source_report"] == SOURCE_REPORT,
            "SOURCE_REPORT",
            "source report mismatch",
            claim_id,
        )
        _expect(
            issues,
            values["source_script"] == "" and values["source_data"] == "",
            "MISSING_SOURCE_PATHS_MUST_NOT_BE_CITED",
            "unavailable historical producer/results paths must remain empty",
            claim_id,
        )
        _expect(
            issues,
            values["source_commit"] == SOURCE_COMMIT,
            "SOURCE_COMMIT",
            "source commit mismatch",
            claim_id,
        )
        _expect(
            issues,
            values["link_validated"] == "YES",
            "LINK",
            "tracked report link must be validated",
            claim_id,
        )
        _expect(
            issues,
            values["blocked_by"] == BLOCKER,
            "BLOCKER",
            "blocker mismatch",
            claim_id,
        )
        note = values["notes"].lower()
        for fragment in note_fragments[claim_id]:
            _expect(
                issues,
                fragment in note,
                "NOTE_CAVEAT",
                f"notes must include '{fragment}'",
                claim_id,
            )

    return {
        "validator": "validate_mv3_legacy_claim_rows.py",
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "claims": list(CLAIM_IDS),
        "source_contract": report_contract,
        "remediation_contract": remediation_contract,
        "rounding_identifiability": {
            "mc_b8": _rounding_count_range(MC_B8, MC_TRACKS),
            "data_b8": _rounding_count_range(DATA_B8, DATA_EVENTS),
        },
        "inputs": {
            "claim_ledger": ledger_prov,
            "legacy_report": {
                **report_prov,
                "git_blob": "b72eed4f7eb3237040a1346d7253080c098c8986",
            },
            "current_remediation": {
                **remediation_prov,
                "git_blob": "9b0dfeaa6e74401345bc78c7ab82b33d7868b665",
            },
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def _write_json(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("legacy_report", type=Path)
    parser.add_argument("current_remediation", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate(args.claim_ledger, args.legacy_report, args.current_remediation)
    except Mv3ClaimError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
