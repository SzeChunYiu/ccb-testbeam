"""Geometry-aware primary / beam intersection preflight (issue #999).

Extents come from a resolved geometry profile (or explicit half-lengths).
AppConfig must not grow a duplicate hard-coded geometry limit table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ccb_mc_validation.exceptions import ConfigurationError
from ccb_mc_validation.geometry.registry import GeometryProfile


@dataclass(frozen=True)
class BeamIntersectionResult:
    """Analytical ray–AABB intersection against the scintillator box."""

    intersects: bool
    enters_neg_z_face: bool
    entry_cm: tuple[float, float, float] | None
    exit_cm: tuple[float, float, float] | None
    path_length_cm: float | None
    launch_cm: tuple[float, float, float]
    direction: tuple[float, float, float]
    reason: str

    def as_metadata(self) -> dict[str, Any]:
        return {
            "intersects": self.intersects,
            "enters_neg_z_face": self.enters_neg_z_face,
            "entry_cm": list(self.entry_cm) if self.entry_cm is not None else None,
            "exit_cm": list(self.exit_cm) if self.exit_cm is not None else None,
            "path_length_cm": self.path_length_cm,
            "launch_cm": list(self.launch_cm),
            "direction": list(self.direction),
            "reason": self.reason,
        }


def _ray_aabb_intersection(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    half: tuple[float, float, float],
    *,
    eps: float = 1e-12,
) -> tuple[bool, float | None, float | None]:
    """Slab method. Returns (hit, t_enter, t_exit) along the ray."""
    t_min = -math.inf
    t_max = math.inf
    for o, d, h in zip(origin, direction, half, strict=True):
        if abs(d) < eps:
            if abs(o) > h:
                return False, None, None
            continue
        inv = 1.0 / d
        t1 = (-h - o) * inv
        t2 = (h - o) * inv
        if t1 > t2:
            t1, t2 = t2, t1
        t_min = max(t_min, t1)
        t_max = min(t_max, t2)
        if t_min > t_max:
            return False, None, None
    if t_max < 0:
        return False, None, None
    t_enter = t_min if t_min >= 0 else 0.0
    return True, t_enter, t_max


def _point_on_neg_z_face(
    point: tuple[float, float, float],
    half: tuple[float, float, float],
    *,
    tol: float = 1e-6,
) -> bool:
    hx, hy, hz = half
    x, y, z = point
    return (
        abs(z + hz) <= tol
        and abs(x) <= hx + tol
        and abs(y) <= hy + tol
    )


def validate_beam_intersection(
    *,
    hit_x_cm: float,
    hit_y_cm: float,
    theta_deg: float,
    phi_deg: float,
    profile: GeometryProfile | None = None,
    half_extents_cm: tuple[float, float, float] | None = None,
    launch_z_offset_cm: float = 0.1,
    mode: str = "calibration",
    allow_miss: bool = False,
    edge_tol_cm: float = 1e-9,
) -> BeamIntersectionResult:
    """Validate that the configured primary intersects the scintillator.

    Parameters
    ----------
    mode:
        ``calibration`` (default) requires an intersection that enters through
        the -z face with θ < 90°. ``free`` only requires any AABB intersection
        unless ``allow_miss`` is set.
    allow_miss:
        When True, a miss is reported but does not raise.
    """
    if half_extents_cm is None:
        if profile is None:
            raise ConfigurationError(
                "validate_beam_intersection requires a geometry profile or "
                "explicit half_extents_cm (no silent geometry defaults; #999)"
            )
        half_extents_cm = profile.stave_half_extents_cm()
    hx, hy, hz = (float(v) for v in half_extents_cm)
    if min(hx, hy, hz) <= 0:
        raise ConfigurationError(f"invalid stave half-extents: {(hx, hy, hz)}")

    th = math.radians(float(theta_deg))
    ph = math.radians(float(phi_deg))
    direction = (
        math.sin(th) * math.cos(ph),
        math.sin(th) * math.sin(ph),
        math.cos(th),
    )
    launch = (float(hit_x_cm), float(hit_y_cm), -hz - float(launch_z_offset_cm))

    # Face-domain check for the intended impact point (before tilt transport).
    outside_face = abs(hit_x_cm) > hx + edge_tol_cm or abs(hit_y_cm) > hy + edge_tol_cm

    hit, t_enter, t_exit = _ray_aabb_intersection(launch, direction, (hx, hy, hz))

    entry = exit_pt = None
    path = None
    enters_neg_z = False
    if hit and t_enter is not None and t_exit is not None:
        entry = (
            launch[0] + t_enter * direction[0],
            launch[1] + t_enter * direction[1],
            launch[2] + t_enter * direction[2],
        )
        exit_pt = (
            launch[0] + t_exit * direction[0],
            launch[1] + t_exit * direction[1],
            launch[2] + t_exit * direction[2],
        )
        path = math.dist(entry, exit_pt)
        enters_neg_z = _point_on_neg_z_face(entry, (hx, hy, hz))

    reason = "ok"
    ok = True
    if not math.isfinite(theta_deg) or not math.isfinite(phi_deg):
        ok = False
        reason = "non_finite_angle"
    elif mode == "calibration" and float(theta_deg) >= 90.0 - 1e-12:
        ok = False
        reason = f"theta_deg={theta_deg} >= 90 (primary not toward +z face)"
    elif outside_face and mode == "calibration":
        ok = False
        reason = (
            f"hit_x/hit_y outside stave face "
            f"(|x|<={hx} cm, |y|<={hy} cm); got ({hit_x_cm}, {hit_y_cm})"
        )
    elif not hit:
        ok = False
        reason = "ray_misses_scintillator_aabb"
    elif mode == "calibration" and not enters_neg_z:
        ok = False
        reason = "intersection_does_not_enter_neg_z_face"

    result = BeamIntersectionResult(
        intersects=bool(hit),
        enters_neg_z_face=enters_neg_z,
        entry_cm=entry,
        exit_cm=exit_pt,
        path_length_cm=path,
        launch_cm=launch,
        direction=direction,
        reason=reason if not ok else "ok",
    )

    if not ok and not allow_miss:
        raise ConfigurationError(
            f"beam/primary fails geometry intersection preflight (#999): {result.reason}. "
            "Pass allow_miss=True / --allow-miss only for intentional miss studies. "
            "See docs/adr/ADR-0003-beam-intersection-preflight.md."
        )
    if not ok and allow_miss:
        # Re-tag reason for metadata while accepting the miss.
        return BeamIntersectionResult(
            intersects=result.intersects,
            enters_neg_z_face=result.enters_neg_z_face,
            entry_cm=result.entry_cm,
            exit_cm=result.exit_cm,
            path_length_cm=result.path_length_cm,
            launch_cm=result.launch_cm,
            direction=result.direction,
            reason=f"allowed_miss:{result.reason}",
        )
    return result
