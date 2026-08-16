#!/usr/bin/env python3
"""Validate TRIGGER_HARDWARE_RESPONSE fail-closed contract (#1045)."""
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
    "fail_closed_policy",
}


def validate(repo: Path) -> dict:
    path = repo / "docs/contracts/TRIGGER_HARDWARE_RESPONSE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = sorted(REQUIRED - set(data))
    errors = [f"missing_key:{k}" for k in missing]
    if data.get("contract_id") != "TRIGGER_HARDWARE_RESPONSE":
        errors.append("bad_contract_id")
    if data.get("evidence_state") != "BLOCKED":
        errors.append("evidence_state_must_be_BLOCKED_until_validated")
    if data.get("hardware_definition_status") != "UNKNOWN_EXTERNAL":
        errors.append("hardware_definition_status_must_be_UNKNOWN_EXTERNAL")
    if "MC_TRIGGER_PROXY" not in data.get("admissible_labels", []):
        errors.append("missing_MC_TRIGGER_PROXY_label")
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
