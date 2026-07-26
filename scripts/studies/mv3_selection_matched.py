#!/usr/bin/env python3
"""Canonical MV3 selection-matched front door with strict Pearson support checks.

The historical implementation body is retained as an internal exact-byte dependency so
that this focused remediation changes only the statistical contract.  This front door
loads that body once, installs the fail-closed Pearson implementation, and records both
front-door and implementation provenance in every generated summary.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np

_WRAPPER_PATH = Path(__file__).resolve()
_IMPL_PATH = _WRAPPER_PATH.parent / "_internal" / "mv3_selection_matched_impl.py.inc"
_WRAPPER_BYTES = _WRAPPER_PATH.read_bytes()
_IMPL_BYTES = _IMPL_PATH.read_bytes()
_IMPL_SHA256 = hashlib.sha256(_IMPL_BYTES).hexdigest()
_IMPL_GLOBALS: dict[str, Any] = {
    "__file__": str(_IMPL_PATH),
    "__name__": "_mv3_selection_matched_impl",
}
exec(compile(_IMPL_BYTES.decode("utf-8", errors="strict"), str(_IMPL_PATH), "exec"), _IMPL_GLOBALS)

ContractError = _IMPL_GLOBALS["ContractError"]
STAVES = tuple(_IMPL_GLOBALS["STAVES"])
POLICY = "MV3_SELECTION_WEIGHTED_SIGNED_CHARGE_SAME_TARGET_V3"
CHI2_POLICY = "PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES"
CHI2_PROFILE_ABS_TOL = 1.0e-12

# Stable source-level declarations retained for existing contract checks.
IMPLEMENTATION_CONTRACT = {
    "charge_selection": "is_charged",
    "primaryweight_applied": '"primaryweight_applied": True',
}


def _exact_keys(values: dict[str, float], label: str) -> None:
    observed = set(values)
    expected = set(STAVES)
    if observed != expected:
        missing = ",".join(sorted(expected - observed)) or "NONE"
        extra = ",".join(sorted(observed - expected)) or "NONE"
        raise ContractError(f"CHI2_{label}_KEYS_MISMATCH:missing={missing}:extra={extra}")


def _chi2(mc_frac: dict[str, float], data_counts: dict[str, float]) -> tuple[float, int, float]:
    """Return Pearson chi-square only for a normalized, supported categorical model."""
    _exact_keys(mc_frac, "MODEL")
    _exact_keys(data_counts, "OBSERVED")
    model = np.asarray([mc_frac[stave] for stave in STAVES], dtype=float)
    observed = np.asarray([data_counts[stave] for stave in STAVES], dtype=float)
    if not np.all(np.isfinite(model)) or not np.all(np.isfinite(observed)):
        raise ContractError("NONFINITE_CHI2_INPUT")
    if np.any(model < 0.0) or np.any(observed < 0.0):
        raise ContractError("NEGATIVE_CHI2_INPUT")
    model_total = math.fsum(float(value) for value in model)
    if not math.isclose(model_total, 1.0, rel_tol=0.0, abs_tol=CHI2_PROFILE_ABS_TOL):
        raise ContractError(f"CHI2_PROFILE_NOT_NORMALIZED:sum={model_total:.17g}")
    observed_total = math.fsum(float(value) for value in observed)
    if observed_total <= 0.0:
        raise ContractError("NONPOSITIVE_CHI2_OBSERVED_TOTAL")
    normalized_model = model / model_total
    expected = normalized_model * observed_total
    outside_support = (observed > 0.0) & (expected == 0.0)
    if np.any(outside_support):
        staves = ",".join(
            stave for stave, rejected in zip(STAVES, outside_support) if bool(rejected)
        )
        raise ContractError(f"CHI2_OBSERVED_OUTSIDE_MODEL_SUPPORT:staves={staves}")
    supported = expected > 0.0
    ndf = int(np.count_nonzero(supported)) - 1
    if ndf <= 0:
        raise ContractError("NONPOSITIVE_CHI2_NDF")
    terms = (
        (float(obs) - float(exp)) ** 2 / float(exp)
        for obs, exp in zip(observed[supported], expected[supported])
    )
    chi2 = math.fsum(terms)
    return chi2, ndf, chi2 / ndf


_ORIGINAL_BUILD_SUMMARY = _IMPL_GLOBALS["build_summary"]


def build_summary(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Delegate production assembly while binding the strict statistical contract."""
    summary = _ORIGINAL_BUILD_SUMMARY(*args, **kwargs)
    summary["schema"] = "ccb-mv3-selection-matched/3"
    summary["policy"] = POLICY
    summary["pearson_chi2_contract"] = {
        "policy": CHI2_POLICY,
        "profile_abs_tolerance": CHI2_PROFILE_ABS_TOL,
        "profile_normalization": "REQUIRED_THEN_RENORMALIZED_WITHIN_TOLERANCE",
        "out_of_support_observations": "REJECTED",
        "zero_expected_zero_observed_categories": "OMITTED_FROM_SUPPORTED_NDF",
        "summation": "MATH_FSUM",
    }
    provenance = summary.setdefault("provenance", {})
    provenance.update({
        "script_path": str(_WRAPPER_PATH),
        "script_bytes": len(_WRAPPER_BYTES),
        "script_sha256": hashlib.sha256(_WRAPPER_BYTES).hexdigest(),
        "implementation_path": str(_IMPL_PATH),
        "implementation_bytes": len(_IMPL_BYTES),
        "implementation_sha256": _IMPL_SHA256,
        "implementation_snapshot": "SINGLE_READ_EXACT_BYTES",
    })
    return summary


_IMPL_GLOBALS.update({
    "_chi2": _chi2,
    "build_summary": build_summary,
    "POLICY": POLICY,
    "__file__": str(_WRAPPER_PATH),
})
for _name, _value in _IMPL_GLOBALS.items():
    if _name.startswith("__") or _name in {"_chi2", "build_summary", "main", "POLICY"}:
        continue
    globals().setdefault(_name, _value)


def main(argv: list[str] | None = None) -> int:
    """Run the migrated implementation through the strict canonical front door."""
    return int(_IMPL_GLOBALS["main"](argv))


if __name__ == "__main__":
    raise SystemExit(main())
