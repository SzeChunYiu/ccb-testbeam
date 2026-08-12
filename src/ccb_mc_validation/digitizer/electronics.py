"""Electronics gain, noise, and ADC quantization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ccb_mc_validation.digitizer.config_types import (
    require_finite_float,
    require_nonnegative_float,
    require_positive_int,
)


@dataclass
class ElectronicsConfig:
    gain_adc_per_mev: float = 120.0
    noise_adc_rms: float = 8.0
    adc_bits: int = 14
    adc_ceiling: int = 7000
    pedestal_adc: float = 300.0

    def __post_init__(self) -> None:
        # gain>=0 allowed as VALID_CONTROL (null gain experiment); negative invalid.
        self.gain_adc_per_mev = require_nonnegative_float(
            self.gain_adc_per_mev, field_name="gain_adc_per_mev"
        )
        self.noise_adc_rms = require_nonnegative_float(
            self.noise_adc_rms, field_name="noise_adc_rms"
        )
        self.adc_bits = require_positive_int(self.adc_bits, field_name="adc_bits")
        if self.adc_bits > 63:
            raise ValueError(f"adc_bits must be in [1, 63], got {self.adc_bits}")
        self.adc_ceiling = require_positive_int(self.adc_ceiling, field_name="adc_ceiling")
        self.pedestal_adc = require_finite_float(self.pedestal_adc, field_name="pedestal_adc")


def apply_gain(signal_mev: np.ndarray, cfg: ElectronicsConfig) -> np.ndarray:
    return np.asarray(signal_mev, dtype=np.float64) * cfg.gain_adc_per_mev


def add_noise(
    adc: np.ndarray,
    rng: np.random.Generator,
    cfg: ElectronicsConfig,
) -> np.ndarray:
    return adc + rng.normal(0.0, cfg.noise_adc_rms, size=adc.shape)


def _adc_dtype(adc_bits: int) -> np.dtype:
    """Smallest signed integer dtype that holds the ADC's full-scale range."""
    if adc_bits < 1 or adc_bits > 63:
        raise ValueError(f"adc_bits must be in [1, 63], got {adc_bits}")
    if adc_bits <= 7:
        return np.dtype(np.int8)
    if adc_bits <= 15:
        return np.dtype(np.int16)
    if adc_bits <= 31:
        return np.dtype(np.int32)
    return np.dtype(np.int64)


def quantize_adc(
    adc: np.ndarray,
    cfg: ElectronicsConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Quantize to integer ADC counts with a saturation flag.

    The effective ceiling is ``min(adc_ceiling, 2**adc_bits - 1)``; BOTH the
    clipping and the saturation flag use this single effective ceiling so they
    can never disagree.  The output dtype is selected from ``adc_bits`` (smallest
    signed integer that holds the full scale).  Non-finite input is rejected.
    """
    arr = np.asarray(adc, dtype=np.float64)
    if not np.all(np.isfinite(arr)):
        raise ValueError("quantize_adc input contains non-finite values")
    if cfg.adc_bits < 1 or cfg.adc_bits > 63:
        raise ValueError(f"adc_bits must be in [1, 63], got {cfg.adc_bits}")
    full_scale = (1 << cfg.adc_bits) - 1
    effective_ceiling = min(int(cfg.adc_ceiling), int(full_scale))
    clipped = np.clip(arr, 0.0, float(effective_ceiling))
    saturated = arr > float(effective_ceiling)
    out = np.rint(clipped).astype(_adc_dtype(cfg.adc_bits))
    # Validate legal bit range (defensive; clip already enforces this).
    if out.size and (int(out.min()) < 0 or int(out.max()) > full_scale):
        raise ValueError(
            f"quantized ADC {int(out.min())}..{int(out.max())} exceeds "
            f"legal range [0, {full_scale}] for adc_bits={cfg.adc_bits}"
        )
    return out, saturated.astype(np.uint8)
