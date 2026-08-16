#!/usr/bin/env python3
"""Validate neutron tracking-time cut provenance contract (#1091)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate(meta: dict, contract: dict) -> dict:
    errors = []
    for key in contract["required_sidecar_fields"]:
        if key not in meta:
            errors.append(f"missing:{key}")
    status = meta.get("neutron_tracking_time_cut_status")
    configured = bool(meta.get("neutron_tracking_time_cut_configured", False))
    cut = meta.get("neutron_tracking_time_cut_us")
    if cut is None:
        errors.append("missing_cut_value")
    if not configured and status != contract["status_when_unconfigured"]:
        errors.append("unconfigured_status_mismatch")
    if meta.get("authorising_delayed_neutron_claim") and not configured:
        errors.append("authorising_delayed_neutron_without_configured_cut")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--meta", type=Path, required=True)
    args = p.parse_args(argv)
    contract = json.loads(
        (args.repo_root / "docs/contracts/NEUTRON_TRACKING_TIME_CUT.json").read_text(encoding="utf-8")
    )
    meta = json.loads(args.meta.read_text(encoding="utf-8"))
    result = validate(meta, contract)
    print(result["status"])
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
