#!/usr/bin/env python3
"""Deterministic interpolation-order sensitivity for the 190 MeV p-d CM source.

Compares two measured-support central-value models that agree at every published
cross-section node but differ between nodes:

* ``linear_node_pdf_exact_inverse_v1``: linearly interpolate g(theta)=sigma(theta)sin(theta).
  This is the current generator reference under #1178.
* ``linear_cross_section_then_jacobian_v1``: linearly interpolate the published
  observable sigma=dσ/dΩ, then multiply by sin(theta).

This is source-model sensitivity only. Neither alternative reconstructs missing
experimental covariance or authorises off-support extrapolation/detector claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TABLE = ROOT / "geant4/src_patch/sigma_pd_cm_190.txt"
CURRENT_MODE = "linear_node_pdf_exact_inverse_v1"
ALTERNATIVE_MODE = "linear_cross_section_then_jacobian_v1"
SUPPORT_MODE = "measured_table_support_truncate_v1"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _read_table(path: Path) -> tuple[bytes, list[float], list[float]]:
    raw = path.read_bytes()
    angles: list[float] = []
    sigma: list[float] = []
    for line_number, line in enumerate(raw.decode("ascii").splitlines(), start=1):
        fields = line.split()
        if len(fields) != 3:
            raise ValueError(f"line {line_number}: expected exactly three columns")
        angle_deg, cross_section, _stat_uncertainty = map(float, fields)
        if not math.isfinite(angle_deg) or not math.isfinite(cross_section):
            raise ValueError(f"line {line_number}: non-finite table value")
        if cross_section < 0.0:
            raise ValueError(f"line {line_number}: negative cross section")
        angles.append(math.radians(angle_deg))
        sigma.append(cross_section)
    if len(angles) < 2:
        raise ValueError("need at least two cross-section rows")
    if any(b <= a for a, b in zip(angles, angles[1:])):
        raise ValueError("CM angles must be strictly increasing")
    return raw, angles, sigma


def _linear_integral(left: float, right: float, y_left: float, y_right: float) -> float:
    return 0.5 * (y_left + y_right) * (right - left)


def _sigma_sin_antiderivative(theta: float, intercept: float, slope: float) -> float:
    # ∫ (intercept + slope*theta) sin(theta) dtheta
    return -(intercept + slope * theta) * math.cos(theta) + slope * math.sin(theta)


def _theta_sigma_sin_antiderivative(theta: float, intercept: float, slope: float) -> float:
    # ∫ theta (intercept + slope*theta) sin(theta) dtheta
    return intercept * (-theta * math.cos(theta) + math.sin(theta)) + slope * (
        -theta * theta * math.cos(theta)
        + 2.0 * theta * math.sin(theta)
        + 2.0 * math.cos(theta)
    )


@dataclass(frozen=True)
class SourceModel:
    angles: tuple[float, ...]
    sigma: tuple[float, ...]
    mode: str
    interval_mass: tuple[float, ...]
    cumulative_mass: tuple[float, ...]
    normalization: float
    mean_theta_rad: float

    def density(self, theta_value: float) -> float:
        if theta_value < self.angles[0] or theta_value > self.angles[-1]:
            return 0.0
        idx = _interval_index(self.angles, theta_value)
        left = self.angles[idx]
        right = self.angles[idx + 1]
        frac = (theta_value - left) / (right - left)
        if self.mode == CURRENT_MODE:
            g0 = self.sigma[idx] * math.sin(left)
            g1 = self.sigma[idx + 1] * math.sin(right)
            return g0 + frac * (g1 - g0)
        sigma_value = self.sigma[idx] + frac * (self.sigma[idx + 1] - self.sigma[idx])
        return sigma_value * math.sin(theta_value)

    def cdf(self, theta_value: float) -> float:
        if theta_value <= self.angles[0]:
            return 0.0
        if theta_value >= self.angles[-1]:
            return 1.0
        idx = _interval_index(self.angles, theta_value)
        left = self.angles[idx]
        right = self.angles[idx + 1]
        if self.mode == CURRENT_MODE:
            g0 = self.sigma[idx] * math.sin(left)
            g1 = self.sigma[idx + 1] * math.sin(right)
            x = theta_value - left
            slope = (g1 - g0) / (right - left)
            partial = g0 * x + 0.5 * slope * x * x
        else:
            slope = (self.sigma[idx + 1] - self.sigma[idx]) / (right - left)
            intercept = self.sigma[idx] - slope * left
            partial = _sigma_sin_antiderivative(
                theta_value, intercept, slope
            ) - _sigma_sin_antiderivative(left, intercept, slope)
        return (self.cumulative_mass[idx] + partial) / self.normalization


def _interval_index(angles: tuple[float, ...], theta_value: float) -> int:
    lo = 0
    hi = len(angles) - 1
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if theta_value < angles[mid]:
            hi = mid
        else:
            lo = mid
    return min(lo, len(angles) - 2)


def _build_model(angles_in: list[float], sigma_in: list[float], mode: str) -> SourceModel:
    angles = tuple(angles_in)
    sigma = tuple(sigma_in)
    if mode not in {CURRENT_MODE, ALTERNATIVE_MODE}:
        raise ValueError(f"unsupported interpolation mode: {mode}")

    masses: list[float] = []
    mean_numerators: list[float] = []
    for i, (left, right) in enumerate(zip(angles, angles[1:])):
        if mode == CURRENT_MODE:
            g0 = sigma[i] * math.sin(left)
            g1 = sigma[i + 1] * math.sin(right)
            mass = _linear_integral(left, right, g0, g1)
            slope = (g1 - g0) / (right - left)
            intercept = g0 - slope * left
            mean_piece = (
                0.5 * intercept * (right * right - left * left)
                + (slope / 3.0) * (right**3 - left**3)
            )
        else:
            slope = (sigma[i + 1] - sigma[i]) / (right - left)
            intercept = sigma[i] - slope * left
            mass = _sigma_sin_antiderivative(
                right, intercept, slope
            ) - _sigma_sin_antiderivative(left, intercept, slope)
            mean_piece = _theta_sigma_sin_antiderivative(
                right, intercept, slope
            ) - _theta_sigma_sin_antiderivative(left, intercept, slope)
        if mass < 0.0 or not math.isfinite(mass):
            raise ValueError("interpolation produced invalid interval mass")
        masses.append(mass)
        mean_numerators.append(mean_piece)

    normalization = math.fsum(masses)
    if not normalization > 0.0 or not math.isfinite(normalization):
        raise ValueError("non-positive source normalization")
    cumulative = [0.0]
    running = 0.0
    for mass in masses:
        running = math.fsum((running, mass))
        cumulative.append(running)
    return SourceModel(
        angles=angles,
        sigma=sigma,
        mode=mode,
        interval_mass=tuple(masses),
        cumulative_mass=tuple(cumulative),
        normalization=normalization,
        mean_theta_rad=math.fsum(mean_numerators) / normalization,
    )


def _bisect_root(function, left: float, right: float, *, iterations: int = 80) -> float:
    f_left = function(left)
    f_right = function(right)
    if f_left == 0.0:
        return left
    if f_right == 0.0:
        return right
    if f_left * f_right > 0.0:
        raise ValueError("root is not bracketed")
    for _ in range(iterations):
        mid = 0.5 * (left + right)
        f_mid = function(mid)
        if f_mid == 0.0:
            return mid
        if f_left * f_mid <= 0.0:
            right = mid
            f_right = f_mid
        else:
            left = mid
            f_left = f_mid
    return 0.5 * (left + right)


def _cdf_sup_difference(a: SourceModel, b: SourceModel) -> tuple[float, float, float]:
    candidates: list[float] = list(a.angles)
    for left, right in zip(a.angles, a.angles[1:]):

        def derivative(theta_value: float) -> float:
            return a.density(theta_value) / a.normalization - b.density(
                theta_value
            ) / b.normalization

        subdivisions = 128
        grid = [left + (right - left) * j / subdivisions for j in range(subdivisions + 1)]
        values = [derivative(value) for value in grid]
        for x0, x1, y0, y1 in zip(grid, grid[1:], values, values[1:]):
            if y0 == 0.0:
                candidates.append(x0)
            if y0 * y1 < 0.0:
                candidates.append(_bisect_root(derivative, x0, x1))
    signed = [(a.cdf(value) - b.cdf(value), value) for value in candidates]
    delta, theta_value = max(signed, key=lambda item: abs(item[0]))
    return abs(delta), delta, theta_value


def _quantile(model: SourceModel, probability: float) -> float:
    if probability <= 0.0:
        return model.angles[0]
    if probability >= 1.0:
        return model.angles[-1]
    left = model.angles[0]
    right = model.angles[-1]
    for _ in range(90):
        mid = 0.5 * (left + right)
        if model.cdf(mid) < probability:
            left = mid
        else:
            right = mid
    return 0.5 * (left + right)


def _refine_sigma_linear_knots(
    angles: list[float], sigma: list[float]
) -> tuple[list[float], list[float]]:
    refined_angles = [angles[0]]
    refined_sigma = [sigma[0]]
    for left, right, s_left, s_right in zip(angles, angles[1:], sigma, sigma[1:]):
        refined_angles.extend((0.5 * (left + right), right))
        refined_sigma.extend((0.5 * (s_left + s_right), s_right))
    return refined_angles, refined_sigma


def audit_interpolation(path: Path) -> dict[str, object]:
    raw, angles, sigma = _read_table(path)
    current = _build_model(angles, sigma, CURRENT_MODE)
    alternative = _build_model(angles, sigma, ALTERNATIVE_MODE)
    sup, signed_sup, theta_sup = _cdf_sup_difference(current, alternative)

    refined_angles, refined_sigma = _refine_sigma_linear_knots(angles, sigma)
    current_refined = _build_model(refined_angles, refined_sigma, CURRENT_MODE)
    alternative_refined = _build_model(refined_angles, refined_sigma, ALTERNATIVE_MODE)
    current_refinement_sup, _, current_refinement_theta = _cdf_sup_difference(
        current, current_refined
    )
    alternative_refinement_sup, _, alternative_refinement_theta = _cdf_sup_difference(
        alternative, alternative_refined
    )

    quantiles = {}
    for probability in (0.05, 0.25, 0.5, 0.75, 0.95):
        current_theta = _quantile(current, probability)
        alternative_theta = _quantile(alternative, probability)
        quantiles[str(probability)] = {
            "current_deg": math.degrees(current_theta),
            "alternative_deg": math.degrees(alternative_theta),
            "alternative_minus_current_deg": math.degrees(
                alternative_theta - current_theta
            ),
        }

    return {
        "schema_version": "ccb_sigma_cm_interpolation_sensitivity_v1",
        "input": {
            "path": _display_path(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "rows": len(angles),
            "support_theta_cm_deg": [
                math.degrees(angles[0]),
                math.degrees(angles[-1]),
            ],
        },
        "models": {
            "current": {
                "interpolation_mode": CURRENT_MODE,
                "support_mode": SUPPORT_MODE,
                "normalization": current.normalization,
                "mean_theta_cm_deg": math.degrees(current.mean_theta_rad),
            },
            "alternative": {
                "interpolation_mode": ALTERNATIVE_MODE,
                "support_mode": SUPPORT_MODE,
                "normalization": alternative.normalization,
                "mean_theta_cm_deg": math.degrees(alternative.mean_theta_rad),
            },
        },
        "comparison": {
            "max_abs_normalized_cdf_difference": sup,
            "signed_current_minus_alternative_at_max": signed_sup,
            "theta_cm_deg_at_max_abs_cdf_difference": math.degrees(theta_sup),
            "alternative_minus_current_mean_theta_cm_deg": math.degrees(
                alternative.mean_theta_rad - current.mean_theta_rad
            ),
            "quantile_shifts": quantiles,
        },
        "representation_refinement_control": {
            "construction": (
                "insert one midpoint per interval with "
                "sigma_mid=(sigma_left+sigma_right)/2"
            ),
            "scientific_meaning": (
                "The inserted knots are redundant under a piecewise-linear interpolation of the "
                "published cross section sigma. They are not redundant under piecewise-linear "
                "interpolation of sigma*sin(theta), demonstrating that the two parameterizations "
                "are distinct model classes."
            ),
            "current_mode_max_abs_cdf_change": current_refinement_sup,
            "current_mode_theta_cm_deg_at_max_change": math.degrees(
                current_refinement_theta
            ),
            "alternative_mode_max_abs_cdf_change": alternative_refinement_sup,
            "alternative_mode_theta_cm_deg_at_max_change": math.degrees(
                alternative_refinement_theta
            ),
        },
        "interpretation": (
            "The current and alternative models match every published sigma node and use identical "
            "measured support, but differ between nodes because interpolation and the sin(theta) "
            "Jacobian do not commute. The source paper does not prescribe an interpolation rule "
            "between its tabulated angles, so this difference is model-form sensitivity rather "
            "than evidence that either interpolation is uniquely physical."
        ),
        "scientific_boundary": (
            "Deterministic central-value source sensitivity only. No off-support extrapolation, "
            "covariance model, generator runtime, detector response, or detector-level claim is "
            "validated by this result."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit_interpolation(args.table)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
