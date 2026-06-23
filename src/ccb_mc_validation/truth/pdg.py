"""PDG parsing, charge, mass, and species labels for HiBeam MC truth."""

from __future__ import annotations

from functools import lru_cache
import math

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
    13: "mu-",
    -13: "mu+",
}

MASS: dict[int, float] = {
    2212: 938.272,
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


@lru_cache(maxsize=None)
def pdg_charge(pdg: int) -> float:
    """Electric charge in units of *e*; supports nuclei (10-digit ``100ZZZAAAI``)."""
    pdg = int(pdg)
    apdg = abs(pdg)
    if apdg > 1_000_000_000:
        z = (apdg // 10_000) % 1000
        return float(z)
    if pdg in _ELEMENTARY_CHARGE:
        return float(_ELEMENTARY_CHARGE[pdg])
    if apdg in _ELEMENTARY_CHARGE:
        return -float(_ELEMENTARY_CHARGE[apdg]) if pdg < 0 else float(_ELEMENTARY_CHARGE[apdg])
    return 0.0


@lru_cache(maxsize=None)
def is_charged(pdg: int) -> bool:
    """Return True when ``|charge| > 0.5 e``."""
    return abs(pdg_charge(int(pdg))) > 0.5


def species_label(pdg: int) -> str:
    """Short species label for histograms and summaries."""
    return PDG_NAME.get(int(pdg), f"pdg{int(pdg)}")


def mass_of(pdg: int) -> float:
    """Rest mass [MeV] for a PDG code."""
    pdg = int(pdg)
    if pdg in MASS:
        return MASS[pdg]
    apdg = abs(pdg)
    if apdg > 1_000_000_000:
        a = (apdg // 10) % 1000
        return a * 931.494
    if abs(pdg) == 11:
        return 0.511
    return 139.57


def kinetic_energy_from_momentum(p_mag: float, pdg: int) -> float:
    """Relativistic kinetic energy [MeV] from momentum magnitude [MeV/c]."""
    m = mass_of(pdg)
    pmag = float(p_mag)
    return math.sqrt(pmag * pmag + m * m) - m


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
