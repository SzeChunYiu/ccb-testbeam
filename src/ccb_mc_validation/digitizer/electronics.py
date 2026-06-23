"""Electronics gain, noise, and ADC quantization."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ElectronicsConfig:
    gain_adc_per_mev: float = 120.0
    noise_adc_rms: float = 8.0
    adc_bits: int = 14
    adc_ceiling: int = 7000
    pedestal_adc: float = 300.0


def apply_gain(signal_mev: np.ndarray, cfg: ElectronicsConfig) -> np.ndarray:
    return np.asarray(signal_mev, dtype=np.float64) * cfg.gain_adc_per_mev


def add_noise(
    adc: np.ndarray,
    rng: np.random.Generator,
    cfg: ElectronicsConfig,
) -> np.ndarray:
    return adc + rng.normal(0.0, cfg.noise_adc_rms, size=adc.shape)


def quantize_adc(
    adc: np.ndarray,
    cfg: ElectronicsConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Quantize to integer ADC counts with saturation flag.

    Returns (adc_int, saturated_mask).
    """
    full_scale = (1 << cfg.adc_bits) - 1
    clipped = np.clip(adc, 0.0, min(cfg.adc_ceiling, full_scale))
    saturated = adc > cfg.adc_ceiling
    return np.rint(clipped).astype(np.int16), saturated.astype(np.uint8)
