#!/usr/bin/env python3
"""Deterministic audit of the CM cross-section sampler contract.

This is a numerical/source-contract audit, not detector validation. It retains
an exact description of the legacy direct-CDF implementation and evaluates the
replacement reference law used by the source patch:

* interpolation: ``linear_node_pdf_exact_inverse_v1``;
* support: ``measured_table_support_truncate_v1``.

The replacement treats the tabulated node values
``p_i = sigma_i * sin(theta_i)`` as a linearly interpolated polar-angle density
on the measured Table-VI support only. Within each interval it analytically
inverts the quadratic accumulated mass. Truncating at measured support is an
explicit conservative reference-model choice, not evidence that the physical
cross section is zero outside the published angular range.

Source-module provenance (#1178): the tracked Geant4 primary generator in
``geant4/src_patch/ScatteringGenerator.cc`` is bound to exactly this reference
law. ``SampleThetaCM`` draws theta_cm from the same measured-support node PDF
using the same analytic quadratic interval-mass inverse, guarded by
``std::isfinite`` and normalized by a positive common ``densityScale``, and it
declares the same ``INTERPOLATION_MODE`` / ``SUPPORT_MODE`` strings --- keeping
the compiled sampler contract identical to the audited numerical reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
INTERPOLATION_MODE = "linear_node_pdf_exact_inverse_v1"
SUPPORT_MODE = "measured_table_support_truncate_v1"


def _read_table(path: Path) -> tuple[bytes, list[float], list[float], list[float]]:
    raw = path.read_bytes()
    angles: list[float] = []
    sigma: list[float] = []
    stat_uncertainty: list[float] = []
    for line_number, line in enumerate(raw.decode("ascii").splitlines(), start=1):
        fields = line.split()
        if len(fields) != 3:
            raise ValueError(f"line {line_number}: expected exactly three columns")
        angle_deg, cross_section, _stat_uncertainty = map(float, fields)
        if not math.isfinite(angle_deg) or not math.isfinite(cross_section):
            raise ValueError(f"line {line_number}: non-finite table value")
        if cross_section < 0.0:
            raise ValueError(f"line {line_number}: negative cross section")
        if not math.isfinite(_stat_uncertainty):
            raise ValueError(f"line {line_number}: non-finite statistical uncertainty")
        if _stat_uncertainty < 0.0:
            raise ValueError(f"line {line_number}: negative statistical uncertainty")
        angles.append(math.radians(angle_deg))
        sigma.append(cross_section)
        stat_uncertainty.append(_stat_uncertainty)
    if len(angles) < 2:
        raise ValueError("need at least two cross-section rows")
    if any(b <= a for a, b in zip(angles, angles[1:])):
        raise ValueError("CM angles must be strictly increasing")
    return raw, angles, sigma, stat_uncertainty


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def inverse_linear_pdf_fraction(p_left: float, p_right: float, fraction: float) -> float:
    """Invert a linearly varying nonnegative PDF on one unit-width interval.

    ``fraction`` is the desired fraction of this interval's total trapezoid
    mass. The returned value is ``x / interval_width`` in ``[0, 1]``.

    For ``p(t)=a+(b-a)t``, the accumulated mass is
    ``I(t)=a t + 0.5 (b-a) t^2``. Both endpoint densities are first divided by
    their positive maximum. The common scaling cancels from the target law and
    prevents overflow/underflow in the quadratic products.
    """

    a = float(p_left)
    b = float(p_right)
    f = float(fraction)
    if not all(math.isfinite(v) for v in (a, b, f)):
        raise ValueError("inverse inputs must be finite")
    if a < 0.0 or b < 0.0:
        raise ValueError("linear PDF endpoints must be nonnegative")
    if f < 0.0 or f > 1.0:
        raise ValueError("interval mass fraction must lie in [0,1]")
    if f == 0.0:
        return 0.0
    if f == 1.0:
        return 1.0

    density_scale = max(a, b)
    if not density_scale > 0.0:
        raise ValueError("cannot invert a zero-mass interval")
    a /= density_scale
    b /= density_scale

    discriminant = a * a + (b - a) * (a + b) * f
    tolerance = 64.0 * 2.220446049250313e-16  # math.ulp(1.0) — Python 3.8 compat
    if discriminant < -tolerance:
        raise ArithmeticError("negative inverse-CDF discriminant")
    root = math.sqrt(max(discriminant, 0.0))
    denominator = a + root
    if not denominator > 0.0:
        return math.sqrt(f)
    t = f * (a + b) / denominator
    return min(1.0, max(0.0, t))


def _legacy_audit(angles: list[float], sigma: list[float]) -> dict[str, object]:
    theta = [0.0, *angles, math.pi]
    node_pdf = [0.0, *[s * math.sin(t) for s, t in zip(sigma, angles)], 0.0]
    interval_mass = [
        0.5 * (p_left + p_right) * (right - left)
        for left, right, p_left, p_right in zip(theta, theta[1:], node_pdf, node_pdf[1:])
    ]
    norm = math.fsum(interval_mass)
    if not norm > 0.0:
        raise ValueError("non-positive legacy sampler normalization")
    interval_probability = [mass / norm for mass in interval_mass]
    cdf_deviations = [
        abs(p_right - p_left) * (right - left) / (8.0 * norm)
        for left, right, p_left, p_right in zip(theta, theta[1:], node_pdf, node_pdf[1:])
    ]
    worst_index = max(range(len(cdf_deviations)), key=cdf_deviations.__getitem__)
    worst_midpoint = 0.5 * (theta[worst_index] + theta[worst_index + 1])
    return {
        "cdf_construction": "trapezoid_integral_of_node_pdf_sigma_times_sin_theta",
        "inverse": "linear_theta_interpolation_within_each_cdf_interval",
        "resulting_within_interval_density": "piecewise_constant_interval_average",
        "normalization": norm,
        "probability_below_measured_support": interval_probability[0],
        "probability_above_measured_support": interval_probability[-1],
        "probability_outside_measured_support": interval_probability[0] + interval_probability[-1],
        "max_cdf_deviation_vs_linear_node_pdf": cdf_deviations[worst_index],
        "max_cdf_deviation_interval_index": worst_index,
        "max_cdf_deviation_theta_cm_deg": math.degrees(worst_midpoint),
    }


def _exact_reference_audit(angles: list[float], sigma: list[float]) -> dict[str, object]:
    theta = list(angles)
    node_pdf = [s * math.sin(t) for s, t in zip(sigma, theta)]
    interval_mass = [
        0.5 * (a + b) * (right - left)
        for left, right, a, b in zip(theta, theta[1:], node_pdf, node_pdf[1:])
    ]
    norm = math.fsum(interval_mass)
    if not norm > 0.0:
        raise ValueError("non-positive exact-reference normalization")

    probe_fractions = (0.0, 0.001, 0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999, 1.0)
    max_mass_fraction_error = 0.0
    worst: dict[str, float | int] = {
        "interval_index": 0,
        "requested_fraction": 0.0,
        "recovered_fraction": 0.0,
    }
    for interval_index, (a, b) in enumerate(zip(node_pdf, node_pdf[1:])):
        interval_total = 0.5 * (a + b)
        if not interval_total > 0.0:
            continue
        for requested in probe_fractions:
            t = inverse_linear_pdf_fraction(a, b, requested)
            recovered = (a * t + 0.5 * (b - a) * t * t) / interval_total
            error = abs(recovered - requested)
            if error > max_mass_fraction_error:
                max_mass_fraction_error = error
                worst = {
                    "interval_index": interval_index,
                    "requested_fraction": requested,
                    "recovered_fraction": recovered,
                }

    return {
        "cross_section_interpolation_mode": INTERPOLATION_MODE,
        "cross_section_support_mode": SUPPORT_MODE,
        "cdf_construction": "trapezoid_integral_of_linear_node_pdf_sigma_times_sin_theta",
        "inverse": "analytic_quadratic_interval_mass_inverse",
        "normalization": norm,
        "support_theta_cm_deg": [math.degrees(theta[0]), math.degrees(theta[-1])],
        "probability_outside_measured_support": 0.0,
        "inverse_probe_fractions": list(probe_fractions),
        "max_inverse_interval_mass_fraction_error": max_mass_fraction_error,
        "worst_inverse_probe": worst,
        "positive_common_density_scaling_invariant": True,
        "support_policy_interpretation": (
            "The nominal reference distribution is conditional on the measured Table-VI angular "
            "support. This is an explicit conservative model choice, not evidence that the physical "
            "cross section vanishes outside the measured range. Extrapolation/support sensitivity "
            "remains a separate source-model uncertainty."
        ),
    }


def _statistical_uncertainty_audit(
    angles: list[float], sigma: list[float], stat_uncertainty: list[float]
) -> dict[str, object]:
    """Audit the statistical uncertainty column of the cross-section table.

    The third column of the table records the per-node statistical uncertainty
    on sigma (mb/sr). The sampler currently uses only the nominal sigma values;
    this audit quantifies the uncertainty that is not yet propagated.
    """
    n = len(angles)
    if n != len(sigma) or n != len(stat_uncertainty):
        raise ValueError("angles, sigma, stat_uncertainty length mismatch")
    fractional = [u / s for u, s in zip(stat_uncertainty, sigma)]
    return {
        "column": "stat_uncertainty (column 3, mb/sr)",
        "nodes": n,
        "min_fractional": min(fractional),
        "max_fractional": max(fractional),
        "mean_fractional": math.fsum(fractional) / n,
        "median_fractional": sorted(fractional)[n // 2],
        "propagation_status": "NOT_PROPAGATED_ISSUE_1179",
        "note": (
            "Statistical uncertainties are tabulated but not propagated by the sampler. "
            "The nominal reference uses only sigma (column 2). Propagation is tracked "
            "as #1179 in the issue campaign ledger."
        ),
    }


def _systematic_uncertainty_envelope_audit(
    angles: list[float], sigma: list[float]
) -> dict[str, object]:
    """Audit a systematic uncertainty envelope for the cross-section.

    The issue #1179 specifies a ±20% systematic envelope at 90° tapering to
    ±10% at the edges of the measured support (26.49–169.78 deg). This audit
    reports the envelope fractional value at each node and the implied
    sigma +- envelope range.
    """
    theta_min = angles[0]
    theta_max = angles[-1]
    envelope: list[dict[str, float]] = []
    for theta_rad, s in zip(angles, sigma):
        normalized = (theta_rad - theta_min) / (theta_max - theta_min)
        fractional = 0.10 + 0.10 * math.sin(math.pi * normalized)
        envelope.append({
            "theta_cm_deg": math.degrees(theta_rad),
            "sigma_mb_per_sr": s,
            "fractional_systematic": fractional,
            "sigma_plus_envelope": s * (1.0 + fractional),
            "sigma_minus_envelope": s * (1.0 - fractional),
        })
    return {
        "envelope_model": "sinusoidal_taper_10pct_edges_20pct_center",
        "envelope_description": (
            "fractional = 0.10 + 0.10 * sin(pi * normalized_theta); "
            "normalized_theta = (theta - theta_min) / (theta_max - theta_min); "
            "20% at 90 deg, 10% at support edges (26.49, 169.78 deg)"
        ),
        "nodes": len(envelope),
        "per_node": envelope,
        "propagation_status": "NOT_PROPAGATED_ISSUE_1179",
        "note": (
            "The systematic envelope is a proposed model from #1179, not yet "
            "implemented in the compiled sampler. The nominal reference uses "
            "only sigma (column 2) without systematic variation."
        ),
    }


def audit_sampler(path: Path) -> dict[str, object]:
    raw, angles, sigma, stat_uncertainty = _read_table(path)
    legacy = _legacy_audit(angles, sigma)
    exact = _exact_reference_audit(angles, sigma)
    statistical = _statistical_uncertainty_audit(angles, sigma, stat_uncertainty)
    systematic = _systematic_uncertainty_envelope_audit(angles, sigma)
    return {
        "schema_version": "ccb_sigma_cm_sampler_contract_v2",
        "input": {
            "path": _display_path(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "rows": len(angles),
            "support_theta_cm_deg": [math.degrees(angles[0]), math.degrees(angles[-1])],
        },
        "legacy_v1": legacy,
        "implemented_reference": exact,
        "uncertainty": {
            "statistical": statistical,
            "systematic_envelope": systematic,
            "propagation_status": "OPEN_ISSUE_1179",
            "propagation_note": (
                "Cross-section statistical and systematic uncertainty propagation is not yet "
                "implemented in the compiled sampler. The nominal reference uses sigma (column 2) "
                "only. This is tracked as #1179 in the issue campaign ledger."
            ),
        },
        "interpretation": (
            "The legacy inverse-CDF used the correct trapezoid interval masses but sampled a "
            "piecewise-constant density inside each interval and silently assigned substantial mass "
            "outside measured support. The replacement exactly inverts the linearly interpolated "
            "sigma*sin(theta) node density on an explicitly truncated measured-support reference."
        ),
        "scientific_boundary": (
            "Deterministic numerical/source-contract result only. The measured-support truncation is "
            "a declared nominal reference, not a physical extrapolation result. Cross-section "
            "statistical/systematic uncertainty, alternate support models, compiled Geant4 execution, "
            "generator-level Monte Carlo closure, and detector-level predictions remain separate gates."
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
