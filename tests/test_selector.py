"""Known-answer fixture tests for the versioned selector module (Issue #1109).

Each test exercises a pure function over a synthetic waveform array so the
test passes before any ROOT data arrives. Waveform fixtures are hand-crafted
to exercise every :class:`PedestalValidity` state and every estimator method.
"""
from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.selector import (
    AmplitudeResult,
    PedestalResult,
    PedestalValidity,
    classify_pedestal_validity,
    estimate_pedestal_dynamic_range,
    estimate_pedestal_early_robust,
    estimate_pedestal_rolling_min,
    estimate_pedestal_v1,
    select_amplitude,
    selectors_available,
)

# ---------------------------------------------------------------------------
# Waveform fixtures — one per PedestalValidity state
# ---------------------------------------------------------------------------
# All waveforms are 18 samples (B-stack, 8 channels), the standard length.
# Each fixture is a (waveform, expected_pedestal, expected_validity) tuple
# where expected_pedestal is the desired pedestal the estimator should find
# and expected_validity is the state classify_pedestal_validity should return
# for the v1 estimator (first-four median).


@pytest.fixture
def quiet_waveform() -> np.ndarray:
    """H0: quiet baseline, pulse centered at sample 9.
    First four samples [100, 100, 100, 100] → median=100, peak=5000, A=4900.
    """
    w = np.full(18, 100.0, dtype=float)
    w[9] = 5000.0
    w[8] = 2500.0
    w[10] = 2500.0
    return w


@pytest.fixture
def early_active_waveform() -> np.ndarray:
    """H1: early pulse onset in samples 0-3.
    w[0:4] = [100, 400, 1200, 800] → median=(400+800)/2=600, first-four median
    overestimates the true baseline (100). The pulse peak at sample 9 is 5000,
    so A4 = 5000 - 600 = 4400 vs true A = 5000 - 100 = 4900. A bias of 500 ADC.
    """
    w = np.full(18, 100.0, dtype=float)
    w[0] = 100.0
    w[1] = 400.0
    w[2] = 1200.0
    w[3] = 800.0
    w[9] = 5000.0
    w[8] = 3000.0
    w[10] = 2000.0
    return w


@pytest.fixture
def recovery_waveform() -> np.ndarray:
    """H2: prior-pulse recovery tail.
    First four samples [800, 600, 400, 200] are falling (recovery tail).
    Later samples [100, 100, 100, 100] are quiet. The first-four median is
    (600+400)/2=500, overestimating the true baseline at 100.
    """
    w = np.full(18, 100.0, dtype=float)
    w[0:4] = [800.0, 600.0, 400.0, 200.0]
    w[9] = 5000.0
    w[8] = 3000.0
    w[10] = 2000.0
    return w


@pytest.fixture
def bipolar_waveform() -> np.ndarray:
    """H3: strong negative excursion before the positive pulse.
    First four samples are quiet [100, 100, 100, 100], then a negative dip
    to -2000 ADC at sample 5, followed by a positive pulse at sample 9.
    The minimum of the waveform (-2000) is far below the pedestal (100),
    so the polarity is ambiguous.
    """
    w = np.full(18, 100.0, dtype=float)
    w[5] = -2000.0
    w[6] = -1000.0
    w[9] = 5000.0
    w[8] = 3000.0
    w[10] = 2000.0
    return w


@pytest.fixture
def jagged_waveform() -> np.ndarray:
    """H4: a single dropout spike in sample 2 of the first four.
    w[0:4] = [100, 100, 1500, 100] → the spike at sample 2 is a lone outlier.
    The median is (100+100)/2=100, which is correct, but the gap between the
    highest ordered values (1500 vs 100) is >150, so it's classified JAGGED.
    Peak at sample 9 is 5000, A4 = 5000 - 100 = 4900.
    """
    w = np.full(18, 100.0, dtype=float)
    w[2] = 1500.0
    w[9] = 5000.0
    w[8] = 3000.0
    w[10] = 2000.0
    return w


@pytest.fixture
def saturated_waveform() -> np.ndarray:
    """H6: waveform clips at the 14-bit ADC max (16383).
    First four samples are quiet [100, 100, 100, 100], but the pulse at
    sample 9 hits the saturation code.
    """
    w = np.full(18, 100.0, dtype=float)
    w[9] = 16383.0
    w[8] = 8000.0
    w[10] = 9000.0
    return w


@pytest.fixture
def noisy_waveform() -> np.ndarray:
    """H5/H7/H8: very noisy early region with no quiet baseline.
    The first four samples span [100, 200, 800, 900] → early_span=800.
    The dynamic range is ~800 (peak at 900, min at 100), so
    early_span / dyn ≈ 1.0 > 0.9 → NO_PEDESTAL_IDENTIFIABLE.
    """
    w = np.full(18, 100.0, dtype=float)
    w[0:4] = [100.0, 200.0, 800.0, 900.0]
    w[9] = 900.0
    return w


# ===================================================================
# Tests: PedestalValidity enum
# ===================================================================


class TestPedestalValidity:
    def test_seven_states(self) -> None:
        assert len(PedestalValidity) == 7

    def test_quiet_valid_is_only_valid(self) -> None:
        for state in PedestalValidity:
            valid = state == PedestalValidity.QUIET_VALID
            if state.name == "QUIET_VALID":
                continue
            assert not valid, f"{state} should NOT be QUIET_VALID"

    def test_str_values(self) -> None:
        assert PedestalValidity.QUIET_VALID.value == "QUIET_VALID"
        assert PedestalValidity.EARLY_ACTIVE.value == "EARLY_ACTIVE"


# ===================================================================
# Tests: PedestalResult dataclass
# ===================================================================


class TestPedestalResult:
    def test_defaults(self) -> None:
        r = PedestalResult(method="test", validity=PedestalValidity.QUIET_VALID)
        assert np.isnan(r.pedestal_adc)
        assert r.first_four_samples.size == 0
        assert r.full_waveform.size == 0

    def test_roundtrip(self) -> None:
        r = PedestalResult(
            method="v1",
            validity=PedestalValidity.EARLY_ACTIVE,
            pedestal_adc=123.4,
            first_four_samples=np.array([10.0, 20.0, 30.0, 40.0]),
            full_waveform=np.arange(18.0),
        )
        assert r.method == "v1"
        assert r.validity == PedestalValidity.EARLY_ACTIVE
        assert r.pedestal_adc == 123.4
        assert r.first_four_samples.tolist() == [10.0, 20.0, 30.0, 40.0]
        assert r.full_waveform.tolist() == list(range(18))


# ===================================================================
# Tests: AmplitudeResult dataclass
# ===================================================================


class TestAmplitudeResult:
    def test_selected_above_cut(self) -> None:
        ped = PedestalResult(method="v1", validity=PedestalValidity.QUIET_VALID, pedestal_adc=100.0)
        r = AmplitudeResult(
            method="v1",
            amplitude_adc=4900.0,
            pedestal=ped,
            selected=True,
            cut_adc=1000.0,
        )
        assert r.selected is True
        assert r.validity == PedestalValidity.QUIET_VALID

    def test_selected_below_cut(self) -> None:
        ped = PedestalResult(method="v1", validity=PedestalValidity.QUIET_VALID, pedestal_adc=100.0)
        r = AmplitudeResult(
            method="v1",
            amplitude_adc=500.0,
            pedestal=ped,
            selected=False,
            cut_adc=1000.0,
        )
        assert r.selected is False

    def test_validity_proxy(self) -> None:
        ped = PedestalResult(method="v1", validity=PedestalValidity.EARLY_ACTIVE, pedestal_adc=100.0)
        r = AmplitudeResult(
            method="v1",
            amplitude_adc=4900.0,
            pedestal=ped,
            selected=True,
            cut_adc=1000.0,
        )
        assert r.validity == PedestalValidity.EARLY_ACTIVE


# ===================================================================
# Tests: estimate_pedestal_v1 (historical, immutable)
# ===================================================================


class TestEstimatePedestalV1:
    def test_quiet_waveform(self, quiet_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(quiet_waveform)
        assert r.method == "v1_first_four_median"
        assert r.pedestal_adc == 100.0
        assert r.validity == PedestalValidity.QUIET_VALID
        assert r.first_four_samples.tolist() == [100.0, 100.0, 100.0, 100.0]

    def test_early_active_waveform(self, early_active_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(early_active_waveform)
        # Median of [100, 400, 1200, 800] = (400 + 800) / 2 = 600
        assert r.pedestal_adc == 600.0
        assert r.validity == PedestalValidity.EARLY_ACTIVE

    def test_recovery_waveform(self, recovery_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(recovery_waveform)
        # Median of [800, 600, 400, 200] = (600 + 400) / 2 = 500
        assert r.pedestal_adc == 500.0
        assert r.validity == PedestalValidity.RECOVERY_CONTAMINATED

    def test_bipolar_waveform(self, bipolar_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(bipolar_waveform)
        assert r.validity == PedestalValidity.BIPOLAR_OR_POLARITY_UNKNOWN

    def test_jagged_waveform(self, jagged_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(jagged_waveform)
        # Median of [100, 100, 1500, 100] = (100 + 100) / 2 = 100
        assert r.pedestal_adc == 100.0
        assert r.validity == PedestalValidity.JAGGED

    def test_saturated_waveform(self, saturated_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(saturated_waveform)
        assert r.validity == PedestalValidity.SATURATED

    def test_noisy_waveform(self, noisy_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(noisy_waveform)
        assert r.validity == PedestalValidity.NO_PEDESTAL_IDENTIFIABLE

    def test_first_four_samples(self, quiet_waveform: np.ndarray) -> None:
        r = estimate_pedestal_v1(quiet_waveform)
        assert r.first_four_samples.shape == (4,)
        assert r.full_waveform.shape == (18,)

    def test_method_immutable(self) -> None:
        """The v1 estimator must always return the same method string."""
        w = np.full(18, 100.0, dtype=float)
        r = estimate_pedestal_v1(w)
        assert r.method == "v1_first_four_median"


# ===================================================================
# Tests: Candidate estimators
# ===================================================================


class TestEstimatePedestalDynamicRange:
    def test_quiet_waveform(self, quiet_waveform: np.ndarray) -> None:
        r = estimate_pedestal_dynamic_range(quiet_waveform)
        assert r.method == "dynamic_range"
        assert r.pedestal_adc == 100.0  # min of the waveform
        assert r.validity == PedestalValidity.QUIET_VALID

    def test_early_active_waveform(self, early_active_waveform: np.ndarray) -> None:
        r = estimate_pedestal_dynamic_range(early_active_waveform)
        assert r.pedestal_adc == 100.0  # min = true baseline
        assert r.validity == PedestalValidity.QUIET_VALID

    def test_saturated_waveform(self, saturated_waveform: np.ndarray) -> None:
        r = estimate_pedestal_dynamic_range(saturated_waveform)
        assert r.validity == PedestalValidity.SATURATED

    def test_bipolar_waveform(self, bipolar_waveform: np.ndarray) -> None:
        r = estimate_pedestal_dynamic_range(bipolar_waveform)
        # min = -2000 (the bipolar dip), classified QUIET_VALID because
        # the dynamic-range estimator trusts the minimum regardless of polarity
        assert r.pedestal_adc == -2000.0
        assert r.validity == PedestalValidity.QUIET_VALID


class TestEstimatePedestalRollingMin:
    def test_quiet_waveform(self, quiet_waveform: np.ndarray) -> None:
        r = estimate_pedestal_rolling_min(quiet_waveform)
        assert r.pedestal_adc == 100.0
        assert r.validity == PedestalValidity.QUIET_VALID

    def test_early_active_waveform(self, early_active_waveform: np.ndarray) -> None:
        r = estimate_pedestal_rolling_min(early_active_waveform)
        assert r.pedestal_adc == 100.0  # robust to early pulse
        assert r.validity == PedestalValidity.QUIET_VALID

    def test_recovery_waveform(self, recovery_waveform: np.ndarray) -> None:
        r = estimate_pedestal_rolling_min(recovery_waveform)
        assert r.pedestal_adc == 100.0  # robust to recovery tail
        assert r.validity == PedestalValidity.QUIET_VALID

    def test_bipolar_waveform(self, bipolar_waveform: np.ndarray) -> None:
        r = estimate_pedestal_rolling_min(bipolar_waveform)
        assert r.pedestal_adc == -2000.0  # follows the negative dip
        assert r.validity == PedestalValidity.BIPOLAR_OR_POLARITY_UNKNOWN


class TestEstimatePedestalEarlyRobust:
    def test_quiet_waveform(self, quiet_waveform: np.ndarray) -> None:
        r = estimate_pedestal_early_robust(quiet_waveform)
        # Early-window P10 of quiet first-four [100,100,100,100]
        assert r.pedestal_adc == 100.0
        assert r.validity == PedestalValidity.QUIET_VALID

    def test_uses_early_window_not_full_waveform(self) -> None:
        """#1137: late negative undershoot must not pull the early-window P10."""
        w = np.full(18, 100.0, dtype=float)
        w[0:4] = [100.0, 100.0, 100.0, 100.0]
        w[15:] = -5000.0  # late bipolar contamination of the full window
        r = estimate_pedestal_early_robust(w)
        assert r.pedestal_adc == 100.0

    def test_early_active_waveform(self, early_active_waveform: np.ndarray) -> None:
        r = estimate_pedestal_early_robust(early_active_waveform)
        # Early window is contaminated; P10 of [100,400,1200,800] is not the
        # quiet baseline, and validity must not claim QUIET_VALID (#1137).
        assert r.pedestal_adc != 100.0
        assert r.validity == PedestalValidity.EARLY_ACTIVE

    def test_noisy_waveform(self, noisy_waveform: np.ndarray) -> None:
        r = estimate_pedestal_early_robust(noisy_waveform)
        assert r.validity != PedestalValidity.QUIET_VALID


# ===================================================================
# Tests: classify_pedestal_validity — direct classification
# ===================================================================


class TestClassifyPedestalValidity:
    def test_empty_first_four(self) -> None:
        val = classify_pedestal_validity(np.array([]), np.array([]), 0.0)
        assert val == PedestalValidity.NO_PEDESTAL_IDENTIFIABLE

    def test_quiet(self, quiet_waveform: np.ndarray) -> None:
        val = classify_pedestal_validity(quiet_waveform, quiet_waveform[0:4], 100.0)
        assert val == PedestalValidity.QUIET_VALID

    def test_early_active(self, early_active_waveform: np.ndarray) -> None:
        first_four = early_active_waveform[0:4]
        val = classify_pedestal_validity(early_active_waveform, first_four, 100.0)
        assert val == PedestalValidity.EARLY_ACTIVE

    def test_recovery(self, recovery_waveform: np.ndarray) -> None:
        first_four = recovery_waveform[0:4]
        val = classify_pedestal_validity(recovery_waveform, first_four, 100.0)
        assert val == PedestalValidity.RECOVERY_CONTAMINATED

    def test_bipolar(self, bipolar_waveform: np.ndarray) -> None:
        first_four = bipolar_waveform[0:4]
        val = classify_pedestal_validity(bipolar_waveform, first_four, 100.0)
        assert val == PedestalValidity.BIPOLAR_OR_POLARITY_UNKNOWN

    def test_jagged(self, jagged_waveform: np.ndarray) -> None:
        first_four = jagged_waveform[0:4]
        val = classify_pedestal_validity(jagged_waveform, first_four, 100.0)
        assert val == PedestalValidity.JAGGED

    def test_saturated(self, saturated_waveform: np.ndarray) -> None:
        first_four = saturated_waveform[0:4]
        val = classify_pedestal_validity(saturated_waveform, first_four, 100.0)
        assert val == PedestalValidity.SATURATED

    def test_noisy(self, noisy_waveform: np.ndarray) -> None:
        first_four = noisy_waveform[0:4]
        val = classify_pedestal_validity(noisy_waveform, first_four, 100.0)
        assert val == PedestalValidity.NO_PEDESTAL_IDENTIFIABLE

    def test_saturation_priority(self, saturated_waveform: np.ndarray) -> None:
        """Saturation (H6) is checked first and should win even if the
        waveform also exhibits early activity."""
        w = saturated_waveform.copy()
        w[1] = 500.0  # add early activity
        val = classify_pedestal_validity(w, w[0:4], 100.0)
        assert val == PedestalValidity.SATURATED

    def test_bipolar_priority(self, bipolar_waveform: np.ndarray) -> None:
        """Bipolar (H3) is checked before early-activity."""
        w = bipolar_waveform.copy()
        w[1] = 500.0  # also has early activity
        val = classify_pedestal_validity(w, w[0:4], 100.0)
        assert val == PedestalValidity.BIPOLAR_OR_POLARITY_UNKNOWN


# ===================================================================
# Tests: select_amplitude pipeline
# ===================================================================


class TestSelectAmplitude:
    def test_v1_quiet_selected(self, quiet_waveform: np.ndarray) -> None:
        r = select_amplitude(quiet_waveform, cut_adc=1000.0, method="v1")
        assert r.method == "v1"
        assert r.amplitude_adc == 4900.0  # 5000 - 100
        assert r.selected is True
        assert r.cut_adc == 1000.0

    def test_v1_quiet_below_cut(self, quiet_waveform: np.ndarray) -> None:
        r = select_amplitude(quiet_waveform, cut_adc=6000.0, method="v1")
        assert r.selected is False

    def test_v1_early_active_selected(self, early_active_waveform: np.ndarray) -> None:
        r = select_amplitude(early_active_waveform, cut_adc=1000.0, method="v1")
        # A4 = 5000 - 600 = 4400, still above 1000 cut
        assert r.amplitude_adc == 4400.0
        assert r.selected is True
        assert r.validity == PedestalValidity.EARLY_ACTIVE

    def test_early_active_threshold_sensitivity(self) -> None:
        """Construct an early-active waveform where the pedestal bias
        pushes A4 below the 1000 ADC cut, even though the true amplitude
        is above cut. This is the censoring mechanism Issue #1109 addresses.
        """
        w = np.full(18, 100.0, dtype=float)
        w[0:4] = [100.0, 800.0, 1500.0, 1200.0]  # median=(800+1200)/2=1000
        w[9] = 2500.0  # true amplitude = 2400, A4 = 2500 - 1000 = 1500
        # Still above cut, but let's push it further
        w[0:4] = [100.0, 1000.0, 1800.0, 1500.0]  # median=(1000+1500)/2=1250
        w[9] = 2000.0  # true amplitude = 1900, A4 = 2000 - 1250 = 750
        r_v1 = select_amplitude(w, cut_adc=1000.0, method="v1")
        assert r_v1.selected is False  # censored by early pulse
        assert r_v1.validity == PedestalValidity.EARLY_ACTIVE
        # Dynamic-range estimator should recover it
        r_dyn = select_amplitude(w, cut_adc=1000.0, method="dynamic_range")
        assert r_dyn.selected is True  # Adyn = 2000 - 100 = 1900
        assert r_dyn.amplitude_adc == 1900.0

    def test_unknown_method(self) -> None:
        with pytest.raises(KeyError, match="unknown selector method"):
            select_amplitude(np.full(18, 100.0, dtype=float), method="nonexistent")


# ===================================================================
# Tests: selectors_available
# ===================================================================


class TestSelectorsAvailable:
    def test_returns_list(self) -> None:
        available = selectors_available()
        assert isinstance(available, list)
        assert "v1" in available
        assert "dynamic_range" in available
        assert "rolling_min" in available
        assert "early_robust_p10" in available

    def test_all_methods_usable(self, quiet_waveform: np.ndarray) -> None:
        for method in selectors_available():
            r = select_amplitude(quiet_waveform, method=method)
            assert r.method == method
            assert r.selected is True or r.selected is False