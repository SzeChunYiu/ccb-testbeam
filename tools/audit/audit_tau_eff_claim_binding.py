#!/usr/bin/env python3
"""Audit CL-011 against the tracked S10b live-time measurement artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

VERSION = "1.0.0"
POLICY = "TAU_EFF_CLAIM_MUST_BIND_TO_PRIMARY_S10B_MEASUREMENT"
EXPECTED_FIELDS = (
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

PRIMARY = {
    "report": "reports/1781000867.546870.5c124aaf/REPORT.md",
    "script": "reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py",
    "result": "reports/1781000867.546870.5c124aaf/result.json",
    "manifest": "reports/1781000867.546870.5c124aaf/manifest.json",
    "heldout": "reports/1781000867.546870.5c124aaf/heldout_run_summary.csv",
}
EXPECTED_COMMIT = "da9651c56ef6495ce9656d84b69b600daa6d8f86"
EXPECTED_CLAIM_TEXT = "S10b run-average 10% template live-time relative to CFD20"
EXPECTED_TRUTH_TYPE = "data_measurement"
EXPECTED_STATUS = "DONE_DATA_ONLY"
EXPECTED_CI_METHOD = "run_mean_nonparametric_bootstrap_percentile"
EXPECTED_CI_STATUS = "CI_AVAILABLE_RUN_BOOTSTRAP_METHOD_LIMITATIONS"
EXPECTED_BLOCKER = "BLK-S10B-001"
REQUIRED_NOTES = (
    "run-average estimand",
    "14 runs",
    "252266 selected pulses",
    "not a detector-wide universal dead time",
    "MV5 uses the value as an input rather than independently validating it",
    "no statistical/systematic uncertainty decomposition",
)


class AuditInputError(ValueError):
    """Controlled input or serialization error."""


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


def _read_json(raw: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_decode(raw, path))
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditInputError(f"expected a JSON object in {path}")
    return value


def _read_csv(raw: bytes, path: Path) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(_decode(raw, path)), strict=True))
    except csv.Error as exc:
        raise AuditInputError(f"invalid CSV in {path}: {exc}") from exc


def _as_finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AuditInputError(f"{label} is not numeric") from exc
    if not math.isfinite(number):
        raise AuditInputError(f"{label} is not finite")
    return number


def _same_number(text: str, expected: float) -> bool:
    try:
        value = float(text)
    except ValueError:
        return False
    return math.isfinite(value) and value == expected


def _issue(issues: list[dict[str, Any]], code: str, **details: Any) -> None:
    issues.append({"code": code, **details})


def _verify_manifest_hash(
    issues: list[dict[str, Any]], manifest: dict[str, Any], filename: str, snapshot: dict[str, Any]
) -> None:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        _issue(issues, "MANIFEST_OUTPUTS_MISSING")
        return
    recorded = outputs.get(filename)
    if recorded != snapshot["sha256"]:
        _issue(
            issues,
            "MANIFEST_OUTPUT_HASH_MISMATCH",
            filename=filename,
            recorded=recorded,
            actual=snapshot["sha256"],
        )


def validate(
    ledger_rows: list[list[str]],
    result: dict[str, Any],
    manifest: dict[str, Any],
    heldout_rows: list[list[str]],
    snapshots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if not ledger_rows or ledger_rows[0] != list(EXPECTED_FIELDS):
        raise AuditInputError("claim ledger header is not the canonical 43-column schema")

    matches = [row for row in ledger_rows[1:] if row and row[0].strip() == "CL-011"]
    if len(matches) != 1:
        _issue(issues, "CL011_CARDINALITY", observed=len(matches), expected=1)
        row = None
    else:
        row = matches[0]
        if len(row) != len(EXPECTED_FIELDS):
            _issue(
                issues,
                "CL011_WIDTH_MISMATCH",
                observed=len(row),
                expected=len(EXPECTED_FIELDS),
            )
            row = None

    if result.get("study") != "S10b" or result.get("ticket") != "1781000867.546870.5c124aaf":
        _issue(issues, "PRIMARY_RESULT_IDENTITY_MISMATCH")
    traditional = result.get("traditional")
    if not isinstance(traditional, dict):
        raise AuditInputError("result.traditional is missing")
    measured = _as_finite(traditional.get("tau_eff_live10_ns"), "tau_eff_live10_ns")
    ci = traditional.get("tau_eff_live10_ci95_ns")
    if not isinstance(ci, list) or len(ci) != 2:
        raise AuditInputError("traditional 95% CI must contain two endpoints")
    ci_low = _as_finite(ci[0], "tau_eff CI low")
    ci_high = _as_finite(ci[1], "tau_eff CI high")
    if not ci_low < measured < ci_high:
        _issue(issues, "PRIMARY_CI_DOES_NOT_BRACKET_ESTIMATE")

    if not heldout_rows:
        raise AuditInputError("heldout summary is empty")
    heldout_header = heldout_rows[0]
    required_columns = {"heldout_run", "n_pulses", "traditional_template_live10_ns"}
    if not required_columns.issubset(set(heldout_header)):
        raise AuditInputError("heldout summary is missing required columns")
    index = {name: heldout_header.index(name) for name in required_columns}
    data = heldout_rows[1:]
    runs = [row[index["heldout_run"]] for row in data]
    if len(runs) != len(set(runs)):
        _issue(issues, "HELDOUT_RUN_DUPLICATE")
    n_runs = len(data)
    n_data = 0
    run_values: list[float] = []
    for row_number, source_row in enumerate(data, start=2):
        try:
            count = int(source_row[index["n_pulses"]])
        except (ValueError, IndexError) as exc:
            raise AuditInputError(f"invalid n_pulses at heldout row {row_number}") from exc
        if count <= 0:
            _issue(issues, "HELDOUT_NONPOSITIVE_PULSE_COUNT", row_number=row_number)
        n_data += count
        run_values.append(
            _as_finite(
                source_row[index["traditional_template_live10_ns"]],
                f"traditional live10 at heldout row {row_number}",
            )
        )

    reconstructed_mean = float(np.mean(np.asarray(run_values, dtype=float)))
    if reconstructed_mean != measured:
        _issue(
            issues,
            "PRIMARY_ESTIMATE_RECONSTRUCTION_MISMATCH",
            recorded=measured,
            reconstructed=reconstructed_mean,
        )

    rng = np.random.default_rng(10102)
    row_split_test_count = math.ceil(n_data * 0.25)
    if row_split_test_count > 60000:
        rng.choice(row_split_test_count, size=60000, replace=False)
    shuffled_placeholder = np.empty(n_data, dtype=float)
    rng.shuffle(shuffled_placeholder)
    draws = rng.integers(0, n_runs, size=(5000, n_runs))
    bootstrap_means = np.asarray(run_values, dtype=float)[draws].mean(axis=1)
    reconstructed_ci = [
        float(np.percentile(bootstrap_means, 2.5)),
        float(np.percentile(bootstrap_means, 97.5)),
    ]
    if reconstructed_ci != [ci_low, ci_high]:
        _issue(
            issues,
            "PRIMARY_CI_RECONSTRUCTION_MISMATCH",
            recorded=[ci_low, ci_high],
            reconstructed=reconstructed_ci,
        )

    result_commit = result.get("git_commit")
    manifest_commit = manifest.get("git_commit")
    if result_commit != manifest_commit or result_commit != EXPECTED_COMMIT:
        _issue(
            issues,
            "PRIMARY_COMMIT_MISMATCH",
            result_commit=result_commit,
            manifest_commit=manifest_commit,
            expected=EXPECTED_COMMIT,
        )
    _verify_manifest_hash(issues, manifest, "result.json", snapshots["result"])
    _verify_manifest_hash(issues, manifest, "heldout_run_summary.csv", snapshots["heldout"])
    _verify_manifest_hash(issues, manifest, "REPORT.md", snapshots["report"])

    if row is not None:
        fields = dict(zip(EXPECTED_FIELDS, row))
        exact_checks = {
            "claim_text": EXPECTED_CLAIM_TEXT,
            "unit": "ns",
            "ci_level": "0.95",
            "ci_method": EXPECTED_CI_METHOD,
            "bootstrap_unit": "run",
            "n_runs": str(n_runs),
            "n_data": str(n_data),
            "truth_type": EXPECTED_TRUTH_TYPE,
            "status": EXPECTED_STATUS,
            "allowed_status_validated": "NO",
            "source_report": PRIMARY["report"],
            "source_script": PRIMARY["script"],
            "source_data": PRIMARY["result"],
            "source_manifest": PRIMARY["manifest"],
            "source_commit": EXPECTED_COMMIT,
            "link_validated": "YES",
            "ci_status": EXPECTED_CI_STATUS,
            "blocked_by": EXPECTED_BLOCKER,
            "supersedes": "90 ns",
        }
        for field, expected in exact_checks.items():
            if fields[field] != expected:
                _issue(
                    issues,
                    "CL011_FIELD_MISMATCH",
                    field=field,
                    observed=fields[field],
                    expected=expected,
                )
        numeric_checks = {
            "current_value": measured,
            "ci_low": ci_low,
            "ci_high": ci_high,
        }
        for field, expected in numeric_checks.items():
            if not _same_number(fields[field], expected):
                _issue(
                    issues,
                    "CL011_NUMERIC_MISMATCH",
                    field=field,
                    observed=fields[field],
                    expected=repr(expected),
                )
        for field in ("stat_unc", "syst_unc", "total_unc"):
            if fields[field].strip():
                _issue(
                    issues,
                    "UNSUPPORTED_UNCERTAINTY_DECOMPOSITION",
                    field=field,
                    observed=fields[field],
                )
        notes = fields["notes"]
        for phrase in REQUIRED_NOTES:
            if phrase not in notes:
                _issue(issues, "CL011_REQUIRED_CAVEAT_MISSING", phrase=phrase)
        if fields["source_report"] == "reports/mv5_pileup_1782678353/REPORT.md":
            _issue(issues, "SECONDARY_MV5_REPORT_USED_AS_PRIMARY_SOURCE")
        if fields["source_data"] == "reports/mv5_pileup_1782678353/results.json":
            _issue(issues, "NONEXISTENT_LEDGER_SOURCE_DATA_PATH")
        if fields["status"] == "VALIDATED":
            _issue(issues, "INDEPENDENT_CLOSURE_OVERSTATED")

    return {
        "validator": "audit_tau_eff_claim_binding.py",
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "claim_id": "CL-011",
        "source_facts": {
            "estimate_ns": measured,
            "ci95_ns": [ci_low, ci_high],
            "run_count": n_runs,
            "selected_pulse_count": n_data,
            "primary_commit": EXPECTED_COMMIT,
            "primary_paths": PRIMARY,
            "estimand": "equal-weight mean of 14 run-level template live10 estimates",
            "reconstructed_estimate_ns": reconstructed_mean,
            "reconstructed_ci95_ns": reconstructed_ci,
            "bootstrap_rng_reconstruction": {
                "generator": "numpy.default_rng_PCG64",
                "seed": 10102,
                "pre_bootstrap_choice_population": row_split_test_count,
                "pre_bootstrap_choice_size": 60000,
                "pre_bootstrap_shuffle_length": n_data,
                "bootstrap_draws": 5000,
                "bootstrap_unit_count": n_runs,
            },
            "secondary_mv5_role": "uses rounded 124.8 ns as an input; not independent validation",
        },
        "inputs": snapshots,
        "issues": issues,
        "n_issues": len(issues),
    }


def audit(
    ledger: Path,
    result_path: Path,
    manifest_path: Path,
    heldout_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    paths = {
        "ledger": ledger,
        "result": result_path,
        "manifest": manifest_path,
        "heldout": heldout_path,
        "report": report_path,
    }
    raw: dict[str, bytes] = {}
    snapshots: dict[str, dict[str, Any]] = {}
    for key, path in paths.items():
        raw[key], snapshots[key] = _snapshot(path)
    ledger_rows = _read_csv(raw["ledger"], ledger)
    result = _read_json(raw["result"], result_path)
    manifest = _read_json(raw["manifest"], manifest_path)
    heldout_rows = _read_csv(raw["heldout"], heldout_path)
    return validate(ledger_rows, result, manifest, heldout_rows, snapshots)


def _assert_safe_output(path: Path, inputs: list[Path]) -> None:
    target = path.resolve()
    for input_path in inputs:
        if target == input_path.resolve():
            raise AuditInputError(f"output path aliases input: {path}")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _svg(payload: dict[str, Any]) -> str:
    facts = payload["source_facts"]
    issues = payload["issues"]
    rows = [
        ("Primary estimate", f"{facts['estimate_ns']:.6f} ns"),
        ("Run-bootstrap 95% CI", f"[{facts['ci95_ns'][0]:.6f}, {facts['ci95_ns'][1]:.6f}] ns"),
        ("Run-level estimand", f"{facts['run_count']} runs"),
        ("Selected pulses", str(facts["selected_pulse_count"])),
        ("Current ledger findings", str(len(issues))),
    ]
    height = 210 + 24 * len(issues)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" '
        f'viewBox="0 0 1000 {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">CL-011 tau-eff source-binding audit</title>',
        '<desc id="desc">Software and documentation provenance evidence, not detector data.</desc>',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="28" y="34" font-family="sans-serif" font-size="22" font-weight="bold">'
        'CL-011 tau_eff provenance and estimand audit</text>',
        '<text x="28" y="58" font-family="sans-serif" font-size="13">'
        'Tracked-artifact audit; this graphic is not a detector-data plot.</text>',
    ]
    y = 92
    for label, value in rows:
        parts.append(
            f'<text x="40" y="{y}" font-family="sans-serif" font-size="14">'
            f'{label}: <tspan font-family="monospace">{value}</tspan></text>'
        )
        y += 25
    y += 10
    parts.append(
        f'<text x="28" y="{y}" font-family="sans-serif" font-size="16" '
        'font-weight="bold">Fail-closed findings</text>'
    )
    y += 24
    for issue in issues:
        code = issue["code"]
        detail = issue.get("field") or issue.get("phrase") or ""
        parts.append(
            f'<text x="45" y="{y}" font-family="monospace" font-size="12">'
            f'• {code} {detail}</text>'
        )
        y += 22
    parts.append(
        f'<text x="28" y="{height - 22}" font-family="sans-serif" font-size="12">'
        f'Status: {payload["status"]}; policy: {payload["policy"]}</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_ledger", type=Path)
    parser.add_argument("result", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("heldout_summary", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--svg", type=Path)
    args = parser.parse_args(argv)
    inputs = [
        args.claim_ledger,
        args.result,
        args.manifest,
        args.heldout_summary,
        args.report,
    ]
    try:
        for output in (args.output, args.svg):
            if output is not None:
                _assert_safe_output(output, inputs)
        payload = audit(*inputs)
        if args.output:
            _atomic_write(args.output, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if args.svg:
            _atomic_write(args.svg, _svg(payload))
    except AuditInputError as exc:
        print(f"INPUT ERROR: {exc}", file=os.sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
