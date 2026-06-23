"""Tests for PDG charge, mass, and nuclear parsing."""

from __future__ import annotations

from ccb_mc_validation.truth.pdg import (
    is_charged,
    mass_of,
    parse_pdg,
    pdg_charge,
    species_label,
)

PROTON = 2212
DEUTERON = 1000010020


def test_proton_charge_and_mass() -> None:
    assert pdg_charge(PROTON) == 1.0
    assert is_charged(PROTON) is True
    assert mass_of(PROTON) == 938.272
    assert species_label(PROTON) == "p"


def test_deuteron_charge_and_mass() -> None:
    assert pdg_charge(DEUTERON) == 1.0
    assert is_charged(DEUTERON) is True
    assert mass_of(DEUTERON) == 1875.613
    assert species_label(DEUTERON) == "d"


def test_parse_pdg_nuclear_code() -> None:
    parsed = parse_pdg(DEUTERON)
    assert parsed["kind"] == "nucleus"
    assert parsed["Z"] == 1
    assert parsed["A"] == 2
    assert parsed["charge_e"] == 1.0
    assert parsed["mass_MeV"] == 1875.613
