#!/usr/bin/env python3
"""Validate remediated legacy MV4 timing claims against exact tracked sources."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import sys
from pathlib import Path
from typing import Any

VERSION = "1.1.0"
POLICY = "LEGACY_MV4_TIMING_REQUIRES_STRICT_INPUTS_AND_SOURCE_BOUND_CLAIMS"
TARGET = tuple(f"CL-{n:03d}" for n in range(2, 10))
UNSUPPORTED = {
    "CL-002": "0.68",
    "CL-003": "0.75",
    "CL-004": "0.54",
    "CL-005": "0.56",
    "CL-006": "-0.127",
}
BLOCKER = "BLK-MV4-LEGACY-001"
SUMMARY_PATH = "reports/mv4_timing_1782678162/mv4_summary.json"
SOURCE_COMMIT = "3c5ff5cf587c8ca9cefda20cb220ba29effd2170"
EXPECTED_FACTS = {
    "n_tracks": 80000,
    "n_events_scanned": 241487,
    "raw_sigma68_ns": 1.744319343085384,
    "raw_bootstrap_se_ns": 0.006755405549476786,
    "corrected_sigma68_ns": 1.7696154242198858,
    "corrected_bootstrap_se_ns": 0.010813166729502352,
    "raw_pull": -1.054403396247793,
    "corrected_pull": 2.680528799917713,
    "assumed_data_unc_ns": 0.1,
    "gain_adc_per_mev": 110.0,
}


class AuditError(ValueError):
    """Controlled input error."""


def snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def read_rows(text: str) -> tuple[list[str], dict[str, list[str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise AuditError(f"invalid ledger CSV: {exc}") from exc
    if not rows or len(rows[0]) != 43:
        raise AuditError("claim ledger header is not the canonical 43-column schema")
    by_id: dict[str, list[str]] = {}
    for row in rows[1:]:
        if not row:
            continue
        if row[0] in by_id:
            raise AuditError(f"duplicate claim id: {row[0]}")
        by_id[row[0]] = row
    return rows[0], by_id


def source_facts(summary_json: dict[str, Any]) -> dict[str, Any]:
    return {
        "n_tracks": summary_json.get("n_tracks"),
        "n_events_scanned": summary_json.get("n_events_scanned"),
        "raw_sigma68_ns": summary_json.get("sigma68_ns", {}).get("raw"),
        "raw_bootstrap_se_ns": summary_json.get("sigma68_ns", {}).get("raw_unc"),
        "corrected_sigma68_ns": summary_json.get("sigma68_ns", {}).get(
            "corrected_test_half"
        ),
        "corrected_bootstrap_se_ns": summary_json.get("sigma68_ns", {}).get(
            "corrected_unc"
        ),
        "raw_pull": summary_json.get("pull", {}).get("raw"),
        "corrected_pull": summary_json.get("pull", {}).get("corrected"),
        "assumed_data_unc_ns": summary_json.get("data_reference", {}).get(
            "assumed_data_unc"
        ),
        "gain_adc_per_mev": summary_json.get("digitizer_params", {}).get(
            "gain_adc_per_mev"
        ),
    }


def issue(
    issues: list[dict[str, Any]], code: str, claim_id: str | None = None, **detail: Any
) -> None:
    item: dict[str, Any] = {"code": code}
    if claim_id is not None:
        item["claim_id"] = claim_id
    item.update(detail)
    issues.append(item)


def audit(ledger: Path, report: Path, summary: Path, contract: Path) -> dict[str, Any]:
    ledger_text, ledger_meta = snapshot(ledger)
    report_text, report_meta = snapshot(report)
    summary_text, summary_meta = snapshot(summary)
    contract_text, contract_meta = snapshot(contract)
    header, rows = read_rows(ledger_text)
    try:
        summary_json = json.loads(summary_text)
    except json.JSONDecodeError as exc:
        raise AuditError(f"invalid MV4 summary JSON: {exc}") from exc

    issues: list[dict[str, Any]] = []
    widths = {claim_id: len(rows.get(claim_id, [])) for claim_id in TARGET}
    for claim_id, width in widths.items():
        if width != len(header):
            issue(
                issues,
                "ROW_WIDTH_MISMATCH",
                claim_id,
                expected_columns=len(header),
                actual_columns=width,
            )

    exact_source_text = report_text + "\n" + summary_text
    source_absence = {
        claim_id: value not in exact_source_text
        for claim_id, value in UNSUPPORTED.items()
    }
    for claim_id, absent in source_absence.items():
        if not absent:
            issue(
                issues,
                "LEGACY_SOURCE_CONTRACT_CHANGED_REVIEW_REQUIRED",
                claim_id,
                legacy_value=UNSUPPORTED[claim_id],
            )

    for claim_id, legacy_value in UNSUPPORTED.items():
        row = rows.get(claim_id, [])
        if len(row) != len(header):
            continue
        if row[4]:
            issue(
                issues,
                "UNSUPPORTED_VALUE_PUBLISHED",
                claim_id,
                published_value=row[4],
                former_value=legacy_value,
            )
        expected = {
            27: "legacy_claim_source_unresolved",
            28: "BLOCKED",
            29: "NO",
            32: SUMMARY_PATH,
            37: SOURCE_COMMIT,
            38: "YES",
            39: "NOT_APPLICABLE_VALUE_WITHHELD_SOURCE_ABSENT",
            40: BLOCKER,
        }
        for index, expected_value in expected.items():
            if row[index] != expected_value:
                issue(
                    issues,
                    "UNSUPPORTED_ROW_CONTRACT_MISMATCH",
                    claim_id,
                    field=header[index],
                    expected=expected_value,
                    actual=row[index],
                )
        if legacy_value not in row[41] or "withheld" not in row[42].lower():
            issue(issues, "UNSUPPORTED_ROW_HISTORY_OR_CAVEAT_MISSING", claim_id)

    pull_expectations = {
        "CL-007": ("-1.054403396247793", "1.85"),
        "CL-008": ("2.680528799917713", "1.50"),
    }
    for claim_id, (value, anchor) in pull_expectations.items():
        row = rows.get(claim_id, [])
        if len(row) != len(header):
            continue
        expected = {
            4: value,
            5: "sigma",
            14: "241487",
            17: "80000",
            22: anchor,
            23: "0.10",
            27: "legacy_toy_digitizer_diagnostic",
            28: "GATED",
            29: "NO",
            32: SUMMARY_PATH,
            37: SOURCE_COMMIT,
            38: "YES",
            39: (
                "NOT_APPLICABLE_ASSUMED_DATA_UNCERTAINTY_AND_"
                "IID_TRACK_BOOTSTRAP_SE"
            ),
            40: BLOCKER,
        }
        for index, expected_value in expected.items():
            if row[index] != expected_value:
                issue(
                    issues,
                    "TOY_PULL_CONTRACT_MISMATCH",
                    claim_id,
                    field=header[index],
                    expected=expected_value,
                    actual=row[index],
                )
        note = row[42].lower()
        for phrase in ("toy", "assumed 0.10 ns", "non-authorizing"):
            if phrase not in note:
                issue(
                    issues,
                    "TOY_PULL_CAVEAT_MISSING",
                    claim_id,
                    required_phrase=phrase,
                )

    verdict = rows.get("CL-009", [])
    if len(verdict) == len(header):
        expected = {
            3: "Legacy analytic CFD20/timewalk timing verdict",
            4: "REVIEW",
            5: "diagnostic",
            27: "legacy_toy_digitizer_diagnostic",
            28: "REVIEW",
            29: "NO",
            32: SUMMARY_PATH,
            37: SOURCE_COMMIT,
            38: "YES",
            39: "NOT_APPLICABLE_QUALITATIVE_DIAGNOSTIC",
            40: BLOCKER,
            41: "ML timing verdict",
        }
        for index, expected_value in expected.items():
            if verdict[index] != expected_value:
                issue(
                    issues,
                    "ANALYTIC_VERDICT_CONTRACT_MISMATCH",
                    "CL-009",
                    field=header[index],
                    expected=expected_value,
                    actual=verdict[index],
                )
        note = verdict[42].lower()
        if "no machine-learning model" not in note or "non-authorizing" not in note:
            issue(issues, "ANALYTIC_VERDICT_CAVEAT_MISSING", "CL-009")
        if "ML" in verdict[3]:
            issue(issues, "ML_METHOD_NOT_IN_SOURCE", "CL-009")

    facts = source_facts(summary_json)
    for name, expected_value in EXPECTED_FACTS.items():
        if facts[name] != expected_value:
            issue(
                issues,
                "SOURCE_FACT_MISMATCH",
                expected=expected_value,
                actual=facts[name],
                fact=name,
            )

    contract_ok = all(
        phrase in contract_text
        for phrase in ("TOY_DIAGNOSTIC", "--strict", "run/block-level")
    )
    if not contract_ok:
        issue(issues, "CURRENT_FAIL_CLOSED_CONTRACT_NOT_FOUND")

    return {
        "auditor": "audit_mv4_legacy_claim_rows.py",
        "version": VERSION,
        "status": "VALIDATED" if not issues else "FLAWED",
        "policy": POLICY,
        "claim_ledger": ledger_meta,
        "legacy_report": report_meta,
        "legacy_summary": summary_meta,
        "current_contract": contract_meta,
        "target_claim_ids": list(TARGET),
        "row_widths": widths,
        "source_absence_confirmed": source_absence,
        "source_facts": facts,
        "claim_states": {
            claim_id: {
                "status": rows.get(claim_id, [""] * 43)[28]
                if len(rows.get(claim_id, [])) == 43
                else "WITHHELD_SCHEMA",
                "current_value": rows.get(claim_id, [""] * 43)[4]
                if len(rows.get(claim_id, [])) == 43
                else None,
            }
            for claim_id in TARGET
        },
        "issues": issues,
        "n_issues": len(issues),
    }


def write_svg(path: Path, result: dict[str, Any]) -> None:
    states = result["claim_states"]
    rows = []
    for index, claim_id in enumerate(TARGET):
        state = states[claim_id]
        y = 86 + index * 46
        label = html.escape(
            f'{state["status"]}: {state["current_value"] or "value withheld"}'
        )
        pattern = "url(#blocked)" if state["status"] == "BLOCKED" else "#ddd"
        rows.append(
            f'<text x="25" y="{y + 19}" font-family="monospace" '
            f'font-size="14">{claim_id}</text>'
        )
        rows.append(
            f'<rect x="115" y="{y}" width="600" height="28" fill="{pattern}" '
            'stroke="black"/>'
        )
        rows.append(
            f'<text x="130" y="{y + 19}" font-family="sans-serif" '
            f'font-size="13">{label}</text>'
        )
    svg = "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="760" height="520" '
            'viewBox="0 0 760 520" role="img" aria-labelledby="title desc">',
            '<title id="title">Legacy MV4 timing claim remediation</title>',
            '<desc id="desc">Five unsupported values are withheld, two pulls are '
            'gated toy diagnostics, and the qualitative method verdict is REVIEW.</desc>',
            '<defs><pattern id="blocked" width="8" height="8" '
            'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<line x1="0" y1="0" x2="0" y2="8" stroke="#555" '
            'stroke-width="2"/></pattern></defs>',
            '<rect width="100%" height="100%" fill="white"/>',
            '<text x="25" y="32" font-family="sans-serif" font-size="21" '
            'font-weight="bold">MV4 legacy timing claims: source-bound state</text>',
            '<text x="25" y="56" font-family="sans-serif" font-size="13">'
            'Software/provenance evidence only — no detector timing measurement.</text>',
            *rows,
            '<text x="25" y="485" font-family="sans-serif" font-size="12">'
            f'Status: {result["status"]}; policy: {html.escape(result["policy"])}</text>',
            '</svg>',
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-svg", type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.ledger, args.report, args.summary, args.contract)
    except AuditError as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(text, encoding="utf-8")
    if args.output_svg:
        write_svg(args.output_svg, result)
    print(text, end="")
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
