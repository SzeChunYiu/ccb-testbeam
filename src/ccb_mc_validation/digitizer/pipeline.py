"""MV0 digitizer pipeline: truth hits → one 18-sample ADC waveform per channel/event."""

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
from ccb_mc_validation.digitizer.sampling import (
    DEFAULT_N_SAMPLES,
    DEFAULT_SAMPLE_SPACING_NS,
    integrate_samples,
)
from ccb_mc_validation.digitizer.transport import smear_time

StageFn = Callable[[Mapping[str, Any], np.random.Generator, dict[str, Any]], Mapping[str, Any]]


@dataclass
class DigitizerPipeline:
    """Configurable staged digitizer.

    The analog hit contributions are summed first.  Pedestal, electronics noise,
    and ADC quantisation are then applied exactly once to the final channel
    waveform.  This prevents a zero-signal multi-hit channel from accumulating
    multiple pedestal/noise realisations.
    """

    n_samples: int = DEFAULT_N_SAMPLES
    sample_spacing_ns: float = DEFAULT_SAMPLE_SPACING_NS
    electronics: ElectronicsConfig = field(default_factory=ElectronicsConfig)
    tau_rise_ns: float = 2.0
    tau_decay_ns: float = 35.0
    transport_sigma_ns: float = 0.5
    apply_birks: bool = False
    stages: list[str] = field(
        default_factory=lambda: ["birks", "scintillation", "transport", "sampling"]
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
        # Current implementation keeps the light yield in MeV-equivalent units;
        # calibration determines the ADC/MeV gain.  No electronics noise belongs
        # in this stage.
        return dict(hit)

    def _stage_transport(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        out["time_ns"] = float(smear_time([float(hit.get("time_ns", 0.0))], rng, self.transport_sigma_ns)[0])
        return out

    def _stage_sampling(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        ctx["light_curve_mev"] = integrate_samples(
            float(hit.get("edep_mev", 0.0)),
            float(hit.get("time_ns", 0.0)),
            sample_spacing_ns=self.sample_spacing_ns,
            n_samples=self.n_samples,
            tau_rise_ns=self.tau_rise_ns,
            tau_decay_ns=self.tau_decay_ns,
        )
        return out

    def _stage_electronics(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        """Deprecated per-hit electronics stage retained for compatibility.

        The production ``run`` method no longer invokes this stage per hit.  If a
        caller explicitly includes ``electronics`` in ``stages`` this method only
        records an analog ADC contribution without pedestal/noise/quantisation;
        final electronics are still applied once per waveform by ``run``.
        """
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
        ctx["analog_adc"] = apply_gain(light, self.electronics)
        return dict(hit)

    def _dispatch(self, stage_name: str) -> StageFn:
        table: dict[str, StageFn] = {
            "birks": self._stage_birks,
            "scintillation": self._stage_scintillation,
            "transport": self._stage_transport,
            "sampling": self._stage_sampling,
            "electronics": self._stage_electronics,
        }
        if stage_name not in table:
            raise KeyError(f"unknown digitizer stage {stage_name!r}")
        return table[stage_name]

    def run(
        self,
        hits: Sequence[Mapping[str, Any]],
        event_id: int,
        channel: int = 0,
        seed_salt: int = 0,
    ) -> dict[str, Any]:
        """Process truth hits for one channel/event into a summed ADC waveform.

        The noise seed mixes (event_id, channel, seed_salt) so different
        channels of the same event — and different studies via ``seed_salt`` —
        get independent noise realisations (fixed 2026-07-03: seeding on
        event_id alone made inter-channel noise 100% correlated).
        """
        rng = np.random.default_rng(
            np.random.SeedSequence([int(event_id), int(channel), int(seed_salt)])
        )
        analog_adc_sum = np.zeros(self.n_samples, dtype=np.float64)

        for hit in hits:
            ctx_hit: dict[str, Any] = {}
            current: Mapping[str, Any] = hit
            for stage_name in self.stages:
                current = self._dispatch(stage_name)(current, rng, ctx_hit)
            light = ctx_hit.get("light_curve_mev")
            if light is None:
                light = integrate_samples(
                    float(current.get("edep_mev", 0.0)),
                    float(current.get("time_ns", 0.0)),
                    sample_spacing_ns=self.sample_spacing_ns,
                    n_samples=self.n_samples,
                    tau_rise_ns=self.tau_rise_ns,
                    tau_decay_ns=self.tau_decay_ns,
                )
            analog_adc_sum += apply_gain(light, self.electronics)

        waveform = analog_adc_sum + self.electronics.pedestal_adc
        waveform = add_noise(waveform, rng, self.electronics)
        adc_final, sat_final = quantize_adc(waveform, self.electronics)
        return {
            "event_id": int(event_id),
            "adc": adc_final,
            "saturated": sat_final,
            "n_hits": len(hits),
        }

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "DigitizerPipeline":
        elec = ElectronicsConfig(
            gain_adc_per_mev=float(config.get("gain_adc_per_mev", 120.0)),
            noise_adc_rms=float(config.get("noise_adc_rms", 8.0)),
            adc_ceiling=int(config.get("adc_ceiling", 7000)),
            pedestal_adc=float(config.get("pedestal_adc", 300.0)),
        )
        stages = list(config.get("stages", ["birks", "scintillation", "transport", "sampling"]))
        return cls(
            n_samples=int(config.get("n_samples", DEFAULT_N_SAMPLES)),
            sample_spacing_ns=float(config.get("sample_spacing_ns", DEFAULT_SAMPLE_SPACING_NS)),
            electronics=elec,
            tau_rise_ns=float(config.get("tau_rise_ns", 2.0)),
            tau_decay_ns=float(config.get("tau_decay_ns", 35.0)),
            transport_sigma_ns=float(config.get("transport_sigma_ns", 0.5)),
            apply_birks=bool(config.get("apply_birks", False)),
            stages=stages,
        )
