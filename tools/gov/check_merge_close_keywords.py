#!/usr/bin/env python3
"""Block GitHub auto-close keywords for scientific-universe issues (#1218)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "1.0.0"

CLOSE_RE = re.compile(r"(?i)\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)")


def scan_text(text: str, policy: dict | None = None) -> list[dict]:
    findings = []
    for m in CLOSE_RE.finditer(text or ""):
        start = max(0, m.start() - 20)
        window = text[start : m.end() + 5]
        if re.search(r"(?i)does not close\s+#" + m.group(2), window):
            continue
        findings.append(
            {
                "keyword": m.group(1),
                "issue": int(m.group(2)),
                "span": m.group(0),
                "decision": "BLOCK_OR_REVIEW_CLOSE",
            }
        )
    return findings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--text-file", type=Path, default=None)
    p.add_argument("--text", default=None)
    p.add_argument("--allow-close", action="append", default=[])
    args = p.parse_args(argv)
    policy_path = args.repo_root / "docs/contracts/SCIENTIFIC_ISSUE_COMPLETION_GATES.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    text = args.text or ""
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8")
    if not text:
        print("PASS")
        print(json.dumps({"status": "PASS", "reason": "empty_text", "policy": policy["contract_id"]}))
        return 0
    findings = scan_text(text, policy)
    allowed = {int(x) for x in args.allow_close}
    blocked = [f for f in findings if f["issue"] not in allowed]
    payload = {
        "status": "PASS" if not blocked else "BLOCK_OR_REVIEW_CLOSE",
        "findings": findings,
        "blocked": blocked,
        "invariant": policy["invariant"],
        "version": VERSION,
    }
    print(payload["status"])
    print(json.dumps(payload, indent=2))
    return 0 if not blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
