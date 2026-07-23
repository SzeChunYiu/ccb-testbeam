"""PDG parsing, charge, mass, and species labels for HiBeam MC truth.

Unit conventions
----------------
The deployed krakow production MC stores the per-hit ``Sci_bar_Momentum_*``
branches in **GeV/c** (reaudit finding #864; confirmed empirically in
``scripts/single_stave/extract_g4_entry_energies.py``: a proton with
``|p| ~= 0.41`` only yields ``KE ~= 85 MeV`` when read as GeV/c, and ``KE ~= 0``
when wrongly read as MeV/c).  All kinetic-energy helpers in this module return
MeV; use :func:`kinetic_energy_from_branch_momentum` for raw HiBeam branch
values so the GeV/c -> MeV/c conversion happens exactly once.
"""

from __future__ import annotations

import math
from functools import cache

from ccb_mc_validation.exceptions import MCValidationError, UnitValidationError

PDG_NAME: dict[int, str] = {
    2212: "p",
    1000010020: "d",
    1000010030: "t",
    1000020030: "He3",
    1000020040: "alpha",
    2112: "n",
    22: "gamma",
    11: "e-",
    -11: "e+",
    211: "pi+",
    -211: "pi-",
    111: "pi0",
    13: "mu-",
    -13: "mu+",
    321: "K+",
    -321: "K-",
    130: "K_L",
    310: "K_S",
}

#: Vetted rest masses [MeV/c^2].  Anti-particles carry the same mass as their
#: matter counterpart and are listed explicitly so no anti-particle ever falls
#: through to a default.  Source: PDG live review (mass values rounded).
MASS: dict[int, float] = {
    # nucleons
    2212: 938.272,
    2112: 939.565,
    # leptons
    11: 0.510999,
    -11: 0.510999,
    13: 105.658,
    -13: 105.658,
    # mesons
    211: 139.570,
    -211: 139.570,
    111: 134.977,
    321: 493.677,
    -321: 493.677,
    130: 497.611,
    310: 497.611,
    22: 0.0,
    # neutrinos (massless for our purposes)
    12: 0.0,
    14: 0.0,
    16: 0.0,
    -12: 0.0,
    -14: 0.0,
    -16: 0.0,
    # light nuclei
    1000010020: 1875.613,
    1000010030: 2808.921,
    1000020030: 2808.391,
    1000020040: 3727.379,
}

_ELEMENTARY_CHARGE: dict[int, float] = {
    2212: 1.0,
    2112: 0.0,
    22: 0.0,
    11: -1.0,
    -11: 1.0,
    13: -1.0,
    -13: 1.0,
    211: 1.0,
    -211: -1.0,
    111: 0.0,
    130: 0.0,
    310: 0.0,
    321: 1.0,
    -321: -1.0,
    12: 0.0,
    14: 0.0,
    16: 0.0,
    -12: 0.0,
    -14: 0.0,
    -16: 0.0,
}

#: Declared physical units of the HiBeam ``Sci_bar`` truth branches.  This is
#: the schema that callers must honour; ``unknown_pending_validation`` marks a
#: branch whose unit has not yet been tied to simulation metadata.
HIBEAM_BRANCH_UNITS: dict[str, str] = {
    "Sci_bar_Momentum_X": "GeV/c",
    "Sci_bar_Momentum_Y": "GeV/c",
    "Sci_bar_Momentum_Z": "GeV/c",
    "Sci_bar_EDep": "MeV",
    "Sci_bar_Time": "ns",
    "Sci_bar_TrackLength": "unknown_pending_validation",
}

#: Unit of the ``Sci_bar_Momentum_*`` branches in the *deployed krakow MC*.
#: Reaudit #864 established GeV/c (assuming MeV/c gives KE ~= 0).  Callers that
#: read a different production must pass ``momentum_unit`` explicitly.
DEFAULT_MOMENTUM_UNIT: str = "GeV"

_MOMENTUM_TO_MEV_C: dict[str, float] = {
    "MeV": 1.0,
    "GeV": 1000.0,
}

#: Nuclear mass approximation [MeV] per nucleon for nuclei not in :data:`MASS`.
_NUCLEON_MASS_MEV: float = 931.494


@cache
def pdg_charge(pdg: int) -> float:
    """Electric charge in units of *e*; supports nuclei (``10LZZZAAAI``).

    Anti-nuclei are encoded with a negative 10-digit PDG code (e.g.
    anti-deuteron = ``-1000010020``); their charge carries the sign of the
    code, per the PDG nuclear-code convention.
    """
    pdg = int(pdg)
    apdg = abs(pdg)
    if apdg > 1_000_000_000:
        z = (apdg // 10_000) % 1000
        # The sign of a nuclear code distinguishes matter (+) from anti (-).
        return float(z) if pdg >= 0 else -float(z)
    if pdg in _ELEMENTARY_CHARGE:
        return float(_ELEMENTARY_CHARGE[pdg])
    if apdg in _ELEMENTARY_CHARGE:
        return -float(_ELEMENTARY_CHARGE[apdg]) if pdg < 0 else float(_ELEMENTARY_CHARGE[apdg])
    return 0.0


@cache
def is_charged(pdg: int) -> bool:
    """Return True when ``|charge| > 0.5 e``."""
    return abs(pdg_charge(int(pdg))) > 0.5


def species_label(pdg: int) -> str:
    """Short species label for histograms and summaries."""
    return PDG_NAME.get(int(pdg), f"pdg{int(pdg)}")


def mass_of(pdg: int) -> float:
    """Rest mass [MeV/c^2] for a PDG code.

    Nuclei not listed explicitly fall back to ``A * 931.494 MeV`` (a standard
    semi-empirical approximation).  Unknown *elementary* particles raise
    :class:`~ccb_mc_validation.exceptions.MCValidationError` rather than
    silently inheriting the pion mass -- assigning the wrong rest mass
    corrupts every downstream kinetic-energy / range-energy observable, so we
    fail closed.
    """
    pdg = int(pdg)
    if pdg in MASS:
        return MASS[pdg]
    apdg = abs(pdg)
    if apdg > 1_000_000_000:
        a = (apdg // 10) % 1000
        if a <= 0:
            raise MCValidationError(f"malformed nuclear PDG code {pdg}: A=0")
        return a * _NUCLEON_MASS_MEV
    raise MCValidationError(
        f"unknown elementary PDG code {pdg}: no vetted rest mass on file; "
        f"add it to MASS in ccb_mc_validation/truth/pdg.py"
    )


def kinetic_energy_from_momentum(p_mag_mev_c: float, pdg: int) -> float:
    """Relativistic kinetic energy [MeV] from momentum magnitude **already in MeV/c**.

    For raw HiBeam ``Sci_bar_Momentum_*`` values (GeV/c) use
    :func:`kinetic_energy_from_branch_momentum` instead, which performs the
    unit conversion exactly once.
    """
    m = mass_of(pdg)
    pmag = float(p_mag_mev_c)
    return math.sqrt(pmag * pmag + m * m) - m


def momentum_to_mev_c(p_mag: float, unit: str = DEFAULT_MOMENTUM_UNIT) -> float:
    """Convert a HiBeam momentum magnitude to MeV/c.

    Raises :class:`~ccb_mc_validation.exceptions.UnitValidationError` for any
    unit not in :data:`_MOMENTUM_TO_MEV_C` so an ambiguous unit can never
    silently corrupt a kinetic-energy calculation.
    """
    unit = str(unit)
    if unit not in _MOMENTUM_TO_MEV_C:
        raise UnitValidationError(
            f"unknown momentum unit {unit!r}; expected one of {sorted(_MOMENTUM_TO_MEV_C)}"
        )
    return float(p_mag) * _MOMENTUM_TO_MEV_C[unit]


def kinetic_energy_from_branch_momentum(
    p_mag: float,
    pdg: int,
    *,
    momentum_unit: str = DEFAULT_MOMENTUM_UNIT,
) -> float:
    """Relativistic KE [MeV] from a raw HiBeam momentum magnitude.

    Converts the branch value to MeV/c exactly once using ``momentum_unit``
    (krakow MC default = GeV/c, see :data:`DEFAULT_MOMENTUM_UNIT`), then
    computes the kinetic energy via :func:`kinetic_energy_from_momentum`.
    """
    return kinetic_energy_from_momentum(momentum_to_mev_c(p_mag, momentum_unit), pdg)


def parse_pdg(pdg: int) -> dict[str, int | float | str]:
    """Parse a PDG code into structured fields.

    Nuclear codes follow Geant4/G4ParticleTable layout ``10LZZZAAAI`` where
    ``Z`` is atomic number, ``A`` is mass number, and ``I`` is the isomer level.
    """
    pdg = int(pdg)
    apdg = abs(pdg)
    out: dict[str, int | float | str] = {
        "pdg": pdg,
        "label": species_label(pdg),
        "charge_e": pdg_charge(pdg),
        "mass_MeV": mass_of(pdg),
        "charged": is_charged(pdg),
    }
    if apdg > 1_000_000_000:
        out["kind"] = "nucleus"
        out["L"] = apdg // 100_000_000
        out["Z"] = (apdg // 10_000) % 1000
        out["A"] = (apdg // 10) % 1000
        out["isomer"] = apdg % 10
    else:
        out["kind"] = "elementary"
    return out
