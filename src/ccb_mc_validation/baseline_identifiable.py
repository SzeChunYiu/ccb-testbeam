"""Identifiable baseline / pulse model (issue #963).

Replaces positivity-forced adaptive pedestal *validation* with estimators that:

1. use a quiet-pretrigger robust location when a quiet region exists;
2. expose baseline as a nuisance alongside signed amplitude;
3. emit an explicit ``BASELINE_UNIDENTIFIABLE`` class when no quiet
   information exists;
4. never treat "0% below tolerance by construction" as validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from ccb_mc_validation.selector import PedestalValidity


class BaselineIdentifiability(str, Enum):
    """Coarse identifiability labels for baseline estimation."""

    QUIET_IDENTIFIABLE = "QUIET_IDENTIFIABLE"
    BASELINE_UNIDENTIFIABLE = "BASELINE_UNIDENTIFIABLE"
    EARLY_OR_RECOVERY = "EARLY_OR_RECOVERY"
    POLARITY_AMBIGUOUS = "POLARITY_AMBIGUOUS"


# Alias required by issue #963 acceptance language.
BASELINE_UNIDENTIFIABLE = BaselineIdentifiability.BASELINE_UNIDENTIFIABLE


@dataclass(frozen=True)
class IdentifiableBaselineResult:
    method: str
    baseline_adc: float
    identifiability: BaselineIdentifiability
    quiet_fraction: float
    signed_amplitude_adc: float
    notes: str = ""

    @property
    def identifiable(self) -> bool:
        return self.identifiability == BaselineIdentifiability.QUIET_IDENTIFIABLE


def _as_1d(waveform: np.ndarray) -> np.ndarray:
    wave = np.asarray(waveform, dtype=float)
    if wave.ndim != 1:
        raise ValueError(f"waveform must be 1-D, got shape {wave.shape}")
    if wave.size < 4:
        raise ValueError(f"waveform needs >=4 samples, got {wave.size}")
    if not np.isfinite(wave).all():
        raise ValueError("waveform contains non-finite samples")
    return wave


def map_pedestal_validity(validity: PedestalValidity) -> BaselineIdentifiability:
    """Map selector validity states onto #963 identifiability labels."""
    if validity == PedestalValidity.QUIET_VALID:
        return BaselineIdentifiability.QUIET_IDENTIFIABLE
    if validity == PedestalValidity.BIPOLAR_OR_POLARITY_UNKNOWN:
        return BaselineIdentifiability.POLARITY_AMBIGUOUS
    if validity in {
        PedestalValidity.EARLY_ACTIVE,
        PedestalValidity.RECOVERY_CONTAMINATED,
    }:
        return BaselineIdentifiability.EARLY_OR_RECOVERY
    return BaselineIdentifiability.BASELINE_UNIDENTIFIABLE


def estimate_quiet_pretrigger_baseline(
    waveform: np.ndarray,
    *,
    pretrigger_samples: int = 4,
    quiet_spread_frac: float = 0.15,
) -> IdentifiableBaselineResult:
    """Robust location on the pretrigger window when it is demonstrably quiet.

    Uses the median of samples ``[0, pretrigger_samples)``. If the early-window
    spread is large relative to the full-window dynamic range, the baseline is
    labelled ``BASELINE_UNIDENTIFIABLE`` and the numeric baseline is ``nan``.
    No positivity constraint is applied.
    """
    wave = _as_1d(waveform)
    n = min(int(pretrigger_samples), wave.size)
    early = wave[:n]
    baseline = float(np.median(early))
    dyn = float(np.max(wave) - np.min(wave))
    early_span = float(np.max(early) - np.min(early))
    quiet_fraction = 0.0 if dyn <= 0 else max(0.0, 1.0 - early_span / dyn)
    if dyn > 0 and (early_span / dyn) > float(quiet_spread_frac):
        return IdentifiableBaselineResult(
            method="quiet_pretrigger_median",
            baseline_adc=float("nan"),
            identifiability=BaselineIdentifiability.BASELINE_UNIDENTIFIABLE,
            quiet_fraction=quiet_fraction,
            signed_amplitude_adc=float("nan"),
            notes="pretrigger span too large relative to dynamic range",
        )
    signed_amp = float(wave[np.argmax(np.abs(wave - baseline))] - baseline)
    return IdentifiableBaselineResult(
        method="quiet_pretrigger_median",
        baseline_adc=baseline,
        identifiability=BaselineIdentifiability.QUIET_IDENTIFIABLE,
        quiet_fraction=quiet_fraction,
        signed_amplitude_adc=signed_amp,
    )


def estimate_joint_baseline_template_nuisance(
    waveform: np.ndarray,
    template: np.ndarray,
) -> IdentifiableBaselineResult:
    """Joint least-squares baseline + signed template scale (baseline nuisance).

    Model: ``waveform ~= baseline + scale * template``. Does not impose global
    waveform positivity. If the template is degenerate, returns
    ``BASELINE_UNIDENTIFIABLE``.
    """
    wave = _as_1d(waveform)
    tmpl = np.asarray(template, dtype=float)
    if tmpl.shape != wave.shape:
        raise ValueError(
            f"template shape {tmpl.shape} must match waveform shape {wave.shape}"
        )
    if not np.isfinite(tmpl).all():
        raise ValueError("template contains non-finite samples")
    # Solve [1, template] @ [baseline, scale] = wave
    a = np.column_stack([np.ones(wave.size), tmpl])
    try:
        coef, *_ = np.linalg.lstsq(a, wave, rcond=None)
    except np.linalg.LinAlgError:
        return IdentifiableBaselineResult(
            method="joint_baseline_template",
            baseline_adc=float("nan"),
            identifiability=BaselineIdentifiability.BASELINE_UNIDENTIFIABLE,
            quiet_fraction=0.0,
            signed_amplitude_adc=float("nan"),
            notes="lstsq failed",
        )
    baseline, scale = float(coef[0]), float(coef[1])
    if not np.isfinite(baseline) or not np.isfinite(scale):
        return IdentifiableBaselineResult(
            method="joint_baseline_template",
            baseline_adc=float("nan"),
            identifiability=BaselineIdentifiability.BASELINE_UNIDENTIFIABLE,
            quiet_fraction=0.0,
            signed_amplitude_adc=float("nan"),
            notes="non-finite nuisance solution",
        )
    residual_rms = float(np.sqrt(np.mean((wave - (baseline + scale * tmpl)) ** 2)))
    signal_rms = float(np.sqrt(np.mean((wave - np.mean(wave)) ** 2)))
    if signal_rms > 0 and residual_rms / signal_rms > 0.9:
        ident = BaselineIdentifiability.BASELINE_UNIDENTIFIABLE
        notes = "residual dominates; baseline not identifiable"
        baseline_out = float("nan")
        amp_out = float("nan")
    else:
        ident = BaselineIdentifiability.QUIET_IDENTIFIABLE
        notes = ""
        baseline_out = baseline
        amp_out = scale * float(np.max(np.abs(tmpl)))
    return IdentifiableBaselineResult(
        method="joint_baseline_template",
        baseline_adc=baseline_out,
        identifiability=ident,
        quiet_fraction=max(0.0, 1.0 - residual_rms / signal_rms) if signal_rms else 0.0,
        signed_amplitude_adc=amp_out,
        notes=notes,
    )


def positivity_forced_zero_violation_is_not_evidence(
    *,
    fraction_below_tolerance: float,
    estimator_enforces_nonnegative: bool,
) -> dict[str, Any]:
    """Reject the B-stack '0% below tolerance by construction' validation metric.

    Issue #963: when the adaptive pedestal lowers until the minimum non-jagged
    corrected sample lies above an amplitude-dependent tolerance, a reported
    0% violation rate is enforced by the estimator and is not independent
    validation evidence.
    """
    if estimator_enforces_nonnegative and float(fraction_below_tolerance) == 0.0:
        return {
            "accepted_as_validation_evidence": False,
            "status": "REJECTED_BY_CONSTRUCTION",
            "issue": 963,
            "message": (
                "zero-below-tolerance is enforced by the positivity-forced "
                "adaptive pedestal and cannot validate baseline quality"
            ),
        }
    return {
        "accepted_as_validation_evidence": True,
        "status": "INDEPENDENT_METRIC",
        "issue": 963,
        "message": "metric is not the positivity-enforced zero-violation rate",
    }


def synthetic_baseline_bias_table(
    *,
    true_baseline: float = 300.0,
    amplitude: float = 2000.0,
    n_samples: int = 18,
    noise_rms: float = 5.0,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Known-answer bias table for quiet / early / undershoot pathologies."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_samples, dtype=float)
    pulse = amplitude * np.exp(-0.5 * ((t - 10.0) / 1.8) ** 2)
    rows: list[dict[str, Any]] = []

    cases = {
        "quiet": true_baseline + pulse + rng.normal(0.0, noise_rms, size=n_samples),
        "early_pulse": true_baseline
        + amplitude * np.exp(-0.5 * ((t - 1.5) / 1.2) ** 2)
        + rng.normal(0.0, noise_rms, size=n_samples),
        "undershoot": true_baseline
        + pulse
        - 0.15 * amplitude * np.exp(-0.5 * ((t - 12.0) / 2.5) ** 2)
        + rng.normal(0.0, noise_rms, size=n_samples),
    }
    for name, wave in cases.items():
        est = estimate_quiet_pretrigger_baseline(wave)
        bias = (
            float("nan")
            if not np.isfinite(est.baseline_adc)
            else float(est.baseline_adc - true_baseline)
        )
        rows.append(
            {
                "pathology": name,
                "method": est.method,
                "identifiability": est.identifiability.value,
                "baseline_bias_adc": bias,
                "identifiable": est.identifiable,
            }
        )
    return rows
