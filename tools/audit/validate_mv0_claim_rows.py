#!/usr/bin/env python3
"""Validate CL-013 and CL-014 against exact MV0 source evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "MV0_CLAIMS_REQUIRE_EXACT_WIDTH_AND_SOURCE_BACKED_LIMITATIONS"
EXPECTED_COLUMNS = 43
SOURCE_COMMIT = "3c5ff5cf587c8ca9cefda20cb220ba29effd2170"
REPORT_PATH = "reports/mv0_calibration_1782677847/REPORT.md"
SCRIPT_PATH = "scripts/mv0_calibrate_from_data.py"
DATA_PATH = "reports/mv0_calibration_1782677847/calibration.json"


class InputError(ValueError):
    """Controlled input or schema error."""


def read_utf8(path: Path) -> tuple[str, dict[str, Any]]:
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


def parse_ledger(text: str) -> tuple[list[str], list[list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid ledger CSV: {exc}") from exc
    if not rows:
        raise InputError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise InputError(
            f"ledger header has {len(header)} columns, expected {EXPECTED_COLUMNS}"
        )
    return header, rows[1:]


def find_row(header: list[str], rows: list[list[str]], claim_id: str) -> dict[str, str]:
    matches = [row for row in rows if row and row[0] == claim_id]
    if len(matches) != 1:
        raise InputError(f"expected one {claim_id} row, found {len(matches)}")
    row = matches[0]
    if len(row) != len(header):
        raise InputError(f"{claim_id} has {len(row)} columns, expected {len(header)}")
    return dict(zip(header, row, strict=True))


def expect(
    issues: list[dict[str, Any]],
    claim_id: str,
    row: dict[str, str],
    field: str,
    expected: str,
) -> None:
    actual = row.get(field, "")
    if actual != expected:
        issues.append(
            {
                "code": "FIELD_MISMATCH",
                "claim_id": claim_id,
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def require_phrases(
    issues: list[dict[str, Any]],
    code: str,
    text: str,
    phrases: tuple[str, ...],
    source: str,
) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        issues.append(
            {
                "code": code,
                "source": source,
                "missing_phrases": missing,
            }
        )


def validate_texts(
    ledger_text: str,
    report_text: str,
    calibration_text: str,
) -> dict[str, Any]:
    header, rows = parse_ledger(ledger_text)
    cl013 = find_row(header, rows, "CL-013")
    cl014 = find_row(header, rows, "CL-014")
    try:
        calibration = json.loads(calibration_text)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid calibration JSON: {exc}") from exc

    issues: list[dict[str, Any]] = []
    common = {
        "chapter": "Energy",
        "section": "7",
        "truth_type": "data_mc_calibration_proxy",
        "source_report": REPORT_PATH,
        "source_script": SCRIPT_PATH,
        "source_data": DATA_PATH,
        "source_commit": SOURCE_COMMIT,
        "link_validated": "YES",
        "blocked_by": "BLK-MV0-001",
    }
    expected = {
        "CL-013": {
            **common,
            "claim_text": "Digitizer gain MV0 v2 median-matching estimate",
            "current_value": "92",
            "unit": "ADC/MeV",
            "stat_unc": "",
            "syst_unc": "28",
            "total_unc": "",
            "ci_low": "",
            "ci_high": "",
            "ci_level": "",
            "ci_method": "systematic_envelope",
            "n_data": "579424",
            "n_mc": "321130",
            "baseline_value": "110",
            "delta_vs_baseline": "-18",
            "status": "GATED",
            "allowed_status_validated": "NO",
            "ci_status": "SYSTEMATIC_ENVELOPE_NOT_CONFIDENCE_INTERVAL",
            "supersedes": "110 ADC/MeV v1",
        },
        "CL-014": {
            **common,
            "claim_text": "MV0 B2 KS statistic at median-matched gain",
            "current_value": "0.1577",
            "unit": "dimensionless",
            "ci_method": "fixed_two_sample_KS_statistic",
            "n_data": "579424",
            "n_mc": "321130",
            "baseline_value": "0.1188",
            "delta_vs_baseline": "0.0389",
            "status": "TENSION",
            "allowed_status_validated": "YES",
            "ci_status": "NOT_APPLICABLE_FIXED_OUTPUT_P_VALUE_NOT_REPORTED",
        },
    }
    for claim_id, row in (("CL-013", cl013), ("CL-014", cl014)):
        for field, value in expected[claim_id].items():
            expect(issues, claim_id, row, field, value)

    notes_013 = cl013.get("notes", "").lower()
    for phrase in (
        "30% heuristic systematic envelope",
        "not a confidence interval",
        "producer/data manifest",
        "not authorized as a precision calibration",
    ):
        if phrase not in notes_013:
            issues.append(
                {
                    "code": "MISSING_REQUIRED_CAVEAT",
                    "claim_id": "CL-013",
                    "missing_phrase": phrase,
                }
            )

    notes_014 = cl014.get("notes", "").lower()
    for phrase in (
        "fixed source output",
        "p-value is not reported",
        "selection-threshold closure",
        "not a calibrated goodness-of-fit probability",
    ):
        if phrase not in notes_014:
            issues.append(
                {
                    "code": "MISSING_REQUIRED_CAVEAT",
                    "claim_id": "CL-014",
                    "missing_phrase": phrase,
                }
            )

    require_phrases(
        issues,
        "REPORT_EVIDENCE_MISSING",
        report_text,
        (
            "Gain = **92 ± 28 ADC/MeV**",
            "KS optimal gain | 60 ADC/MeV (KS=0.119)",
            "KS at gain=92 | 0.158",
            "±30% on the gain",
        ),
        REPORT_PATH,
    )

    cal = calibration.get("calibration", {})
    checks = {
        "gain_adc_per_mev": 92.0,
        "gain_systematic_unc_pct": 30,
        "ks_best": 0.1188,
        "ks_best_gain": 60.0,
        "ks_at_median_gain": 0.1577,
    }
    for field, value in checks.items():
        if cal.get(field) != value:
            issues.append(
                {
                    "code": "CALIBRATION_VALUE_MISMATCH",
                    "field": field,
                    "expected": value,
                    "actual": cal.get(field),
                }
            )
    b2 = calibration.get("data_net_amplitude_stats", {}).get("B2", {})
    mc = calibration.get("mc_b2_edep_stats_mev", {})
    if b2.get("n") != 579424:
        issues.append({"code": "DATA_COUNT_MISMATCH", "actual": b2.get("n")})
    if mc.get("n_tracks_with_B2_hit") != 321130:
        issues.append(
            {"code": "MC_COUNT_MISMATCH", "actual": mc.get("n_tracks_with_B2_hit")}
        )

    return {
        "validator": "validate_mv0_claim_rows.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "expected_columns": EXPECTED_COLUMNS,
        "validated_claim_ids": ["CL-013", "CL-014"],
        "source_commit_required": SOURCE_COMMIT,
        "issues": issues,
        "n_issues": len(issues),
        "source_values": {
            "gain_adc_per_mev": cal.get("gain_adc_per_mev"),
            "gain_systematic_unc_pct": cal.get("gain_systematic_unc_pct"),
            "ks_at_median_gain": cal.get("ks_at_median_gain"),
            "ks_best": cal.get("ks_best"),
            "ks_best_gain": cal.get("ks_best_gain"),
            "n_data_b2": b2.get("n"),
            "n_mc_b2_tracks": mc.get("n_tracks_with_B2_hit"),
        },
    }


def audit(ledger: Path, report: Path, calibration: Path) -> dict[str, Any]:
    ledger_text, ledger_prov = read_utf8(ledger)
    report_text, report_prov = read_utf8(report)
    calibration_text, calibration_prov = read_utf8(calibration)
    result = validate_texts(ledger_text, report_text, calibration_text)
    result["claim_ledger"] = ledger_prov
    result["report"] = report_prov
    result["calibration_json"] = calibration_prov
    return result


def write_svg(path: Path, result: dict[str, Any]) -> None:
    status = html.escape(result["status"])
    issues = result["n_issues"]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="980" height="470"
 viewBox="0 0 980 470" role="img" aria-labelledby="title desc">
<title id="title">MV0 claim-row source gate</title>
<desc id="desc">Synthetic provenance diagram, not detector data.</desc>
<rect width="100%" height="100%" fill="white"/>
<text x="35" y="42" font-family="sans-serif" font-size="23" font-weight="bold">
MV0 gain and KS claims: exact-width source reconstruction</text>
<text x="35" y="70" font-family="sans-serif" font-size="14">
Repository provenance evidence; no new detector measurement or calibration fit.</text>
<rect x="55" y="110" width="250" height="105" fill="white" stroke="black"/>
<text x="180" y="140" text-anchor="middle" font-family="monospace" font-size="17">CL-013</text>
<text x="180" y="168" text-anchor="middle" font-family="sans-serif" font-size="14">92 ADC/MeV</text>
<text x="180" y="192" text-anchor="middle" font-family="sans-serif"
 font-size="13">30% heuristic envelope; GATED</text>
<line x1="320" y1="162" x2="455" y2="162" stroke="black" stroke-width="2"/>
<rect x="470" y="110" width="250" height="105" fill="#eeeeee" stroke="black"/>
<text x="595" y="140" text-anchor="middle" font-family="monospace" font-size="17">CL-014</text>
<text x="595" y="168" text-anchor="middle" font-family="sans-serif"
 font-size="14">KS D = 0.1577</text>
<text x="595" y="192" text-anchor="middle" font-family="sans-serif"
 font-size="13">fixed diagnostic; p-value absent</text>
<rect x="55" y="255" width="850" height="120" fill="white" stroke="black"/>
<text x="80" y="286" font-family="sans-serif" font-size="15">Exact source values:</text>
<text x="80" y="314" font-family="monospace" font-size="14">
n_data(B2)=579424; n_mc(B2 tracks)=321130</text>
<text x="80" y="340" font-family="monospace" font-size="14">
KS optimum: gain=60, D=0.1188; at gain=92, D=0.1577</text>
<text x="80" y="365" font-family="sans-serif" font-size="13">Policy: {html.escape(POLICY)}</text>
<text x="35" y="430" font-family="sans-serif" font-size="14">
Status: {status}; issues: {issues}; synthetic validation diagram, not data.</text>
</svg>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("calibration_json", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.claim_ledger, args.report, args.calibration_json)
    except InputError as exc:
        print(f"INPUT ERROR: {exc}")
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.svg:
        write_svg(args.svg, result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
