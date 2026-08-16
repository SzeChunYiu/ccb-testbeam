#!/usr/bin/env python3
"""Deterministic falsifiers for the signed-event-weight numerical contract.

This is a research utility, not an authorising production validator.  It
compares the legacy raw-moment/cancellation conventions with a max-absolute
scaled signed-measure decomposition and constructs a signed-CDF counterexample.

No detector data or Monte Carlo generation is performed.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterable

import numpy as np

RESEARCH_ID = "ARU-MC-WEIGHT-SIGNED-001"
METHOD_ID = "max_abs_scaled_signed_diagnostic_v1"
SEED = None


@dataclass(frozen=True)
class SignedDiagnostic:
    n: int
    n_positive: int
    n_negative: int
    n_zero: int
    weight_scale: float
    signed_mass_over_scale: float
    total_variation_over_scale: float
    squared_mass_over_scale2: float
    signed_ess_like: float
    absolute_ess: float
    max_abs_weight_fraction: float
    cancellation_severity: float
    signed_mass_orientation: int


def _finite_vector(weights: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(weights), dtype=np.float64)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError("weights must be a nonempty one-dimensional vector")
    if not np.isfinite(arr).all():
        raise ValueError("weights must be finite")
    if not np.any(arr != 0.0):
        raise ValueError("weights must contain nonzero signed mass")
    return arr


def stable_signed_diagnostic(weights: Iterable[float]) -> SignedDiagnostic:
    """Return scale-stable dimensionless diagnostics for one signed vector."""
    arr = _finite_vector(weights)
    scale = float(np.max(np.abs(arr)))
    scaled = arr / scale
    signed_mass = math.fsum(float(v) for v in scaled)
    total_variation = math.fsum(abs(float(v)) for v in scaled)
    squared_mass = math.fsum(float(v) * float(v) for v in scaled)
    if total_variation <= 0.0 or squared_mass <= 0.0:
        raise ValueError("invalid signed-measure moments")

    cancellation = 1.0 - abs(signed_mass) / total_variation
    cancellation = min(1.0, max(0.0, float(cancellation)))
    orientation = 1 if signed_mass > 0.0 else -1 if signed_mass < 0.0 else 0

    return SignedDiagnostic(
        n=int(arr.size),
        n_positive=int(np.count_nonzero(arr > 0.0)),
        n_negative=int(np.count_nonzero(arr < 0.0)),
        n_zero=int(np.count_nonzero(arr == 0.0)),
        weight_scale=scale,
        signed_mass_over_scale=float(signed_mass),
        total_variation_over_scale=float(total_variation),
        squared_mass_over_scale2=float(squared_mass),
        signed_ess_like=float(signed_mass * signed_mass / squared_mass),
        absolute_ess=float(total_variation * total_variation / squared_mass),
        max_abs_weight_fraction=float(1.0 / total_variation),
        cancellation_severity=cancellation,
        signed_mass_orientation=orientation,
    )


def legacy_raw_diagnostic(weights: Iterable[float]) -> dict[str, float | str | bool]:
    """Reproduce the pre-#1174 raw-moment conventions for comparison."""
    arr = _finite_vector(weights)

    def _legacy_sum(values):
        try:
            total = math.fsum(values)
        except OverflowError as exc:
            return f"OVERFLOW:{type(exc).__name__}"
        return float(total) if math.isfinite(total) else "NONFINITE"

    sum_w = _legacy_sum(float(v) for v in arr)
    sum_abs_w = _legacy_sum(abs(float(v)) for v in arr)
    sum_w2 = _legacy_sum(float(v) * float(v) for v in arr)

    numeric_sum = sum_w if isinstance(sum_w, float) else None
    numeric_abs = sum_abs_w if isinstance(sum_abs_w, float) else None
    legacy_cancellation = (
        1.0 - numeric_sum / numeric_abs
        if numeric_sum is not None and numeric_abs not in (None, 0.0)
        else None
    )
    n_positive = int(np.count_nonzero(arr > 0.0))
    legacy_all_zero_predicate = bool(n_positive == 0 and arr.size > 0)
    return {
        "sum_w": sum_w,
        "sum_abs_w": sum_abs_w,
        "sum_w2": sum_w2,
        "legacy_cancellation_fraction": legacy_cancellation,
        "legacy_all_zero_predicate": legacy_all_zero_predicate,
    }


def signed_cdf_counterexample() -> dict[str, object]:
    """Show why a signed measure cannot be reused as a probability ECDF."""
    x = np.array([0.0, 1.0, 2.0])
    w = np.array([1.0, -2.0, 2.0])
    total = math.fsum(float(v) for v in w)
    cumulative = np.cumsum(w, dtype=np.float64) / total
    monotone = bool(np.all(np.diff(cumulative) >= 0.0))
    inside_unit_interval = bool(np.all((cumulative >= 0.0) & (cumulative <= 1.0)))
    return {
        "x": x.tolist(),
        "weights": w.tolist(),
        "signed_total": total,
        "cumulative_normalized_signed_mass": cumulative.tolist(),
        "monotone_non_decreasing": monotone,
        "inside_unit_interval": inside_unit_interval,
    }


def exact_small_fixture_oracle() -> dict[str, object]:
    """Exact rational oracle for [10, -9, 1]."""
    s = Fraction(2, 1)
    a = Fraction(20, 1)
    q = Fraction(182, 1)
    return {
        "weights": [10, -9, 1],
        "signed_mass": str(s),
        "total_variation": str(a),
        "squared_mass": str(q),
        "signed_ess_like": str(s * s / q),
        "absolute_ess": str(a * a / q),
        "max_abs_weight_fraction": str(Fraction(10, 20)),
        "cancellation_severity": str(1 - abs(s) / a),
    }


def run_research() -> dict[str, object]:
    tiny = float(np.nextafter(0.0, 1.0))
    fixtures = {
        "mixed_base": [10.0, -9.0, 1.0],
        "mixed_scaled_up": [1e300, -9e299, 1e299],
        "mixed_scaled_down": [1e-300, -9e-301, 1e-301],
        "all_negative": [-1.0, -2.0],
        "exact_cancellation": [1.0, -1.0],
        "binary64_large": [1e308, -9e307, 1e307],
        "binary64_subnormal": [tiny, -tiny, tiny],
    }
    diagnostics = {
        name: {
            "stable": asdict(stable_signed_diagnostic(values)),
            "legacy": legacy_raw_diagnostic(values),
        }
        for name, values in fixtures.items()
    }

    base = diagnostics["mixed_base"]["stable"]
    scale_checks = {}
    for name in ("mixed_scaled_up", "mixed_scaled_down"):
        candidate = diagnostics[name]["stable"]
        scale_checks[name] = {
            key: candidate[key] == base[key]
            for key in (
                "signed_ess_like",
                "absolute_ess",
                "max_abs_weight_fraction",
                "cancellation_severity",
                "signed_mass_orientation",
            )
        }

    return {
        "research_id": RESEARCH_ID,
        "method_id": METHOD_ID,
        "seed": SEED,
        "scientific_status": "NONAUTHORISING_NUMERICAL_RESEARCH",
        "exact_oracle": exact_small_fixture_oracle(),
        "diagnostics": diagnostics,
        "positive_common_scale_invariance_checks": scale_checks,
        "signed_cdf_counterexample": signed_cdf_counterexample(),
        "conclusions": [
            "raw-unit signed second moments can overflow although dimensionless signed diagnostics remain defined",
            "legacy 1-S/A is not a bounded cancellation fraction for all-negative orientation",
            "cancellation severity 1-|S|/A and signed-mass orientation are distinct diagnostics",
            "the legacy n_positive==0 all-zero predicate misclassifies all-negative vectors",
            "signed normalized cumulative mass is not a probability ECDF",
            "no production CCB generator signed-weight use is established by these fixtures",
        ],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    result = run_research()
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
