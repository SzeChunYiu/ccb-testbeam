#!/usr/bin/env python3
"""Validate the source-bound Cluster E canonical front door."""
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
INPUT_POLICY = "INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS"
VERSION = "2.1.0"
EXPECTED_COLUMNS = 43
REQUIRED_IDENTITIES = {
    "docs/claim_ledger.csv",
    "reports/mv0_calibration_1782677847/calibration.json",
    "reports/mv3_stopping_v3_1782679272/mv3_summary.json",
    "reports/mv6_representation_1782678362/mv6_representation_summary.json",
    "reports/studies/clusterD/mv_runs/mv3/mv3_summary.json",
    "scripts/clusterE/clusterE_canonical_frontdoor.py",
}


class AuditInputError(RuntimeError):
    """Controlled invalid-input failure."""


def read(path: Path) -> tuple[str, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise AuditInputError(f"invalid UTF-8 in {path}") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def ledger(path: Path) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    text, provenance = read(path)
    rows = list(csv.reader(text.splitlines()))
    if not rows or len(rows[0]) != EXPECTED_COLUMNS:
        raise AuditInputError("claim ledger header width mismatch")
    out: dict[str, dict[str, str]] = {}
    for line_no, row in enumerate(rows[1:], 2):
        if len(row) != EXPECTED_COLUMNS:
            raise AuditInputError(f"claim ledger line {line_no} width mismatch")
        item = dict(zip(rows[0], row, strict=True))
        claim = item["claim_id"]
        if not claim or claim in out:
            raise AuditInputError(f"duplicate or empty claim_id {claim}")
        out[claim] = item
    return out, provenance


def object_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    text, provenance = read(path)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AuditInputError(f"invalid JSON in {path}") from exc
    if not isinstance(value, dict):
        raise AuditInputError(f"JSON root must be object: {path}")
    return value, provenance


def finding(code: str, artifact: str, message: str = "") -> dict[str, str]:
    return {"code": code, "artifact": artifact, "message": message}


def audit(
    ledger_path: Path,
    dashboard_path: Path,
    summary_path: Path,
    table_path: Path,
    provenance_path: Path,
    mv3_path: Path,
) -> dict[str, Any]:
    claims, ledger_prov = ledger(ledger_path)
    dashboard, dashboard_prov = read(dashboard_path)
    summary, summary_prov = read(summary_path)
    table_text, table_prov = read(table_path)
    provenance, provenance_prov = object_json(provenance_path)
    mv3, mv3_prov = object_json(mv3_path)
    findings: list[dict[str, str]] = []
    expected = {
        "CL-013": {
            "current_value": "92",
            "unit": "ADC/MeV",
            "syst_unc": "28",
            "truth_type": "data_mc_calibration_proxy",
            "status": "GATED",
        },
        "CL-021": {
            "current_value": "68269.40598948313",
            "truth_type": "legacy_data_mc_profile_diagnostic",
            "status": "FLAWED",
        },
        "CL-022": {
            "current_value": "0.003232254011764034",
            "numerator": "283",
            "denominator": "87555",
            "truth_type": "mc_truth_only",
            "status": "TRUTH_LEVEL_MC_ONLY",
        },
    }
    for claim, fields in expected.items():
        row = claims.get(claim)
        if row is None:
            findings.append(finding("CLAIM_MISSING", "ledger", claim))
            continue
        for field, value in fields.items():
            if row.get(field) != value:
                findings.append(
                    finding(
                        "CLAIM_FIELD_MISMATCH",
                        "ledger",
                        f"{claim}.{field}",
                    )
                )
    for artifact, text in {"dashboard": dashboard, "summary": summary}.items():
        required = (
            "92 ADC/MeV",
            "28 ADC/MeV",
            "68269.40598948313",
            "283/87555",
        )
        for token in required:
            if token not in text:
                findings.append(
                    finding("CANONICAL_TOKEN_MISSING", artifact, token)
                )
        if re.search(r"CL-013[^\n]{0,120}\b110(?:\.0)?\b", text):
            findings.append(
                finding("CL013_CANONICAL_VALUE_MISMATCH", artifact)
            )
        if re.search(
            r"CL-021[^\n]{0,140}(?:86135|8\.6e4|6\.8e4)",
            text,
            re.IGNORECASE,
        ):
            findings.append(
                finding("CL021_CLUSTERD_RERUN_CONFLATED", artifact)
            )
        if "25/38 toy early-peak C12" in text:
            findings.append(finding("CL022_TOY_COUNTS_SUBSTITUTED", artifact))
        if not any(
            value in text
            for value in (
                "does not supersede CL-021",
                "does **not supersede CL-021**",
            )
        ):
            findings.append(
                finding("DISTINCT_DIAGNOSTIC_CAVEAT_MISSING", artifact)
            )
    rows = list(csv.DictReader(table_text.splitlines()))
    by_claim = {row.get("claim"): row for row in rows}
    table_checks = {
        "ADC gain (data/MC proxy, MV0)": ("92", "GATED"),
        "Stopping-depth data/MC closure": (
            "68269.40598948313",
            "FLAWED",
        ),
        "Anomaly / C12 identity": ("283/87555", "TRUTH_LEVEL_MC_ONLY"),
    }
    for name, (token, status) in table_checks.items():
        row = by_claim.get(name)
        if (
            not row
            or token not in row.get("headline", "")
            or row.get("status") != status
        ):
            findings.append(
                finding("CLAIMS_TABLE_MISMATCH", "claims_table", name)
            )
    commit = provenance.get("base_commit")
    commit_is_valid = isinstance(commit, str) and bool(
        re.fullmatch(r"[0-9a-f]{40}", commit)
    )
    if not commit_is_valid:
        findings.append(finding("PROVENANCE_BASE_COMMIT_UNBOUND", "provenance"))
    if provenance.get("input_authorization_policy") != INPUT_POLICY:
        findings.append(
            finding("PROVENANCE_INPUT_POLICY_MISSING", "provenance")
        )
    identities = provenance.get("input_identities")
    if not isinstance(identities, dict):
        findings.append(finding("PROVENANCE_IDENTITIES_MISSING", "provenance"))
    else:
        for path in sorted(REQUIRED_IDENTITIES):
            item = identities.get(path)
            ok = isinstance(item, dict)
            ok = ok and item.get("algorithm") == "git_blob_sha1"
            digest = str(item.get("digest", "")) if isinstance(item, dict) else ""
            commit_digest = (
                str(item.get("commit_blob_digest", ""))
                if isinstance(item, dict)
                else ""
            )
            ok = ok and bool(re.fullmatch(r"[0-9a-f]{40}", digest))
            ok = ok and commit_digest == digest
            ok = ok and item.get("commit") == commit
            ok = ok and item.get("commit_match") is True
            ok = ok and item.get("authorization_policy") == INPUT_POLICY
            ok = ok and bool(
                re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", "")))
            )
            ok = ok and isinstance(item.get("bytes"), int) and item["bytes"] > 0
            ok = ok and (
                item.get("snapshot_policy")
                == "SINGLE_READ_STRICT_UTF8_EXACT_BYTES"
            )
            if not ok:
                findings.append(
                    finding("PROVENANCE_INPUT_UNBOUND", "provenance", path)
                )
    canonical = 68269.40598948313
    rerun = mv3.get("chi2_per_ndf")
    return {
        "schema": "ccb-clusterE-canonical-binding-audit/2",
        "validator_version": VERSION,
        "policy": POLICY,
        "input_authorization_policy": INPUT_POLICY,
        "status": "VALIDATED" if not findings else "FLAWED",
        "finding_count": len(findings),
        "findings": findings,
        "mv3_source_comparison": {
            "canonical_cl021_chi2_per_ndf": canonical,
            "clusterD_rerun_chi2_per_ndf": rerun,
            "absolute_difference": (
                None
                if not isinstance(rerun, (int, float))
                else rerun - canonical
            ),
            "scientific_interpretation": (
                "distinct diagnostics; rerun does not supersede CL-021"
            ),
        },
        "inputs": {
            "ledger": ledger_prov,
            "dashboard": dashboard_prov,
            "summary": summary_prov,
            "claims_table": table_prov,
            "provenance": provenance_prov,
            "clusterD_mv3": mv3_prov,
        },
        "scientific_boundary": (
            "Claim/provenance binding only; no accepted closure or detector "
            "performance."
        ),
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
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
    for option in (
        "ledger",
        "dashboard",
        "summary",
        "claims-table",
        "provenance",
        "cluster-d-mv3",
        "output",
    ):
        parser.add_argument(f"--{option}", type=Path, required=True)
    args = parser.parse_args()
    inputs = [
        args.ledger,
        args.dashboard,
        args.summary,
        args.claims_table,
        args.provenance,
        args.cluster_d_mv3,
    ]
    if any(
        path.resolve(strict=False) == args.output.resolve(strict=False)
        for path in inputs
    ):
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
