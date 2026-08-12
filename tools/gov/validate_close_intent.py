#!/usr/bin/env python3
"""Deterministic close-intent validator for #1218 (no live GitHub API)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "1.0.0"
CLOSE_RE = re.compile(r"(?i)\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)")


def _has_autoclose(pr_text: str, issue: int) -> bool:
    for m in CLOSE_RE.finditer(pr_text or ""):
        if int(m.group(2)) != issue:
            continue
        start = max(0, m.start() - 20)
        window = pr_text[start : m.end() + 5]
        if re.search(rf"(?i)does not close\s+#{issue}", window):
            continue
        return True
    return False


def validate_manifest(manifest: dict) -> dict:
    errors: list[str] = []
    issue = int(manifest.get("issue_number", -1))
    disposition = str(manifest.get("disposition", ""))
    basis = str(manifest.get("basis", ""))
    leaves = list(manifest.get("unresolved_leaves") or [])
    successors = list(manifest.get("successors") or [])
    pr_text = str(manifest.get("pr_text") or "")
    expected_atom = manifest.get("expected_atom_id")
    atom_id = manifest.get("atom_id")

    if disposition != basis:
        errors.append("disposition_basis_mismatch")
    if expected_atom is not None and atom_id != expected_atom:
        errors.append("issue_atom_id_mismatch")

    if disposition == "ACCEPTANCE_COMPLETE":
        if leaves:
            errors.append("acceptance_complete_with_unresolved_leaves")
        if _has_autoclose(pr_text, issue) and leaves:
            errors.append("autoclose_with_unresolved")
    elif disposition == "EXPLICIT_SUCCESSOR_TRANSFER":
        if not leaves:
            errors.append("successor_transfer_without_unresolved_leaves")
        if not successors:
            errors.append("missing_successor_id")
        for s in successors:
            if not s.get("inherits_blockers", False) or not s.get("inherits_claim_state", False):
                errors.append("successor_omits_blocker_or_claim_consequence")
            if "issue_number" not in s:
                errors.append("missing_successor_id")
        if _has_autoclose(pr_text, issue) and not successors:
            errors.append("autoclose_without_complete_transfer")
    elif disposition == "SUPERSEDED":
        if not successors or "issue_number" not in successors[0]:
            errors.append("superseded_missing_successor")
        if manifest.get("emit_complete", False):
            errors.append("superseded_must_not_emit_complete")
        if _has_autoclose(pr_text, issue):
            # superseded may close, but only with exact successor present
            if not successors:
                errors.append("superseded_autoclose_without_successor")
    elif disposition == "PARTIAL_NO_CLOSE":
        if _has_autoclose(pr_text, issue):
            errors.append("partial_implementation_must_not_autoclose")
        if re.search(r"(?i)does not close", pr_text) and _has_autoclose(pr_text, issue):
            errors.append("pr_text_says_does_not_close_but_close_intent_closes")
    else:
        errors.append("unknown_disposition")

    # Universal: PR text conflict — explicit does-not-close plus autoclose keyword
    if re.search(rf"(?i)does not close\s+#{issue}", pr_text) and _has_autoclose(pr_text, issue):
        errors.append("pr_text_conflict_does_not_close_vs_autoclose")

    status = "PASS" if not errors else "BLOCK_OR_REVIEW_CLOSE"
    return {
        "status": status,
        "errors": errors,
        "issue_number": issue,
        "disposition": disposition,
        "version": VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--expect", choices=("PASS", "BLOCK_OR_REVIEW_CLOSE"), default=None)
    args = p.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = validate_manifest(manifest)
    print(result["status"])
    print(json.dumps(result, indent=2))
    if args.expect is not None:
        return 0 if result["status"] == args.expect else 2
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
