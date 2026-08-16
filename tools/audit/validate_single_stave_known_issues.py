#!/usr/bin/env python3
"""Validate single-stave status prose against the canonical runtime record."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
POLICY = "KNOWN_ISSUES_MUST_MATCH_REPOSITORY_RECORDED_G4_VALIDATION"


class ValidationError(ValueError):
    """Controlled malformed-input error."""


def read_utf8(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValidationError(f"cannot read {path}: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path} is not valid UTF-8") from exc
    return text, {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _require_match(pattern: str, text: str, name: str) -> re.Match[str]:
    match = re.search(pattern, text)
    if not match:
        raise ValidationError(f"validation record lacks {name}")
    return match


def parse_results(text: str) -> dict[str, Any]:
    build = _require_match(
        r"\*\*Build:\*\* Geant4 ([0-9.]+) \(GCC ([0-9.]+)\).*\(([^)]+)\)",
        text,
        "build provenance",
    )
    events = _require_match(r"100 MeV proton, ([0-9,]+) events per run", text, "event count")
    branches = _require_match(
        r"([0-9]+)/([0-9]+) branches exact equal across all ([0-9,]+) events",
        text,
        "event-tree equality",
    )
    photons = _require_match(r"([0-9,]+) photon records in both runs", text, "photon count")
    fields = _require_match(r"All ([0-9]+) fields .* exact equal", text, "photon fields")
    yield_line = _require_match(
        r"Cross-seed mean optical yield: ([0-9.]+) PE \(RSE = ([0-9.]+)%\)",
        text,
        "cross-seed yield",
    )
    seed_rows = re.findall(r"^\|\s*([1-4])\s*\|\s*([0-9.]+)\s*\|", text, re.MULTILINE)
    if len(seed_rows) != 4:
        raise ValidationError("validation record must contain four seed rows")
    return {
        "geant4_version": build.group(1),
        "gcc_version": build.group(2),
        "node": build.group(3),
        "events_per_run": int(events.group(1).replace(",", "")),
        "event_branches_equal": int(branches.group(1)),
        "event_branches_total": int(branches.group(2)),
        "event_equality_count": int(branches.group(3).replace(",", "")),
        "photon_records": int(photons.group(1).replace(",", "")),
        "photon_fields_equal": int(fields.group(1)),
        "cross_seed_mean_pe": float(yield_line.group(1)),
        "cross_seed_rse_percent": float(yield_line.group(2)),
        "seed_means_pe": [float(value) for _, value in seed_rows],
    }


def audit(known_path: Path, results_path: Path) -> dict[str, Any]:
    known, known_provenance = read_utf8(known_path)
    results, results_provenance = read_utf8(results_path)
    measured = parse_results(results)
    issues: list[dict[str, Any]] = []

    required_tokens = {
        "validated_status": "Implementation/runtime status:** VALIDATED",
        "canonical_evidence": "docs/validation/G4_VALIDATION_RESULTS.md",
        "geant4_version": f"Geant4 {measured['geant4_version']}",
        "gcc_version": f"GCC {measured['gcc_version']}",
        "events_per_run": f"{measured['events_per_run']} events per run",
        "event_branches": (
            f"{measured['event_branches_equal']}/{measured['event_branches_total']} "
            "branches exact equal"
        ),
        "photon_records": f"{measured['photon_records']:,} records",
        "photon_fields": f"all {measured['photon_fields_equal']} stored fields exact equal",
        "mean_yield": f"{measured['cross_seed_mean_pe']} PE/event",
        "rse": f"RSE {measured['cross_seed_rse_percent']}%",
        "stopping_power_boundary": "BLK-G4-SP-001",
        "calibration_boundary": "not a detector calibration",
        "pr_state": "PR #868 remains closed and unmerged",
    }
    for name, token in required_tokens.items():
        if token not in known:
            issues.append({"code": "MISSING_CURRENT_STATUS_TOKEN", "name": name, "token": token})

    for value in measured["seed_means_pe"]:
        token = str(value)
        if token not in known:
            issues.append({"code": "MISSING_SEED_MEAN", "value": value})

    forbidden = (
        "## Open issue A",
        "## Open issue B",
        "photon-collection readout IN_PROGRESS",
        "Thread-count reproducibility | NOT VALIDATED",
        "Multiseed stability | NOT VALIDATED",
        "optical calibration plots require issue A resolved first",
    )
    for phrase in forbidden:
        if count := known.count(phrase):
            issues.append({
                "code": "STALE_RESOLVED_ISSUE_NARRATIVE",
                "phrase": phrase,
                "occurrences": count,
            })

    return {
        "validator": Path(__file__).name,
        "version": VERSION,
        "policy": POLICY,
        "status": "VALIDATED" if not issues else "FLAWED",
        "known_issues": known_provenance,
        "validation_results": results_provenance,
        "reconstructed": measured,
        "required_tokens": required_tokens,
        "forbidden_stale_phrases": list(forbidden),
        "issues": issues,
        "n_issues": len(issues),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--known-issues", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = audit(args.known_issues, args.results)
    except ValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "VALIDATED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
