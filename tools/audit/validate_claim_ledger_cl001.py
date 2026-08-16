#!/usr/bin/env python3
"""Validate the source-backed CL-001 claim-ledger reconstruction."""
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

import yaml

VERSION = "1.0.0"
POLICY = "SOURCE_BACKED_EXACT_COUNT_LEDGER_ROW"
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
    """Controlled input/schema failure."""


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


def relative_prov(prov: dict[str, Any], root: Path) -> dict[str, Any]:
    normalized = dict(prov)
    normalized["path"] = str(Path(prov["path"]).relative_to(root))
    return normalized


def csv_rows(text: str, label: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid CSV in {label}: {exc}") from exc


def one_dict_row(path: Path, key: str, value: str) -> tuple[dict[str, str], dict[str, Any]]:
    text, prov = snapshot(path)
    try:
        rows = list(csv.DictReader(io.StringIO(text), strict=True))
    except csv.Error as exc:
        raise InputError(f"invalid CSV in {path}: {exc}") from exc
    matches = [row for row in rows if row.get(key) == value]
    if len(matches) != 1:
        raise InputError(f"expected one {key}={value!r} row in {path}")
    return matches[0], prov


def resolve(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise InputError(f"path escapes repository root: {relative}") from exc
    return candidate


def audit(root: Path) -> dict[str, Any]:
    ledger_path = root / "docs/claim_ledger.csv"
    config_path = root / "configs/s00_reproduction.yaml"
    report_path = root / "reports/S00_data_integrity_pipeline_reproduction/REPORT.md"
    count_path = root / "reports/S00_data_integrity_pipeline_reproduction/count_match_table.csv"
    manifest_path = root / "reports/S00_data_integrity_pipeline_reproduction/manifest.json"
    registry_path = root / "docs/figure_registry.csv"

    ledger_text, ledger_prov = snapshot(ledger_path)
    ledger_prov = relative_prov(ledger_prov, root)
    rows = csv_rows(ledger_text, str(ledger_path))
    if not rows or rows[0] != FIELDS:
        raise InputError("claim ledger header is not the canonical 43-column schema")
    matches = [row for row in rows[1:] if row and row[0] == "CL-001"]
    if len(matches) != 1:
        raise InputError(f"expected exactly one CL-001 row, found {len(matches)}")

    issues: list[dict[str, Any]] = []
    row = matches[0]
    if len(row) != len(FIELDS):
        issues.append({
            "code": "LEDGER_ROW_WIDTH_MISMATCH",
            "expected": len(FIELDS),
            "actual": len(row),
        })
        return result(ledger_prov, {}, issues)
    claim = dict(zip(FIELDS, row))

    config_text, config_prov = snapshot(config_path)
    config_prov = relative_prov(config_prov, root)
    try:
        config = yaml.safe_load(config_text)
        expected = int(config["expected_counts"]["total_selected_pulses"])
        runs = sorted({int(run) for group in config["run_groups"].values() for run in group})
    except (yaml.YAMLError, KeyError, TypeError, ValueError) as exc:
        raise InputError(f"invalid S00 config: {exc}") from exc

    report, report_prov = snapshot(report_path)
    report_prov = relative_prov(report_prov, root)
    count, count_prov = one_dict_row(count_path, "quantity", "total selected B-stave pulses")
    count_prov = relative_prov(count_prov, root)
    manifest_text, manifest_prov = snapshot(manifest_path)
    manifest_prov = relative_prov(manifest_prov, root)
    try:
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid manifest JSON: {exc}") from exc
    figure, figure_prov = one_dict_row(registry_path, "figure_id", "FIG-GL-001")
    figure_prov = relative_prov(figure_prov, root)

    expected_fields = {
        "current_value": str(expected),
        "unit": "pulses",
        "stat_unc": "0",
        "syst_unc": "0",
        "total_unc": "0",
        "n_runs": str(len(runs)),
        "n_data": str(expected),
        "truth_type": "data_count",
        # CL-001 is GATED (not VALIDATED) until data-contract gates #952/#953/#954
        # prove channel/schema/raw-to-sorted closure. The exact count is
        # reproducible, but claim status is governingly conservative (issue #955).
        "status": "GATED",
        "allowed_status_validated": "NO",
        "source_report": str(report_path.relative_to(root)),
        "source_script": "scripts/01_build_pulse_table_from_root.py",
        "source_data": str(config["pulse_table_path"]),
        "source_config": str(config_path.relative_to(root)),
        "source_manifest": str(manifest_path.relative_to(root)),
        "figure_ids": "FIG-GL-001",
        "table_ids": "TAB-GL-001",
        "link_validated": "YES",
        "ci_status": "EXACT_COUNT_FIXED_INPUTS",
    }
    for field, wanted in expected_fields.items():
        if claim[field] != wanted:
            issues.append({"code": "LEDGER_FIELD_MISMATCH", "field": field,
                           "expected": wanted, "actual": claim[field]})

    for field in ("report_value", "reproduced"):
        if count.get(field) != str(expected):
            issues.append({"code": "COUNT_TABLE_VALUE_MISMATCH", "field": field})
    for field, wanted in {"delta": "0", "tolerance": "0", "pass": "True"}.items():
        if count.get(field) != wanted:
            issues.append({"code": "COUNT_TABLE_GATE_MISMATCH", "field": field})

    row_text = f"| total selected B-stave pulses | {expected} | {expected} | 0 | 0 | yes |"
    if row_text not in report:
        issues.append({"code": "REPORT_COUNT_ROW_MISSING"})
    data_path_missing = str(config["pulse_table_path"]) not in report
    untracked_scope_missing = "intentionally ignored by git" not in report
    if data_path_missing or untracked_scope_missing:
        issues.append({"code": "REPORT_DATA_SCOPE_MISSING"})
    if not claim["source_commit"].startswith("dcde28d") or "`dcde28d`" not in report:
        issues.append({"code": "SOURCE_COMMIT_MISMATCH"})

    manifest_expected = {
        "config": str(config_path.relative_to(root)),
        "count_match_passed": True,
        "selected_pulse_table": str(config["pulse_table_path"]),
    }
    for field, wanted in manifest_expected.items():
        if manifest.get(field) != wanted:
            issues.append({"code": "MANIFEST_FIELD_MISMATCH", "field": field})

    figure_expected = {
        "source_script": claim["source_script"],
        "source_csv_json": str(count_path.relative_to(root)),
        "output_png": (
            "reports/S00_data_integrity_pipeline_reproduction/"
            "fig_counts_by_group_stave.png"
        ),
        "status": "exists",
    }
    for field, wanted in figure_expected.items():
        if figure.get(field) != wanted:
            issues.append({"code": "FIGURE_REGISTRY_MISMATCH", "field": field})
    for field in ("source_report", "source_script", "source_config", "source_manifest"):
        if not resolve(root, claim[field]).exists():
            issues.append({"code": "TRACKED_SOURCE_MISSING", "field": field})
    if not resolve(root, figure_expected["output_png"]).exists():
        issues.append({"code": "FIGURE_FILE_MISSING"})

    inputs = {
        "ledger": ledger_prov,
        "config": config_prov,
        "report": report_prov,
        "count_table": count_prov,
        "manifest": manifest_prov,
        "figure_registry": figure_prov,
    }
    return result(ledger_prov, inputs, issues, expected, len(runs), count, claim)


def result(ledger: dict[str, Any], inputs: dict[str, Any], issues: list[dict[str, Any]],
           expected: int | None = None, runs: int | None = None,
           count: dict[str, str] | None = None,
           claim: dict[str, str] | None = None) -> dict[str, Any]:
    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "claim_id": "CL-001",
        "status": "VALIDATED" if not issues else "FLAWED",
        "expected_count": expected,
        "configured_runs": runs,
        "source_commit": claim.get("source_commit") if claim else None,
        "source_data_tracking": "INTENTIONALLY_UNTRACKED_GENERATED_ARTIFACT",
        "count_table_gate": ({key: count.get(key) for key in
                              ("report_value", "reproduced", "delta", "tolerance", "pass")}
                             if count else None),
        "inputs": inputs or {"ledger": ledger},
        "issues": issues,
        "n_issues": len(issues),
    }


def write_svg(path: Path, payload: dict[str, Any]) -> None:
    status = html.escape(payload["status"])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="790" height="230"
 viewBox="0 0 790 230" role="img" aria-labelledby="title desc">
<title id="title">CL-001 source-backed reconstruction chain</title>
<desc id="desc">Configuration, count table, manifest and figure registry are checked
 against the canonical 43-field claim-ledger row.</desc>
<rect width="100%" height="100%" fill="white"/>
<text x="25" y="28" font-family="sans-serif" font-size="19"
 font-weight="bold">CL-001 exact-count traceability</text>
<text x="25" y="50" font-family="sans-serif" font-size="12">
 Repository provenance validation; no beam-data reprocessing.</text>
<rect x="30" y="78" width="160" height="78" fill="#f2f2f2" stroke="black"/>
<text x="40" y="105" font-family="sans-serif" font-size="13">Config: 640737 / 33 runs</text>
<rect x="220" y="78" width="160" height="78" fill="#f2f2f2" stroke="black"/>
<text x="230" y="105" font-family="sans-serif" font-size="13">Count: 640737; delta 0</text>
<rect x="410" y="78" width="160" height="78" fill="#f2f2f2" stroke="black"/>
<text x="420" y="105" font-family="sans-serif" font-size="13">Manifest / figure paths</text>
<rect x="600" y="78" width="160" height="78" fill="#f2f2f2" stroke="black"/>
<text x="610" y="105" font-family="sans-serif" font-size="13">Ledger: 43 fields</text>
<text x="25" y="190" font-family="sans-serif" font-size="13">
 Status: {status}; issues: {payload['n_issues']}; policy: {POLICY}</text>
<text x="25" y="211" font-family="sans-serif" font-size="11">
 Selected pulse table is generated and intentionally untracked.</text>
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
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.svg:
        write_svg(args.svg, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
