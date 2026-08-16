#!/usr/bin/env python3
"""Relativistic two-body elastic p+d kinematics cross-check.

The tool answers a narrow question raised by AF-041/#989: what recoil-deuteron
kinetic energy is implied by a proton of known kinetic energy striking a
deuteron at rest when the outgoing deuteron is observed at a chosen lab angle?

It does *not* model target energy loss, p+d breakup, p+C reactions, detector
acceptance or material transport. Those must be added separately before using
its output as an event-level beam-test prediction.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass

# High-precision reference values adequate for this diagnostic. Production
# analyses should source/version their chosen mass constants explicitly; the
# CLI allows overriding both masses.
DEFAULT_PROTON_MASS_MEV = 938.27208816
DEFAULT_DEUTERON_MASS_MEV = 1875.61294257
C_CM_PER_NS = 29.9792458


@dataclass(frozen=True)
class ElasticSolution:
    projectile_kinetic_in_MeV: float
    recoil_lab_angle_deg: float
    recoil_kinetic_MeV: float
    projectile_kinetic_out_MeV: float
    projectile_lab_angle_deg: float
    recoil_beta: float
    recoil_momentum_MeV_c: float
    energy_closure_MeV: float
    momentum_closure_MeV_c: float


def momentum_from_kinetic(kinetic_MeV: float, mass_MeV: float) -> float:
    if kinetic_MeV < 0 or mass_MeV <= 0:
        raise ValueError("kinetic energy must be >=0 and mass >0")
    energy = mass_MeV + kinetic_MeV
    return math.sqrt(max(0.0, energy * energy - mass_MeV * mass_MeV))


def beta_from_kinetic(kinetic_MeV: float, mass_MeV: float) -> float:
    energy = mass_MeV + kinetic_MeV
    p = momentum_from_kinetic(kinetic_MeV, mass_MeV)
    return p / energy if energy > 0 else 0.0


def _bisect_nonzero_root(func, lo: float, hi: float, iterations: int = 120) -> float:
    flo = func(lo)
    fhi = func(hi)
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if flo * fhi > 0:
        raise ValueError("root is not bracketed")
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        fm = func(mid)
        if fm == 0:
            return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return 0.5 * (lo + hi)


def solve_pd_elastic_recoil_deuteron(
    projectile_kinetic_MeV: float,
    recoil_lab_angle_deg: float,
    *,
    proton_mass_MeV: float = DEFAULT_PROTON_MASS_MEV,
    deuteron_mass_MeV: float = DEFAULT_DEUTERON_MASS_MEV,
) -> ElasticSolution:
    """Solve p+d -> p+d for the non-trivial recoil-deuteron lab solution."""
    if not (0.0 < recoil_lab_angle_deg < 180.0):
        raise ValueError("recoil angle must be strictly between 0 and 180 degrees")
    if projectile_kinetic_MeV <= 0:
        raise ValueError("projectile kinetic energy must be >0")

    theta = math.radians(recoil_lab_angle_deg)
    ep_in = proton_mass_MeV + projectile_kinetic_MeV
    p_in = momentum_from_kinetic(projectile_kinetic_MeV, proton_mass_MeV)
    e_total = ep_in + deuteron_mass_MeV

    # Final proton is the four-momentum remainder after choosing a recoil
    # deuteron momentum q at the requested lab angle. Enforce p_p^2=m_p^2.
    def residual(q: float) -> float:
        ed = math.sqrt(deuteron_mass_MeV**2 + q**2)
        ep_out = e_total - ed
        pp2 = p_in**2 + q**2 - 2.0 * p_in * q * math.cos(theta)
        return ep_out**2 - pp2 - proton_mass_MeV**2

    # q=0 is the trivial no-recoil root. Scan for the first nonzero sign change.
    max_ed = e_total - proton_mass_MeV
    q_max = math.sqrt(max(0.0, max_ed**2 - deuteron_mass_MeV**2))
    eps = max(1e-9, q_max * 1e-10)
    n_scan = 20000
    previous_q = eps
    previous_f = residual(previous_q)
    bracket: tuple[float, float] | None = None
    for i in range(1, n_scan + 1):
        q = eps + (q_max - eps) * i / n_scan
        f = residual(q)
        if previous_f * f < 0 or f == 0:
            bracket = (previous_q, q)
            break
        previous_q, previous_f = q, f
    if bracket is None:
        raise ValueError("no non-trivial elastic recoil solution at this lab angle")

    q = _bisect_nonzero_root(residual, *bracket)
    ed = math.sqrt(deuteron_mass_MeV**2 + q**2)
    td = ed - deuteron_mass_MeV
    ep_out = e_total - ed
    tp_out = ep_out - proton_mass_MeV

    px = -q * math.sin(theta)
    pz = p_in - q * math.cos(theta)
    pp = math.hypot(px, pz)
    proton_angle = math.degrees(math.atan2(abs(px), pz))

    energy_closure = (projectile_kinetic_MeV - td - tp_out)
    # Magnitude of vector momentum closure; should be numerical roundoff.
    recoil_px = q * math.sin(theta)
    recoil_pz = q * math.cos(theta)
    projectile_px = -recoil_px
    projectile_pz = pz
    momentum_closure = math.hypot(projectile_px + recoil_px,
                                  projectile_pz + recoil_pz - p_in)

    return ElasticSolution(
        projectile_kinetic_in_MeV=projectile_kinetic_MeV,
        recoil_lab_angle_deg=recoil_lab_angle_deg,
        recoil_kinetic_MeV=td,
        projectile_kinetic_out_MeV=tp_out,
        projectile_lab_angle_deg=proton_angle,
        recoil_beta=q / ed,
        recoil_momentum_MeV_c=q,
        energy_closure_MeV=energy_closure,
        momentum_closure_MeV_c=momentum_closure,
    )


def tof_ns(distance_cm: float, beta: float) -> float:
    if distance_cm < 0 or not (0.0 < beta < 1.0):
        raise ValueError("distance must be >=0 and beta in (0,1)")
    return distance_cm / (beta * C_CM_PER_NS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--beam-MeV", type=float, default=190.0)
    ap.add_argument("--deuteron-angle-deg", type=float, default=38.0)
    ap.add_argument("--proton-mass-MeV", type=float, default=DEFAULT_PROTON_MASS_MEV)
    ap.add_argument("--deuteron-mass-MeV", type=float, default=DEFAULT_DEUTERON_MASS_MEV)
    ap.add_argument("--distance-cm", type=float, nargs="*", default=[2.0, 4.0, 12.0])
    args = ap.parse_args()

    result = solve_pd_elastic_recoil_deuteron(
        args.beam_MeV,
        args.deuteron_angle_deg,
        proton_mass_MeV=args.proton_mass_MeV,
        deuteron_mass_MeV=args.deuteron_mass_MeV,
    )
    out = asdict(result)
    out["tof_ns"] = {
        str(distance): tof_ns(distance, result.recoil_beta)
        for distance in args.distance_cm
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
