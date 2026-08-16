#!/usr/bin/env python3
"""Fail-closed gate for same-sample timing method selection (#1062)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def validate(result: dict) -> dict:
    errors = []
    ms = result.get("method_selection") or {}
    if ms.get("policy") != "SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY":
        errors.append("unexpected_or_missing_method_selection_policy")
    if ms.get("authorising") is True:
        errors.append("same_sample_minimum_marked_authorising")
    if result.get("best_pair_sigma68_authorising") is True:
        errors.append("best_pair_sigma68_authorising_true")
    claim = result.get("claim") or {}
    if claim.get("authorising") and claim.get("uses_same_sample_minimum"):
        errors.append("authorising_claim_uses_same_sample_minimum")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--result", type=Path, required=True)
    args = p.parse_args(argv)
    result = json.loads(args.result.read_text(encoding="utf-8"))
    out = validate(result)
    print(out["status"])
    print(json.dumps(out, indent=2))
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
