#!/usr/bin/env python3
"""Audit one event-aligned nonnegative MC weight vector and report weighted ESS.

The raw generator carrier is outside this helper.  Once a source adapter has
produced one event-aligned nonnegative vector, normalized diagnostics delegate
to ``nonnegative_event_measure_v2`` so a common positive weight scale cannot
change authorisation merely through binary64 overflow/underflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.event_weight_population import (
    EVENT_WEIGHT_POPULATION_POLICY_ID,
    summarize_event_weight_population,
)

VERSION = "3.0.0"
POLICY = "MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED"
WEIGHT_CANDIDATES = ("PrimaryWeight", "weight", "EventWeight")
VALIDATION_FAILURES = {
    "P0_NO_WEIGHT_BRANCH",
    "P0_AMBIGUOUS_WEIGHT_BRANCHES",
    "P0_WEIGHT_SHAPE_INVALID",
    "P0_WEIGHT_LENGTH_MISMATCH",
    "P0_NONFINITE_WEIGHT",
    "P0_NEGATIVE_WEIGHT",
    "P0_EMPTY_WEIGHT_VECTOR",
    "P0_ZERO_TOTAL_WEIGHT",
}


def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _base_result(root: Path, tree: str) -> dict[str, Any]:
    return {
        "validator": "audit_mc_weight_usage",
        "validator_version": VERSION,
        "policy": POLICY,
        "population_policy_id": EVENT_WEIGHT_POPULATION_POLICY_ID,
        "input_path": str(root),
        "input_size_bytes": root.stat().st_size,
        "input_sha256": _sha256_file(root),
        "tree": tree,
    }


def _failure(base: dict[str, Any], status: str, **details: Any) -> dict[str, Any]:
    return {**base, "status": status, **details}


def _summarize_weight_vector(
    base: dict[str, Any],
    branch: str,
    weights: np.ndarray,
    n_entries: int,
) -> dict[str, Any]:
    if weights.ndim != 1:
        return _failure(
            base,
            "P0_WEIGHT_SHAPE_INVALID",
            branch=branch,
            weight_shape=list(weights.shape),
        )

    n_weights = int(weights.size)
    if n_weights != n_entries:
        return _failure(
            base,
            "P0_WEIGHT_LENGTH_MISMATCH",
            branch=branch,
            n_entries=n_entries,
            n_weights=n_weights,
        )
    if n_weights == 0:
        return _failure(
            base,
            "P0_EMPTY_WEIGHT_VECTOR",
            branch=branch,
            n_entries=n_entries,
            n_weights=0,
        )

    finite = np.isfinite(weights)
    n_nonfinite = int((~finite).sum())
    if n_nonfinite:
        return _failure(
            base,
            "P0_NONFINITE_WEIGHT",
            branch=branch,
            n_entries=n_entries,
            n_weights=n_weights,
            n_nonfinite=n_nonfinite,
        )

    negative = weights < 0.0
    n_negative = int(negative.sum())
    if n_negative:
        return _failure(
            base,
            "P0_NEGATIVE_WEIGHT",
            branch=branch,
            n_entries=n_entries,
            n_weights=n_weights,
            n_negative=n_negative,
            min=float(weights.min()),
        )

    if not np.any(weights > 0.0):
        return _failure(
            base,
            "P0_ZERO_TOTAL_WEIGHT",
            branch=branch,
            n_entries=n_entries,
            n_weights=n_weights,
            sum_w=0.0,
            sum_w2=0.0,
        )

    try:
        summary = summarize_event_weight_population(
            weights,
            expected_length=n_entries,
        )
    except DataContractError as exc:
        return _failure(
            base,
            "P0_WEIGHT_SHAPE_INVALID",
            branch=branch,
            n_entries=n_entries,
            n_weights=n_weights,
            reason=str(exc),
        )

    assert summary.effective_sample_size is not None
    assert summary.effective_sample_fraction is not None
    assert summary.max_weight_fraction is not None
    mean = summary.sum_w / n_weights if summary.sum_w is not None else None
    quantiles = {
        str(q): float(np.quantile(weights, q)) for q in (0.0, 0.01, 0.5, 0.99, 1.0)
    }
    return {
        **base,
        "status": "OK",
        "branch": branch,
        "n": n_weights,
        "n_entries": n_entries,
        "n_weights": n_weights,
        "n_zero": summary.n_zero,
        "n_positive": summary.n_positive,
        "weight_scale": summary.weight_scale,
        "sum_w_over_scale": summary.sum_w_over_scale,
        "sum_w2_over_scale2": summary.sum_w2_over_scale2,
        "sum_w": summary.sum_w,
        "sum_w2": summary.sum_w2,
        "ess": summary.effective_sample_size,
        "ess_fraction": summary.effective_sample_fraction,
        "mean": mean,
        "min": float(weights.min()),
        "max": float(weights.max()),
        "max_weight_fraction": summary.max_weight_fraction,
        "max_over_mean": float(n_weights * summary.max_weight_fraction),
        "quantiles": quantiles,
        "summation_method": summary.summation_method,
        "statistical_unit": summary.statistical_unit,
        "measure_defined": summary.measure_defined,
    }


def audit(root: Path, tree: str) -> dict[str, Any]:
    """Return a fail-closed weight-vector audit for ``tree`` inside ``root``."""
    base = _base_result(root, tree)
    try:
        import uproot

        with uproot.open(root) as root_file:
            root_tree = root_file[tree]
            keys = {key.split(";")[0] for key in root_tree.keys()}
            candidates = [name for name in WEIGHT_CANDIDATES if name in keys]
            if not candidates:
                return _failure(
                    base,
                    "P0_NO_WEIGHT_BRANCH",
                    tree_keys_sample=sorted(keys)[:100],
                )
            if len(candidates) != 1:
                return _failure(
                    base,
                    "P0_AMBIGUOUS_WEIGHT_BRANCHES",
                    weight_branch_candidates=candidates,
                )

            branch = candidates[0]
            raw = root_tree[branch].array(library="np")
            try:
                weights = np.asarray(raw, dtype=np.float64)
            except (TypeError, ValueError) as exc:
                return _failure(
                    base,
                    "P0_WEIGHT_SHAPE_INVALID",
                    branch=branch,
                    reason=f"{type(exc).__name__}: {exc}",
                )
            return _summarize_weight_vector(
                base,
                branch,
                weights,
                int(root_tree.num_entries),
            )
    except Exception as exc:
        return _failure(
            base,
            "INPUT_ERROR",
            error_type=type(exc).__name__,
            error=str(exc),
        )


def _publish_json(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate one event-aligned MC weight branch and report weighted ESS."
    )
    parser.add_argument("root", type=Path, help="ROOT file to inspect.")
    parser.add_argument(
        "--tree",
        default="hibeam",
        help="Tree name inside the ROOT file (default: hibeam).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON path for the weight-usage report.",
    )
    args = parser.parse_args(argv)

    if not args.root.is_file():
        result = {
            "validator": "audit_mc_weight_usage",
            "validator_version": VERSION,
            "policy": POLICY,
            "population_policy_id": EVENT_WEIGHT_POPULATION_POLICY_ID,
            "status": "INPUT_ERROR",
            "input_path": str(args.root),
            "error": "ROOT file does not exist",
        }
    elif args.root.resolve() == args.out.resolve():
        result = {
            "validator": "audit_mc_weight_usage",
            "validator_version": VERSION,
            "policy": POLICY,
            "population_policy_id": EVENT_WEIGHT_POPULATION_POLICY_ID,
            "status": "INPUT_OUTPUT_ALIAS",
            "input_path": str(args.root),
            "output_path": str(args.out),
        }
    else:
        result = audit(args.root, args.tree)
        _publish_json(args.out, result)

    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    if result["status"] == "OK":
        raise SystemExit(0)
    if result["status"] in VALIDATION_FAILURES:
        raise SystemExit(1)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
