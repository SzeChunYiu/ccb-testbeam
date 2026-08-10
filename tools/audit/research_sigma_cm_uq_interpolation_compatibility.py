#!/usr/bin/env python3
"""Cross-atom audit of interpolation-model and source-node uncertainty composition.

This is deterministic source-model sensitivity research. It composes two already
surviving measured-support interpolation classes with the explicit nonprobabilistic
±3% node box used under #1179. It does not infer a nuisance probability law,
experimental covariance, detector response, or confidence band.
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
CURRENT_MODE = "linear_node_pdf_exact_inverse_v1"
ALTERNATIVE_MODE = "linear_cross_section_then_jacobian_v1"
SUPPORT_MODE = "measured_table_support_truncate_v1"
POINT_TO_POINT_FRACTION = 0.03
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
        if not all(
            math.isfinite(v)
            for v in (angle_deg, cross_section, statistical_uncertainty)
        ):
            raise ValueError(f"line {line_number}: non-finite table value")
        if cross_section <= 0.0:
            raise ValueError(f"line {line_number}: cross section must be positive")
        if statistical_uncertainty < 0.0:
            raise ValueError(
                f"line {line_number}: statistical uncertainty must be nonnegative"
            )
        angles.append(math.radians(angle_deg))
        sigma.append(cross_section)
        stat_unc.append(statistical_uncertainty)
    if len(angles) < 2:
        raise ValueError("need at least two cross-section rows")
    if any(b <= a for a, b in zip(angles, angles[1:])):
        raise ValueError("CM angles must be strictly increasing")
    return raw, angles, sigma, stat_unc


def _i0(left: float, right: float) -> float:
    return math.cos(left) - math.cos(right)


def _i1(left: float, right: float) -> float:
    return (-right * math.cos(right) + math.sin(right)) - (
        -left * math.cos(left) + math.sin(left)
    )


def _i2(left: float, right: float) -> float:
    return (
        -right * right * math.cos(right)
        + 2.0 * right * math.sin(right)
        + 2.0 * math.cos(right)
    ) - (
        -left * left * math.cos(left)
        + 2.0 * left * math.sin(left)
        + 2.0 * math.cos(left)
    )


def _coefficients(
    angles: list[float],
    theta: float | None,
    *,
    mode: str,
    first_moment: bool = False,
) -> list[float]:
    """Return linear coefficients of source mass/cumulative mass/first moment."""
    if mode not in {CURRENT_MODE, ALTERNATIVE_MODE}:
        raise ValueError(f"unsupported interpolation mode: {mode}")
    if theta is not None and first_moment:
        raise ValueError("theta and first_moment are mutually exclusive")

    out = [0.0] * len(angles)
    if theta is not None and theta <= angles[0]:
        return out
    upper_limit = angles[-1] if theta is None else min(theta, angles[-1])

    for i, (left, right) in enumerate(zip(angles, angles[1:])):
        if upper_limit <= left:
            break
        upper = min(upper_limit, right)
        width = right - left

        if mode == CURRENT_MODE:
            if first_moment:
                out[i] += (
                    left * width / 2.0 + width * width / 6.0
                ) * math.sin(left)
                out[i + 1] += (
                    left * width / 2.0 + width * width / 3.0
                ) * math.sin(right)
            else:
                offset = upper - left
                out[i] += (
                    offset - offset * offset / (2.0 * width)
                ) * math.sin(left)
                out[i + 1] += (
                    offset * offset / (2.0 * width)
                ) * math.sin(right)
        else:
            if first_moment:
                i1 = _i1(left, right)
                i2 = _i2(left, right)
                out[i] += (right * i1 - i2) / width
                out[i + 1] += (i2 - left * i1) / width
            else:
                i0 = _i0(left, upper)
                i1 = _i1(left, upper)
                out[i] += (right * i0 - i1) / width
                out[i + 1] += (i1 - left * i0) / width

        if upper_limit <= right:
            break
    return out


def total_mass_coefficients(angles: list[float], mode: str) -> list[float]:
    return _coefficients(angles, angles[-1], mode=mode)


def first_moment_coefficients(angles: list[float], mode: str) -> list[float]:
    return _coefficients(angles, None, mode=mode, first_moment=True)


def cdf_mass_coefficients(
    angles: list[float], theta: float, mode: str
) -> list[float]:
    return _coefficients(angles, theta, mode=mode)


def ratio_box_extreme(
    numerator: list[float],
    denominator: list[float],
    central: list[float],
    relative_half_width: float,
    *,
    maximize: bool,
) -> float:
    """Exact linear-fractional box extreme by monotone root bisection."""
    if not 0.0 <= relative_half_width < 1.0:
        raise ValueError("relative_half_width must lie in [0,1)")
    ratios = [a / b for a, b in zip(numerator, denominator) if b > 0.0]
    if not ratios:
        raise ValueError("positive denominator mass is required")
    lo, hi = min(ratios), max(ratios)
    lower = [v * (1.0 - relative_half_width) for v in central]
    upper = [v * (1.0 + relative_half_width) for v in central]

    for _ in range(90):
        trial = 0.5 * (lo + hi)
        coefficients = [
            a - trial * b for a, b in zip(numerator, denominator, strict=True)
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
    numerator: list[float],
    denominator: list[float],
    central: list[float],
    standard_uncertainties: list[float],
) -> float:
    den = _dot(denominator, central)
    num = _dot(numerator, central)
    return math.sqrt(
        math.fsum(
            (((a * den - num * b) / (den * den)) * unc) ** 2
            for a, b, unc in zip(
                numerator, denominator, standard_uncertainties, strict=True
            )
        )
    )


def audit_compatibility(
    path: Path, *, grid_points: int = GRID_POINTS
) -> dict[str, object]:
    if grid_points < 3:
        raise ValueError("grid_points must be at least 3")
    raw, angles, sigma, stat_unc = _read_table(path)
    digest = hashlib.sha256(raw).hexdigest()
    if path.resolve() == DEFAULT_TABLE.resolve() and digest != TABLE_SHA256:
        raise ValueError("canonical source-table SHA-256 mismatch")

    totals = {
        mode: total_mass_coefficients(angles, mode)
        for mode in (CURRENT_MODE, ALTERNATIVE_MODE)
    }
    firsts = {
        mode: first_moment_coefficients(angles, mode)
        for mode in (CURRENT_MODE, ALTERNATIVE_MODE)
    }
    normalizations = {mode: _dot(totals[mode], sigma) for mode in totals}
    means = {
        mode: _dot(firsts[mode], sigma) / normalizations[mode] for mode in totals
    }

    grid = [
        angles[0] + (angles[-1] - angles[0]) * i / (grid_points - 1)
        for i in range(grid_points)
    ]

    max_interp = (-1.0, angles[0])
    max_current_up = (-1.0, angles[0])
    max_current_down = (-1.0, angles[0])
    max_alternative_up = (-1.0, angles[0])
    max_alternative_down = (-1.0, angles[0])
    max_union_up = (-1.0, angles[0])
    max_union_down = (-1.0, angles[0])
    max_upper_extension = (-1.0, angles[0])
    max_lower_extension = (-1.0, angles[0])
    max_nominal_outside_current_box = 0.0
    max_current_stat = (-1.0, angles[0])
    max_alternative_stat = (-1.0, angles[0])

    for theta in grid:
        coefficients = {
            mode: cdf_mass_coefficients(angles, theta, mode)
            for mode in (CURRENT_MODE, ALTERNATIVE_MODE)
        }
        nominal = {
            mode: _dot(coefficients[mode], sigma) / normalizations[mode]
            for mode in coefficients
        }
        bounds: dict[str, tuple[float, float]] = {}
        for mode in (CURRENT_MODE, ALTERNATIVE_MODE):
            lower = ratio_box_extreme(
                coefficients[mode],
                totals[mode],
                sigma,
                POINT_TO_POINT_FRACTION,
                maximize=False,
            )
            upper = ratio_box_extreme(
                coefficients[mode],
                totals[mode],
                sigma,
                POINT_TO_POINT_FRACTION,
                maximize=True,
            )
            bounds[mode] = (lower, upper)

        interp = abs(nominal[CURRENT_MODE] - nominal[ALTERNATIVE_MODE])
        if interp > max_interp[0]:
            max_interp = (interp, theta)

        current_lower, current_upper = bounds[CURRENT_MODE]
        alternative_lower, alternative_upper = bounds[ALTERNATIVE_MODE]
        candidates = {
            "current_up": current_upper - nominal[CURRENT_MODE],
            "current_down": nominal[CURRENT_MODE] - current_lower,
            "alternative_up": alternative_upper - nominal[ALTERNATIVE_MODE],
            "alternative_down": nominal[ALTERNATIVE_MODE] - alternative_lower,
            "union_up": max(current_upper, alternative_upper) - nominal[CURRENT_MODE],
            "union_down": nominal[CURRENT_MODE] - min(current_lower, alternative_lower),
            "upper_extension": alternative_upper - current_upper,
            "lower_extension": current_lower - alternative_lower,
        }
        holders = {
            "current_up": max_current_up,
            "current_down": max_current_down,
            "alternative_up": max_alternative_up,
            "alternative_down": max_alternative_down,
            "union_up": max_union_up,
            "union_down": max_union_down,
            "upper_extension": max_upper_extension,
            "lower_extension": max_lower_extension,
        }
        for name, value in candidates.items():
            if value <= holders[name][0]:
                continue
            if name == "current_up":
                max_current_up = (value, theta)
            elif name == "current_down":
                max_current_down = (value, theta)
            elif name == "alternative_up":
                max_alternative_up = (value, theta)
            elif name == "alternative_down":
                max_alternative_down = (value, theta)
            elif name == "union_up":
                max_union_up = (value, theta)
            elif name == "union_down":
                max_union_down = (value, theta)
            elif name == "upper_extension":
                max_upper_extension = (value, theta)
            elif name == "lower_extension":
                max_lower_extension = (value, theta)

        outside = max(
            nominal[ALTERNATIVE_MODE] - current_upper,
            current_lower - nominal[ALTERNATIVE_MODE],
            0.0,
        )
        max_nominal_outside_current_box = max(
            max_nominal_outside_current_box, outside
        )

        for mode in (CURRENT_MODE, ALTERNATIVE_MODE):
            value = diagonal_statistical_standard_uncertainty(
                coefficients[mode], totals[mode], sigma, stat_unc
            )
            if mode == CURRENT_MODE and value > max_current_stat[0]:
                max_current_stat = (value, theta)
            if mode == ALTERNATIVE_MODE and value > max_alternative_stat[0]:
                max_alternative_stat = (value, theta)

    mean_bounds = {}
    mean_stat = {}
    for mode in (CURRENT_MODE, ALTERNATIVE_MODE):
        mean_bounds[mode] = (
            ratio_box_extreme(
                firsts[mode],
                totals[mode],
                sigma,
                POINT_TO_POINT_FRACTION,
                maximize=False,
            ),
            ratio_box_extreme(
                firsts[mode],
                totals[mode],
                sigma,
                POINT_TO_POINT_FRACTION,
                maximize=True,
            ),
        )
        mean_stat[mode] = diagonal_statistical_standard_uncertainty(
            firsts[mode], totals[mode], sigma, stat_unc
        )

    union_mean_lower = min(
        mean_bounds[CURRENT_MODE][0], mean_bounds[ALTERNATIVE_MODE][0]
    )
    union_mean_upper = max(
        mean_bounds[CURRENT_MODE][1], mean_bounds[ALTERNATIVE_MODE][1]
    )

    def pair(value: tuple[float, float]) -> dict[str, float]:
        return {"value": value[0], "theta_cm_deg": math.degrees(value[1])}

    return {
        "schema_version": "ccb_sigma_cm_uq_interpolation_compatibility_v1",
        "input": {
            "path": (
                str(path.resolve().relative_to(ROOT.resolve()))
                if path.resolve().is_relative_to(ROOT.resolve())
                else str(path)
            ),
            "sha256": digest,
            "bytes": len(raw),
            "rows": len(angles),
            "support_theta_cm_deg": [
                math.degrees(angles[0]),
                math.degrees(angles[-1]),
            ],
        },
        "models": {
            "interpolation_modes": [CURRENT_MODE, ALTERNATIVE_MODE],
            "support_mode": SUPPORT_MODE,
            "node_box_fraction": POINT_TO_POINT_FRACTION,
            "node_box_status": "NONPROBABILISTIC_ENVELOPE",
            "grid_points": grid_points,
        },
        "central_model_difference": {
            "grid_max_abs_cdf_difference": pair(max_interp),
            "mean_theta_cm_deg": {
                CURRENT_MODE: math.degrees(means[CURRENT_MODE]),
                ALTERNATIVE_MODE: math.degrees(means[ALTERNATIVE_MODE]),
                "alternative_minus_current": math.degrees(
                    means[ALTERNATIVE_MODE] - means[CURRENT_MODE]
                ),
            },
        },
        "node_box_by_interpolation": {
            CURRENT_MODE: {
                "max_upward_cdf_excursion_from_own_nominal": pair(max_current_up),
                "max_downward_cdf_excursion_from_own_nominal": pair(max_current_down),
                "mean_theta_cm_deg_range": [
                    math.degrees(mean_bounds[CURRENT_MODE][0]),
                    math.degrees(mean_bounds[CURRENT_MODE][1]),
                ],
            },
            ALTERNATIVE_MODE: {
                "max_upward_cdf_excursion_from_own_nominal": pair(max_alternative_up),
                "max_downward_cdf_excursion_from_own_nominal": pair(
                    max_alternative_down
                ),
                "mean_theta_cm_deg_range": [
                    math.degrees(mean_bounds[ALTERNATIVE_MODE][0]),
                    math.degrees(mean_bounds[ALTERNATIVE_MODE][1]),
                ],
            },
        },
        "cross_atom_compatibility": {
            "alternative_nominal_max_violation_of_current_box": (
                max_nominal_outside_current_box
            ),
            "alternative_box_max_upper_extension_beyond_current_box": pair(
                max_upper_extension
            ),
            "alternative_box_max_lower_extension_beyond_current_box": pair(
                max_lower_extension
            ),
            "union_envelope_relative_to_current_nominal": {
                "max_upward_cdf_excursion": pair(max_union_up),
                "max_downward_cdf_excursion": pair(max_union_down),
                "mean_theta_cm_deg_range": [
                    math.degrees(union_mean_lower),
                    math.degrees(union_mean_upper),
                ],
            },
            "interpretation": (
                "The alternative central interpolation lies inside the current-mode "
                "3% node box on the tested grid, but the alternative mode's own 3% "
                "box extends beyond the current-mode box. Therefore the two nuisance "
                "universes are not interchangeable: a current-mode node box cannot be "
                "declared cross-model closure merely because it covers the alternative "
                "central curve."
            ),
        },
        "conditional_diagonal_statistical_reference": {
            CURRENT_MODE: {
                "max_pointwise_cdf_standard_uncertainty": pair(max_current_stat),
                "mean_theta_cm_standard_uncertainty_deg": math.degrees(
                    mean_stat[CURRENT_MODE]
                ),
            },
            ALTERNATIVE_MODE: {
                "max_pointwise_cdf_standard_uncertainty": pair(max_alternative_stat),
                "mean_theta_cm_standard_uncertainty_deg": math.degrees(
                    mean_stat[ALTERNATIVE_MODE]
                ),
            },
            "status": "DELTA_METHOD_CONDITIONAL_ON_INDEPENDENT_ROW_STATISTICS",
        },
        "scientific_boundary": (
            "Deterministic cross-atom source sensitivity only. The interpolation "
            "classes carry no probability weights; the 3% node box is not a confidence "
            "region; the diagonal statistical reference is conditional. Do not add "
            "these quantities in quadrature or promote them as detector uncertainty."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--grid-points", type=int, default=GRID_POINTS)
    args = parser.parse_args()
    result = audit_compatibility(args.table, grid_points=args.grid_points)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
