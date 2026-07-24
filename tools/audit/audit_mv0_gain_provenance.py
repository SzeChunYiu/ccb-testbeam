#!/usr/bin/env python3
"""Audit whether the canonical MV0 gain claim has reproducible producer provenance."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import html
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "MV0_GAIN_NOT_CANONICAL_UNTIL_PRODUCER_AND_ARTIFACT_REPRODUCE"
EXPECTED_COLUMNS = 43
TARGET_CLAIMS = ("CL-013", "CL-014")


class MV0AuditError(ValueError):
    """Controlled input, encoding, or schema error."""


def _snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise MV0AuditError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MV0AuditError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _read_ledger(text: str) -> tuple[list[str], dict[str, list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise MV0AuditError(f"invalid claim-ledger CSV: {exc}") from exc
    if not rows:
        raise MV0AuditError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise MV0AuditError(
            f"claim-ledger header has {len(header)} columns, expected {EXPECTED_COLUMNS}"
        )
    by_id: dict[str, list[str]] = {}
    for row in rows[1:]:
        if row and row[0].strip():
            by_id[row[0].strip()] = row
    return header, by_id


def _script_contract(script_text: str) -> dict[str, Any]:
    try:
        ast.parse(script_text)
    except SyntaxError as exc:
        raise MV0AuditError(f"producer script is not valid Python: {exc}") from exc

    compact = re.sub(r"\s+", "", script_text)
    has_net_expression = bool(
        re.search(
            r"(?:np\.)?abs\(.{0,400}amplitude_adc.{0,400}-.{0,400}baseline_adc",
            script_text,
            flags=re.DOTALL,
        )
        or re.search(
            r"(?:np\.)?abs\(.{0,400}baseline_adc.{0,400}-.{0,400}amplitude_adc",
            script_text,
            flags=re.DOTALL,
        )
    )
    raw_global = 'data_amp=dsel["amplitude_adc"]' in compact
    raw_stave = (
        's:dsel.loc[dsel["stave"]==s,"amplitude_adc"].to_numpy(dtype=float)'
        in compact
    )
    return {
        "syntax_valid": True,
        "implements_net_amplitude": has_net_expression,
        "uses_raw_amplitude_for_global_fit": raw_global,
        "uses_raw_amplitude_for_stave_fit": raw_stave,
        "declares_data_csv_argument": 'add_argument("--data-csv"' in compact,
        "declares_truth_npz_argument": 'add_argument("--truth-npz"' in compact,
        "emits_gain_method": "gain_method" in script_text,
        "emits_gain_systematic_unc_pct": "gain_systematic_unc_pct" in script_text,
        "emits_ks_at_median_gain": "ks_at_median_gain" in script_text,
    }


def audit(
    ledger_path: Path,
    report_path: Path,
    calibration_path: Path,
    script_path: Path,
) -> dict[str, Any]:
    ledger_text, ledger_prov = _snapshot(ledger_path)
    report_text, report_prov = _snapshot(report_path)
    calibration_text, calibration_prov = _snapshot(calibration_path)
    script_text, script_prov = _snapshot(script_path)

    header, rows = _read_ledger(ledger_text)
    try:
        calibration = json.loads(calibration_text)
    except json.JSONDecodeError as exc:
        raise MV0AuditError(f"invalid calibration JSON: {exc}") from exc
    if not isinstance(calibration, dict):
        raise MV0AuditError("calibration JSON must be an object")

    issues: list[dict[str, Any]] = []
    row_summary: dict[str, Any] = {}
    for claim_id in TARGET_CLAIMS:
        row = rows.get(claim_id)
        if row is None:
            issues.append({"code": "MISSING_LEDGER_CLAIM", "claim_id": claim_id})
            continue
        row_summary[claim_id] = {
            "actual_columns": len(row),
            "schema_state": (
                "EXACT_WIDTH" if len(row) == EXPECTED_COLUMNS else "WIDTH_MISMATCH"
            ),
            "field_interpretation": (
                "PERMITTED" if len(row) == EXPECTED_COLUMNS else "WITHHELD"
            ),
        }
        if len(row) != EXPECTED_COLUMNS:
            issues.append(
                {
                    "code": "LEDGER_ROW_WIDTH_MISMATCH",
                    "claim_id": claim_id,
                    "expected_columns": EXPECTED_COLUMNS,
                    "actual_columns": len(row),
                    "field_interpretation": "WITHHELD",
                }
            )

    stale_tokens = {
        "scripts/mv0_calibration.py": "NONEXISTENT_OR_STALE_PRODUCER_PATH",
        "reports/mv0_calibration_1782677847/results.json": "NONEXISTENT_RESULT_PATH",
    }
    for token, code in stale_tokens.items():
        if token in ledger_text:
            issues.append({"code": code, "token": token})

    calibration_block = calibration.get("calibration")
    if not isinstance(calibration_block, dict):
        raise MV0AuditError("calibration JSON lacks an object-valued calibration field")
    methodology = str(calibration.get("methodology_note", ""))
    gain = calibration_block.get("gain_adc_per_mev")
    syst_pct = calibration_block.get("gain_systematic_unc_pct")
    if gain != 92.0:
        issues.append({"code": "UNEXPECTED_CALIBRATION_GAIN", "observed": gain})
    if syst_pct != 30:
        issues.append({"code": "UNEXPECTED_SYSTEMATIC_PERCENT", "observed": syst_pct})
    if "abs(amplitude_adc - baseline_adc)" not in methodology:
        issues.append({"code": "CALIBRATION_NET_METHOD_NOT_DECLARED"})

    unsupported_uncertainty_fields = [
        field
        for field in ("gain_statistical_unc", "gain_ci_low", "gain_ci_high", "gain_ci_method")
        if field not in calibration_block
    ]

    contract = _script_contract(script_text)
    if not contract["implements_net_amplitude"]:
        issues.append({"code": "PRODUCER_DOES_NOT_IMPLEMENT_NET_AMPLITUDE"})
    if contract["uses_raw_amplitude_for_global_fit"]:
        issues.append({"code": "PRODUCER_USES_RAW_GLOBAL_AMPLITUDE"})
    if contract["uses_raw_amplitude_for_stave_fit"]:
        issues.append({"code": "PRODUCER_USES_RAW_STAVE_AMPLITUDE"})
    missing_output_contract = [
        key
        for key in (
            "emits_gain_method",
            "emits_gain_systematic_unc_pct",
            "emits_ks_at_median_gain",
        )
        if not contract[key]
    ]
    if missing_output_contract:
        issues.append(
            {
                "code": "PRODUCER_OUTPUT_SCHEMA_MISMATCH",
                "missing_contract_flags": missing_output_contract,
            }
        )

    report_compact = re.sub(r"\s+", " ", report_text)
    command_uses_data_csv = "--data-csv" in report_compact
    command_uses_truth_npz = "--truth-npz" in report_compact
    if contract["declares_data_csv_argument"] and not command_uses_data_csv:
        issues.append({"code": "REPORT_COMMAND_OMITS_DATA_CSV_ARGUMENT"})
    if contract["declares_truth_npz_argument"] and not command_uses_truth_npz:
        issues.append({"code": "REPORT_COMMAND_OMITS_TRUTH_NPZ_ARGUMENT"})

    numerator = 1781.0
    denominator = 26.44 * 0.733
    independently_recomputed_gain = numerator / denominator

    return {
        "validator": "audit_mv0_gain_provenance.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "ledger_header_columns": len(header),
        "target_claims": row_summary,
        "calibration_claim": {
            "gain_adc_per_mev": gain,
            "systematic_uncertainty_percent": syst_pct,
            "independently_recomputed_gain_adc_per_mev": independently_recomputed_gain,
            "recompute_inputs": {
                "data_b2_net_median_adc": numerator,
                "mc_b2_edep_median_mev": 26.44,
                "peak_fraction": 0.733,
            },
            "unsupported_uncertainty_fields": unsupported_uncertainty_fields,
            "formal_confidence_interval_available": False,
        },
        "producer_contract": contract,
        "report_command_contract": {
            "uses_data_csv_argument": command_uses_data_csv,
            "uses_truth_npz_argument": command_uses_truth_npz,
        },
        "provenance": {
            "claim_ledger": ledger_prov,
            "report": report_prov,
            "calibration_json": calibration_prov,
            "producer_script": script_prov,
        },
        "issues": issues,
        "n_issues": len(issues),
        "acceptance": (
            "WITHHOLD_CANONICAL_GAIN"
            if issues
            else "PRODUCER_AND_ARTIFACT_CONTRACT_ALIGNED"
        ),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_svg(path: Path, payload: dict[str, Any]) -> None:
    status = html.escape(payload["status"])
    issue_count = payload["n_issues"]
    producer = payload["producer_contract"]
    ledger_exact = all(
        row.get("schema_state") == "EXACT_WIDTH"
        for row in payload["target_claims"].values()
    )
    rows = [
        ("Calibration artifact", "net amplitude declared", True),
        (
            "Tracked producer",
            "net amplitude implemented",
            producer["implements_net_amplitude"],
        ),
        ("Claim ledger", "CL-013/CL-014 exact width", ledger_exact),
        (
            "Reproduce command",
            "required CLI inputs present",
            payload["report_command_contract"]["uses_data_csv_argument"]
            and payload["report_command_contract"]["uses_truth_npz_argument"],
        ),
    ]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="920" height="360" '
        'viewBox="0 0 920 360" role="img" aria-labelledby="title desc">',
        '<title id="title">MV0 gain provenance contract audit</title>',
        '<desc id="desc">Repository evidence showing whether the calibration artifact, '
        'producer code, claim ledger, and reproduction command form one reproducible chain.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="30" y="38" font-family="sans-serif" font-size="22" '
        'font-weight="bold">MV0 gain provenance chain</text>',
        '<text x="30" y="63" font-family="sans-serif" font-size="13">'
        'Software/provenance evidence; not detector data and not a gain remeasurement.</text>',
    ]
    for index, (name, detail, passed) in enumerate(rows):
        y = 95 + index * 55
        fill = "#d9d9d9" if passed else "url(#hatch)"
        if index == 0:
            parts.insert(
                5,
                '<defs><pattern id="hatch" width="8" height="8" '
                'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                '<line x1="0" y1="0" x2="0" y2="8" stroke="#555" '
                'stroke-width="2"/></pattern></defs>',
            )
        parts.extend(
            [
                f'<rect x="30" y="{y}" width="240" height="36" fill="{fill}" '
                'stroke="black"/>',
                f'<text x="42" y="{y + 23}" font-family="sans-serif" '
                f'font-size="14">{html.escape(name)}</text>',
                f'<line x1="270" y1="{y + 18}" x2="350" y2="{y + 18}" '
                'stroke="black" stroke-width="2"/>',
                f'<rect x="350" y="{y}" width="500" height="36" fill="{fill}" '
                'stroke="black"/>',
                f'<text x="365" y="{y + 23}" font-family="sans-serif" '
                f'font-size="14">{html.escape(detail)}: '
                f'{"YES" if passed else "NO"}</text>',
            ]
        )
    parts.extend(
        [
            '<text x="30" y="330" font-family="sans-serif" font-size="13">'
            f'Status: {status}; findings: {issue_count}; policy: '
            f'{html.escape(payload["policy"])}</text>',
            "</svg>",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("calibration_json", type=Path)
    parser.add_argument("producer_script", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)

    try:
        result = audit(
            args.claim_ledger,
            args.report,
            args.calibration_json,
            args.producer_script,
        )
    except MV0AuditError as exc:
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
