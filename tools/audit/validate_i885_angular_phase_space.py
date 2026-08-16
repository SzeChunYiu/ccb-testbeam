#!/usr/bin/env python3
"""Validate I885 normal-incidence-only angular undercoverage gate (#1093)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate(repo: Path) -> dict:
    path = repo / "docs/contracts/I885_ANGULAR_PHASE_SPACE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if data.get("evidence_state") != "BLOCKED":
        errors.append("evidence_state_must_be_BLOCKED")
    if data.get("campaign_coverage") != "NORMAL_INCIDENCE_ONLY":
        errors.append("campaign_coverage_must_be_NORMAL_INCIDENCE_ONLY")
    campaign = repo / "geant4/single_stave/slurm/points_i885_campaign.csv"
    text = campaign.read_text(encoding="utf-8")
    if "NORMAL_INCIDENCE_ONLY" not in text:
        errors.append("campaign_csv_missing_NORMAL_INCIDENCE_ONLY")
    if "theta_deg=0.0" not in text or "phi_deg=0.0" not in text:
        errors.append("campaign_csv_missing_explicit_zero_angles")
    gen = (repo / "geant4/single_stave/slurm/make_i885_campaign.py").read_text(encoding="utf-8")
    if "ANGULAR_COVERAGE" not in gen or "NORMAL_INCIDENCE_ONLY" not in gen:
        errors.append("generator_missing_angular_coverage_declaration")
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
