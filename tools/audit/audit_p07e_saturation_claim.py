#!/usr/bin/env python3
"""Audit the source chain and scientific interpretation of claim CL-016 (P07e)."""

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
TARGET_CLAIM_ID = "CL-016"
POLICY = "P07E_EXTERNAL_DUPLICATE_CLOSURE_OVERRIDES_PSEUDO_SATURATION"
EXPECTED_LEDGER_FIELDS = (
    "claim_id",
    "chapter",
    "section",
    "claim_text",
    "current_value",
    "unit",
    "stat_unc",
    "syst_unc",
    "total_unc",
    "ci_low",
    "ci_high",
    "ci_level",
    "ci_method",
    "bootstrap_unit",
    "n_events",
    "n_runs",
    "n_data",
    "n_mc",
    "numerator",
    "denominator",
    "p_value",
    "effect_size",
    "baseline_value",
    "baseline_unc",
    "delta_vs_baseline",
    "delta_ci_low",
    "delta_ci_high",
    "truth_type",
    "status",
    "allowed_status_validated",
    "source_report",
    "source_script",
    "source_data",
    "source_config",
    "source_manifest",
    "figure_ids",
    "table_ids",
    "source_commit",
    "link_validated",
    "ci_status",
    "blocked_by",
    "supersedes",
    "notes",
)
EXPECTED_PATHS = {
    "source_report": "reports/1781018174.2030.05ac1ce2/REPORT.md",
    "source_script": (
        "scripts/p07e_1781018174_2030_05ac1ce2_"
        "duplicate_saturation_validation.py"
    ),
    "source_data": "reports/1781018174.2030.05ac1ce2/result.json",
    "source_config": (
        "configs/p07e_1781018174_2030_05ac1ce2_"
        "duplicate_saturation_validation.json"
    ),
    "source_manifest": "reports/1781018174.2030.05ac1ce2/manifest.json",
}
EXPECTED_CLAIM_TEXT = "B2 saturation ratio-transfer duplicate charge res68"


class P07eAuditError(ValueError):
    """Controlled input or schema error."""


def _snapshot(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise P07eAuditError(f"cannot read {path}: {exc}") from exc
    return raw, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _utf8(raw: bytes, path: Path) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise P07eAuditError(f"{path} is not valid UTF-8") from exc


def _json(raw: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_utf8(raw, path))
    except json.JSONDecodeError as exc:
        raise P07eAuditError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise P07eAuditError(f"top-level JSON object required in {path}")
    return value


def _finite_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise P07eAuditError(f"{label} is not numeric") from exc
    if not math.isfinite(number):
        raise P07eAuditError(f"{label} is not finite")
    return number


def _method(summary: Any, name: str) -> dict[str, Any]:
    if not isinstance(summary, list):
        raise P07eAuditError("result.summary must be a list")
    matches = [row for row in summary if isinstance(row, dict) and row.get("method") == name]
    if len(matches) != 1:
        raise P07eAuditError(f"result.summary must contain exactly one {name!r} row")
    return matches[0]


def _interval(row: dict[str, Any], key: str, estimate: float) -> tuple[float, float]:
    value = row.get(key)
    if not isinstance(value, list) or len(value) != 2:
        raise P07eAuditError(f"{key} must be a two-element list")
    low = _finite_float(value[0], f"{key}[0]")
    high = _finite_float(value[1], f"{key}[1]")
    if low > high:
        raise P07eAuditError(f"{key} is reversed")
    if not low <= estimate <= high:
        raise P07eAuditError(f"{key} does not contain its point estimate")
    return low, high


def _parse_target_ledger(text: str) -> tuple[dict[str, str] | None, list[dict[str, Any]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise P07eAuditError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows:
        raise P07eAuditError("claim ledger is empty")
    if tuple(rows[0]) != EXPECTED_LEDGER_FIELDS:
        raise P07eAuditError("claim ledger header is not the canonical 43-column schema")

    findings: list[dict[str, Any]] = []
    matches = [
        (index + 2, row)
        for index, row in enumerate(rows[1:])
        if row and row[0] == TARGET_CLAIM_ID
    ]
    if len(matches) != 1:
        raise P07eAuditError(f"expected exactly one {TARGET_CLAIM_ID} row")
    row_number, row = matches[0]
    if len(row) != len(EXPECTED_LEDGER_FIELDS):
        findings.append({
            "code": "LEDGER_ROW_WIDTH_MISMATCH",
            "row_number": row_number,
            "claim_id": TARGET_CLAIM_ID,
            "expected_columns": len(EXPECTED_LEDGER_FIELDS),
            "actual_columns": len(row),
            "field_interpretation": "WITHHELD",
        })
        return None, findings
    return dict(zip(EXPECTED_LEDGER_FIELDS, row)), findings


def _check_ledger_alignment(
    ledger: dict[str, str] | None,
    ml: dict[str, Any],
    raw: dict[str, Any],
    ml_ci: tuple[float, float],
    delta: float,
) -> list[dict[str, Any]]:
    if ledger is None:
        return []
    findings: list[dict[str, Any]] = []

    expected_text = {
        "claim_text": EXPECTED_CLAIM_TEXT,
        "unit": "fraction",
        "ci_level": "0.95",
        "ci_method": "run_block_bootstrap_percentile",
        "bootstrap_unit": "run",
        "truth_type": "data_external_duplicate_readout",
        "status": "GATED",
        "allowed_status_validated": "YES",
        "link_validated": "YES",
        "ci_status": "CI_AVAILABLE_PRODUCER_BYTES_UNBOUND",
        "blocked_by": "BLK-P07E-001",
    }
    expected_text.update(EXPECTED_PATHS)
    for field, expected in expected_text.items():
        if ledger.get(field) != expected:
            findings.append({
                "code": "LEDGER_FIELD_MISMATCH",
                "field": field,
                "expected": expected,
                "observed": ledger.get(field),
            })

    expected_numeric = {
        "current_value": _finite_float(ml.get("charge_res68_abs_frac"), "ml charge res68"),
        "ci_low": ml_ci[0],
        "ci_high": ml_ci[1],
        "n_events": float(int(ml.get("n", 0))),
        "n_data": float(int(ml.get("n", 0))),
        "baseline_value": _finite_float(raw.get("charge_res68_abs_frac"), "raw charge res68"),
        "delta_vs_baseline": delta,
    }
    for field, expected in expected_numeric.items():
        try:
            observed = float(ledger.get(field, ""))
        except ValueError:
            findings.append({
                "code": "LEDGER_NUMERIC_FIELD_INVALID",
                "field": field,
                "observed": ledger.get(field),
            })
            continue
        if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-15):
            findings.append({
                "code": "LEDGER_NUMERIC_FIELD_MISMATCH",
                "field": field,
                "expected": expected,
                "observed": observed,
            })
    return findings


def audit(
    ledger_path: Path,
    report_path: Path,
    result_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    snapshots: dict[str, dict[str, Any]] = {}
    raw_inputs: dict[str, bytes] = {}
    for name, path in {
        "claim_ledger": ledger_path,
        "report": report_path,
        "result": result_path,
        "manifest": manifest_path,
    }.items():
        raw, provenance = _snapshot(path)
        raw_inputs[name] = raw
        snapshots[name] = provenance

    report = _utf8(raw_inputs["report"], report_path)
    result = _json(raw_inputs["result"], result_path)
    manifest = _json(raw_inputs["manifest"], manifest_path)
    ledger, findings = _parse_target_ledger(_utf8(raw_inputs["claim_ledger"], ledger_path))

    if result.get("study") != "P07e":
        findings.append({"code": "RESULT_STUDY_MISMATCH", "observed": result.get("study")})
    if manifest.get("study") != "P07e":
        findings.append({"code": "MANIFEST_STUDY_MISMATCH", "observed": manifest.get("study")})
    if manifest.get("ticket") != result.get("ticket_id"):
        findings.append({
            "code": "TICKET_ID_MISMATCH",
            "result": result.get("ticket_id"),
            "manifest": manifest.get("ticket"),
        })

    ml = _method(result.get("summary"), "ml_ratio_transfer")
    raw = _method(result.get("summary"), "observed_raw")
    traditional = _method(result.get("summary"), "traditional_template")

    ml_value = _finite_float(ml.get("charge_res68_abs_frac"), "ml charge res68")
    raw_value = _finite_float(raw.get("charge_res68_abs_frac"), "raw charge res68")
    traditional_value = _finite_float(
        traditional.get("charge_res68_abs_frac"),
        "traditional charge res68",
    )
    ml_ci = _interval(
        ml,
        "run_block_charge_res68_abs_frac_ci95",
        ml_value,
    )
    raw_ci = _interval(
        raw,
        "run_block_charge_res68_abs_frac_ci95",
        raw_value,
    )
    delta = ml_value - raw_value

    pseudo_ml = _method(
        result.get("pseudo_saturation_recovery_median_by_method"),
        "ml_ratio_transfer",
    )
    pseudo_value = _finite_float(pseudo_ml.get("res68_abs_frac"), "pseudo ML res68")
    if pseudo_value >= ml_value:
        findings.append({
            "code": "EXPECTED_PSEUDO_EXTERNAL_ORDERING_MISSING",
            "pseudo_res68": pseudo_value,
            "external_res68": ml_value,
        })

    if ml_ci[0] <= raw_ci[1]:
        findings.append({
            "code": "ML_HARM_INTERVALS_NOT_SEPARATED",
            "ml_ci95": list(ml_ci),
            "raw_ci95": list(raw_ci),
        })

    required_report_tokens = (
        "duplicate readout therefore does not support applying the ratio-transfer correction",
        "leave-one-run-out",
        "no Monte Carlo was used",
    )
    for token in required_report_tokens:
        if token not in report:
            findings.append({"code": "REPORT_TOKEN_MISSING", "token": token})

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        findings.append({"code": "MANIFEST_OUTPUT_HASHES_MISSING"})
    else:
        for name, key in (("report", "REPORT.md"), ("result", "result.json")):
            declared = outputs.get(key)
            measured = snapshots[name]["sha256"]
            if declared != measured:
                findings.append({
                    "code": "MANIFEST_OUTPUT_HASH_MISMATCH",
                    "artifact": key,
                    "declared": declared,
                    "measured": measured,
                })

    if not manifest.get("producer_sha256"):
        findings.append({"code": "PRODUCER_BYTES_NOT_HASH_BOUND"})
    if manifest.get("worktree_clean") is not True:
        findings.append({"code": "WORKTREE_STATE_NOT_RECORDED_CLEAN"})

    findings.extend(_check_ledger_alignment(ledger, ml, raw, ml_ci, delta))

    return {
        "validator": "audit_p07e_saturation_claim.py",
        "version": VERSION,
        "status": "VALIDATED" if not findings else "FLAWED",
        "policy": POLICY,
        "claim_id": TARGET_CLAIM_ID,
        "scientific_decision": "WITHHOLD_ML_CORRECTION",
        "scientific_basis": {
            "external_validation_rows": int(ml.get("n", 0)),
            "ml_charge_res68_abs_frac": ml_value,
            "ml_charge_res68_abs_frac_ci95": list(ml_ci),
            "raw_charge_res68_abs_frac": raw_value,
            "raw_charge_res68_abs_frac_ci95": list(raw_ci),
            "traditional_charge_res68_abs_frac": traditional_value,
            "ml_minus_raw_charge_res68_abs_frac": delta,
            "pseudo_saturation_ml_res68_abs_frac": pseudo_value,
            "external_ml_worse_than_raw_with_nonoverlapping_run_block_ci95": (
                delta > 0 and ml_ci[0] > raw_ci[1]
            ),
            "interpretation": (
                "Pseudo-saturation recovery is a synthetic closure test. The held-out "
                "odd duplicate channel is external real-data validation and shows worse "
                "ML charge closure than the uncorrected waveform."
            ),
        },
        "provenance": snapshots,
        "manifest_git_commit": manifest.get("git_commit"),
        "findings": findings,
        "n_findings": len(findings),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_svg(path: Path, payload: dict[str, Any]) -> None:
    basis = payload["scientific_basis"]
    ml = basis["ml_charge_res68_abs_frac"]
    raw = basis["raw_charge_res68_abs_frac"]
    pseudo = basis["pseudo_saturation_ml_res68_abs_frac"]
    maximum = max(ml, raw, pseudo) * 1.18
    left, top, width = 180, 90, 560

    def x(value: float) -> float:
        return left + width * value / maximum

    rows = [
        ("Pseudo-saturation ML", pseudo, "synthetic closure"),
        ("Observed raw duplicate", raw, "external data"),
        ("ML duplicate closure", ml, "external data — worse"),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="820" height="390" '
        'viewBox="0 0 820 390" role="img" aria-labelledby="title desc">',
        '<title id="title">P07e saturation recovery evidence hierarchy</title>',
        '<desc id="desc">Synthetic pseudo-saturation recovery appears strong, but held-out '
        'duplicate-channel data show worse ML charge closure than the raw waveform.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="20" y="30" font-family="sans-serif" font-size="20" '
        'font-weight="bold">P07e: synthetic recovery does not authorize '
        'real-data correction</text>',
        '<text x="20" y="54" font-family="sans-serif" font-size="13">'
        'Repository result artifact; res68 is the 68th percentile absolute '
        'fractional '
        'charge error.</text>',
    ]
    for index, (label, value, note) in enumerate(rows):
        y = top + index * 80
        fill = "#d9d9d9" if index < 2 else "url(#hatch)"
        parts.extend([
            f'<text x="20" y="{y + 18}" font-family="sans-serif" font-size="13">{label}</text>',
            f'<rect x="{left}" y="{y}" width="{x(value) - left:.1f}" height="24" '
            f'fill="{fill}" stroke="black"/>',
            f'<text x="{x(value) + 8:.1f}" y="{y + 18}" font-family="monospace" '
            f'font-size="12">{value:.6f} — {note}</text>',
        ])
    parts.insert(
        5,
        '<defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" '
        'stroke="#555" stroke-width="2"/></pattern></defs>',
    )
    axis_y = 335
    parts.extend([
        f'<line x1="{left}" y1="{axis_y}" x2="{left + width}" y2="{axis_y}" stroke="black"/>',
        f'<text x="{left + width / 2}" y="365" text-anchor="middle" '
        'font-family="sans-serif" font-size="13">charge res68 absolute fractional '
        'error (lower is better)</text>',
        '<text x="20" y="385" font-family="sans-serif" font-size="11">'
        'Visual evidence from committed P07e result.json; not a detector calibration '
        'and not a new data analysis.</text>',
        '</svg>',
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)

    try:
        result = audit(args.claim_ledger, args.report, args.result, args.manifest)
    except P07eAuditError as exc:
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
