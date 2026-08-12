"""MV0 digitizer pipeline: truth hits → one 18-sample ADC waveform per channel/event."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ccb_mc_validation.digitizer.birks import birks_quench
from ccb_mc_validation.digitizer.config_types import (
    parse_strict_bool,
    require_nonnegative_float,
    require_positive_float,
    require_positive_int,
    resolve_stage_graph,
)
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
from ccb_mc_validation.strict_bool import PARSER_VERSION, resolve_bool_field

StageFn = Callable[[Mapping[str, Any], np.random.Generator, dict[str, Any]], Mapping[str, Any]]

DIGITIZER_RNG_SCHEMA = "hit_keyed_v1"

# Schema fields required on every hit.  Missing fields or non-finite values are a
# hard error -- silently defaulting them to zero would corrupt the physics.
REQUIRED_HIT_FIELDS: tuple[str, ...] = ("edep_mev", "time_ns")
HIT_IDENTITY_FIELDS: tuple[str, ...] = ("track_id", "step_id")

# Stochastic stages that consume RNG; each receives its own independent
# deterministic stream derived from (global_seed, source, run, event, channel).
# "electronics" here names the final DAQ-observation noise stream (always applied),
# not a toggleable per-hit stage in ``stages``.
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

    Stage graph contract (``digitizer-stage-graph/1``, #1077):
      - ``stages`` lists per-hit transforms only.
      - Final DAQ observation (gain/pedestal/noise/quantize) is always applied
        once after summation and is not a stages-list toggle.
      - ``sampling`` is mandatory for the ADC observation model; omission is
        recorded as ``mandatory_inserted`` on the resolved graph.
      - Hidden sampling fallbacks are removed: no silent integrate_samples when
        sampling was not in the effective graph.
    """

    n_samples: int = DEFAULT_N_SAMPLES
    sample_spacing_ns: float = DEFAULT_SAMPLE_SPACING_NS
    electronics: ElectronicsConfig = field(default_factory=ElectronicsConfig)
    tau_rise_ns: float = 2.0
    tau_decay_ns: float = 35.0
    transport_sigma_ns: float = 0.5
    apply_birks: bool = False
    # Required when apply_birks is True (#1079). Units: cm/MeV.
    birks_kB_cm_per_MeV: float | None = None
    global_seed: int = 0
    stages: list[str] = field(
        default_factory=lambda: ["birks", "scintillation", "transport", "sampling"]
    )
    # Provenance filled by __post_init__ / resolve_stage_graph.
    requested_stages: list[str] = field(default_factory=list, repr=False)
    effective_stages: list[str] = field(default_factory=list, repr=False)
    stage_graph_meta: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self.n_samples = require_positive_int(self.n_samples, field_name="n_samples")
        self.sample_spacing_ns = require_positive_float(
            self.sample_spacing_ns, field_name="sample_spacing_ns"
        )
        self.tau_rise_ns = require_positive_float(self.tau_rise_ns, field_name="tau_rise_ns")
        self.tau_decay_ns = require_positive_float(self.tau_decay_ns, field_name="tau_decay_ns")
        self.transport_sigma_ns = require_nonnegative_float(
            self.transport_sigma_ns, field_name="transport_sigma_ns"
        )
        if not isinstance(self.apply_birks, bool):
            # Direct construction should already pass a real bool; coerce via
            # strict parser so string accidents fail closed here too.
            self.apply_birks = parse_strict_bool(self.apply_birks, field_name="apply_birks")
        if not isinstance(self.electronics, ElectronicsConfig):
            raise TypeError("electronics must be an ElectronicsConfig")
        # Re-run electronics validation in case a caller mutated fields.
        self.electronics.__post_init__()

        graph = resolve_stage_graph(list(self.stages))
        self.requested_stages = list(graph["requested_stages"])
        self.effective_stages = list(graph["effective_stages"])
        self.stage_graph_meta = graph
        # Execute the effective graph (may include mandatory sampling insert).
        self.stages = list(self.effective_stages)

    def resolved_config(self) -> dict[str, Any]:
        """Requested/effective config snapshot for provenance (#1076/#1077/#1080)."""
        return {
            "n_samples": self.n_samples,
            "sample_spacing_ns": self.sample_spacing_ns,
            "tau_rise_ns": self.tau_rise_ns,
            "tau_decay_ns": self.tau_decay_ns,
            "transport_sigma_ns": self.transport_sigma_ns,
            "apply_birks": {
                "effective": bool(self.apply_birks),
            },
            "global_seed": int(self.global_seed),
            "electronics": {
                "gain_adc_per_mev": self.electronics.gain_adc_per_mev,
                "noise_adc_rms": self.electronics.noise_adc_rms,
                "adc_bits": self.electronics.adc_bits,
                "adc_ceiling": self.electronics.adc_ceiling,
                "pedestal_adc": self.electronics.pedestal_adc,
            },
            "stage_graph": dict(self.stage_graph_meta),
        }

    def __post_init__(self) -> None:
        if self.apply_birks:
            if self.birks_kB_cm_per_mev is None:
                raise ValueError(
                    "apply_birks=True requires explicit birks_kB_cm_per_mev "
                    "(cm/MeV); refusing the implicit birks_quench default (#1079)"
                )
            kb = float(self.birks_kB_cm_per_mev)
            if not np.isfinite(kb) or kb < 0.0:
                raise ValueError(
                    f"birks_kB_cm_per_mev must be finite and >= 0, got {self.birks_kB_cm_per_mev!r}"
                )
            self.birks_kB_cm_per_mev = kb

    # ------------------------------------------------------------------
    # field validation
    # ------------------------------------------------------------------
    def _require_field(
        self,
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
                f"requires {REQUIRED_HIT_FIELDS}"
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
            if self.birks_kB_cm_per_MeV is None:
                raise ValueError(
                    "apply_birks=True requires an explicit birks_kB_cm_per_MeV "
                    "(#1079); refusing the silent 0.008 cm/MeV function default "
                    "as a production response identity"
                )
            try:
                out["edep_mev"] = birks_quench(
                    edep,
                    step_length_cm=hit.get("step_length_cm"),
                    dedx_mev_per_cm=hit.get("dedx_mev_per_cm"),
                    k_b_cm_per_mev=float(self.birks_kB_cm_per_MeV),
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
        ctx["_sampling_executed"] = True
        return out

    def _dispatch(self, stage_name: str) -> StageFn:
        table: dict[str, StageFn] = {
            "birks": self._stage_birks,
            "scintillation": self._stage_scintillation,
            "transport": self._stage_transport,
            "sampling": self._stage_sampling,
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
            "stage_graph": dict(getattr(self, "stage_graph_meta", {})),
            "requested_stages": list(getattr(self, "requested_stages", [])),
            "effective_stages": list(getattr(self, "effective_stages", getattr(self, "stages", []))),
        }

    @staticmethod
    def _parse_birks_kB(config: Mapping[str, Any], *, apply_birks: bool) -> float | None:
        """Parse explicit Birks kB with unit conversion (#1079).

        Worlds disagree (Python helper default 0.008 cm/MeV, Geant4 stave
        0.126 mm/MeV, Chapter-10 MV0 prose kB=0). Production must name the
        requested value; we do not invent a canonical physics choice here.
        """
        raw = config.get("birks_kB", config.get("birks_kB_cm_per_mev", None))
        unit = config.get("birks_kB_unit", None)
        if raw is None:
            if apply_birks:
                raise ValueError(
                    "apply_birks=True requires config key 'birks_kB' (or "
                    "'birks_kB_cm_per_mev') with 'birks_kB_unit' in "
                    "{'cm_per_MeV','mm_per_MeV'} (#1079)"
                )
            return None
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"birks_kB not coercible to float: {raw!r}") from exc
        if not np.isfinite(value) or value < 0.0:
            raise ValueError(f"birks_kB must be finite and >= 0, got {raw!r}")
        if unit is None:
            # Allow bare birks_kB_cm_per_mev key without separate unit.
            if "birks_kB_cm_per_mev" in config and "birks_kB" not in config:
                return value
            raise ValueError(
                "birks_kB_unit is required when birks_kB is set "
                "(expected 'cm_per_MeV' or 'mm_per_MeV') (#1079)"
            )
        unit_norm = str(unit).strip()
        if unit_norm in {"cm_per_MeV", "cm/MeV", "cm_per_mev"}:
            return value
        if unit_norm in {"mm_per_MeV", "mm/MeV", "mm_per_mev"}:
            return value / 10.0  # 1 cm/MeV = 10 mm/MeV
        raise ValueError(
            f"unsupported birks_kB_unit {unit!r}; use cm_per_MeV or mm_per_MeV (#1079)"
        )


    def _parse_birks_kb_cm_per_mev(config: Mapping[str, Any]) -> float | None:
        """Parse explicit Birks kB with unit tags (#1079).

        Accepts ``birks_kB_cm_per_MeV`` or ``birks_kB_mm_per_MeV`` (×0.1 → cm/MeV).
        Providing both, or a bare unlabelled ``kB`` / ``birks_kB``, is rejected.
        """
        has_cm = "birks_kB_cm_per_MeV" in config
        has_mm = "birks_kB_mm_per_MeV" in config
        forbidden = [k for k in ("kB", "birks_kB", "kb", "birks_kb") if k in config]
        if forbidden:
            raise ValueError(
                f"digitizer config has unlabelled Birks key(s) {forbidden}; "
                "use birks_kB_cm_per_MeV or birks_kB_mm_per_MeV (#1079)"
            )
        if has_cm and has_mm:
            raise ValueError(
                "digitizer config provides both birks_kB_cm_per_MeV and "
                "birks_kB_mm_per_MeV; provide exactly one unit-tagged value (#1079)"
            )
        if has_cm:
            kb = float(config["birks_kB_cm_per_MeV"])
        elif has_mm:
            kb = float(config["birks_kB_mm_per_MeV"]) * 0.1  # mm/MeV → cm/MeV
        else:
            return None
        if not np.isfinite(kb) or kb < 0.0:
            raise ValueError(
                f"Birks kB must be finite and non-negative in cm/MeV, got {kb!r} (#1079)"
            )
        return kb
    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> DigitizerPipeline:
        """Build a pipeline with strict typed parsing before event 0.

        Scientific booleans use :func:`parse_strict_bool` (#1076). Scalar domains
        and the stage graph are validated in ``__post_init__`` (#1075/#1077/#1080).
        """
        # #1076: resolve before preflight so bool("false") cannot leak into truthiness.
        from ccb_mc_validation.response.digitizer_domains import (
            DigitizerDomainError,
            preflight_digitizer_config,
        )

        from ccb_mc_validation.response.digitizer_domains import DigitizerDomainError

        try:
            birks_prov = resolve_bool_field(config, "apply_birks", default=False)
        except Exception as exc:  # ConfigurationError from strict_bool (#1076)
            # Satisfy both lane08 ValueError and lane03 ConfigurationError contracts.
            if isinstance(exc, DigitizerDomainError):
                raise
            raise DigitizerDomainError(str(exc)) from exc
        sanitized = dict(config)
        sanitized["apply_birks"] = bool(birks_prov["effective"])
        try:
            resolved = preflight_digitizer_config(sanitized)
        except DigitizerDomainError:
            raise
        except ValueError as exc:
            raise DigitizerDomainError(str(exc)) from exc
        effective = resolved["effective"]
        elec_cfg = effective["electronics"]
        elec = ElectronicsConfig(
            gain_adc_per_mev=config.get("gain_adc_per_mev", 120.0),
            noise_adc_rms=config.get("noise_adc_rms", 8.0),
            adc_bits=config.get("adc_bits", 14),
            adc_ceiling=config.get("adc_ceiling", 7000),
            pedestal_adc=config.get("pedestal_adc", 300.0),
        )

        kb = cls._parse_birks_kb_cm_per_mev(config)
        if bool(birks_prov["effective"]) and kb is None:
            raise ValueError(
                "apply_birks=True requires birks_kB_cm_per_MeV or "
                "birks_kB_mm_per_MeV (#1079); no silent default across "
                "Python/Geant4/prose quenching worlds"
            )
        pipe = cls(
            n_samples=int(effective["n_samples"]),
            sample_spacing_ns=float(effective["sample_spacing_ns"]),
            electronics=elec,
            tau_rise_ns=float(effective["tau_rise_ns"]),
            tau_decay_ns=float(effective["tau_decay_ns"]),
            transport_sigma_ns=float(effective["transport_sigma_ns"]),
            apply_birks=bool(birks_prov["effective"]),
            birks_kB_cm_per_MeV=kb,
            global_seed=int(effective["global_seed"]),
            stages=list(effective["stages"]),
        )
        pipe._bool_provenance = {  # type: ignore[attr-defined]
            "apply_birks": birks_prov,
            "parser_version": PARSER_VERSION,
        }
        return pipe

    def bool_provenance(self) -> Mapping[str, Any]:
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
