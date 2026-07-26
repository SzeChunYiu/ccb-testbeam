#!/usr/bin/env python3
"""Fail-closed audit for Cluster E canonical claim/provenance binding."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

POLICY = "CLUSTERE_HEADLINES_MUST_BIND_CANONICAL_LEDGER_AND_FULL_PROVENANCE"
VERSION = "2.0.0"
EXPECTED_COLUMNS = 43
REQUIRED_PROVENANCE_INPUTS = {
    "docs/claim_ledger.csv",
    "reports/studies/clusterA/counts.json",
    "reports/studies/clusterB/metrics.json",
    "reports/studies/clusterC/metrics.json",
    "reports/studies/clusterD/figures/fig_sipm_summary.json",
    "reports/studies/clusterD/figures/fig_birks_summary.json",
    "reports/studies/clusterD/figures/fig_i885_summary.json",
    "reports/studies/clusterD/mv_runs/mv3/mv3_summary.json",
    "figures/opticks/SUMMARY.md",
}
CURRENT_REQUIRED_IDENTITIES = {
    "docs/claim_ledger.csv",
    "reports/mv0_calibration_1782677847/calibration.json",
    "reports/mv3_stopping_v3_1782679272/mv3_summary.json",
    "reports/mv6_representation_1782678362/mv6_representation_summary.json",
    "reports/studies/clusterD/mv_runs/mv3/mv3_summary.json",
    "scripts/clusterE/clusterE_canonical_frontdoor.py",
}


class AuditInputError(RuntimeError):
    pass


def snapshot(path: Path) -> tuple[str, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"invalid UTF-8 in {path}: {exc}") from exc
    return text, {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    text, prov = snapshot(path)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditInputError(f"JSON root must be object: {path}")
    return value, prov


def load_ledger(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    text, prov = snapshot(path)
    rows = list(csv.reader(text.splitlines()))
    if not rows or len(rows[0]) != EXPECTED_COLUMNS:
        raise AuditInputError "claim ledger header width mismatch"
    out: dict[str, dict[str, str]] = {}
    for line_no, row in enumerate(rows[1:], 2):
        if len(row) != EXPECTED_COLUMNS:
            raise AuditInputError(f"claim ledger line {line_no} width mismatch")
        item = dict(zip(rows[0], row, strict=True))
        claim_id = item["claim_id"]
        if not claim_id or claim_id in out:
            raise AuditInputError(f"duplicate or empty claim_id {claim_id}")
        out[claim_id] = item
    prov.update({"rows": len(out), "columns": EXPECTED_COLUMNS})
    return out, prov


def _finding(code: str, artifact: str, message: str = "") -> dict[str, str]:
    return {"code": code, "artifact": artifact, "message": message}


def _require(claims: dict[str, dict[str, str]], claim: str, expected: dict[str, str], findings: list[dict[str, str]]) -> None:
    row = claims.get(claim)
    if row is None:
        findings.append(_finding("CLAIM_MISSING", "ledger", claim))
        return
    for field, value in expected.items():
        if row.get(field) != value:
            findings.append(_finding("CLAIM_FIELD_MISMATCH", "ledger", f"{claim}.{field}"))


def _documents(documents: dict[str, str], findings: list[dict[str, str]]) -> None:
    for artifact, text in documents.items():
        if re.search(r"CL-013[^\n]{0,120}\b110(?:\.0)?\b", text):
            findings.append(_finding("CL013_CANONICAL_VALUE_MISMATCH", artifact))
        if "92 ADC/MeV" not in text or "28 ADC/MeV" not in text:
            findings.append(_finding("CL013_EXACT_BINDING_MISSING", artifact))
        if re.search(r"CL-021[^\n]{0,140}(?:8\.6e4|86135|6\.8e4)", text, re.I):
            findings.append(_finding("CL021_CLUSTERD_RERUN_CONFLATED", artifact))
        if "68269.40598948313" not in text:
            findings.append(_finding("CL021_EXACT_BINDING_MISSING", artifact))
        if "25/38 toy early-peak C12" in text:
            findings.append(_finding("CL022_TOY_COUNTS_SUBSTITUTED", artifact))
        if "283/87555" not in text:
            findings.append(_finding("CL022_EXACT_COUNTS_MISSING", artifact))
        caveats = ("does not supersede CL-021", "does **not supersede CL-021**")
        if not any(token in text for token in caveats):
            findings.append(_finding("CL021_DISTINCT_DIAGNOSTIC_CAVEAT_MISSING", artifact))


def _table(text: str, findings: list[dict[str, str]]) -> None:
    rows = list(csv.DictReader(text.splitlines()))
    columns = {"claim", "headline", "evidence_class", "status", "source", "figure", "claim_id"}
    if not rows or set(rows[0]) != columns:
        findings.append(_finding("CLAIMS_TABLE_SCHEMA_INVALID", "claims_table"))
        return
    by_claim = {row["claim"]: row for row in rows}
    checks = [
        ("ADC gain (data/MC proxy, MV0)", ("92", "28"), "GATED", "CL013"),
        ("Stopping-depth data/MC closure", ("68269.40598948313",), "FLAWED", "CL021"),
        ("Anomaly / C12 identity", ("283/87555",), "TRUTH_LEVEL_MC_ONLY", "CL022"),
    ]
    for name, tokens, status, label in checks:
        row = by_claim.get(name)
        if not row or not all(token in row["headline"] for token in tokens):
            findings.append(_finding(f"CLAIMS_TABLE_{label}_MISMATCH", "claims_table"))
        elif row["status"] != status:
            findings.append(_finding(f"CLAIMS_TABLE_{label}_STATUS_MISMATCH", "claims_table"))


def _provenance(value: dict[str, Any], findings: list[dict[str, str]]) -> None:
    commit = value.get("base_commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        findings.append(_finding("PROVENANCE_BASE_COMMIT_UNBOUND", "provenance"))
    identities = value.get("input_identities")
    if isinstance(identities, dict):
        for path in sorted(CURRENT_REQUIRED_IDENTITIES):
            item = identities.get(path)
            valid = isinstance(item, dict)
            valid = valid and item.get("algorithm") == "git_blob_sha1"
            valid = valid and isinstance(item.get("digest"), str) and bool(re.fullmatch(r"[0-9a-f]{40}", item["digest"]))
            valid = valid and isinstance(item.get("sha256"), str) and bool(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]))
            if not valid:
                findings.append(_finding("PROVENANCE_INPUT_UNBOUND", "provenance", path))
        return
    legacy = value.get("input_sha256")
    if not isinstance(legacy, dict):
        findings.append(_finding("PROVENANCE_FULL_SHA256_MISSING", "provenance"))
        return
    for path in sorted(REQUIRED_PROVENANCE_INPUTS):
        digest = legacy.get(path)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            findings.append(_finding("PROVENANCE_INPUT_UNBOUND", "provenance", path))


def audit(ledger_path: Path, dashboard_path: Path, summary_path: Path, claims_table_path: Path, provenance_path: Path, mv3_path: Path) -> dict[str, Any]:
    claims, ledger_prov = load_ledger(ledger_path)
    dashboard, dashboard_prov = snapshot(dashboard_path)
    summary, summary_prov = snapshot(summary_path)
    table, table_prov = snapshot(claims_table_path)
    provenance, provenance_prov = load_json(provenance_path)
    mv3, mv3_prov = load_json(mv3_path)
    findings: list[dict[str, str]] = []
    _require(claims, "CL-013", {"current_value": "92", "unit": "ADC/MeV", "syst_unc": "28", "truth_type": "data_mc_calibration_proxy", "status": "GATED"}, findings)
    _require(claims, "CL-021", {"current_value": "68269.40598948313", "truth_type": "legacy_data_mc_profile_diagnostic", "status": "FLAWED"}, findings)
    _require(claims, "CL-022", {"current_value": "0.003232254011764034", "numerator": "283", "denominator": "87555", "truth_type": "mc_truth_only", "status": "TRUTH_LEVEL_MC_ONLY"}, findings)
    _documents({"dashboard": dashboard, "summary": summary}, findings)
    _table(table, findings)
    _provenance(provenance, findings)
    canonical = float(claims["CL-021"]["current_value"])
    rerun = mv3.get("chi2_per_ndf")
    return {
        "schema": "ccb-clusterE-canonical-binding-audit/2",
        "validator_version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "finding_count": len(findings),
        "findings": findings,
        "canonical_values": {
            "CL-013": {"value": 92.0, "syst_envelope_adc_per_mev": 28.0, "status": "GATED"},
            "CL-021": {"chi2_per_ndf": canonical, "status": "FLAWED"},
            "CL-022": {"rate": 0.003232254011764034, "numerator": 283, "denominator": 87555, "status": "TRUTH_LEVEL_MC_ONLY"},
        },
        "mv3_source_comparison": {
            "canonical_cl021_chi2_per_ndf": canonical,
            "clusterD_rerun_chi2_per_ndf": rerun,
            "absolute_difference": None if not isinstance(rerun, (int, float)) else rerun - canonical,
            "scientific_interpretation": "distinct diagnostics; rerun does not supersede CL-021",
        },
        "inputs": {"ledger": ledger_prov, "dashboard": dashboard_prov, "summary": summary_prov, "claims_table": table_prov, "provenance": provenance_prov, "clusterD_mv3": mv3_prov},
        "scientific_boundary": "Claim/provenance binding only; no detector performance or accepted closure.",
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    except Exception:
        Path(name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--claims-table", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--cluster-d-mv3", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.ledger, args.dashboard, args.summary, args.claims_table, args.provenance, args.cluster_d_mv3]
    if any(path.resolve(strict=False) == args.output.resolve(strict=False) for path in inputs):
        print("ERROR: output aliases input")
        return 2
    try:
        payload = audit(*inputs)
        atomic_json(args.output, payload)
    except (OSError, AuditInputError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"{payload['status']}: {payload['finding_count']} finding(s)")
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
