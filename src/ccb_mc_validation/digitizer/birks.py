"""Birks quenching for heavy ions (minimal implementation)."""

from __future__ import annotations


def birks_quench(edep_mev: float, k_b: float = 0.008, density_g_cm3: float = 1.03) -> float:
    """
    Apply Birks law: S = S0 / (1 + kB * dE/dx).

    Uses edep per unit path as a proxy for dE/dx when only total edep is known.
    """
    dedx_proxy = edep_mev * density_g_cm3
    return edep_mev / (1.0 + k_b * dedx_proxy)
