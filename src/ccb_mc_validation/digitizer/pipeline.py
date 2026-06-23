"""MV0 digitizer pipeline: truth hits → 18-sample ADC waveforms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from ccb_mc_validation.digitizer.birks import birks_quench
from ccb_mc_validation.digitizer.electronics import (
    ElectronicsConfig,
    add_noise,
    apply_gain,
    quantize_adc,
)
from ccb_mc_validation.digitizer.sampling import DEFAULT_N_SAMPLES, DEFAULT_SAMPLE_SPACING_NS, integrate_samples
from ccb_mc_validation.digitizer.transport import smear_time


StageFn = Callable[[Mapping[str, Any], np.random.Generator, dict[str, Any]], Mapping[str, Any]]


@dataclass
class DigitizerPipeline:
    """
    Configurable staged digitizer.

    Deterministic given ``event_id``: numpy Generator is seeded from event_id
    at the start of ``run()``.
    """

    n_samples: int = DEFAULT_N_SAMPLES
    sample_spacing_ns: float = DEFAULT_SAMPLE_SPACING_NS
    electronics: ElectronicsConfig = field(default_factory=ElectronicsConfig)
    tau_rise_ns: float = 2.0
    tau_decay_ns: float = 35.0
    transport_sigma_ns: float = 0.5
    apply_birks: bool = False
    stages: list[str] = field(
        default_factory=lambda: [
            "birks",
            "scintillation",
            "transport",
            "sampling",
            "electronics",
        ]
    )

    def _stage_birks(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        if self.apply_birks:
            out["edep_mev"] = birks_quench(float(hit.get("edep_mev", 0.0)))
        return out

    def _stage_scintillation(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        return dict(hit)

    def _stage_transport(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        t = np.array([float(hit.get("time_ns", 0.0))])
        out["time_ns"] = float(smear_time(t, rng, self.transport_sigma_ns)[0])
        return out

    def _stage_sampling(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        light = integrate_samples(
            float(hit.get("edep_mev", 0.0)),
            float(hit.get("time_ns", 0.0)),
            sample_spacing_ns=self.sample_spacing_ns,
            n_samples=self.n_samples,
            tau_rise_ns=self.tau_rise_ns,
            tau_decay_ns=self.tau_decay_ns,
        )
        ctx["light_curve_mev"] = light
        return out

    def _stage_electronics(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        light = ctx.get("light_curve_mev")
        if light is None:
            light = integrate_samples(
                float(hit.get("edep_mev", 0.0)),
                float(hit.get("time_ns", 0.0)),
                sample_spacing_ns=self.sample_spacing_ns,
                n_samples=self.n_samples,
                tau_rise_ns=self.tau_rise_ns,
                tau_decay_ns=self.tau_decay_ns,
            )
        adc = apply_gain(light, self.electronics) + self.electronics.pedestal_adc
        adc = add_noise(adc, rng, self.electronics)
        adc_int, saturated = quantize_adc(adc, self.electronics)
        ctx["adc"] = adc_int
        ctx["saturated"] = saturated
        return hit

    def _dispatch(self, stage: str) -> StageFn:
        table = {
            "birks": self._stage_birks,
            "scintillation": self._stage_scintillation,
            "transport": self._stage_transport,
            "sampling": self._stage_sampling,
            "electronics": self._stage_electronics,
        }
        if stage not in table:
            raise ValueError(f"unknown digitizer stage: {stage}")
        return table[stage]

    def run(
        self,
        hits: Sequence[Mapping[str, Any]],
        event_id: int,
    ) -> dict[str, Any]:
        """
        Process truth hits for one event into summed 18-sample ADC waveform.

        Uses ``np.random.default_rng(event_id)`` for reproducibility.
        """
        rng = np.random.default_rng(int(event_id))
        ctx: dict[str, Any] = {}
        adc_sum = np.zeros(self.n_samples, dtype=np.float64)
        any_saturated = np.zeros(self.n_samples, dtype=np.uint8)

        for hit in hits:
            ctx_hit: dict[str, Any] = {}
            current = hit
            for stage_name in self.stages:
                current = self._dispatch(stage_name)(current, rng, ctx_hit)
            if "adc" in ctx_hit:
                adc_sum += ctx_hit["adc"].astype(np.float64)
                any_saturated = np.maximum(any_saturated, ctx_hit["saturated"])

        adc_final, sat_final = quantize_adc(adc_sum, self.electronics)
        return {
            "event_id": int(event_id),
            "adc": adc_final,
            "saturated": sat_final,
            "n_hits": len(hits),
        }

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> DigitizerPipeline:
        elec = ElectronicsConfig(
            gain_adc_per_mev=float(config.get("gain_adc_per_mev", 120.0)),
            noise_adc_rms=float(config.get("noise_adc_rms", 8.0)),
            adc_ceiling=int(config.get("adc_ceiling", 7000)),
            pedestal_adc=float(config.get("pedestal_adc", 300.0)),
        )
        return cls(
            n_samples=int(config.get("n_samples", DEFAULT_N_SAMPLES)),
            sample_spacing_ns=float(config.get("sample_spacing_ns", DEFAULT_SAMPLE_SPACING_NS)),
            electronics=elec,
            tau_rise_ns=float(config.get("tau_rise_ns", 2.0)),
            tau_decay_ns=float(config.get("tau_decay_ns", 35.0)),
            transport_sigma_ns=float(config.get("transport_sigma_ns", 0.5)),
            apply_birks=bool(config.get("apply_birks", False)),
            stages=list(config.get("stages", ["birks", "scintillation", "transport", "sampling", "electronics"])),
        )
