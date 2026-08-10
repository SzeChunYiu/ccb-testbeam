#!/usr/bin/env python3
"""Deterministic audit of the current CM cross-section sampler discretization.

This is a numerical/source-contract audit, not detector validation.  It compares
what ``BuildSigmaCDF`` integrates (trapezoids between p_i = sigma_i sin(theta_i))
with what ``SampleThetaCM`` actually samples (uniform theta inside each CDF
interval because it linearly interpolates theta against cumulative mass).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"


def _read_table(path: Path) -> tuple[bytes, list[float], list[float]]:
    raw = path.read_bytes()
    angles: list[float] = []
    sigma: list[float] = []
    for line_number, line in enumerate(raw.decode("ascii").splitlines(), start=1):
        fields = line.split()
        if len(fields) != 3:
            raise ValueError(f"line {line_number}: expected exactly three columns")
        angle_deg, cross_section, _stat_uncertainty = map(float, fields)
        angles.append(math.radians(angle_deg))
        sigma.append(cross_section)
    if len(angles) < 2:
        raise ValueError("need at least two cross-section rows")
    if any(b <= a for a, b in zip(angles, angles[1:])):
        raise ValueError("CM angles must be strictly increasing")
    return raw, angles, sigma


def audit_sampler(path: Path) -> dict[str, object]:
    raw, angles, sigma = _read_table(path)
    theta = [0.0, *angles, math.pi]
    node_pdf = [0.0, *[s * math.sin(t) for s, t in zip(sigma, angles)], 0.0]

    interval_mass: list[float] = []
    for left, right, p_left, p_right in zip(theta, theta[1:], node_pdf, node_pdf[1:]):
        interval_mass.append(0.5 * (p_left + p_right) * (right - left))
    norm = math.fsum(interval_mass)
    if not norm > 0.0:
        raise ValueError("non-positive sampler normalization")

    interval_probability = [mass / norm for mass in interval_mass]

    # BuildSigmaCDF treats each interval mass as the trapezoid integral of a
    # linearly varying node PDF. SampleThetaCM then interpolates theta linearly
    # in cumulative probability, which instead makes the generated density
    # constant inside that interval.  For one interval of width d with node
    # values a,b, the CDF difference is
    #   Delta(x) = (b-a) x (1-x/d) / (2 Z),
    # whose maximum absolute value occurs at x=d/2 and equals
    #   |b-a| d / (8 Z).
    cdf_deviations = [
        abs(p_right - p_left) * (right - left) / (8.0 * norm)
        for left, right, p_left, p_right in zip(theta, theta[1:], node_pdf, node_pdf[1:])
    ]
    worst_index = max(range(len(cdf_deviations)), key=cdf_deviations.__getitem__)
    worst_midpoint = 0.5 * (theta[worst_index] + theta[worst_index + 1])

    return {
        "schema_version": "ccb_sigma_cm_sampler_contract_v1",
        "input": {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "rows": len(angles),
            "support_theta_cm_deg": [math.degrees(angles[0]), math.degrees(angles[-1])],
        },
        "current_algorithm": {
            "cdf_construction": "trapezoid_integral_of_node_pdf_sigma_times_sin_theta",
            "inverse": "linear_theta_interpolation_within_each_cdf_interval",
            "resulting_within_interval_density": "piecewise_constant_interval_average",
        },
        "trapezoid_normalization_mb_per_sr_rad": norm,
        "probability_below_measured_support": interval_probability[0],
        "probability_above_measured_support": interval_probability[-1],
        "probability_outside_measured_support": interval_probability[0] + interval_probability[-1],
        "max_cdf_deviation_vs_linear_node_pdf": cdf_deviations[worst_index],
        "max_cdf_deviation_interval_index": worst_index,
        "max_cdf_deviation_theta_cm_deg": math.degrees(worst_midpoint),
        "interpretation": (
            "The current inverse-CDF implementation does not sample the linearly varying node PDF "
            "whose trapezoid integrals define its CDF; it samples a piecewise-constant density with "
            "the same interval masses. The outside-support probability is model extrapolation, not "
            "measured 190 MeV cross-section support."
        ),
        "scientific_boundary": (
            "Deterministic numerical self-consistency result only. It does not choose the physically "
            "correct extrapolation below 26.49 deg or above 169.78 deg, propagate cross-section "
            "systematics, or validate detector-level predictions."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit_sampler(args.table)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
