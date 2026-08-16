"""Cross-section perturbation for uncertainty propagation.

Implements statistical and systematic envelope perturbations with fail-closed
contract IDs per issue #1179.
"""

from enum import Enum
from dataclasses import dataclass
import math
from typing import Literal


class ContractID(str, Enum):
    NOMINAL_V1 = "NOMINAL_V1"
    STAT_PERTURB_V1 = "STAT_PERTURB_V1"
    SYST_ENVELOPE_SINUSOIDAL_TAPER = "SYST_ENVELOPE_SINUSOIDAL_TAPER"


@dataclass
class UncertaintyVariant:
    contract_id: ContractID
    angles_deg: list[float]
    sigma_perturbed: list[float]
    seed: int | None
    metadata: dict


def perturb_cross_section_nominal(angles_deg, sigma):
    if len(angles_deg) != len(sigma):
        raise ValueError(f"Length mismatch: {len(angles_deg)} vs {len(sigma)}")
    return UncertaintyVariant(
        contract_id=ContractID.NOMINAL_V1,
        angles_deg=list(angles_deg),
        sigma_perturbed=list(sigma),
        seed=None,
        metadata={"perturbation": "none", "description": "Nominal (no perturbation)"},
    )


def perturb_cross_section_statistical(angles_deg, sigma, stat_uncertainty, seed):
    if len(angles_deg) != len(sigma) or len(angles_deg) != len(stat_uncertainty):
        raise ValueError(f"Length mismatch")
    import random
    rng = random.Random(seed)
    sigma_perturbed = []
    for i, (s_i, u_i) in enumerate(zip(sigma, stat_uncertainty)):
        if s_i <= 0:
            raise ValueError(f"Node {i}: non-positive sigma")
        if u_i < 0:
            raise ValueError(f"Node {i}: negative stat_uncertainty")
        s_pert = rng.gauss(s_i, u_i)
        if s_pert <= 0:
            raise ValueError(f"Node {i}: perturbed sigma non-positive {s_pert}")
        sigma_perturbed.append(s_pert)
    return UncertaintyVariant(
        contract_id=ContractID.STAT_PERTURB_V1,
        angles_deg=list(angles_deg),
        sigma_perturbed=sigma_perturbed,
        seed=seed,
        metadata={"perturbation": "gaussian_per_node", "n_nodes": len(angles_deg)},
    )


def perturb_cross_section_systematic(angles_deg, sigma, sign="plus"):
    if len(angles_deg) != len(sigma):
        raise ValueError(f"Length mismatch")
    if sign not in ("plus", "minus"):
        raise ValueError(f"Invalid sign: {sign}")
    theta_min = math.radians(angles_deg[0])
    theta_max = math.radians(angles_deg[-1])
    sigma_perturbed = []
    for theta_deg, s_i in zip(angles_deg, sigma):
        if s_i <= 0:
            raise ValueError(f"Non-positive sigma at {theta_deg}")
        theta_rad = math.radians(theta_deg)
        normalized = (theta_rad - theta_min) / (theta_max - theta_min)
        fractional = 0.10 + 0.10 * math.sin(math.pi * normalized)
        if sign == "plus":
            s_pert = s_i * (1.0 + fractional)
        else:
            s_pert = s_i * (1.0 - fractional)
        if s_pert <= 0:
            raise ValueError(f"Perturbed sigma non-positive {s_pert}")
        sigma_perturbed.append(s_pert)
    return UncertaintyVariant(
        contract_id=ContractID.SYST_ENVELOPE_SINUSOIDAL_TAPER,
        angles_deg=list(angles_deg),
        sigma_perturbed=sigma_perturbed,
        seed=None,
        metadata={"perturbation": "systematic_envelope", "sign": sign},
    )
