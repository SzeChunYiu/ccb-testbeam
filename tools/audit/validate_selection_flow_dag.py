#!/usr/bin/env python3
"""Validate selection-flow DAG contract and report artifact hygiene (#970)."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VERSION = "1.0.0"


def validate(repo: Path, report_globs: list[str] | None = None) -> list[str]:
    dag_path = repo / "docs/contracts/SELECTION_FLOW_DAG.json"
    dag = json.loads(dag_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    nodes = dag.get("nodes") or []
    ids = [n["node_id"] for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("DUPLICATE_NODE_ID")
    idset = set(ids)
    for n in nodes:
        parent = n.get("parent")
        if parent is not None and parent not in idset:
            errors.append(f"MISSING_PARENT:{n['node_id']}:{parent}")
    for field in dag.get("required_table_fields", []):
        if not isinstance(field, str) or not field:
            errors.append(f"EMPTY_REQUIRED_FIELD_NAME:{field!r}")
    # Forbidden leaked pandas bound-method text in timing-related reports
    patterns = [re.compile(re.escape(p)) for p in dag.get("forbidden_report_artifacts", [])]
    globs = report_globs or [
        "docs/academic_chapters/04_timing_analysis.md",
        "reports/studies/**/*.md",
        "reports/**/*timing*.md",
    ]
    files: list[Path] = []
    for g in globs:
        files.extend(repo.glob(g))
    for path in files:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in patterns:
            if pat.search(text):
                errors.append(f"LEAKED_BOUND_METHOD:{path.relative_to(repo)}")
    # Known inconsistency must remain marked OPEN until regen
    for inc in dag.get("known_inconsistencies", []):
        if inc.get("id") == "TIMING-NOTE-TAB3-TAB4" and inc.get("status") != "OPEN":
            errors.append("PREMATURE_TIMING_NOTE_INCONSISTENCY_CLOSURE")
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
