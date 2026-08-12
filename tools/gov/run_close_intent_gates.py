#!/usr/bin/env python3
"""Deterministic close-intent governance workflow for #1218 (no GitHub API).

Runs the hostile fixture matrix, merge-close keyword smoke checks, and optional
PR-body scanning. Intended for CI and local pre-merge review.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_merge_close_keywords import scan_text  # noqa: E402
from validate_close_intent import validate_manifest  # noqa: E402

VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "gov" / "close_intent"
FIXTURE_EXPECT = {
    "01_acceptance_complete_pass.json": "PASS",
    "02_unresolved_autoclose_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "03_successor_transfer_pass.json": "PASS",
    "04_missing_successor_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "05_successor_omits_blocker_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "06_superseded_pass.json": "PASS",
    "07_pr_text_conflict_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "08_issue_atom_mismatch_block.json": "BLOCK_OR_REVIEW_CLOSE",
    "09_partial_no_close_pass.json": "PASS",
}


def run_fixture_matrix(fixtures_dir: Path = FIXTURES) -> dict:
    results: list[dict] = []
    failures: list[str] = []
    for name, expected in sorted(FIXTURE_EXPECT.items()):
        manifest = json.loads((fixtures_dir / name).read_text(encoding="utf-8"))
        outcome = validate_manifest(manifest)
        ok = outcome["status"] == expected
        results.append(
            {
                "fixture": name,
                "expected": expected,
                "actual": outcome["status"],
                "ok": ok,
                "errors": outcome.get("errors", []),
            }
        )
        if not ok:
            failures.append(f"{name}: expected {expected}, got {outcome['status']}")
    return {
        "status": "PASS" if not failures else "BLOCK_OR_REVIEW_CLOSE",
        "fixtures": results,
        "failures": failures,
    }


def run_keyword_smoke() -> dict:
    safe = scan_text("Refs #1057. Does not close #1057.", {})
    blocked = scan_text("Closes #1057 after partial work.", {})
    failures: list[str] = []
    if safe:
        failures.append("safe_text_should_not_match")
    if not blocked:
        failures.append("blocked_text_should_match")
    return {
        "status": "PASS" if not failures else "BLOCK_OR_REVIEW_CLOSE",
        "failures": failures,
        "blocked_sample": blocked,
    }


def scan_pr_text(text: str) -> dict:
    findings = scan_text(text, {})
    return {
        "status": "PASS" if not findings else "BLOCK_OR_REVIEW_CLOSE",
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixtures-dir", type=Path, default=FIXTURES)
    p.add_argument("--pr-text-file", type=Path, default=None)
    p.add_argument("--pr-text", default=None)
    p.add_argument("--skip-pr-text", action="store_true")
    args = p.parse_args(argv)

    report = {
        "version": VERSION,
        "contract": "SCIENTIFIC_ISSUE_COMPLETION_GATES",
        "issue": "#1218",
        "fixture_matrix": run_fixture_matrix(args.fixtures_dir),
        "keyword_smoke": run_keyword_smoke(),
    }

    if not args.skip_pr_text:
        text = args.pr_text or ""
        if args.pr_text_file:
            text = args.pr_text_file.read_text(encoding="utf-8")
        if text.strip():
            report["pr_text_scan"] = scan_pr_text(text)

    status = "PASS"
    for section in ("fixture_matrix", "keyword_smoke", "pr_text_scan"):
        if section in report and report[section]["status"] != "PASS":
            status = "BLOCK_OR_REVIEW_CLOSE"

    report["status"] = status
    print(status)
    print(json.dumps(report, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
