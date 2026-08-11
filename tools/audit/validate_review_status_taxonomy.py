#!/usr/bin/env python3
"""Ensure chapter badges follow REVIEW_STATUS_TAXONOMY (#990)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VERSION = "1.0.0"

BADGE_OK = re.compile(
    r">\s*\*\*REVIEW_STATUS:\s*(EDITORIAL_REVIEWED|METHOD_REVIEWED|SOURCE_VERIFIED|"
    r"EXECUTED_REPRODUCED|CLAIM_AUTHORIZED)\b"
)


def validate(repo: Path) -> list[str]:
    tax = json.loads((repo / "docs/contracts/REVIEW_STATUS_TAXONOMY.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    chapters = sorted((repo / "docs/academic_chapters").glob("*.md"))
    for path in chapters:
        text = path.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:12])
        for bad in tax.get("forbidden_unqualified_badges", []):
            if bad in head:
                errors.append(f"UNQUALIFIED_NATURE_BADGE:{path.name}")
        # If a REVIEW_STATUS badge is present it must be taxonomy-valid
        if "REVIEW_STATUS:" in head and not BADGE_OK.search(head):
            errors.append(f"INVALID_REVIEW_STATUS_BADGE:{path.name}")
        if "AI role-separated" not in head and "REVIEW_STATUS:" in head:
            errors.append(f"MISSING_AI_ROLE_DISCLOSURE:{path.name}")
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = p.parse_args(argv)
    errs = validate(args.repo_root)
    if errs:
        print("FAIL")
        for e in errs:
            print(e)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
