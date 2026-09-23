#!/usr/bin/env python3
"""Validate TRIGGER_HARDWARE_RESPONSE fail-closed contract (#1045).

Two admissible evidence states:

- ``BLOCKED`` (ADR-0002 baseline): no instrumented geometry; the contract must
  carry ``hardware_definition_status = UNKNOWN_EXTERNAL``.
- ``MIGRATION_VALIDATED`` (ADR-1045): the MC-side proxy -> instrumented
  hardware-response migration has been quantified on the authorising
  corrected-source MC. The contract must carry a ``hardware_response_study``
  block whose artifacts exist on disk and whose headline reference-point
  numbers reproduce from the committed report.

In BOTH states real-data hardware-trigger claims stay forbidden:
``forbidden_labels_until_validated`` non-empty, ``MC_TRIGGER_PROXY`` admissible,
ADR-0002 present.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED = {
    "schema_version",
    "contract_id",
    "issue",
    "evidence_state",
    "hardware_definition_status",
    "admissible_labels",
    "forbidden_labels_until_validated",
    "fail_closed_policy",
}

STUDY_REQUIRED = {
    "geometry",
    "joint_matrix",
    "report",
    "n_events",
    "reference_point",
    "retention",
    "adr",
}
STUDY_REFPOINT_REQUIRED = {"threshold_mev", "coinc_ns", "both", "proxy_only", "hardware_only"}


def _validate_migration_validated(repo: Path, data: dict) -> list[str]:
    errors: list[str] = []
    if data.get("hardware_definition_status") != "GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED":
        errors.append(
            "hardware_definition_status_must_be_GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED"
        )
    labels = data.get("admissible_labels", [])
    if "MC_TRIGGER_MIGRATION" not in labels:
        errors.append("missing_MC_TRIGGER_MIGRATION_label")
    study = data.get("hardware_response_study")
    if not isinstance(study, dict):
        return errors + ["missing_hardware_response_study_block"]
    missing = sorted(STUDY_REQUIRED - set(study))
    errors += [f"missing_study_key:{k}" for k in missing]
    refpoint = study.get("reference_point")
    if not isinstance(refpoint, dict):
        errors.append("study_reference_point_must_be_object")
    else:
        rp_missing = sorted(STUDY_REFPOINT_REQUIRED - set(refpoint))
        errors += [f"missing_reference_point_key:{k}" for k in rp_missing]

    # Artifacts referenced by the study block must exist in-repo.
    artifact_keys = [study.get("joint_matrix"), study.get("report"), study.get("adr")]
    geom = study.get("geometry")
    if isinstance(geom, dict):
        artifact_keys.append(geom.get("receipt"))
    figs = study.get("figures")
    if isinstance(figs, list):
        artifact_keys.extend(figs)
    for rel in artifact_keys:
        if isinstance(rel, str) and rel and not (repo / rel).is_file():
            errors.append(f"study_artifact_missing:{rel}")

    # ADR-0002 stays in force for real-data claims; ADR-1045 records the bump.
    adr1045 = repo / "docs/mc_validation/adr/ADR-1045-migration-validated.md"
    if not adr1045.is_file():
        errors.append("missing_ADR-1045")

    # Headline numbers must reproduce from the committed report (the study
    # block may not drift from the machine-readable source of truth).
    report_rel = study.get("report")
    if isinstance(report_rel, str) and (repo / report_rel).is_file():
        try:
            report = json.loads((repo / report_rel).read_text(encoding="utf-8"))
            ref = report["reference"]
            if isinstance(refpoint, dict) and {"both", "proxy_only", "hardware_only"} <= set(refpoint):
                for k in ("both", "proxy_only", "hardware_only"):
                    if int(refpoint[k]) != int(ref[k]):
                        errors.append(f"reference_point_mismatch:{k}")
                if int(ref["proxy_total"]) != int(ref["both"]) + int(ref["proxy_only"]):
                    errors.append("report_proxy_total_inconsistent")
                if abs(float(study.get("retention", -1.0)) - float(ref["retention"])) > 5e-4:
                    errors.append("study_retention_mismatch_vs_report")
            if int(study.get("n_events", -1)) != int(report["n_events"]):
                errors.append("study_n_events_mismatch_vs_report")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"report_not_readable:{exc}")
    return errors


def validate(repo: Path) -> dict:
    path = repo / "docs/contracts/TRIGGER_HARDWARE_RESPONSE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED - set(data))
    errors = [f"missing_key:{k}" for k in missing]
    if data.get("contract_id") != "TRIGGER_HARDWARE_RESPONSE":
        errors.append("bad_contract_id")

    state = data.get("evidence_state")
    if state == "BLOCKED":
        if data.get("hardware_definition_status") != "UNKNOWN_EXTERNAL":
            errors.append("hardware_definition_status_must_be_UNKNOWN_EXTERNAL")
    elif state == "MIGRATION_VALIDATED":
        errors += _validate_migration_validated(repo, data)
    else:
        errors.append(f"unsupported_evidence_state:{state}")

    if "MC_TRIGGER_PROXY" not in data.get("admissible_labels", []):
        errors.append("missing_MC_TRIGGER_PROXY_label")
    if not data.get("forbidden_labels_until_validated"):
        errors.append("forbidden_labels_must_stay_non_empty")
    adr = repo / "docs/mc_validation/ADR-0002-trigger-hardware-proxy-blocked.md"
    if not adr.is_file():
        errors.append("missing_ADR-0002")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "path": str(path)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = ap.parse_args(argv)
    payload = validate(args.repo_root)
    print(payload["status"])
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
