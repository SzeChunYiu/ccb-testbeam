"""Fail-closed scalar domain preflight for DigitizerPipeline (#1080).

Invalid configs must raise before RNG creation / event 0 and must not produce
plausible nonphysical waveforms (e.g. n_samples=0 or sample_spacing_ns=0).
"""

from __future__ import annotations

import math
from dataclasses import asdict
from typing import Any, Mapping

from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.exceptions import ConfigurationError

PHYSICAL_PRODUCTION = "PHYSICAL_PRODUCTION"
VALID_CONTROL = "VALID_CONTROL"
INVALID_INPUT = "INVALID_INPUT"


class DigitizerDomainError(ConfigurationError, ValueError):
    """Raised when digitizer scalars are outside the allowed domain."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


def _require_finite_number(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise DigitizerDomainError(
            f"{name} must be a real number, got bool {value!r}",
            field=name,
        )
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise DigitizerDomainError(
            f"{name} must be a real number, got {value!r}",
            field=name,
        ) from exc
    if not math.isfinite(f):
        raise DigitizerDomainError(
            f"{name} must be finite, got {value!r}",
            field=name,
        )
    return f


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise DigitizerDomainError(
            f"{name} must be an integer, got bool {value!r}",
            field=name,
        )
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise DigitizerDomainError(
                f"{name} must be an integer-valued number, got {value!r}",
                field=name,
            )
        return int(value)
    if isinstance(value, str):
        raise DigitizerDomainError(
            f"{name} must be an integer, got string {value!r}",
            field=name,
        )
    raise DigitizerDomainError(
        f"{name} must be an integer, got {value!r}",
        field=name,
    )


def validate_electronics_config(cfg: ElectronicsConfig) -> dict[str, str]:
    """Validate electronics scalars; return per-field classification tags."""
    tags: dict[str, str] = {}

    gain = _require_finite_number("gain_adc_per_mev", cfg.gain_adc_per_mev)
    if gain < 0.0:
        raise DigitizerDomainError(
            f"gain_adc_per_mev must be >= 0, got {gain}",
            field="gain_adc_per_mev",
        )
    tags["gain_adc_per_mev"] = PHYSICAL_PRODUCTION if gain > 0.0 else VALID_CONTROL

    noise = _require_finite_number("noise_adc_rms", cfg.noise_adc_rms)
    if noise < 0.0:
        raise DigitizerDomainError(
            f"noise_adc_rms must be >= 0 (0 is a valid zero-noise control), got {noise}",
            field="noise_adc_rms",
        )
    tags["noise_adc_rms"] = PHYSICAL_PRODUCTION if noise > 0.0 else VALID_CONTROL

    _require_finite_number("pedestal_adc", cfg.pedestal_adc)
    tags["pedestal_adc"] = PHYSICAL_PRODUCTION

    bits = _require_int("adc_bits", cfg.adc_bits)
    if bits < 1 or bits > 63:
        raise DigitizerDomainError(
            f"adc_bits must be in [1, 63], got {bits}",
            field="adc_bits",
        )
    tags["adc_bits"] = PHYSICAL_PRODUCTION

    ceiling = _require_int("adc_ceiling", cfg.adc_ceiling)
    if ceiling < 0:
        raise DigitizerDomainError(
            f"adc_ceiling must be >= 0, got {ceiling}",
            field="adc_ceiling",
        )
    tags["adc_ceiling"] = PHYSICAL_PRODUCTION
    return tags


def preflight_digitizer_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate digitizer config before event 0 / RNG use (#1080)."""
    if not isinstance(config, Mapping):
        raise DigitizerDomainError("digitizer config must be a mapping")

    n_samples = _require_int("n_samples", config.get("n_samples", 18))
    if n_samples <= 0:
        raise DigitizerDomainError(
            f"n_samples must be > 0 for the ordinary observation model, got {n_samples}",
            field="n_samples",
        )

    spacing = _require_finite_number(
        "sample_spacing_ns", config.get("sample_spacing_ns", 10.0)
    )
    if spacing <= 0.0:
        raise DigitizerDomainError(
            "sample_spacing_ns must be > 0 for the ordinary observation model "
            f"(zero/negative spacing yields nonphysical binning), got {spacing}",
            field="sample_spacing_ns",
        )

    tau_rise = _require_finite_number("tau_rise_ns", config.get("tau_rise_ns", 2.0))
    if tau_rise <= 0.0:
        raise DigitizerDomainError(
            f"tau_rise_ns must be > 0, got {tau_rise}",
            field="tau_rise_ns",
        )
    tau_decay = _require_finite_number(
        "tau_decay_ns", config.get("tau_decay_ns", 35.0)
    )
    if tau_decay <= 0.0:
        raise DigitizerDomainError(
            f"tau_decay_ns must be > 0, got {tau_decay}",
            field="tau_decay_ns",
        )

    transport = _require_finite_number(
        "transport_sigma_ns", config.get("transport_sigma_ns", 0.5)
    )
    if transport < 0.0:
        raise DigitizerDomainError(
            "transport_sigma_ns must be >= 0 "
            f"(0 is a valid deterministic control; negative is INVALID_INPUT), got {transport}",
            field="transport_sigma_ns",
        )

    elec = ElectronicsConfig(
        gain_adc_per_mev=_require_finite_number(
            "gain_adc_per_mev", config.get("gain_adc_per_mev", 120.0)
        ),
        noise_adc_rms=_require_finite_number(
            "noise_adc_rms", config.get("noise_adc_rms", 8.0)
        ),
        adc_bits=_require_int("adc_bits", config.get("adc_bits", 14)),
        adc_ceiling=_require_int("adc_ceiling", config.get("adc_ceiling", 7000)),
        pedestal_adc=_require_finite_number(
            "pedestal_adc", config.get("pedestal_adc", 300.0)
        ),
    )
    elec_tags = validate_electronics_config(elec)
    seed = _require_int("global_seed", config.get("global_seed", 0))

    classifications = {
        "n_samples": PHYSICAL_PRODUCTION,
        "sample_spacing_ns": PHYSICAL_PRODUCTION,
        "tau_rise_ns": PHYSICAL_PRODUCTION,
        "tau_decay_ns": PHYSICAL_PRODUCTION,
        "transport_sigma_ns": (
            PHYSICAL_PRODUCTION if transport > 0.0 else VALID_CONTROL
        ),
        "global_seed": VALID_CONTROL,
        **{f"electronics.{k}": v for k, v in elec_tags.items()},
    }

    return {
        "schema": "ccb-digitizer-resolved-config/1",
        "issue": 1080,
        "requested": dict(config),
        "effective": {
            "n_samples": n_samples,
            "sample_spacing_ns": spacing,
            "tau_rise_ns": tau_rise,
            "tau_decay_ns": tau_decay,
            "transport_sigma_ns": transport,
            "global_seed": seed,
            "electronics": asdict(elec),
            "apply_birks": bool(config.get("apply_birks", False)),
            "stages": list(
                config.get(
                    "stages",
                    ["birks", "scintillation", "transport", "sampling"],
                )
            ),
        },
        "classification": classifications,
        "status": "PREFLIGHT_OK",
    }
