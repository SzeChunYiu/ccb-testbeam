#!/usr/bin/env python3
"""Validate exact tracked-source governance for legacy MV3 claim rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from pathlib import Path
from typing import Any

VERSION = "2.0.0"
POLICY = "TRACKED_MV3_SUMMARY_EXACT_COUNTS_WITH_FAIL_CLOSED_STRICT_RERUN"
EXPECTED_COLUMNS = 43
CLAIM_IDS = ("CL-019", "CL-020", "CL-021")
SOURCE_COMMIT = "3c5ff5cf587c8ca9cefda20cb220ba29effd2170"
SOURCE_REPORT = "reports/mv3_stopping_v3_1782679272/REPORT.md"
SOURCE_SUMMARY = "reports/mv3_stopping_v3_1782679272/mv3_summary.json"
BLOCKER = "BLK-MV3-LEGACY-001"
STAVES = ("B2", "B4", "B6", "B8")


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


def _load_ledger(text: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise Mv3ClaimError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows:
        raise Mv3ClaimError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise Mv3ClaimError(
            f"claim-ledger header has {len(header)} columns, expected {EXPECTED_COLUMNS}"
        )
    selected: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        if not row or row[0] not in CLAIM_IDS:
            continue
        if row[0] in selected:
            raise Mv3ClaimError(f"duplicate claim row {row[0]}")
        if len(row) != EXPECTED_COLUMNS:
            raise Mv3ClaimError(
                f"{row[0]} has {len(row)} columns, expected {EXPECTED_COLUMNS}"
            )
        selected[row[0]] = dict(zip(header, row, strict=True))
    missing = [claim_id for claim_id in CLAIM_IDS if claim_id not in selected]
    if missing:
        raise Mv3ClaimError(f"missing required rows: {', '.join(missing)}")
    return header, selected


def _load_summary(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Mv3ClaimError(f"invalid MV3 summary JSON: {exc}") from exc
    try:
        mc = payload["mc"]
        data = payload["data"]["all"]
        mc_counts = {stave: int(mc["counts"][stave]) for stave in STAVES}
        data_counts = {stave: int(data["counts"][stave]) for stave in STAVES}
        mc_fractions = {stave: float(mc["fractions"][stave]) for stave in STAVES}
        data_fractions = {stave: float(data["fractions"][stave]) for stave in STAVES}
        mc_n = int(mc["n_above_threshold"])
        data_n = int(data["n_events"])
        stated_chi2 = float(payload["chi2_mc_vs_data_all"])
        stated_ndf = int(payload["chi2_ndf"])
        stated_ratio = float(payload["chi2_per_ndf"])
    except (KeyError, TypeError, ValueError) as exc:
        raise Mv3ClaimError(f"MV3 summary schema mismatch: {exc}") from exc

    expected = {stave: data_n * mc_fractions[stave] for stave in STAVES}
    reconstructed_chi2 = math.fsum(
        (data_counts[stave] - expected[stave]) ** 2 / expected[stave]
        for stave in STAVES
    )
    reconstructed_ndf = len(STAVES) - 1
    return {
        "mc_counts": mc_counts,
        "data_counts": data_counts,
        "mc_fractions": mc_fractions,
        "data_fractions": data_fractions,
        "mc_n": mc_n,
        "data_n": data_n,
        "stated_chi2": stated_chi2,
        "stated_ndf": stated_ndf,
        "stated_chi2_per_ndf": stated_ratio,
        "reconstructed_expected_data_counts": expected,
        "reconstructed_chi2": reconstructed_chi2,
        "reconstructed_ndf": reconstructed_ndf,
        "reconstructed_chi2_per_ndf": reconstructed_chi2 / reconstructed_ndf,
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


def _issue(
    issues: list[dict[str, Any]],
    code: str,
    detail: str,
    claim_id: str | None = None,
) -> None:
    item: dict[str, Any] = {"code": code, "detail": detail}
    if claim_id is not None:
        item["claim_id"] = claim_id
    issues.append(item)


def _expect(
    issues: list[dict[str, Any]],
    condition: bool,
    code: str,
    detail: str,
    claim_id: str | None = None,
) -> None:
    if not condition:
        _issue(issues, code, detail, claim_id)


def _close(left: float, right: float, tolerance: float = 1e-12) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def _check_summary(summary: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    _expect(
        issues,
        sum(summary["mc_counts"].values()) == summary["mc_n"],
        "SUMMARY_MC_COUNT_SUM",
        "MC stave counts do not sum to n_above_threshold",
    )
    _expect(
        issues,
        sum(summary["data_counts"].values()) == summary["data_n"],
        "SUMMARY_DATA_COUNT_SUM",
        "data stave counts do not sum to n_events",
    )
    for stave in STAVES:
        _expect(
            issues,
            _close(
                summary["mc_counts"][stave] / summary["mc_n"],
                summary["mc_fractions"][stave],
            ),
            "SUMMARY_MC_FRACTION",
            f"MC count/fraction mismatch for {stave}",
        )
        _expect(
            issues,
            _close(
                summary["data_counts"][stave] / summary["data_n"],
                summary["data_fractions"][stave],
            ),
            "SUMMARY_DATA_FRACTION",
            f"data count/fraction mismatch for {stave}",
        )
    _expect(
        issues,
        _close(summary["reconstructed_chi2"], summary["stated_chi2"]),
        "SUMMARY_CHI2_MISMATCH",
        "stored Pearson chi2 is not reproduced from tracked counts and fractions",
    )
    _expect(
        issues,
        summary["reconstructed_ndf"] == summary["stated_ndf"],
        "SUMMARY_NDF_MISMATCH",
        "stored ndf is not number of stave bins minus one",
    )
    _expect(
        issues,
        _close(
            summary["reconstructed_chi2_per_ndf"],
            summary["stated_chi2_per_ndf"],
        ),
        "SUMMARY_RATIO_MISMATCH",
        "stored chi2/ndf is not reproduced",
    )


def _expected_rows(summary: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        "CL-019": {
            "claim_text": "Legacy MV3 v3 exact B8 fraction in thresholded MC",
            "current_value": repr(summary["mc_fractions"]["B8"]),
            "n_data": "",
            "n_mc": str(summary["mc_n"]),
            "numerator": str(summary["mc_counts"]["B8"]),
            "denominator": str(summary["mc_n"]),
            "ci_method": "fixed_exact_summary_count_fraction",
            "truth_type": "legacy_thresholded_mc_summary",
            "status": "GATED",
            "ci_status": "NOT_APPLICABLE_FIXED_EXACT_COUNTS_SYSTEMATICS_UNEVALUATED",
        },
        "CL-020": {
            "claim_text": "Legacy MV3 v3 exact B8 fraction in selected data",
            "current_value": repr(summary["data_fractions"]["B8"]),
            "n_data": str(summary["data_n"]),
            "n_mc": "",
            "numerator": str(summary["data_counts"]["B8"]),
            "denominator": str(summary["data_n"]),
            "ci_method": "fixed_exact_summary_count_fraction",
            "truth_type": "legacy_selected_data_summary",
            "status": "GATED",
            "ci_status": "NOT_APPLICABLE_FIXED_EXACT_COUNTS_SYSTEMATICS_UNEVALUATED",
        },
        "CL-021": {
            "claim_text": "Legacy MV3 v3 exact Pearson profile chi2/ndf diagnostic",
            "current_value": repr(summary["stated_chi2_per_ndf"]),
            "n_data": str(summary["data_n"]),
            "n_mc": str(summary["mc_n"]),
            "numerator": "",
            "denominator": "",
            "ci_method": "pearson_chi2_from_data_counts_vs_mc_fraction_expected_counts",
            "truth_type": "legacy_data_mc_profile_diagnostic",
            "status": "FLAWED",
            "ci_status": "NOT_APPLICABLE_FIXED_PEARSON_CHI2_SYSTEMATICS_UNEVALUATED",
        },
    }


def _check_rows(
    rows: dict[str, dict[str, str]],
    summary: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    required_notes = {
        "CL-019": ("tracked summary", "55619/249484", "systematics", "not an accepted"),
        "CL-020": ("tracked summary", "7051/306745", "systematics", "not an accepted"),
        "CL-021": (
            "204808.2179684494",
            "3 degrees of freedom",
            "pearson",
            "not a calibrated goodness-of-fit",
        ),
    }
    forbidden_notes = {
        "CL-019": ("omits exact per-stave counts", "exact numerator can be reconstructed"),
        "CL-020": ("omits exact per-stave counts", "exact numerator can be reconstructed"),
        "CL-021": ("does not provide the underlying chi2", "no machine-readable result"),
    }
    for claim_id, expected in _expected_rows(summary).items():
        row = rows[claim_id]
        for field, expected_value in expected.items():
            _expect(
                issues,
                row[field] == expected_value,
                f"FIELD_{field.upper()}",
                f"{field} must be {expected_value!r}, found {row[field]!r}",
                claim_id,
            )
        for field in (
            "stat_unc",
            "syst_unc",
            "total_unc",
            "ci_low",
            "ci_high",
            "ci_level",
            "p_value",
        ):
            _expect(
                issues,
                row[field] == "",
                "UNSUPPORTED_QUANTITATIVE_FIELD",
                f"{field} must remain empty",
                claim_id,
            )
        common = {
            "allowed_status_validated": "NO",
            "source_report": SOURCE_REPORT,
            "source_script": "",
            "source_data": SOURCE_SUMMARY,
            "source_commit": SOURCE_COMMIT,
            "link_validated": "YES",
            "blocked_by": BLOCKER,
        }
        for field, expected_value in common.items():
            _expect(
                issues,
                row[field] == expected_value,
                f"FIELD_{field.upper()}",
                f"{field} must be {expected_value!r}",
                claim_id,
            )
        note = row["notes"].lower()
        for fragment in required_notes[claim_id]:
            _expect(
                issues,
                fragment in note,
                "NOTE_CAVEAT",
                f"notes must include {fragment!r}",
                claim_id,
            )
        for fragment in forbidden_notes[claim_id]:
            _expect(
                issues,
                fragment not in note,
                "NOTE_DENIES_TRACKED_SUMMARY",
                f"notes must not include {fragment!r}",
                claim_id,
            )


def validate(
    ledger_path: Path,
    report_path: Path,
    summary_path: Path,
    remediation_path: Path,
) -> dict[str, Any]:
    ledger_raw, ledger_prov = _snapshot(ledger_path)
    report_raw, report_prov = _snapshot(report_path)
    summary_raw, summary_prov = _snapshot(summary_path)
    remediation_raw, remediation_prov = _snapshot(remediation_path)
    _, rows = _load_ledger(_decode(ledger_raw, ledger_path))
    report = _decode(report_raw, report_path)
    summary = _load_summary(_decode(summary_raw, summary_path))
    remediation = _remediation_contract(_decode(remediation_raw, remediation_path))
    issues: list[dict[str, Any]] = []

    _check_summary(summary, issues)
    _expect(
        issues,
        "χ²/ndf = 68269.4" in report,
        "REPORT_ROUNDED_LABEL",
        "legacy report rounded chi2/ndf label changed",
    )
    for key, present in remediation.items():
        _expect(
            issues,
            present,
            "REMEDIATION_CONTRACT",
            f"strict remediation contract is missing {key}",
        )
    _check_rows(rows, summary, issues)

    return {
        "validator": "validate_mv3_legacy_claim_rows.py",
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "claims": list(CLAIM_IDS),
        "source_contract": summary,
        "remediation_contract": remediation,
        "inputs": {
            "claim_ledger": ledger_prov,
            "legacy_report": report_prov,
            "tracked_summary": summary_prov,
            "strict_remediation": remediation_prov,
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("legacy_report", type=Path)
    parser.add_argument("tracked_summary", type=Path)
    parser.add_argument("strict_remediation", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate(
            args.claim_ledger,
            args.legacy_report,
            args.tracked_summary,
            args.strict_remediation,
        )
    except Mv3ClaimError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
