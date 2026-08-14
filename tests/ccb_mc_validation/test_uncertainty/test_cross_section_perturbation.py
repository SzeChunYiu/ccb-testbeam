import pytest
from ccb_mc_validation.uncertainty import (
    ContractID,
    perturb_cross_section_nominal,
    perturb_cross_section_statistical,
    perturb_cross_section_systematic,
)

ANGLES_DEG = [26.49, 31.1, 35.69, 40.24, 44.75]
SIGMA = [6.005, 4.383, 3.123, 2.363, 1.71]
STAT_UNC = [0.011, 0.007, 0.009, 0.005, 0.008]

class TestNominal:
    def test_returns_nominal_variant(self):
        variant = perturb_cross_section_nominal(ANGLES_DEG, SIGMA)
        assert variant.contract_id == ContractID.NOMINAL_V1
        assert variant.angles_deg == ANGLES_DEG
        assert variant.sigma_perturbed == SIGMA

class TestStatistical:
    def test_reproducibility_same_seed(self):
        v1 = perturb_cross_section_statistical(ANGLES_DEG, SIGMA, STAT_UNC, seed=42)
        v2 = perturb_cross_section_statistical(ANGLES_DEG, SIGMA, STAT_UNC, seed=42)
        assert v1.sigma_perturbed == v2.sigma_perturbed

    def test_contract_id_present(self):
        variant = perturb_cross_section_statistical(ANGLES_DEG, SIGMA, STAT_UNC, seed=42)
        assert variant.contract_id == ContractID.STAT_PERTURB_V1

    def test_fail_closed_non_positive_sigma(self):
        with pytest.raises(ValueError, match="non-positive"):
            perturb_cross_section_statistical(ANGLES_DEG, [0.0] * 5, STAT_UNC, seed=42)

    def test_no_variance_zero_uncertainty(self):
        zero_unc = [0.0] * 5
        variant = perturb_cross_section_statistical(ANGLES_DEG, SIGMA, zero_unc, seed=42)
        for s_orig, s_pert in zip(SIGMA, variant.sigma_perturbed):
            assert abs(s_pert - s_orig) < 1e-10

class TestSystematic:
    def test_contract_id_present(self):
        variant = perturb_cross_section_systematic(ANGLES_DEG, SIGMA, sign="plus")
        assert variant.contract_id == ContractID.SYST_ENVELOPE_SINUSOIDAL_TAPER

    def test_plus_envelope_increases_sigma(self):
        variant = perturb_cross_section_systematic(ANGLES_DEG, SIGMA, sign="plus")
        for s_orig, s_pert in zip(SIGMA, variant.sigma_perturbed):
            assert s_pert > s_orig

    def test_fail_closed_invalid_sign(self):
        with pytest.raises(ValueError, match="Invalid sign"):
            perturb_cross_section_systematic(ANGLES_DEG, SIGMA, sign="invalid")
