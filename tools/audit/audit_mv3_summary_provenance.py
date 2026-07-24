#!/usr/bin/env python3
"""Audit MV3 claim rows against the tracked exact summary and report."""

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

VERSION = "1.0.0"
POLICY = "TRACKED_MV3_SUMMARY_OVERRIDES_ROUNDED_REPORT_PROSE"
EXPECTED_COLUMNS = 43
CLAIM_IDS = ("CL-019", "CL-020", "CL-021")
SUMMARY_PATH = "reports/mv3_stopping_v3_1782679272/mv3_summary.json"
STAVES = ("B2", "B4", "B6", "B8")


class AuditInputError(ValueError):
    """Controlled invalid-input error."""


def _snapshot(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"cannot read {path}: {exc}") from exc
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
        raise AuditInputError(f"{path} is not valid UTF-8") from exc


def _load_ledger(text: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise AuditInputError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows:
        raise AuditInputError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise AuditInputError(f"claim-ledger header has {len(header)} columns, expected 43")
    selected: dict[str, dict[str, str]] = {}
    for row in rows[1:]:
        if row and row[0] in CLAIM_IDS:
            if len(row) != EXPECTED_COLUMNS:
                raise AuditInputError(f"{row[0]} has {len(row)} columns, expected 43")
            selected[row[0]] = dict(zip(header, row, strict=True))
    missing = [claim_id for claim_id in CLAIM_IDS if claim_id not in selected]
    if missing:
        raise AuditInputError(f"missing required rows: {', '.join(missing)}")
    return header, selected


def _load_summary(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"invalid MV3 summary JSON: {exc}") from exc
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
        raise AuditInputError(f"MV3 summary schema mismatch: {exc}") from exc

    expected = {stave: data_n * mc_fractions[stave] for stave in STAVES}
    reconstructed_chi2 = math.fsum(
        (data_counts[stave] - expected[stave]) ** 2 / expected[stave]
        for stave in STAVES
    )
    reconstructed_ndf = len(STAVES) - 1
    reconstructed_ratio = reconstructed_chi2 / reconstructed_ndf
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
        "reconstructed_chi2_per_ndf": reconstructed_ratio,
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


def _close(left: float, right: float, tolerance: float = 1e-12) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def audit(ledger_path: Path, report_path: Path, summary_path: Path) -> dict[str, Any]:
    ledger_raw, ledger_prov = _snapshot(ledger_path)
    report_raw, report_prov = _snapshot(report_path)
    summary_raw, summary_prov = _snapshot(summary_path)
    _, rows = _load_ledger(_decode(ledger_raw, ledger_path))
    report_text = _decode(report_raw, report_path)
    summary = _load_summary(_decode(summary_raw, summary_path))
    issues: list[dict[str, Any]] = []

    if sum(summary["mc_counts"].values()) != summary["mc_n"]:
        _issue(issues, "SUMMARY_MC_COUNT_SUM", "MC stave counts do not sum to n_above_threshold")
    if sum(summary["data_counts"].values()) != summary["data_n"]:
        _issue(issues, "SUMMARY_DATA_COUNT_SUM", "data stave counts do not sum to n_events")
    for stave in STAVES:
        if not _close(
            summary["mc_counts"][stave] / summary["mc_n"],
            summary["mc_fractions"][stave],
        ):
            _issue(issues, "SUMMARY_MC_FRACTION", f"MC fraction mismatch for {stave}")
        if not _close(
            summary["data_counts"][stave] / summary["data_n"],
            summary["data_fractions"][stave],
        ):
            _issue(issues, "SUMMARY_DATA_FRACTION", f"data fraction mismatch for {stave}")
    if not _close(summary["reconstructed_chi2"], summary["stated_chi2"]):
        _issue(issues, "SUMMARY_CHI2_MISMATCH", "stored chi2 is not reproduced from tracked counts")
    if summary["reconstructed_ndf"] != summary["stated_ndf"]:
        _issue(issues, "SUMMARY_NDF_MISMATCH", "stored ndf is not bins minus one")
    if not _close(summary["reconstructed_chi2_per_ndf"], summary["stated_chi2_per_ndf"]):
        _issue(issues, "SUMMARY_RATIO_MISMATCH", "stored chi2/ndf is not reproduced")
    if "χ²/ndf = 68269.4" not in report_text:
        _issue(issues, "REPORT_ROUNDED_LABEL", "legacy report rounded chi2/ndf label changed")

    expected_rows = {
        "CL-019": {
            "current_value": repr(summary["mc_fractions"]["B8"]),
            "numerator": str(summary["mc_counts"]["B8"]),
            "denominator": str(summary["mc_n"]),
            "source_data": SUMMARY_PATH,
            "ci_method": "fixed_exact_summary_count_fraction",
            "ci_status": "NOT_APPLICABLE_FIXED_EXACT_COUNTS_SYSTEMATICS_UNEVALUATED",
        },
        "CL-020": {
            "current_value": repr(summary["data_fractions"]["B8"]),
            "numerator": str(summary["data_counts"]["B8"]),
            "denominator": str(summary["data_n"]),
            "source_data": SUMMARY_PATH,
            "ci_method": "fixed_exact_summary_count_fraction",
            "ci_status": "NOT_APPLICABLE_FIXED_EXACT_COUNTS_SYSTEMATICS_UNEVALUATED",
        },
        "CL-021": {
            "current_value": repr(summary["stated_chi2_per_ndf"]),
            "source_data": SUMMARY_PATH,
            "ci_method": "pearson_chi2_from_data_counts_vs_mc_fraction_expected_counts",
            "ci_status": "NOT_APPLICABLE_FIXED_PEARSON_CHI2_SYSTEMATICS_UNEVALUATED",
        },
    }
    forbidden_note_fragments = {
        "CL-019": ("omits exact per-stave counts", "exact numerator can be reconstructed"),
        "CL-020": ("omits exact per-stave counts", "exact numerator can be reconstructed"),
        "CL-021": (
            "does not provide the underlying chi2",
            "does not provide the underlying chi2, ndf",
            "no machine-readable result",
        ),
    }
    required_note_fragments = {
        "CL-019": ("tracked summary", "55619/249484", "systematics"),
        "CL-020": ("tracked summary", "7051/306745", "systematics"),
        "CL-021": (
            "204808.2179684494",
            "3 degrees of freedom",
            "pearson",
            "not a calibrated goodness-of-fit",
        ),
    }

    for claim_id, expected in expected_rows.items():
        row = rows[claim_id]
        for field, value in expected.items():
            if row[field] != value:
                _issue(
                    issues,
                    f"LEDGER_{field.upper()}",
                    f"{field} must be {value!r}, found {row[field]!r}",
                    claim_id,
                )
        note = row["notes"].lower()
        for fragment in forbidden_note_fragments[claim_id]:
            if fragment in note:
                _issue(
                    issues,
                    "LEDGER_DENIES_TRACKED_SUMMARY",
                    f"notes incorrectly state {fragment!r}",
                    claim_id,
                )
        for fragment in required_note_fragments[claim_id]:
            if fragment not in note:
                _issue(
                    issues,
                    "LEDGER_MISSING_SOURCE_CAVEAT",
                    f"notes must include {fragment!r}",
                    claim_id,
                )

    return {
        "auditor": "audit_mv3_summary_provenance.py",
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "claims": list(CLAIM_IDS),
        "source_contract": summary,
        "inputs": {
            "claim_ledger": ledger_prov,
            "legacy_report": report_prov,
            "tracked_summary": summary_prov,
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("legacy_report", type=Path)
    parser.add_argument("tracked_summary", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.claim_ledger, args.legacy_report, args.tracked_summary)
    except AuditInputError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
