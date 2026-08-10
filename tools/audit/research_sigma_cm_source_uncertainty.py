#!/usr/bin/env python3
"""Deterministic source-uncertainty audit for the 190 MeV p-d CM table.

This is source-model sensitivity research, not detector validation and not a
probabilistic covariance reconstruction. The source gives row statistical
uncertainties plus a 3% point-to-point systematic at 190 MeV and a total
systematic bound below 4.5%, but it does not publish a row covariance matrix.

The nominal normalized source is the repository's measured-support,
linearly-interpolated p(theta)=sigma(theta)*sin(theta) reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
TABLE_SHA256 = "0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc"
INTERPOLATION_MODE = "linear_node_pdf_exact_inverse_v1"
SUPPORT_MODE = "measured_table_support_truncate_v1"
POINT_TO_POINT_FRACTION = 0.03
TOTAL_SYSTEMATIC_BOUND = 0.045
GRID_POINTS = 10_001


def _dot(a: list[float], b: list[float]) -> float:
    return math.fsum(x * y for x, y in zip(a, b, strict=True))


def _read_table(path: Path) -> tuple[bytes, list[float], list[float], list[float]]:
    raw = path.read_bytes()
    angles: list[float] = []
    sigma: list[float] = []
    stat_unc: list[float] = []
    for line_number, line in enumerate(raw.decode("ascii").splitlines(), start=1):
        fields = line.split()
        if len(fields) != 3:
            raise ValueError(f"line {line_number}: expected exactly three columns")
        angle_deg, cross_section, statistical_uncertainty = map(float, fields)
        if not all(math.isfinite(v) for v in (angle_deg, cross_section, statistical_uncertainty)):
            raise ValueError(f"line {line_number}: non-finite table value")
        if cross_section <= 0.0:
            raise ValueError(f"line {line_number}: cross section must be positive")
        if statistical_uncertainty < 0.0:
            raise ValueError(f"line {line_number}: statistical uncertainty must be nonnegative")
        angles.append(math.radians(angle_deg))
        sigma.append(cross_section)
        stat_unc.append(statistical_uncertainty)
    if len(angles) < 2:
        raise ValueError("need at least two cross-section rows")
    if any(b <= a for a, b in zip(angles, angles[1:])):
        raise ValueError("CM angles must be strictly increasing")
    return raw, angles, sigma, stat_unc


def total_mass_coefficients(angles: list[float]) -> list[float]:
    """Return coefficients b_i such that Z=sum_i b_i*sigma_i."""
    out = [0.0] * len(angles)
    for i, (left, right) in enumerate(zip(angles, angles[1:])):
        width = right - left
        out[i] += 0.5 * width * math.sin(left)
        out[i + 1] += 0.5 * width * math.sin(right)
    return out


def cdf_mass_coefficients(angles: list[float], theta: float) -> list[float]:
    """Return a_i(theta) with cumulative mass N(theta)=sum_i a_i*sigma_i."""
    total = total_mass_coefficients(angles)
    if theta <= angles[0]:
        return [0.0] * len(angles)
    if theta >= angles[-1]:
        return total

    out = [0.0] * len(angles)
    for i, (left, right) in enumerate(zip(angles, angles[1:])):
        width = right - left
        if theta >= right:
            out[i] += 0.5 * width * math.sin(left)
            out[i + 1] += 0.5 * width * math.sin(right)
            continue
        if theta > left:
            offset = theta - left
            out[i] += (offset - offset * offset / (2.0 * width)) * math.sin(left)
            out[i + 1] += (offset * offset / (2.0 * width)) * math.sin(right)
        break
    return out


def first_moment_coefficients(angles: list[float]) -> list[float]:
    """Return a_i with integral(theta*p(theta)dtheta)=sum a_i*sigma_i."""
    out = [0.0] * len(angles)
    for i, (left, right) in enumerate(zip(angles, angles[1:])):
        width = right - left
        out[i] += (left * width / 2.0 + width * width / 6.0) * math.sin(left)
        out[i + 1] += (left * width / 2.0 + width * width / 3.0) * math.sin(right)
    return out


def ratio_box_extreme(
    numerator_coefficients: list[float],
    denominator_coefficients: list[float],
    central_values: list[float],
    relative_half_width: float,
    *,
    maximize: bool,
) -> float:
    """Optimize (a.s)/(b.s) over independent positive box bounds on s.

    This is a deterministic linear-fractional sensitivity envelope. It is not a
    probability distribution for the nuisance vector.
    """
    if not 0.0 <= relative_half_width < 1.0:
        raise ValueError("relative_half_width must lie in [0,1)")
    if not (
        len(numerator_coefficients)
        == len(denominator_coefficients)
        == len(central_values)
    ):
        raise ValueError("coefficient and value lengths must match")
    if any(v <= 0.0 or not math.isfinite(v) for v in central_values):
        raise ValueError("central values must be finite and positive")
    if any(v < 0.0 or not math.isfinite(v) for v in denominator_coefficients):
        raise ValueError("denominator coefficients must be finite and nonnegative")

    ratios = [
        a / b
        for a, b in zip(numerator_coefficients, denominator_coefficients)
        if b > 0.0
    ]
    if not ratios:
        raise ValueError("positive denominator mass is required")
    lo, hi = min(ratios), max(ratios)
    lower = [v * (1.0 - relative_half_width) for v in central_values]
    upper = [v * (1.0 + relative_half_width) for v in central_values]

    for _ in range(120):
        trial = 0.5 * (lo + hi)
        coefficients = [
            a - trial * b
            for a, b in zip(numerator_coefficients, denominator_coefficients)
        ]
        if maximize:
            objective = math.fsum(
                c * (u if c >= 0.0 else l)
                for c, l, u in zip(coefficients, lower, upper, strict=True)
            )
        else:
            objective = math.fsum(
                c * (l if c >= 0.0 else u)
                for c, l, u in zip(coefficients, lower, upper, strict=True)
            )
        if objective > 0.0:
            lo = trial
        else:
            hi = trial
    return 0.5 * (lo + hi)


def diagonal_statistical_standard_uncertainty(
    numerator_coefficients: list[float],
    denominator_coefficients: list[float],
    central_values: list[float],
    standard_uncertainties: list[float],
) -> float:
    """Delta-method standard uncertainty conditional on diagonal row statistics."""
    denominator = _dot(denominator_coefficients, central_values)
    numerator = _dot(numerator_coefficients, central_values)
    if not denominator > 0.0:
        raise ValueError("positive denominator is required")
    variance_terms = []
    for a, b, uncertainty in zip(
        numerator_coefficients,
        denominator_coefficients,
        standard_uncertainties,
        strict=True,
    ):
        gradient = (a * denominator - numerator * b) / (denominator * denominator)
        variance_terms.append((gradient * uncertainty) ** 2)
    return math.sqrt(math.fsum(variance_terms))


def _cdf(angles: list[float], sigma: list[float], theta: float) -> float:
    return _dot(cdf_mass_coefficients(angles, theta), sigma) / _dot(
        total_mass_coefficients(angles),
        sigma,
    )


def audit_source_uncertainty(path: Path, *, grid_points: int = GRID_POINTS) -> dict[str, object]:
    if grid_points < 3:
        raise ValueError("grid_points must be at least 3")
    raw, angles, sigma, stat_unc = _read_table(path)
    digest = hashlib.sha256(raw).hexdigest()
    if path.resolve() == DEFAULT_TABLE.resolve() and digest != TABLE_SHA256:
        raise ValueError("canonical source-table SHA-256 mismatch")

    denominator_coefficients = total_mass_coefficients(angles)
    normalization = _dot(denominator_coefficients, sigma)
    first_moment = first_moment_coefficients(angles)
    mean_theta = _dot(first_moment, sigma) / normalization

    common_scaled = [(1.0 + TOTAL_SYSTEMATIC_BOUND) * v for v in sigma]
    grid = [
        angles[0] + (angles[-1] - angles[0]) * i / (grid_points - 1)
        for i in range(grid_points)
    ]
    max_common_delta = 0.0
    max_up = (-1.0, angles[0])
    max_down = (-1.0, angles[0])
    max_stat = (-1.0, angles[0])

    for theta in grid:
        coefficients = cdf_mass_coefficients(angles, theta)
        nominal = _dot(coefficients, sigma) / normalization
        common = _dot(coefficients, common_scaled) / _dot(
            denominator_coefficients,
            common_scaled,
        )
        max_common_delta = max(max_common_delta, abs(common - nominal))

        upper = ratio_box_extreme(
            coefficients,
            denominator_coefficients,
            sigma,
            POINT_TO_POINT_FRACTION,
            maximize=True,
        )
        lower = ratio_box_extreme(
            coefficients,
            denominator_coefficients,
            sigma,
            POINT_TO_POINT_FRACTION,
            maximize=False,
        )
        if upper - nominal > max_up[0]:
            max_up = (upper - nominal, theta)
        if nominal - lower > max_down[0]:
            max_down = (nominal - lower, theta)

        statistical = diagonal_statistical_standard_uncertainty(
            coefficients,
            denominator_coefficients,
            sigma,
            stat_unc,
        )
        if statistical > max_stat[0]:
            max_stat = (statistical, theta)

    alternating = [
        value * (1.0 + POINT_TO_POINT_FRACTION * (1.0 if i % 2 == 0 else -1.0))
        for i, value in enumerate(sigma)
    ]
    alternating_opposite = [
        value * (1.0 - POINT_TO_POINT_FRACTION * (1.0 if i % 2 == 0 else -1.0))
        for i, value in enumerate(sigma)
    ]

    def cdf_sup_delta(values: list[float]) -> tuple[float, float]:
        maximum = (-1.0, angles[0])
        for theta in grid:
            delta = abs(_cdf(angles, values, theta) - _cdf(angles, sigma, theta))
            if delta > maximum[0]:
                maximum = (delta, theta)
        return maximum

    alternating_delta = cdf_sup_delta(alternating)
    alternating_opposite_delta = cdf_sup_delta(alternating_opposite)

    mean_min = ratio_box_extreme(
        first_moment,
        denominator_coefficients,
        sigma,
        POINT_TO_POINT_FRACTION,
        maximize=False,
    )
    mean_max = ratio_box_extreme(
        first_moment,
        denominator_coefficients,
        sigma,
        POINT_TO_POINT_FRACTION,
        maximize=True,
    )
    mean_stat = diagonal_statistical_standard_uncertainty(
        first_moment,
        denominator_coefficients,
        sigma,
        stat_unc,
    )

    return {
        "schema_version": "ccb_sigma_cm_source_uncertainty_v1",
        "input": {
            "path": (
                str(path.resolve().relative_to(ROOT.resolve()))
                if path.resolve().is_relative_to(ROOT.resolve())
                else str(path)
            ),
            "sha256": digest,
            "bytes": len(raw),
            "rows": len(angles),
            "support_theta_cm_deg": [math.degrees(angles[0]), math.degrees(angles[-1])],
            "source_doi": "10.1103/PhysRevC.71.064004",
            "source_table": "VI",
        },
        "nominal_source_model": {
            "cross_section_interpolation_mode": INTERPOLATION_MODE,
            "cross_section_support_mode": SUPPORT_MODE,
            "normalization": normalization,
            "mean_theta_cm_deg": math.degrees(mean_theta),
        },
        "source_uncertainty_contract": {
            "row_third_column": "absolute_statistical_uncertainty_dsigma_domega_mb_per_sr",
            "point_to_point_systematic_fraction_at_190_MeV": POINT_TO_POINT_FRACTION,
            "total_systematic_fraction_bound_at_190_MeV": "<0.045",
            "published_row_covariance_matrix": False,
            "point_to_point_construction": (
                "The source reports an extra per-point error chosen so a high-order polynomial fit "
                "to the angular cross section reaches chi^2 approximately one after target-thickness "
                "and background-subtraction limitations; this does not uniquely define a stochastic "
                "row covariance model."
            ),
        },
        "deterministic_sensitivity": {
            "grid_points": grid_points,
            "grid_support_theta_cm_deg": [math.degrees(angles[0]), math.degrees(angles[-1])],
            "common_scale_bound_control": {
                "relative_scale": 1.0 + TOTAL_SYSTEMATIC_BOUND,
                "max_abs_normalized_cdf_delta": max_common_delta,
                "interpretation": (
                    "A fully common multiplicative source normalization cancels from normalized shape."
                ),
            },
            "nodewise_relative_box_3pct_sensitivity_v1": {
                "status": "NONPROBABILISTIC_ENVELOPE",
                "box_definition": "each central sigma_i independently allowed in [0.97,1.03]*sigma_i",
                "max_cdf_upward_excursion": max_up[0],
                "max_cdf_downward_excursion": max_down[0],
                "theta_cm_deg_at_max_upward_excursion": math.degrees(max_up[1]),
                "theta_cm_deg_at_max_downward_excursion": math.degrees(max_down[1]),
                "nominal_mean_theta_cm_deg": math.degrees(mean_theta),
                "min_mean_theta_cm_deg": math.degrees(mean_min),
                "max_mean_theta_cm_deg": math.degrees(mean_max),
            },
            "alternating_3pct_controls": {
                "plus_minus_max_abs_cdf_delta": alternating_delta[0],
                "minus_plus_max_abs_cdf_delta": alternating_opposite_delta[0],
                "theta_cm_deg_at_plus_minus_max": math.degrees(alternating_delta[1]),
                "theta_cm_deg_at_minus_plus_max": math.degrees(alternating_opposite_delta[1]),
            },
        },
        "conditional_diagonal_statistical_reference": {
            "status": "DELTA_METHOD_CONDITIONAL_ON_INDEPENDENT_ROW_STATISTICS",
            "max_pointwise_cdf_standard_uncertainty": max_stat[0],
            "theta_cm_deg_at_max_pointwise_cdf_standard_uncertainty": math.degrees(max_stat[1]),
            "mean_theta_cm_standard_uncertainty_deg": math.degrees(mean_stat),
            "interpretation": (
                "This uses only the published row statistical uncertainties and a diagonal approximation. "
                "It is not a replacement for unavailable systematic covariance."
            ),
        },
        "scientific_boundary": (
            "Source-level deterministic/conditional uncertainty research only. The nodewise 3% box is a "
            "sensitivity envelope, not a confidence region or inferred covariance. No beam data, detector "
            "response, production Geant4 sample, or detector-performance claim is validated."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--grid-points", type=int, default=GRID_POINTS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_source_uncertainty(args.table, grid_points=args.grid_points)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
