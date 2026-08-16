#!/usr/bin/env python3
"""Validate Cluster D public claim wording against tracked sources and ledger gates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "CLUSTERD_PUBLIC_STATUS_MUST_NOT_OVERRIDE_CANONICAL_CLAIM_GATES"
EXPECTED_COLUMNS = 43

PATHS = {
    "summary": "reports/studies/clusterD/SUMMARY.md",
    "ledger": "docs/claim_ledger.csv",
    "mv0_report": "reports/studies/clusterD/mv_runs/mv0/REPORT.md",
    "mv0_json": "reports/studies/clusterD/mv_runs/mv0/calibration.json",
    "mv5_report": "reports/studies/clusterD/mv_runs/mv5/REPORT.md",
    "mv5_json": "reports/studies/clusterD/mv_runs/mv5/mv5_pileup_summary.json",
    "mv6_report": "reports/studies/clusterD/mv_runs/mv6/REPORT.md",
    "mv6_json": "reports/studies/clusterD/mv_runs/mv6/mv6_representation_summary.json",
    "common": "scripts/single_stave/campaign_plots/_common.py",
}

REQUIRED_SUMMARY_PHRASES = (
    "Post-merge scientific governance correction",
    "**GATED (MARGINAL DATA/MC PROXY)**",
    "BLK-MV0-001",
    "**TRUTH_LEVEL_MC_ONLY / TABLE GENERATED**",
    "does not close the data-side absolute-energy calibration",
    "**BLOCKED (RMAX DEFINITION UNRESOLVED), TOY DIAGNOSTIC**",
    "rmax_from_failure_ceiling_mhz = null",
    "S-STAT-003",
    "**TRUTH_LEVEL_MC_ONLY, TOY DIAGNOSTIC**",
    "25/38",
    "does not identify the beam-data anomaly",
    "internal diagnostic plots; not proof that the simulation is empirically correct",
    "plotter uses an embedded coarse table rather than the committed CSV bytes",
)

FORBIDDEN_SUMMARY_PHRASES = (
    "**PASS** (PRODUCTION)",
    "Closing the absolute-energy question",
    "**PASS (analytic), TOY overlay**",
    "Confirms the data-corrected dead-time picture",
    "**PASS (species ID), TOY digitizer**",
    "proving the sim works",
)

REQUIRED_REPORT_PHRASES = {
    "mv0_report": (
        "status: **GATED / MARGINAL DATA/MC PROXY**",
        "not an authorized production calibration",
        "Global KS=0.108 -> **MARGINAL**",
        "chi2 / ndf",
    ),
    "mv5_report": (
        "status: **BLOCKED / TOY_DIAGNOSTIC**",
        "does not define or validate Rmax",
        "rmax_from_failure_ceiling_mhz is null",
        "S-STAT-003",
    ),
    "mv6_report": (
        "status: **TRUTH_LEVEL_MC_ONLY / TOY_DIAGNOSTIC**",
        "does not identify the beam-data anomaly",
        "25/38",
        "cluster 3 is only 46.4% C12-labelled",
    ),
}

FORBIDDEN_REPORT_PHRASES = {
    "mv0_report": ("status: **PRODUCTION**", "Calibrated gain 110 ADC/MeV written"),
    "mv5_report": ("This MC study quantifies the pile-up consequences and pins Rmax",),
    "mv6_report": ("truth-labelled MC thus assigns a concrete particle identity",),
}


class AuditInputError(ValueError):
    """Controlled invalid input or schema error."""


def _snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise AuditInputError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_method": "SINGLE_READ_EXACT_BYTES",
    }


def _load_json(text: str, path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditInputError(f"expected JSON object in {path}")
    return payload


def _parse_ledger(text: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as exc:
        raise AuditInputError(f"invalid ledger CSV: {exc}") from exc
    if not rows:
        raise AuditInputError("empty claim ledger")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise AuditInputError(
            f"claim ledger header has {len(header)} columns; expected {EXPECTED_COLUMNS}"
        )
    selected: dict[str, dict[str, str]] = {}
    wanted = {"CL-010", "CL-011", "CL-012", "CL-013", "CL-014", "CL-022"}
    for row in rows[1:]:
        if not row or row[0] not in wanted:
            continue
        if len(row) != EXPECTED_COLUMNS:
            raise AuditInputError(f"{row[0]} has {len(row)} columns; expected 43")
        if row[0] in selected:
            raise AuditInputError(f"duplicate claim row {row[0]}")
        selected[row[0]] = dict(zip(header, row))
    missing = sorted(wanted - set(selected))
    if missing:
        raise AuditInputError(f"missing claim rows: {', '.join(missing)}")
    return header, selected


def _append_phrase_issues(
    text: str,
    required: tuple[str, ...],
    forbidden: tuple[str, ...],
    prefix: str,
    issues: list[dict[str, Any]],
) -> None:
    for phrase in required:
        if phrase not in text:
            issues.append({"code": f"{prefix}_REQUIRED_PHRASE_MISSING", "phrase": phrase})
    for phrase in forbidden:
        if phrase in text:
            issues.append({"code": f"{prefix}_FORBIDDEN_PHRASE_PRESENT", "phrase": phrase})


def _append_ledger_issues(
    claims: dict[str, dict[str, str]], issues: list[dict[str, Any]]
) -> None:
    expected = {
        "CL-010": {"status": "BLOCKED", "blocked_by": "S-STAT-003", "current_value": ""},
        "CL-011": {"status": "DONE_DATA_ONLY", "current_value": "124.79018394263471"},
        "CL-012": {"status": "SUPERSEDED", "blocked_by": "S-STAT-003", "current_value": ""},
        "CL-013": {"status": "GATED", "blocked_by": "BLK-MV0-001", "current_value": "92"},
        "CL-014": {"status": "TENSION", "blocked_by": "BLK-MV0-001", "current_value": "0.1577"},
        "CL-022": {"status": "TRUTH_LEVEL_MC_ONLY", "current_value": "0.003232254011764034"},
    }
    for claim_id, fields in expected.items():
        for field, expected_value in fields.items():
            observed = claims[claim_id].get(field, "")
            if observed != expected_value:
                issues.append({
                    "code": "CANONICAL_LEDGER_MISMATCH",
                    "claim_id": claim_id,
                    "field": field,
                    "expected": expected_value,
                    "observed": observed,
                })


def _append_source_issues(
    mv0_json: dict[str, Any],
    mv5_json: dict[str, Any],
    mv6_json: dict[str, Any],
    common_text: str,
    issues: list[dict[str, Any]],
) -> None:
    calibration = mv0_json.get("calibration", {})
    expected_mv0 = {
        "gain_adc_per_mev": 110.0,
        "ks_statistic": 0.10773131550396098,
        "chi2_per_ndf": 2928.1720074390482,
    }
    for field, expected in expected_mv0.items():
        if calibration.get(field) != expected:
            issues.append({
                "code": "MV0_SOURCE_VALUE_MISMATCH",
                "field": field,
                "expected": expected,
                "observed": calibration.get(field),
            })
    if mv5_json.get("rmax_from_failure_ceiling_mhz", "missing") is not None:
        issues.append({
            "code": "MV5_RECOVERY_CEILING_EXPECTED_NULL",
            "observed": mv5_json.get("rmax_from_failure_ceiling_mhz"),
        })
    rmax_rows = mv5_json.get("rmax_by_tau_eff", [])
    matched = [row for row in rmax_rows if row.get("tau_eff_ns") == 124.8]
    if len(matched) != 1 or matched[0].get("rmax_duty_corrected_mhz") != 3.0448717948717947:
        issues.append({"code": "MV5_DUTY_PRODUCT_SOURCE_MISMATCH"})
    morphology = mv6_json.get("morphology_counts", {})
    composition = mv6_json.get("early_peak_species_composition", {})
    clusters = mv6_json.get("gmm_clusters", {})
    cluster3 = clusters.get("3", {}) if isinstance(clusters, dict) else {}
    if morphology.get("early_peak") != 38:
        issues.append({"code": "MV6_EARLY_PEAK_COUNT_MISMATCH"})
    if composition.get("C12") != 25:
        issues.append({"code": "MV6_C12_COUNT_MISMATCH"})
    if cluster3.get("purity") != 0.464339908952959:
        issues.append({"code": "MV6_CLUSTER3_PURITY_MISMATCH"})
    if "PSTAR_POLYSTYRENE = [" not in common_text:
        issues.append({"code": "PSTAR_EMBEDDED_TABLE_NOT_FOUND"})


def audit(root: Path) -> dict[str, Any]:
    root = root.resolve()
    texts: dict[str, str] = {}
    provenance: dict[str, dict[str, Any]] = {}
    for key, relative in PATHS.items():
        text, meta = _snapshot(root / relative)
        texts[key] = text
        provenance[key] = meta
    _, claims = _parse_ledger(texts["ledger"])
    mv0_json = _load_json(texts["mv0_json"], root / PATHS["mv0_json"])
    mv5_json = _load_json(texts["mv5_json"], root / PATHS["mv5_json"])
    mv6_json = _load_json(texts["mv6_json"], root / PATHS["mv6_json"])
    issues: list[dict[str, Any]] = []

    _append_phrase_issues(
        texts["summary"],
        REQUIRED_SUMMARY_PHRASES,
        FORBIDDEN_SUMMARY_PHRASES,
        "SUMMARY",
        issues,
    )
    for key, required in REQUIRED_REPORT_PHRASES.items():
        _append_phrase_issues(
            texts[key], required, FORBIDDEN_REPORT_PHRASES[key], key.upper(), issues
        )
    _append_ledger_issues(claims, issues)
    _append_source_issues(mv0_json, mv5_json, mv6_json, texts["common"], issues)

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "root": str(root),
        "inputs": provenance,
        "canonical_claim_ids": sorted(claims),
        "issues": issues,
        "n_issues": len(issues),
        "scientific_boundary": (
            "Documentation and source-binding validation only; no raw data or simulation was rerun."
        ),
    }


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return os.path.abspath(left) == os.path.abspath(right)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.output:
        for relative in PATHS.values():
            if _same_file(args.output, args.root / relative):
                print("INPUT ERROR: output must not alias an input", file=sys.stderr)
                return 2
    try:
        result = audit(args.root)
        if args.output:
            _write_json_atomic(args.output, result)
    except AuditInputError as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
