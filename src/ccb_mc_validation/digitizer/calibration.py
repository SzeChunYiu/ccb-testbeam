"""Staged calibration skeleton for MV0 digitizer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CalibrationStage:
    name: str
    params: dict[str, float] = field(default_factory=dict)
    complete: bool = False


class DigitizerCalibration:
    """Multi-stage calibration registry (shape → ADC scale → noise)."""

    def __init__(self) -> None:
        self.stages = [
            CalibrationStage("shape_template", {"tau_rise_ns": 2.0, "tau_decay_ns": 35.0}),
            CalibrationStage("adc_scale", {"gain_adc_per_mev": 120.0}),
            CalibrationStage("noise_pedestal", {"noise_adc_rms": 8.0, "pedestal_adc": 300.0}),
        ]

    def stage(self, name: str) -> CalibrationStage:
        for st in self.stages:
            if st.name == name:
                return st
        raise KeyError(name)

    def as_dict(self) -> dict[str, Any]:
        return {
            st.name: {"params": st.params, "complete": st.complete} for st in self.stages
        }

    def apply_to_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Merge completed stage params into digitizer config dict."""
        out = dict(config)
        for st in self.stages:
            if st.complete:
                out.update(st.params)
        return out
