"""Species/dE/dx-dependent Birks scintillation quenching (Phase 4).

Replaces the dimensionally meaningless Phase-0 stub (EXTERNAL_REVIEW_2026-07-02.md
F2.2: it used ``edep * density`` — units MeV·g/cm³ — as a "dE/dx proxy", so the
quench depended on how much energy a hit happened to deposit, not on the actual
ionisation density).  The physically correct per-hit form implemented here is

    L = edep / (1 + kB * dE/dx)                      [first-order Birks law]

with dE/dx in MeV/cm and kB in cm/MeV.

Birks constant (documented):
    kB = 0.0126 g MeV^-1 cm^-2  — the standard polystyrene-based plastic
    scintillator value (Craun & Smith, NIM 80 (1970) 239, for NE-102;
    adopted as the GEANT4 default for polystyrene scintillators).
    Divided by the polystyrene density rho = 1.06 g/cm^3:
        kB = 0.0126 / 1.06 = 0.011887 cm/MeV.

dE/dx source, in resolution order (per hit):
  1. an explicit ``dedx_mev_per_cm`` measured from truth
     (edep_hit / step_length; the mc02 builder derives step lengths from
     consecutive-hit differences of the CUMULATIVE ``Sci_bar_TrackLength``
     branch — verified 2026-07-04 on output_krakow_1M.root: TrackLength is
     cumulative in cm, ~112 cm at B-arm entry for target primaries, ~20 um
     for in-bar alpha recoils, so the raw branch value is usable directly
     only for the first hit of locally created tracks);
  2. a species+energy lookup ``dedx_polystyrene_mev_per_cm(pdg, ekin_mev)``;
  3. the species lookup at a documented testbeam-typical default energy;
  4. a MIP-like default (2.2 MeV/cm) when nothing is known — this keeps
     legacy single-argument calls ``birks_quench(edep)`` well-defined and
     nearly quench-free (~2.5%), matching the old no-information behaviour
     as closely as physics allows.

Stopping-power table (documented sources):
    The proton table below is anchored on NIST PSTAR collision stopping
    powers for liquid water (well-tabulated reference values, MeV cm^2/g)
    scaled to polystyrene by the PSTAR polystyrene/water mass-stopping-power
    ratio ~0.976 (Z/A 0.5377 vs 0.5551, partially offset by the lower mean
    excitation energy I = 68.7 eV vs 75 eV) and multiplied by
    rho = 1.06 g/cm^3.  Accuracy of the anchors is a few percent — ample for
    a quench correction that enters as 1/(1 + kB*dE/dx).

    Other species use the standard range-energy scaling laws:
      * same charge, same velocity: dE/dx_d(E) = dE/dx_p(E * m_p/m_d)
        (deuteron, triton);
      * charge-squared scaling at the same velocity for ions:
        dE/dx_ion(E) = Z_eff^2 * dE/dx_p(E * m_p/m_ion),
        with the Barkas/Ziegler effective charge
        Z_eff = Z * (1 - exp(-125 * beta / Z^(2/3)))
        which suppresses the bare-Z^2 overestimate for slow ions (essential
        for the few-MeV C12 recoils: bare 6^2 = 36 overestimates SRIM by
        ~3x at 5 MeV, Z_eff^2 ~ 16 is within ~40%).
    Cross-checks: alpha at 5 MeV -> ~890 MeV cm^2/g water-equivalent here vs
    ASTAR ~890; C12 at 5 MeV -> ~7e3 MeV/cm here vs SRIM ~5e3 (the quench
    factor is saturated in this regime, so the residual effective-charge
    error is second-order for the light output).
"""

from __future__ import annotations

import math

import numpy as np

from ccb_mc_validation.truth.pdg import mass_of, parse_pdg

# --- constants (documented in the module docstring) --------------------------
KB_G_PER_MEV_CM2 = 0.0126          # Craun & Smith / GEANT4 polystyrene kB
POLYSTYRENE_DENSITY_G_CM3 = 1.06
KB_CM_PER_MEV = KB_G_PER_MEV_CM2 / POLYSTYRENE_DENSITY_G_CM3  # 0.011887 cm/MeV

# MIP-like fallback: minimum-ionising singly-charged particle in polystyrene
# (~2.1 MeV cm^2/g * 1.06 g/cm^3).  Used only when neither dE/dx nor species
# information is available.
MIP_DEDX_MEV_PER_CM = 2.2

# Proton collision stopping power in POLYSTYRENE, MeV/cm.
# PSTAR(water) anchors * 0.976 (polystyrene/water mass ratio) * 1.06 g/cm^3.
_PROTON_E_MEV = np.array(
    [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 150.0, 200.0, 300.0, 1000.0, 2000.0]
)
_PROTON_DEDX_MEV_PER_CM = np.array(
    [
        442.8,   # 0.5 MeV   (PSTAR water 428.0 MeV cm^2/g)
        269.8,   # 1 MeV     (water 260.8)
        164.6,   # 2 MeV     (water 159.1)
        81.8,    # 5 MeV     (water 79.1)
        47.2,    # 10 MeV    (water 45.7)
        27.0,    # 20 MeV    (water 26.1)
        12.9,    # 50 MeV    (water 12.45)
        7.54,    # 100 MeV   (water 7.289)
        5.63,    # 150 MeV   (water 5.445)
        4.65,    # 200 MeV   (water 4.492)
        3.64,    # 300 MeV   (water 3.52)
        2.29,    # 1 GeV     (water ~2.21)
        2.11,    # 2 GeV     (water ~2.04, near-MIP plateau)
    ]
)
_LOG_E = np.log(_PROTON_E_MEV)
_LOG_S = np.log(_PROTON_DEDX_MEV_PER_CM)

PROTON_MASS_MEV = 938.272

# Testbeam-typical kinetic energies (MeV) used when a species is known but the
# per-hit energy is not (documented defaults; see MV1/MV2 truth spectra and
# pd-elastic kinematics: ~150 MeV forward protons, ~105 MeV conjugate
# deuterons; alpha/C12 are target/bar recoils at a few MeV):
DEFAULT_EKIN_MEV: dict[int, float] = {
    2212: 150.0,        # proton (pd-elastic forward proton)
    1000010020: 105.0,  # deuteron (pd-elastic conjugate)
    1000010030: 105.0,  # triton (breakup, same scale as d)
    1000020030: 10.0,   # He3
    1000020040: 5.0,    # alpha (recoil / breakup)
    1000060120: 3.0,    # C12 (elastic carbon recoil, few MeV)
}


def _proton_dedx_mev_per_cm(ekin_mev: float) -> float:
    """Log-log interpolated proton stopping power in polystyrene [MeV/cm]."""
    e = min(max(float(ekin_mev), float(_PROTON_E_MEV[0])), float(_PROTON_E_MEV[-1]))
    return float(np.exp(np.interp(math.log(e), _LOG_E, _LOG_S)))


def _effective_charge(z: float, beta: float) -> float:
    """Barkas/Ziegler effective charge Z_eff = Z(1 - exp(-125 beta / Z^(2/3)))."""
    if z <= 0.0 or beta <= 0.0:
        return 0.0
    return z * (1.0 - math.exp(-125.0 * beta / z ** (2.0 / 3.0)))


def dedx_polystyrene_mev_per_cm(pdg: int, ekin_mev: float | None = None) -> float:
    """Species+energy stopping-power lookup in polystyrene [MeV/cm].

    Supported directly: p, d, t, He3, alpha, C12, and any G4 nuclear PDG code
    (``10LZZZAAAI``) via Z_eff^2-scaled proton stopping at equal velocity.
    Electrons/muons/pions and neutrals fall back to the MIP-like value (their
    quench is negligible, which is physically the right scale for e/mu/pi
    at these energies).  When ``ekin_mev`` is None/invalid a documented
    testbeam-typical default energy is used.
    """
    pdg = int(pdg)
    info = parse_pdg(pdg)
    z = abs(float(info["charge_e"]))
    if z < 0.5:
        return MIP_DEDX_MEV_PER_CM
    mass = mass_of(pdg)
    if ekin_mev is None or not np.isfinite(ekin_mev) or ekin_mev <= 0.0:
        default = DEFAULT_EKIN_MEV.get(pdg)
        if default is None:
            if info.get("kind") == "nucleus":
                # generic ion default: 1 MeV/u (recoil regime)
                default = float(info["A"])
            else:
                return MIP_DEDX_MEV_PER_CM
        ekin_mev = default
    ekin_mev = float(ekin_mev)
    if pdg == 2212:
        return _proton_dedx_mev_per_cm(ekin_mev)
    if info.get("kind") != "nucleus":
        # charged elementary (e/mu/pi/K): near-MIP at testbeam energies
        return MIP_DEDX_MEV_PER_CM
    # same-velocity proton-equivalent kinetic energy
    e_p = ekin_mev * PROTON_MASS_MEV / max(mass, 1.0)
    s_p = _proton_dedx_mev_per_cm(e_p)
    # relativistic beta of the ion for the effective-charge correction
    gamma = 1.0 + ekin_mev / max(mass, 1.0)
    beta = math.sqrt(max(1.0 - 1.0 / (gamma * gamma), 1e-12))
    z_eff = _effective_charge(z, beta)
    return float(z_eff * z_eff * s_p)


def birks_quench(
    edep_mev: float,
    dedx_mev_per_cm: float | None = None,
    k_b_cm_per_mev: float = KB_CM_PER_MEV,
    *,
    pdg: int | None = None,
    ekin_mev: float | None = None,
) -> float:
    """First-order Birks law: light = edep / (1 + kB * dE/dx).

    ``dedx_mev_per_cm`` (truth-measured, MeV/cm) wins when given and finite;
    otherwise the species+energy lookup is used; otherwise a MIP-like default
    (legacy single-argument calls quench by only ~2.5%).
    ``k_b_cm_per_mev = 0`` conserves edep exactly (unit-tested).
    """
    edep = float(edep_mev)
    if edep <= 0.0:
        return 0.0
    if dedx_mev_per_cm is not None and np.isfinite(dedx_mev_per_cm) and dedx_mev_per_cm > 0.0:
        dedx = float(dedx_mev_per_cm)
    elif pdg is not None and int(pdg) != 0:
        dedx = dedx_polystyrene_mev_per_cm(int(pdg), ekin_mev)
    else:
        dedx = MIP_DEDX_MEV_PER_CM
    return edep / (1.0 + float(k_b_cm_per_mev) * dedx)
