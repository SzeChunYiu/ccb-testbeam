#!/usr/bin/env python3
"""Validate mutually exclusive run-role groups in a study configuration.

The validator exists because set-based run collection plus a last-write-wins
lookup can hide calibration/analysis leakage.  It is deliberately independent
of the S00 producer so it can be used in CI on every YAML/JSON study config.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence


def validate_exclusive_run_groups(
    run_groups: Mapping[str, Sequence[int]],
    *,
    exclusive_groups: Sequence[str] | None = None,
) -> dict:
    if not isinstance(run_groups, Mapping) or not run_groups:
        raise ValueError("run_groups must be a non-empty mapping")

    selected = list(exclusive_groups) if exclusive_groups is not None else list(run_groups)
    missing = [name for name in selected if name not in run_groups]
    if missing:
        raise ValueError(f"exclusive group(s) not present in run_groups: {missing}")

    duplicate_within: dict[str, list[int]] = {}
    assignments: dict[int, list[str]] = defaultdict(list)
    normalized: dict[str, list[int]] = {}

    for group in selected:
        raw = list(run_groups[group])
        try:
            values = [int(x) for x in raw]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"group {group!r} contains a non-integer run") from exc
        if any(run < 0 for run in values):
            raise ValueError(f"group {group!r} contains a negative run number")
        counts = Counter(values)
        dup = sorted(run for run, count in counts.items() if count > 1)
        if dup:
            duplicate_within[group] = dup
        normalized[group] = values
        for run in sorted(set(values)):
            assignments[run].append(group)

    overlaps = {
        str(run): groups
        for run, groups in sorted(assignments.items())
        if len(groups) > 1
    }
    passed = not duplicate_within and not overlaps
    return {
        "status": "PASS" if passed else "FAIL",
        "exclusive_groups": selected,
        "normalized_groups": normalized,
        "duplicate_within_group": duplicate_within,
        "overlapping_run_roles": overlaps,
        "n_unique_runs": len(assignments),
        "pass": passed,
    }


def _load(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise SystemExit("PyYAML is required for YAML input") from exc
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("configuration root must be a mapping")
        return data
    raise ValueError(f"unsupported config format: {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("config", type=Path)
    ap.add_argument(
        "--groups",
        nargs="+",
        help="mutually exclusive run-group names; defaults to every run_groups entry",
    )
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        cfg = _load(args.config)
        if "run_groups" not in cfg:
            raise ValueError("configuration has no run_groups mapping")
        result = validate_exclusive_run_groups(cfg["run_groups"], exclusive_groups=args.groups)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "ERROR", "pass": False, "error": str(exc)}

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
