#!/usr/bin/env python3
"""Validate paired multi-seed nuisance-sweep design (#984)."""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from pathlib import Path


def _data_rows(text: str) -> list[dict[str, str]]:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(line)
    if not lines:
        return []
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


def validate_csv(path: Path) -> list[str]:
    rows = _data_rows(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if not rows:
        return [f"{path.name}:empty"]
    by_seed: dict[str, set[str]] = defaultdict(set)
    seeds = set()
    for row in rows:
        seed = row.get("seed", "")
        label = row.get("label", "")
        seeds.add(seed)
        # value token is between first '=' and '__rep='
        if "__rep=" not in label:
            errors.append(f"{path.name}:label_missing_rep:{label}")
            continue
        value_token = label.split("__rep=", 1)[0]
        by_seed[seed].add(value_token)
        if label.split("__rep=", 1)[1] != seed:
            errors.append(f"{path.name}:rep_seed_mismatch:{label}")
    if len(seeds) < 2:
        errors.append(f"{path.name}:need_ge_2_replicate_seeds")
    # CRN: every seed must cover the same set of values
    value_sets = list(by_seed.values())
    if value_sets:
        ref = value_sets[0]
        for seed, vs in by_seed.items():
            if vs != ref:
                errors.append(f"{path.name}:seed_{seed}_value_set_mismatch")
    # Anti-pattern: unique seed per value (old design) within a single replicate
    # is already ruled out by requiring identical value sets across seeds with
    # len(values) reused; additionally ensure each seed appears more than once
    # when there are multiple values.
    n_values = len(next(iter(value_sets))) if value_sets else 0
    if n_values >= 2:
        for seed, vs in by_seed.items():
            if len(vs) < 2:
                errors.append(f"{path.name}:seed_{seed}_not_paired_across_values")
    return errors


def validate(repo: Path) -> dict:
    grids = repo / "geant4/single_stave/slurm/grids"
    errors: list[str] = []
    design_path = grids / "PAIRED_SEED_DESIGN.json"
    if not design_path.is_file():
        errors.append("missing_PAIRED_SEED_DESIGN.json")
    else:
        design = json.loads(design_path.read_text(encoding="utf-8"))
        if design.get("design") != "common_random_number":
            errors.append("design_not_CRN")
        if len(design.get("seed_replicates", [])) < 2:
            errors.append("design_need_ge_2_seeds")
        for row in design.get("rows", []):
            for key in ("knob", "value_str", "replicate_seed"):
                if key not in row:
                    errors.append(f"design_row_missing_{key}")
                    break
    for csv_path in sorted(grids.glob("points_*.csv")):
        errors.extend(validate_csv(csv_path))
    return {"status": "PASS" if not errors else "FAIL", "errors": errors}


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
