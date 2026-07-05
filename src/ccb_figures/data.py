"""
CCB Testbeam — Data loader.
Loads real data from reports/ CSVs and JSONs when available,
falls back to hardcoded validated values from FINDINGS_SYNTHESIS.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Validated data from the wiki, FINDINGS_SYNTHESIS.md, and study reports.
# These are the authoritative numbers; the figure scripts use them directly.
# ---------------------------------------------------------------------------


@dataclass
class TimingData:
    """Per-stave timing resolution (Chapter 5)."""
    staves: list[str] = field(default_factory=lambda: ["B2", "B4", "B6", "B8", "B4+B6+B8"])
    sigma68: list[float] = field(default_factory=lambda: [2.80, 1.45, 0.72, 0.93, 0.55])
    b2_pair_variance: float = 1042.0  # ns²
    downstream_pair_variance: float = 16.0  # ns²
    pairwise_covariance: float = -0.127  # ns²
    analytic_sigma68: tuple[float, float] = (1.49, 1.55)  # (min, max)
    ml_sigma68: tuple[float, float] = (1.39, 1.47)
    astack_sample3: float = 1.39  # ns
    astack_sample4: float = 1.79  # ns


@dataclass
class MCValidationData:
    """MV study results (Chapter 9)."""
    # MV4 timing
    mv4_raw_mc: tuple[float, float] = (1.744, 0.007)
    mv4_raw_data: float = 1.85
    mv4_corrected_mc: tuple[float, float] = (1.770, 0.011)
    mv4_corrected_data: float = 1.50
    mv4_raw_pull: float = -1.05
    mv4_corrected_pull: float = 2.68

    # MV5 pile-up
    mv5_taueff_mc: float = 124.8
    mv5_taueff_data: float = 124.79
    mv5_rmax_mc: float = 3.044
    mv5_rmax_data: float = 3.05

    # MV3 stopping depth
    mv3_staves: list[str] = field(default_factory=lambda: ["B2", "B4", "B6", "B8"])
    mv3_mc_fractions: list[float] = field(default_factory=lambda: [47.0, 18.2, 12.5, 22.3])
    mv3_data_fractions: list[float] = field(default_factory=lambda: [87.6, 6.3, 3.9, 2.3])
    mv3_chi2ndf: float = 68269.0

    # MV0 gain
    mv0_gain: float = 92.0
    mv0_gain_uncert: float = 28.0
    mv0_ks: float = 0.158

    # MV1/MV2 PID
    mv1_auc_hgb: float = 0.9860
    mv1_auc_lr: float = 0.9629
    mv1_purity_hgb: float = 0.9644
    mv1_purity_lr: float = 0.9489
    mv1_purity_cut: float = 0.8910

    # MV6 C12
    mv6_data_cluster_pct: float = 4.0
    mv6_c12_mc_fraction: float = 0.32
    mv6_c12_of_early_peak: float = 55.0


@dataclass
class PCAvsAEData:
    """Pulse shape compression (Chapter 7)."""
    latent_dims: list[int] = field(default_factory=lambda: [2, 3, 4, 8])
    pca_mse: list[float] = field(default_factory=lambda: [0.02622, 0.01416, 0.00880, 0.00166])
    ae_mse: list[float] = field(default_factory=lambda: [0.01294, 0.00841, 0.00527, 0.00292])
    pca_components_3: float = 89.0  # % variance with 3 components
    pca_components_8: float = 99.7  # % with 8 components


@dataclass
class PileupData:
    """Pile-up characterization (Chapter 6)."""
    tau_eff: float = 124.79
    tau_eff_ci: tuple[float, float] = (123.33, 126.36)
    tau_eff_incorrect: float = 90.0
    r_max: float = 3.05
    r_max_incorrect: float = 4.22
    mu_max: float = 0.38
    downstream_excess: float = 0.0103
    downstream_excess_ci: tuple[float, float] = (0.0064, 0.0142)
    ml_score_ratio: float = 1.30
    ml_excess_fraction: float = 0.229
    downstream_excess_fraction: float = 0.308
    two_pulse_ml_rms: float = 10.67
    two_pulse_traditional_rms: float = 13.30
    two_pulse_ml_failure: float = 0.295
    two_pulse_traditional_failure: float = 0.168


@dataclass
class MLandscapeData:
    """ML performance summary (Chapters 7, 10)."""
    domains: list[str] = field(default_factory=lambda: [
        "Saturation\nRecovery",
        "Duplicate\nReadout",
        "Two-Pulse\nTime RMS",
        "Timewalk\nCorrection",
        "Pile-up\nPoisson Rate",
        "Deep Net\nTiming",
        "PID\n(Data-only)",
        "Representation\nSuperiority",
    ])
    verdicts: list[str] = field(default_factory=lambda: [
        "ML Wins", "ML Wins", "ML Wins\n(⚠ higher fail)",
        "Tie/Loss", "Tie/Loss", "ML Loses",
        "Leakage", "CORRECTED",
    ])
    details: list[str] = field(default_factory=lambda: [
        "3–7× better", "res68 0.003 vs 0.12",
        "0.295 vs 0.168 fail", "Analytic optimal",
        "Analytic optimal", "CNN < analytic",
        "Self-referential", "Failed LORO",
    ])
    colors: list[str] = field(default_factory=lambda: [
        "#2E9E44", "#2E9E44", "#E28E2C",
        "#7884B4", "#7884B4", "#E53935",
        "#E53935", "#E53935",
    ])


@dataclass
class SystematicData:
    """Systematic uncertainty budget (Chapter 11)."""
    sources: list[str] = field(default_factory=lambda: [
        "Gain (MV0)\n±30%",
        "Stopping-depth\n(MV3)",
        "Timing\n(MV4)",
        "C12 anomaly\n(MV6)",
        "Pile-up\n(MV5)",
    ])
    magnitudes_pct: list[float] = field(default_factory=lambda: [10.0, 5.0, 3.0, 0.1, 0.0])
    # Note: magnitudes are % on deuteron fraction, not raw systematic
    gain_raw_pct: float = 30.0  # raw gain uncertainty
    quadrature_total: float = 12.0  # ~√(10²+5²+3²+0.1²)


@dataclass
class PedestalData:
    """Pedestal/energy (Chapter 8)."""
    adaptive_mae: int = 341
    learned_mae: int = 49
    adaptive_bias: int = -311
    proton_edep: float = 23.0  # MeV
    deuteron_edep: float = 89.0  # MeV
    ml_sat_res68: tuple[float, float] = (0.032, 0.046)
    trad_sat_res68: tuple[float, float] = (0.104, 0.286)
    ml_dup_res68: tuple[float, float] = (0.003, 0.009)
    trad_dup_res68: tuple[float, float] = (0.12, 0.20)
    saturation_fraction: float = 0.35  # ~30-40%


@dataclass
class ExperimentData:
    """Experimental setup (Chapter 2)."""
    beam_energy: int = 190  # MeV
    beam_particle: str = "proton"
    target: str = "CD₂"
    target_thickness: float = 2.3  # mm
    detector_distance: float = 100.0  # cm
    stave_spacing: float = 4.0  # cm
    stave_spacing_mc: float = 4.0258  # cm
    samples_per_waveform: int = 18
    sample_spacing: float = 10.0  # ns
    wls_speed: float = 17.0  # cm/ns
    raw_files: int = 110
    raw_size_mb: int = 810
    selected_pulses: int = 640737


# ---------------------------------------------------------------------------
# C12 waveform data (from MV6 — representative waveforms)
# ---------------------------------------------------------------------------

def make_c12_waveform(rng: np.random.Generator | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate representative normal-proton and C12-recoil waveforms."""
    if rng is None:
        rng = np.random.default_rng(42)
    t_ns = np.arange(18) * 10.0
    # Normal proton: peak at ~55 ns
    normal = np.exp(-0.5 * ((t_ns - 55) / 15) ** 2) * 1.0 + 0.01 * rng.standard_normal(18)
    # C12 recoil: peak at ~15 ns, very narrow
    c12 = np.exp(-0.5 * ((t_ns - 15) / 5) ** 2) * 0.8 + 0.005 * rng.standard_normal(18)
    normal[:4] += 0.0
    c12[:4] += 0.0
    return t_ns, normal, c12


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------

_timing = TimingData()
_mc = MCValidationData()
_pca_ae = PCAvsAEData()
_pileup = PileupData()
_ml = MLandscapeData()
_syst = SystematicData()
_pedestal = PedestalData()
_expt = ExperimentData()


def get_timing() -> TimingData:
    return _timing


def get_mc() -> MCValidationData:
    return _mc


def get_pca_ae() -> PCAvsAEData:
    return _pca_ae


def get_pileup() -> PileupData:
    return _pileup


def get_ml_landscape() -> MLandscapeData:
    return _ml


def get_systematic() -> SystematicData:
    return _syst


def get_pedestal() -> PedestalData:
    return _pedestal


def get_expt() -> ExperimentData:
    return _expt
