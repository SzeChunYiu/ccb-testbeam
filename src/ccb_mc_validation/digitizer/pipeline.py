"""MV0 digitizer pipeline: truth hits → one 18-sample ADC waveform per channel/event."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ccb_mc_validation.strict_bool import PARSER_VERSION, resolve_bool_field

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

# Schema fields required on every hit.  Missing fields or non-finite values are a
# hard error -- silently defaulting them to zero would corrupt the physics.
REQUIRED_HIT_FIELDS: tuple[str, ...] = ("edep_mev", "time_ns")

# Stable microscopic identity fields for hit-keyed RNG (#1074).
HIT_IDENTITY_FIELDS: tuple[str, ...] = ("track_id", "step_id")

# Versioned RNG schema persisted in waveform provenance.
DIGITIZER_RNG_SCHEMA = "hit_keyed_v1"

# Stochastic stages that consume RNG; each receives its own independent
# deterministic stream derived from (global_seed, source, run, event, channel).
_STOCHASTIC_STAGES: tuple[str, ...] = ("transport", "electronics")


def _hash_to_int(token: Any) -> int:
    """Stably hash an arbitrary identifier (int or str) into a 32-bit seed word.

    Python's ``hash()`` is salted per-process for strings, so we use a stable
    digest to keep RNG streams reproducible across runs and machines.
    """
    if isinstance(token, bool):
        return int(token)
    if isinstance(token, (int, np.integer)):
        return int(token) & 0xFFFFFFFF
    s = str(token)
    h = hashlib.blake2b(s.encode("utf-8"), digest_size=4).hexdigest()
    return int(h, 16)


@dataclass
class DigitizerPipeline:
    """Configurable staged digitizer.

    The analog hit contributions are summed first.  Pedestal, electronics noise,
    and ADC quantisation are then applied exactly once to the final channel
    waveform.  This prevents a zero-signal multi-hit channel from accumulating
    multiple pedestal/noise realisations.

    Random numbers are drawn from independent deterministic streams keyed on
    ``(global_seed, source_id, run_id, event_id, channel_id)`` so that distinct
    channels/stages of the same event never share RNG state, while the same
    inputs always reproduce the same waveform.
    """

    n_samples: int = DEFAULT_N_SAMPLES
    sample_spacing_ns: float = DEFAULT_SAMPLE_SPACING_NS
    electronics: ElectronicsConfig = field(default_factory=ElectronicsConfig)
    tau_rise_ns: float = 2.0
    tau_decay_ns: float = 35.0
    transport_sigma_ns: float = 0.5
    apply_birks: bool = False
    global_seed: int = 0
    stages: list[str] = field(
        default_factory=lambda: ["birks", "scintillation", "transport", "sampling"]
    )

    # ------------------------------------------------------------------
    # schema validation
    # ------------------------------------------------------------------
    @staticmethod
    def _require_field(
        hit: Mapping[str, Any],
        key: str,
        *,
        event_id: Any,
        channel_id: Any,
    ) -> float:
        if key not in hit:
            raise ValueError(
                f"digitizer hit missing required field {key!r} "
                f"(event_id={event_id!r}, channel_id={channel_id!r}); "
                f"schema requires {REQUIRED_HIT_FIELDS}"
            )
        val = hit[key]
        try:
            f = float(val)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"digitizer hit field {key!r} not coercible to float "
                f"(event_id={event_id!r}, channel_id={channel_id!r}): {val!r}"
            ) from exc
        if not np.isfinite(f):
            raise ValueError(
                f"digitizer hit field {key!r} is non-finite "
                f"(event_id={event_id!r}, channel_id={channel_id!r}): {f}"
            )
        return f

    # ------------------------------------------------------------------
    # stages
    # ------------------------------------------------------------------
    def _stage_birks(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        if self.apply_birks:
            edep = self._require_field(
                hit, "edep_mev", event_id=ctx["event_id"], channel_id=ctx["channel_id"]
            )
            try:
                out["edep_mev"] = birks_quench(
                    edep,
                    step_length_cm=hit.get("step_length_cm"),
                    dedx_mev_per_cm=hit.get("dedx_mev_per_cm"),
                )
            except ValueError as exc:
                raise ValueError(
                    f"birks stage cannot run (event_id={ctx['event_id']!r}, "
                    f"channel_id={ctx['channel_id']!r}): {exc}. Provide "
                    f"step_length_cm/dedx_mev_per_cm on the hit or disable apply_birks."
                ) from exc
        return out

    def _stage_scintillation(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        # Light yield stays in MeV-equivalent units; calibration determines the
        # ADC/MeV gain.  No electronics noise belongs in this stage.
        return dict(hit)

    def _stage_transport(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        t = self._require_field(
            hit, "time_ns", event_id=ctx["event_id"], channel_id=ctx["channel_id"]
        )
        out["time_ns"] = float(smear_time([t], rng, self.transport_sigma_ns)[0])
        return out

    def _stage_sampling(
        self,
        hit: Mapping[str, Any],
        rng: np.random.Generator,
        ctx: dict[str, Any],
    ) -> Mapping[str, Any]:
        out = dict(hit)
        edep = self._require_field(
            hit, "edep_mev", event_id=ctx["event_id"], channel_id=ctx["channel_id"]
        )
        t = self._require_field(
            hit, "time_ns", event_id=ctx["event_id"], channel_id=ctx["channel_id"]
        )
        ctx["light_curve_mev"] = integrate_samples(
            edep,
            t,
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
            edep = self._require_field(
                hit, "edep_mev", event_id=ctx["event_id"], channel_id=ctx["channel_id"]
            )
            t = self._require_field(
                hit, "time_ns", event_id=ctx["event_id"], channel_id=ctx["channel_id"]
            )
            light = integrate_samples(
                edep,
                t,
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

    # ------------------------------------------------------------------
    # RNG plumbing
    # ------------------------------------------------------------------

    def _hit_identity_tokens(
        self,
        hit: Mapping[str, Any],
        *,
        event_id: Any,
        channel_id: Any,
        hit_index: int,
        require_identity: bool,
    ) -> tuple[Any, Any]:
        """Return stable (track_id, step_id) or fail closed when required.

        Row index is never used as a physical identity. When a single hit has
        no identity and stochastic transport is inactive, a sentinel is used
        only for empty-stream bookkeeping. Multi-hit stochastic digitization
        requires explicit track/step identity (#1074).
        """
        missing = [k for k in HIT_IDENTITY_FIELDS if k not in hit]
        if missing:
            if require_identity:
                raise ValueError(
                    "digitizer hit missing stable identity fields "
                    f"{missing} (event_id={event_id!r}, channel_id={channel_id!r}, "
                    f"hit_index={hit_index}); RNG schema {DIGITIZER_RNG_SCHEMA} "
                    "forbids row-order stochastic assignment"
                )
            return ("__no_hit_identity__", hit_index)
        track_id = hit["track_id"]
        step_id = hit["step_id"]
        if track_id is None or step_id is None:
            raise ValueError(
                "digitizer hit identity fields must be non-None "
                f"(event_id={event_id!r}, channel_id={channel_id!r}, "
                f"track_id={track_id!r}, step_id={step_id!r})"
            )
        return track_id, step_id

    def _hit_stage_rng(
        self,
        *,
        event_id: Any,
        source_id: Any,
        run_id: Any,
        channel_id: Any,
        track_id: Any,
        step_id: Any,
        stage_name: str,
    ) -> np.random.Generator:
        """Independent deterministic Generator keyed on hit identity + stage."""
        entropy = [
            int(self.global_seed),
            _hash_to_int(source_id),
            _hash_to_int(run_id),
            _hash_to_int(event_id),
            _hash_to_int(channel_id),
            _hash_to_int(track_id),
            _hash_to_int(step_id),
            _hash_to_int(stage_name),
            _hash_to_int(DIGITIZER_RNG_SCHEMA),
        ]
        return np.random.default_rng(np.random.SeedSequence(entropy))

    def _seed_sequence(
        self,
        *,
        event_id: Any,
        source_id: Any,
        run_id: Any,
        channel_id: Any,
    ) -> np.random.SeedSequence:
        entropy = [
            int(self.global_seed),
            _hash_to_int(source_id),
            _hash_to_int(run_id),
            _hash_to_int(event_id),
            _hash_to_int(channel_id),
        ]
        return np.random.SeedSequence(entropy)

    def _stage_rngs(
        self,
        *,
        event_id: Any,
        source_id: Any,
        run_id: Any,
        channel_id: Any,
    ) -> dict[str, np.random.Generator]:
        """Independent deterministic ``Generator`` per stochastic stage."""
        seed_seq = self._seed_sequence(
            event_id=event_id,
            source_id=source_id,
            run_id=run_id,
            channel_id=channel_id,
        )
        children = seed_seq.spawn(len(_STOCHASTIC_STAGES))
        return {
            name: np.random.default_rng(child) for name, child in zip(_STOCHASTIC_STAGES, children)
        }

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------
    def run(
        self,
        hits: Sequence[Mapping[str, Any]],
        event_id: Any,
        *,
        source_id: Any = 0,
        run_id: Any = 0,
        channel_id: Any = 0,
    ) -> dict[str, Any]:
        """Process truth hits for one channel/event into a summed ADC waveform.

        Stochastic hit-level draws use hit-keyed substreams under
        ``DIGITIZER_RNG_SCHEMA`` so that a pure storage-order permutation of
        the same physical hit multiset does not change the fixed-seed
        waveform (#1074). Channel-level electronics noise remains on the
        event/channel stage stream.
        """
        stage_rng = self._stage_rngs(
            event_id=event_id,
            source_id=source_id,
            run_id=run_id,
            channel_id=channel_id,
        )
        idle_rng = np.random.default_rng(
            np.random.SeedSequence(
                [int(self.global_seed), _hash_to_int(event_id), 0xBAD]
            )
        )

        transport_stochastic = (
            "transport" in self.stages and float(self.transport_sigma_ns) != 0.0
        )
        require_identity = transport_stochastic and len(hits) > 1

        # Accumulate in identity order so float summation is permutation-stable
        # for the same physical multiset.
        prepared: list[tuple[tuple[Any, Any], Mapping[str, Any], dict[str, Any]]] = []
        for hit_index, hit in enumerate(hits):
            track_id, step_id = self._hit_identity_tokens(
                hit,
                event_id=event_id,
                channel_id=channel_id,
                hit_index=hit_index,
                require_identity=require_identity,
            )
            ctx_hit: dict[str, Any] = {
                "event_id": event_id,
                "channel_id": channel_id,
                "track_id": track_id,
                "step_id": step_id,
            }
            current: Mapping[str, Any] = hit
            for stage_name in self.stages:
                if stage_name in _STOCHASTIC_STAGES and stage_name == "transport":
                    rng_for_stage = self._hit_stage_rng(
                        event_id=event_id,
                        source_id=source_id,
                        run_id=run_id,
                        channel_id=channel_id,
                        track_id=track_id,
                        step_id=step_id,
                        stage_name=stage_name,
                    )
                else:
                    rng_for_stage = stage_rng.get(stage_name, idle_rng)
                current = self._dispatch(stage_name)(current, rng_for_stage, ctx_hit)
            prepared.append(((track_id, step_id), current, ctx_hit))

        prepared.sort(key=lambda item: (_hash_to_int(item[0][0]), _hash_to_int(item[0][1])))

        analog_adc_sum = np.zeros(self.n_samples, dtype=np.float64)
        for _identity, current, ctx_hit in prepared:
            light = ctx_hit.get("light_curve_mev")
            if light is None:
                edep = self._require_field(
                    current, "edep_mev", event_id=event_id, channel_id=channel_id
                )
                t = self._require_field(
                    current, "time_ns", event_id=event_id, channel_id=channel_id
                )
                light = integrate_samples(
                    edep,
                    t,
                    sample_spacing_ns=self.sample_spacing_ns,
                    n_samples=self.n_samples,
                    tau_rise_ns=self.tau_rise_ns,
                    tau_decay_ns=self.tau_decay_ns,
                )
            analog_adc_sum += apply_gain(light, self.electronics)

        waveform = analog_adc_sum + self.electronics.pedestal_adc
        waveform = add_noise(waveform, stage_rng["electronics"], self.electronics)
        adc_final, sat_final = quantize_adc(waveform, self.electronics)
        return {
            "event_id": event_id,
            "adc": adc_final,
            "saturated": sat_final,
            "n_hits": len(hits),
            "digitizer_rng_schema": DIGITIZER_RNG_SCHEMA,
        }


    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> DigitizerPipeline:
        elec = ElectronicsConfig(
            gain_adc_per_mev=float(config.get("gain_adc_per_mev", 120.0)),
            noise_adc_rms=float(config.get("noise_adc_rms", 8.0)),
            adc_bits=int(config.get("adc_bits", 14)),
            adc_ceiling=int(config.get("adc_ceiling", 7000)),
            pedestal_adc=float(config.get("pedestal_adc", 300.0)),
        )
        stages = list(config.get("stages", ["birks", "scintillation", "transport", "sampling"]))
        # #1076: never use Python truthiness — bool("false") is True.
        birks_prov = resolve_bool_field(config, "apply_birks", default=False)
        pipe = cls(
            n_samples=int(config.get("n_samples", DEFAULT_N_SAMPLES)),
            sample_spacing_ns=float(config.get("sample_spacing_ns", DEFAULT_SAMPLE_SPACING_NS)),
            electronics=elec,
            tau_rise_ns=float(config.get("tau_rise_ns", 2.0)),
            tau_decay_ns=float(config.get("tau_decay_ns", 35.0)),
            transport_sigma_ns=float(config.get("transport_sigma_ns", 0.5)),
            apply_birks=bool(birks_prov["effective"]),
            global_seed=int(config.get("global_seed", 0)),
            stages=stages,
        )
        # Provenance: requested vs effective boolean state (issue #1076).
        pipe._bool_provenance = {  # type: ignore[attr-defined]
            "apply_birks": birks_prov,
            "parser_version": PARSER_VERSION,
        }
        return pipe

    def bool_provenance(self) -> Mapping[str, Any]:
        """Requested/effective boolean config provenance (#1076)."""
        return getattr(
            self,
            "_bool_provenance",
            {
                "apply_birks": {
                    "key": "apply_birks",
                    "requested": None,
                    "requested_present": False,
                    "effective": bool(self.apply_birks),
                    "parser_version": PARSER_VERSION,
                    "default_applied": False,
                },
                "parser_version": PARSER_VERSION,
            },
        )
