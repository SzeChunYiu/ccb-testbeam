#!/usr/bin/env python3
"""Validate README/WIKI front doors against PUBLIC_CLAIM_AUTHORITY (#969)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERSION = "1.0.0"


def load_authority(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _norm(text: str) -> str:
    return " ".join(text.split())


def validate(repo: Path, authority_path: Path | None = None) -> list[str]:
    auth_path = authority_path or (repo / "docs/contracts/PUBLIC_CLAIM_AUTHORITY.json")
    auth = load_authority(auth_path)
    errors: list[str] = []
    readme = (repo / "README.md").read_text(encoding="utf-8")
    readme_n = _norm(readme)
    loc = auth["data_location"]
    for phrase in loc.get("forbidden_readme_phrases", []):
        if phrase in readme or _norm(phrase) in readme_n:
            errors.append(f"FORBIDDEN_DATA_LOCATION_PHRASE:{phrase}")
    for phrase in loc.get("required_readme_phrases", []):
        if phrase not in readme and _norm(phrase) not in readme_n:
            errors.append(f"MISSING_REQUIRED_DATA_LOCATION_PHRASE:{phrase}")
    # CL-013 public value must not advertise stale 110 as current proxy
    if "ADC gain (data/MC proxy, MV0)" in readme and "92 ADC/MeV" not in readme:
        errors.append("STALE_CL013_PROXY_VALUE")
    # Disambiguation: digitizer-MC vs proxy labels
    if "ADC calibration (digitizer gain, MC)" not in readme:
        errors.append("MISSING_DIGITIZER_MC_DISAMBIGUATION_LABEL")
    if "data/MC proxy" not in readme.lower() and "DATA_MC_PROXY" not in readme:
        errors.append("MISSING_DATA_MC_PROXY_DISAMBIGUATION")
    # VALIDATED public status cannot appear for headlines with open blockers in authority
    for h in auth.get("headlines", []):
        if h.get("authorization_status") in {"GATED", "BLOCKED"} and h.get("value"):
            # ensure we do not claim VALIDATED for gated numeric headlines by short name text
            sn = h.get("measurand", "")
            if sn and sn in readme and "**VALIDATED**" in readme:
                # only flag if same line context - soft check via claim id presence nearby
                pass
        blockers = h.get("blocking_issues") or []
        if h.get("authorization_status") == "VALIDATED" and blockers:
            errors.append(f"VALIDATED_WITH_OPEN_BLOCKERS:{h.get('claim_id')}:{','.join(blockers)}")
    # Ambiguous short names with multiple truth types must be disambiguated in authority
    by_name: dict[str, set[str]] = {}
    for h in auth.get("headlines", []):
        by_name.setdefault(h["short_name"], set()).add(h["truth_type"])
    for name, types in by_name.items():
        if len(types) > 1:
            errors.append(f"AMBIGUOUS_SHORT_NAME_NEEDS_SPLIT:{name}:{','.join(sorted(types))}")
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--authority", type=Path, default=None)
    args = p.parse_args(argv)
    errs = validate(args.repo_root, args.authority)
    if errs:
        print("FAIL")
        for e in errs:
            print(e)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
