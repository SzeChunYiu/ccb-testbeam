#!/usr/bin/env python3
"""Validate source-backed quarantine of the conflicted CL-010/CL-012 Rmax claims."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "QUARANTINE_CONFLICTED_RMAX_DEFINITION"
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
    """Controlled input or schema failure."""


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


def relative(prov: dict[str, Any], root: Path) -> dict[str, Any]:
    normalized = dict(prov)
    normalized["path"] = str(Path(prov["path"]).relative_to(root))
    return normalized


def csv_rows(text: str, label: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid CSV in {label}: {exc}") from exc


def one_row(rows: list[list[str]], claim_id: str) -> list[str]:
    matches = [row for row in rows[1:] if row and row[0] == claim_id]
    if len(matches) != 1:
        raise InputError(f"expected exactly one {claim_id} row, found {len(matches)}")
    return matches[0]


def one_dict_row(text: str, key: str, value: str, label: str) -> dict[str, str]:
    try:
        rows = list(csv.DictReader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid CSV in {label}: {exc}") from exc
    matches = [row for row in rows if row.get(key) == value]
    if len(matches) != 1:
        raise InputError(f"expected one {key}={value!r} row in {label}")
    return matches[0]


def resolve(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise InputError(f"path escapes repository root: {relative_path}") from exc
    return candidate


def mismatch(issues: list[dict[str, Any]], field: str, expected: str, actual: str) -> None:
    if actual != expected:
        issues.append({
            "code": "LEDGER_FIELD_MISMATCH",
            "field": field,
            "expected": expected,
            "actual": actual,
        })


def audit(root: Path) -> dict[str, Any]:
    ledger_path = root / "docs/claim_ledger.csv"
    report_path = root / "reports/mv5_pileup_1782678353/REPORT.md"
    summary_path = root / "reports/mv5_pileup_1782678353/mv5_pileup_summary.json"
    chapter_path = root / "docs/academic_chapters/05_pileup_analysis.md"
    registry_path = root / "docs/figure_registry.csv"

    ledger_text, ledger_prov = snapshot(ledger_path)
    rows = csv_rows(ledger_text, str(ledger_path))
    if not rows or rows[0] != FIELDS:
        raise InputError("claim ledger header is not the canonical 43-column schema")

    issues: list[dict[str, Any]] = []
    claims: dict[str, dict[str, str]] = {}
    for claim_id in ("CL-010", "CL-012"):
        row = one_row(rows, claim_id)
        if len(row) != len(FIELDS):
            issues.append({
                "code": "LEDGER_ROW_WIDTH_MISMATCH",
                "claim_id": claim_id,
                "expected": len(FIELDS),
                "actual": len(row),
            })
            continue
        claims[claim_id] = dict(zip(FIELDS, row))

    expected_common = {
        "unit": "MHz",
        "truth_type": "derived_model_conflicted",
        "allowed_status_validated": "NO",
        "source_report": "reports/mv5_pileup_1782678353/REPORT.md",
        "source_script": "scripts/mv5_pileup_study.py",
        "source_data": "reports/mv5_pileup_1782678353/mv5_pileup_summary.json",
        "figure_ids": "FIG-PU-003",
        "source_commit": "3c5ff5cf587c8ca9cefda20cb220ba29effd2170",
        "link_validated": "YES",
        "blocked_by": "S-STAT-003",
    }
    if "CL-010" in claims:
        claim = claims["CL-010"]
        for field, expected in expected_common.items():
            mismatch(issues, f"CL-010.{field}", expected, claim[field])
        for field, expected in {
            "current_value": "",
            "status": "BLOCKED",
            "ci_status": "NOT_APPLICABLE_WITH_REASON",
            "supersedes": "4.22 MHz",
        }.items():
            mismatch(issues, f"CL-010.{field}", expected, claim[field])
        required_notes = (
            "0.38 is the beam duty factor",
            "3.20 MHz",
            "rmax_from_failure_ceiling_mhz=null",
        )
        for phrase in required_notes:
            if phrase not in claim["notes"]:
                issues.append({"code": "CL010_NOTE_SCOPE_MISSING", "phrase": phrase})

    if "CL-012" in claims:
        claim = claims["CL-012"]
        for field, expected in expected_common.items():
            mismatch(issues, f"CL-012.{field}", expected, claim[field])
        for field, expected in {
            "current_value": "",
            "status": "SUPERSEDED",
            "ci_status": "SUPERSEDED_DO_NOT_USE",
            "supersedes": "CL-010",
        }.items():
            mismatch(issues, f"CL-012.{field}", expected, claim[field])
        if "not a validated lower bound" not in claim["notes"]:
            issues.append({"code": "CL012_NOTE_SCOPE_MISSING"})

    report_text, report_prov = snapshot(report_path)
    summary_text, summary_prov = snapshot(summary_path)
    chapter_text, chapter_prov = snapshot(chapter_path)
    registry_text, registry_prov = snapshot(registry_path)
    try:
        summary = json.loads(summary_text)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid MV5 summary JSON: {exc}") from exc

    try:
        constants = summary["constants"]
        tau_ns = float(constants["tau_eff_new_ns"])
        duty = float(constants["duty"])
        ceiling = float(summary["failure_ceiling"])
        failure_rows = summary["recovery_failure_vs_rate"]
        rmax_rows = summary["rmax_by_tau_eff"]
    except (KeyError, TypeError, ValueError) as exc:
        raise InputError(f"invalid MV5 summary structure: {exc}") from exc

    duty_scaled = (1.0 / (tau_ns * 1.0e-9) / 1.0e6) * duty
    tau_matches = [
        row for row in rmax_rows
        if math.isclose(float(row.get("tau_eff_ns")), tau_ns, rel_tol=0, abs_tol=1e-12)
    ]
    if len(tau_matches) != 1:
        issues.append({"code": "MV5_TAU_ROW_MISSING"})
        reported_duty_scaled = None
    else:
        reported_duty_scaled = float(tau_matches[0]["rmax_duty_corrected_mhz"])
        if not math.isclose(reported_duty_scaled, duty_scaled, rel_tol=0, abs_tol=1e-12):
            issues.append({"code": "MV5_DUTY_SCALED_ARITHMETIC_MISMATCH"})

    if summary.get("rmax_from_failure_ceiling_mhz") is not None:
        issues.append({"code": "RECOVERY_CEILING_NOW_CROSSED_REVIEW_REQUIRED"})
    above = [
        float(row["failure_rate"])
        for row in failure_rows
        if float(row["failure_rate"]) > ceiling
    ]
    if above:
        issues.append({"code": "FAILURE_RATE_ABOVE_RECORDED_CEILING", "values": above})

    required_report = (
        "not reached within [0.5, 4.0] MHz",
        "tau_eff = 124.8 ns x 0.38 duty",
    )
    for phrase in required_report:
        if phrase not in report_text:
            issues.append({"code": "REPORT_EVIDENCE_MISSING", "phrase": phrase})

    required_chapter = (
        "mu_{\\text{max}} = 0.1",
        "= 3.20 \\text{ MHz}",
        "= 3.05 \\text{ MHz",
        "R_{\\text{max}}^{\\text{(recovery)}} = 3.044",
        "self-consistency check, not an independent validation",
    )
    for phrase in required_chapter:
        if phrase not in chapter_text:
            issues.append({"code": "CHAPTER_CONFLICT_EVIDENCE_MISSING", "phrase": phrase})

    figure = one_dict_row(registry_text, "figure_id", "FIG-PU-003", str(registry_path))
    expected_figure = {
        "source_script": "scripts/mv5_pileup_study.py",
        "source_csv_json": "reports/mv5_pileup_1782678353/mv5_pileup_summary.json",
        "output_png": "reports/mv5_pileup_1782678353/mv5_pileup.png",
        "status": "exists",
        "dpi": "130",
    }
    for field, expected in expected_figure.items():
        if figure.get(field) != expected:
            issues.append({
                "code": "FIGURE_REGISTRY_MISMATCH",
                "field": field,
                "expected": expected,
                "actual": figure.get(field),
            })

    for relative_path in (
        expected_common["source_report"],
        expected_common["source_script"],
        expected_common["source_data"],
        expected_figure["output_png"],
    ):
        if not resolve(root, relative_path).exists():
            issues.append({"code": "TRACKED_SOURCE_MISSING", "path": relative_path})

    source_conflicts = [
        {
            "code": "DUTY_SCALED_RECIPROCAL_NOT_OCCUPANCY_CRITERION",
            "tau_eff_ns": tau_ns,
            "duty_factor": duty,
            "derived_mhz": duty_scaled,
        },
        {
            "code": "ACADEMIC_CHAPTER_3P20_TO_3P05_NON_ROUNDING_STEP",
            "chapter_occupancy_mhz": 3.20,
            "published_headline_mhz": 3.05,
        },
        {
            "code": "RECOVERY_CEILING_NOT_REACHED",
            "failure_ceiling": ceiling,
            "maximum_failure_rate": max(float(row["failure_rate"]) for row in failure_rows),
            "reported_crossing_mhz": summary.get("rmax_from_failure_ceiling_mhz"),
        },
    ]

    inputs = {
        "ledger": relative(ledger_prov, root),
        "report": relative(report_prov, root),
        "summary": relative(summary_prov, root),
        "academic_chapter": relative(chapter_prov, root),
        "figure_registry": relative(registry_prov, root),
    }
    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "claim_ids": ["CL-010", "CL-012"],
        "status": "VALIDATED" if not issues else "FLAWED",
        "scientific_acceptance": "BLOCKED",
        "accepted_rmax_mhz": None,
        "source_conflicts": source_conflicts,
        "inputs": inputs,
        "issues": issues,
        "n_issues": len(issues),
    }


def write_svg(path: Path, payload: dict[str, Any]) -> None:
    status = html.escape(payload["status"])
    conflicts = {item["code"]: item for item in payload["source_conflicts"]}
    duty = conflicts["DUTY_SCALED_RECIPROCAL_NOT_OCCUPANCY_CRITERION"]
    recovery = conflicts["RECOVERY_CEILING_NOT_REACHED"]
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="280"
 viewBox="0 0 900 280" role="img" aria-labelledby="title desc">
<title id="title">CL-010 Rmax source-conflict quarantine</title>
<desc id="desc">Repository evidence distinguishes a duty-scaled reciprocal,
 an inconsistent occupancy derivation, and a recovery ceiling that was not reached.</desc>
<rect width="100%" height="100%" fill="white"/>
<text x="24" y="30" font-family="sans-serif" font-size="20" font-weight="bold">
CL-010/CL-012 Rmax provenance audit</text>
<text x="24" y="52" font-family="sans-serif" font-size="12">
Repository-method evidence; no beam-rate measurement or simulation rerun.</text>
<rect x="25" y="78" width="250" height="105" fill="#f2f2f2" stroke="black"/>
<text x="38" y="105" font-family="sans-serif" font-size="13">MV5 summary</text>
<text x="38" y="130" font-family="monospace" font-size="12">
(1/tau)*duty = {duty['derived_mhz']:.6f} MHz</text>
<text x="38" y="153" font-family="sans-serif" font-size="11">
0.38 is recorded as duty factor</text>
<rect x="325" y="78" width="250" height="105" fill="#f2f2f2" stroke="black"/>
<text x="338" y="105" font-family="sans-serif" font-size="13">Academic chapter</text>
<text x="338" y="130" font-family="monospace" font-size="12">
mu=0.1, four staves -&gt; 3.20 MHz</text>
<text x="338" y="153" font-family="sans-serif" font-size="11">
3.05 MHz is not a rounding of 3.20</text>
<rect x="625" y="78" width="250" height="105" fill="#f2f2f2" stroke="black"/>
<text x="638" y="105" font-family="sans-serif" font-size="13">Recovery curve</text>
<text x="638" y="130" font-family="monospace" font-size="12">
max fail = {recovery['maximum_failure_rate']:.5f}</text>
<text x="638" y="153" font-family="sans-serif" font-size="11">
ceiling 0.17; crossing = null</text>
<text x="24" y="220" font-family="sans-serif" font-size="13">
Ledger action: CL-010 BLOCKED; CL-012 SUPERSEDED; accepted Rmax withheld.</text>
<text x="24" y="246" font-family="sans-serif" font-size="12">
Status: {status}; issues: {payload['n_issues']}; policy: {POLICY}</text>
</svg>\n'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = audit(args.repo_root.resolve())
    except InputError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if args.svg:
        write_svg(args.svg, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
