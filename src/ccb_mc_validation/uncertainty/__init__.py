"""Cross-section uncertainty propagation for MC source variation.

Contract IDs (fail-closed):
- NOMINAL_V1: No perturbation (baseline)
- STAT_PERTURB_V1: Gaussian per-node statistical perturbation
- SYST_ENVELOPE_SINUSOIDAL_TAPER: Systematic envelope (10% edges, 20% center)
"""

from .cross_section_perturbation import (
    ContractID,
    UncertaintyVariant,
    perturb_cross_section_nominal,
    perturb_cross_section_statistical,
    perturb_cross_section_systematic,
)

__all__ = [
    "ContractID",
    "UncertaintyVariant",
    "perturb_cross_section_nominal",
    "perturb_cross_section_statistical",
    "perturb_cross_section_systematic",
]
