#!/usr/bin/env python3
"""Fail-closed audit for Cluster E canonical claim and provenance binding."""
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
VERSION = "1.0.0"
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


class AuditInputError(RuntimeError):
    """Controlled invalid-input failure."""


def snapshot_text(path: Path) -> tuple[str, dict[str, Any]]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"invalid UTF-8 in {path}: {exc}") from exc
    return text, {
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "snapshot_policy": "SINGLE_READ_EXACT_BYTES",
    }


def load_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    text, provenance = snapshot_text(path)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditInputError(f"JSON root must be an object: {path}")
    return value, provenance


def load_ledger(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    text, provenance = snapshot_text(path)
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise AuditInputError("claim ledger is empty")
    header = rows[0]
    if len(header) != EXPECTED_COLUMNS:
        raise AuditInputError(
            f"claim ledger header has {len(header)} columns, expected {EXPECTED_COLUMNS}"
        )
    out: dict[str, dict[str, str]] = {}
    for line_no, row in enumerate(rows[1:], start=2):
        if len(row) != EXPECTED_COLUMNS:
            raise AuditInputError(
                f"claim ledger line {line_no} has {len(row)} columns, expected {EXPECTED_COLUMNS}"
            )
        item = dict(zip(header, row, strict=True))
        claim_id = item["claim_id"]
        if not claim_id:
            raise AuditInputError(f"claim ledger line {line_no} has empty claim_id")
        if claim_id in out:
            raise AuditInputError(f"duplicate claim_id {claim_id}")
        out[claim_id] = item
    provenance["rows"] = len(out)
    provenance["columns"] = len(header)
    return out, provenance


def finding(code: str, message: str, *, artifact: str, evidence: Any = None) -> dict[str, Any]:
    item: dict[str, Any] = {"code": code, "artifact": artifact, "message": message}
    if evidence is not None:
        item["evidence"] = evidence
    return item


def require_claim(
    claims: dict[str, dict[str, str]],
    claim_id: str,
    expected: dict[str, str],
    findings: list[dict[str, Any]],
) -> None:
    row = claims.get(claim_id)
    if row is None:
        findings.append(finding("CLAIM_MISSING", f"missing {claim_id}", artifact="ledger"))
        return
    for field, value in expected.items():
        if row.get(field) != value:
            findings.append(
                finding(
                    "CLAIM_FIELD_MISMATCH",
                    f"{claim_id}.{field}={row.get(field)!r}, expected {value!r}",
                    artifact="ledger",
                )
            )


def find_row(rows: list[dict[str, str]], claim: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("claim") == claim:
            return row
    return None


def audit(
    ledger_path: Path,
    dashboard_path: Path,
    summary_path: Path,
    claims_table_path: Path,
    provenance_path: Path,
    mv3_path: Path,
) -> dict[str, Any]:
    claims, ledger_prov = load_ledger(ledger_path)
    dashboard, dashboard_prov = snapshot_text(dashboard_path)
    summary, summary_prov = snapshot_text(summary_path)
    claims_table_text, claims_table_prov = snapshot_text(claims_table_path)
    provenance, provenance_prov = load_json(provenance_path)
    mv3, mv3_prov = load_json(mv3_path)

    findings: list[dict[str, Any]] = []
    require_claim(
        claims,
        "CL-013",
        {
            "current_value": "92",
            "unit": "ADC/MeV",
            "syst_unc": "28",
            "truth_type": "data_mc_calibration_proxy",
            "status": "GATED",
        },
        findings,
    )
    require_claim(
        claims,
        "CL-021",
        {
            "current_value": "68269.40598948313",
            "status": "FLAWED",
            "truth_type": "legacy_data_mc_profile_diagnostic",
        },
        findings,
    )
    require_claim(
        claims,
        "CL-022",
        {
            "current_value": "0.003232254011764034",
            "numerator": "283",
            "denominator": "87555",
            "truth_type": "mc_truth_only",
            "status": "TRUTH_LEVEL_MC_ONLY",
        },
        findings,
    )

    documents = {"dashboard": dashboard, "summary": summary}
    for artifact, text in documents.items():
        if re.search(r"CL-013[^\n]{0,120}\b110(?:\.0)?\b", text):
            findings.append(
                finding(
                    "CL013_CANONICAL_VALUE_MISMATCH",
                    "CL-013 is bound to 110 instead of the canonical 92 ADC/MeV",
                    artifact=artifact,
                )
            )
        if "92 ADC/MeV" not in text or "28 ADC/MeV" not in text:
            findings.append(
                finding(
                    "CL013_EXACT_BINDING_MISSING",
                    "canonical 92 ADC/MeV and 28 ADC/MeV envelope are not both bound",
                    artifact=artifact,
                )
            )
        if re.search(r"CL-021[^\n]{0,140}(?:8\.6e4|86135|6\.8e4)", text, re.IGNORECASE):
            findings.append(
                finding(
                    "CL021_CLUSTERD_RERUN_CONFLATED",
                    "a Cluster D rerun/rounded value is cited as canonical CL-021",
                    artifact=artifact,
                    evidence={
                        "canonical": 68269.40598948313,
                        "clusterD_rerun": mv3.get("chi2_per_ndf"),
                    },
                )
            )
        if "68269.40598948313" not in text:
            findings.append(
                finding(
                    "CL021_EXACT_BINDING_MISSING",
                    "exact canonical CL-021 chi2/ndf is absent",
                    artifact=artifact,
                )
            )
        if "25/38 toy early-peak C12" in text:
            findings.append(
                finding(
                    "CL022_TOY_COUNTS_SUBSTITUTED",
                    "Cluster D toy counts replace canonical CL-022 283/87555 morphology rate",
                    artifact=artifact,
                )
            )
        if "283/87555" not in text:
            findings.append(
                finding(
                    "CL022_EXACT_COUNTS_MISSING",
                    "canonical CL-022 counts 283/87555 are absent",
                    artifact=artifact,
                )
            )

    table_rows = list(csv.DictReader(claims_table_text.splitlines()))
    required_columns = {
        "claim",
        "headline",
        "evidence_class",
        "status",
        "source",
        "figure",
        "claim_id",
    }
    if set(table_rows[0]) != required_columns if table_rows else True:
        findings.append(
            finding(
                "CLAIMS_TABLE_SCHEMA_INVALID",
                "claims table schema is missing or unexpected",
                artifact="claims_table",
            )
        )
    else:
        mv0 = find_row(table_rows, "ADC gain (data/MC proxy, MV0)")
        if not mv0 or "92" not in mv0["headline"] or "28" not in mv0["headline"]:
            findings.append(
                finding(
                    "CLAIMS_TABLE_CL013_MISMATCH",
                    "MV0 claim-table row is not bound to 92 ADC/MeV with 28 ADC/MeV envelope",
                    artifact="claims_table",
                )
            )
        anomaly = find_row(table_rows, "Anomaly / C12 identity")
        if not anomaly or "283/87555" not in anomaly["headline"]:
            findings.append(
                finding(
                    "CLAIMS_TABLE_CL022_MISMATCH",
                    "anomaly row is not bound to canonical 283/87555 counts",
                    artifact="claims_table",
                )
            )
        elif anomaly["status"] != "TRUTH_LEVEL_MC_ONLY":
            findings.append(
                finding(
                    "CLAIMS_TABLE_CL022_STATUS_MISMATCH",
                    "anomaly row status does not match CL-022",
                    artifact="claims_table",
                )
            )
        stopping = find_row(table_rows, "Stopping-depth data/MC closure")
        if not stopping or "68269.40598948313" not in stopping["headline"]:
            findings.append(
                finding(
                    "CLAIMS_TABLE_CL021_MISMATCH",
                    "stopping row is not bound to exact canonical CL-021 value",
                    artifact="claims_table",
                )
            )
        elif stopping["status"] != "FLAWED":
            findings.append(
                finding(
                    "CLAIMS_TABLE_CL021_STATUS_MISMATCH",
                    "stopping row status does not match CL-021 FLAWED",
                    artifact="claims_table",
                )
            )

    base_commit = provenance.get("base_commit")
    if not isinstance(base_commit, str) or re.fullmatch(r"[0-9a-f]{40}", base_commit) is None:
        findings.append(
            finding(
                "PROVENANCE_BASE_COMMIT_UNBOUND",
                "base_commit is not a full 40-hex commit SHA",
                artifact="provenance",
                evidence=base_commit,
            )
        )
    digest_map = provenance.get("input_sha256")
    if not isinstance(digest_map, dict):
        findings.append(
            finding(
                "PROVENANCE_FULL_SHA256_MISSING",
                "input_sha256 mapping with full digests is absent",
                artifact="provenance",
            )
        )
        digest_map = {}
    for path in sorted(REQUIRED_PROVENANCE_INPUTS):
        digest = digest_map.get(path)
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            findings.append(
                finding(
                    "PROVENANCE_INPUT_UNBOUND",
                    f"missing full SHA-256 for {path}",
                    artifact="provenance",
                )
            )

    canonical = float(claims["CL-021"]["current_value"])
    rerun = mv3.get("chi2_per_ndf")
    comparison = {
        "canonical_cl021_chi2_per_ndf": canonical,
        "clusterD_rerun_chi2_per_ndf": rerun,
        "absolute_difference": None if not isinstance(rerun, (int, float)) else rerun - canonical,
        "scientific_interpretation": (
            "distinct source-bound diagnostics; the Cluster D rerun does not "
            "silently supersede CL-021"
        ),
    }

    return {
        "schema": "ccb-clusterE-canonical-binding-audit/1",
        "validator_version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "finding_count": len(findings),
        "findings": findings,
        "canonical_values": {
            "CL-013": {"value": 92.0, "syst_envelope_adc_per_mev": 28.0, "status": "GATED"},
            "CL-021": {"chi2_per_ndf": canonical, "status": "FLAWED"},
            "CL-022": {
                "rate": 0.003232254011764034,
                "numerator": 283,
                "denominator": 87555,
                "status": "TRUTH_LEVEL_MC_ONLY",
            },
        },
        "mv3_source_comparison": comparison,
        "inputs": {
            "ledger": ledger_prov,
            "dashboard": dashboard_prov,
            "summary": summary_prov,
            "claims_table": claims_table_prov,
            "provenance": provenance_prov,
            "clusterD_mv3": mv3_prov,
        },
        "scientific_boundary": (
            "This audit validates claim/provenance binding only; it does not validate detector "
            "performance, data/MC transfer, calibration, or an accepted stopping-profile closure."
        ),
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--claims-table", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--cluster-d-mv3", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inputs = [
        args.ledger,
        args.dashboard,
        args.summary,
        args.claims_table,
        args.provenance,
        args.cluster_d_mv3,
    ]
    output_resolved = args.output.resolve(strict=False)
    for input_path in inputs:
        if input_path.resolve(strict=False) == output_resolved:
            print(f"ERROR: output aliases input: {input_path}")
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
