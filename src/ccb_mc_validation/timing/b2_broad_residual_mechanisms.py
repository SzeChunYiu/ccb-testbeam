"""Mechanism-neutral B2 broad-residual discrimination contract (#968).

Broad B2-containing timing residuals are not uniquely pile-up.  This module
provides fail-closed authorization for microscopic ``pile-up-like`` wording and
mechanism-neutral waveform observables that rank competing hypotheses without
collapsing them into a single microscopic label.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

import numpy as np

CONTRACT_PROFILE = "b2_broad_residual_mechanism_neutral_v1"
AUTHORISING_PILEUP_LIKE = False

# Required external discriminants from AF-020 / ARU section 15 before any
# microscopic pile-up-like classification may be promoted.
REQUIRED_DISCRIMINANTS: tuple[str, ...] = (
    "current_rate_dependence",
    "delay_spectrum",
    "duplicate_channel_parity",
    "track_tpc_association",
    "injected_correlated_noise_mc",
    "electronics_impulse_response",
    "raw_word_defect_flags",
    "exact_event_key_closure",
)


class BroadResidualMechanism(str, Enum):
    """Competing microscopic descriptions for broad B2 timing residuals."""

    TWO_PARTICLE_PILEUP = "two_particle_pileup"
    TERMINAL_PRIMARY_SECONDARY = "terminal_primary_secondary"
    SIPM_AFTERPULSE_RECOVERY = "sipm_afterpulse_recovery"
    ELECTRONICS_SHAPING = "electronics_shaping"
    OPTICAL_CROSSTALK = "optical_crosstalk"
    ADC_LOW_WORD_DEFECT = "adc_low_word_defect"
    POLARITY_MAPPING = "polarity_mapping"
    BUFFER_PHASE = "buffer_phase"
    EVENT_ASSOCIATION = "event_association"
    SPECIES_VELOCITY = "species_velocity"
    UNRESOLVED = "unresolved"


class DiscriminantEvidence(str, Enum):
    NOT_EXECUTED = "NOT_EXECUTED"
    PARTIAL = "PARTIAL"
    SATISFIED = "SATISFIED"


class PileupLikeAuthorizationError(RuntimeError):
    """Raised when microscopic pile-up-like wording is requested without evidence."""


@dataclass(frozen=True)
class MechanismNeutralObservables:
    """Waveform-only observables that do not imply a microscopic mechanism."""

    late_tail_fraction: float
    pretrigger_excursion_adc: float
    secondary_peak_delay_samples: float | None
    duplicate_parity_mismatch: bool | None
    selected_to_global_ratio: float | None
    eligible_local_peak_count: int
    selector_fallback: bool


@dataclass(frozen=True)
class MechanismSupportTable:
    """Diagnostic support scores in [0, 1]; not calibrated probabilities."""

    observables: MechanismNeutralObservables
    support: dict[BroadResidualMechanism, float]
    leading_mechanisms: tuple[BroadResidualMechanism, ...]
    pileup_like_authorized: bool
    authorization_status: str
    missing_discriminants: tuple[str, ...]


@dataclass(frozen=True)
class PileupLikeAuthorization:
    authorized: bool
    status: str
    missing_discriminants: tuple[str, ...]
    authorising_pileup_like: bool = AUTHORISING_PILEUP_LIKE


def _as_1d(waveform: np.ndarray) -> np.ndarray:
    wave = np.asarray(waveform, dtype=float)
    if wave.ndim != 1:
        raise ValueError(f"waveform must be 1-D, got shape {wave.shape}")
    if wave.size < 4:
        raise ValueError(f"waveform needs >=4 samples, got {wave.size}")
    if not np.isfinite(wave).all():
        raise ValueError("waveform contains non-finite samples")
    return wave


def _secondary_peak_delay_samples(wave: np.ndarray) -> float | None:
    global_index = int(np.argmax(wave))
    floor = 0.05 * float(np.max(wave))
    eligible: list[int] = []
    for index in range(1, wave.size - 1):
        if (
            wave[index] >= wave[index - 1]
            and wave[index] >= wave[index + 1]
            and wave[index] >= floor
        ):
            eligible.append(index)
    if len(eligible) < 2:
        return None
    first, second = eligible[0], eligible[1]
    if first == global_index:
        return float(second - first)
    if second == global_index:
        return float(second - first)
    return float(global_index - first)


def compute_mechanism_neutral_observables(
    waveform: np.ndarray,
    *,
    duplicate_parity_mismatch: bool | None = None,
    selector_diagnostics: Mapping[str, object] | None = None,
) -> MechanismNeutralObservables:
    """Return mechanism-neutral waveform observables for B2 broad-residual study."""
    wave = _as_1d(waveform)
    peak_index = int(np.argmax(wave))
    peak_value = float(wave[peak_index])
    pretrigger = wave[: min(4, wave.size)]
    pretrigger_excursion = float(np.max(pretrigger) - np.min(pretrigger))
    tail = wave[peak_index + 1 :] if peak_index + 1 < wave.size else np.asarray([], dtype=float)
    late_tail_fraction = 0.0
    if peak_value > 0 and tail.size:
        late_tail_fraction = float(np.sum(tail > 0.05 * peak_value) / tail.size)

    selected_to_global_ratio: float | None = None
    eligible_local_peak_count = 0
    selector_fallback = False
    if selector_diagnostics is not None:
        ratios = np.asarray(selector_diagnostics["selected_to_global_ratio"], dtype=float)
        counts = np.asarray(selector_diagnostics["eligible_local_peak_counts"], dtype=int)
        statuses = np.asarray(selector_diagnostics["statuses"], dtype=object)
        if ratios.size:
            selected_to_global_ratio = float(ratios[0])
        if counts.size:
            eligible_local_peak_count = int(counts[0])
        if statuses.size:
            selector_fallback = str(statuses[0]).endswith("FALLBACK_GLOBAL")

    return MechanismNeutralObservables(
        late_tail_fraction=late_tail_fraction,
        pretrigger_excursion_adc=pretrigger_excursion,
        secondary_peak_delay_samples=_secondary_peak_delay_samples(wave),
        duplicate_parity_mismatch=duplicate_parity_mismatch,
        selected_to_global_ratio=selected_to_global_ratio,
        eligible_local_peak_count=eligible_local_peak_count,
        selector_fallback=selector_fallback,
    )


def rank_mechanism_support(
    observables: MechanismNeutralObservables,
) -> dict[BroadResidualMechanism, float]:
    """Rank mechanism hypotheses using neutral observables only."""
    support = {mechanism: 0.0 for mechanism in BroadResidualMechanism}
    if observables.late_tail_fraction > 0.2 and observables.secondary_peak_delay_samples:
        delay = observables.secondary_peak_delay_samples
        support[BroadResidualMechanism.TWO_PARTICLE_PILEUP] += min(1.0, delay / 6.0)
        support[BroadResidualMechanism.SIPM_AFTERPULSE_RECOVERY] += min(
            1.0, delay / 10.0
        )
        support[BroadResidualMechanism.TERMINAL_PRIMARY_SECONDARY] += 0.5 * min(
            1.0, delay / 8.0
        )
    if observables.pretrigger_excursion_adc > 150.0:
        support[BroadResidualMechanism.ELECTRONICS_SHAPING] += 0.7
        support[BroadResidualMechanism.BUFFER_PHASE] += 0.5
    if observables.duplicate_parity_mismatch is True:
        support[BroadResidualMechanism.POLARITY_MAPPING] += 0.9
        support[BroadResidualMechanism.ADC_LOW_WORD_DEFECT] += 0.6
    if observables.selector_fallback:
        support[BroadResidualMechanism.BUFFER_PHASE] += 0.4
        support[BroadResidualMechanism.UNRESOLVED] += 0.3
    if (
        observables.selected_to_global_ratio is not None
        and observables.selected_to_global_ratio < 0.2
    ):
        support[BroadResidualMechanism.TWO_PARTICLE_PILEUP] += 0.4
        support[BroadResidualMechanism.SIPM_AFTERPULSE_RECOVERY] += 0.4
        support[BroadResidualMechanism.UNRESOLVED] += 0.2
    if observables.eligible_local_peak_count > 1:
        support[BroadResidualMechanism.UNRESOLVED] += 0.5
    return support


def select_leading_mechanisms(
    support: Mapping[BroadResidualMechanism, float],
    *,
    tolerance: float = 1e-9,
) -> tuple[BroadResidualMechanism, ...]:
    if not support:
        return (BroadResidualMechanism.UNRESOLVED,)
    best = max(support.values())
    leaders = tuple(
        mechanism
        for mechanism, score in support.items()
        if abs(score - best) <= tolerance and score > 0.0
    )
    if len(leaders) != 1:
        return (BroadResidualMechanism.UNRESOLVED,)
    return leaders


def authorize_pileup_like_wording(
    discriminant_status: Mapping[str, DiscriminantEvidence | str],
) -> PileupLikeAuthorization:
    """Fail-closed gate for microscopic pile-up-like classification."""
    missing: list[str] = []
    for name in REQUIRED_DISCRIMINANTS:
        status = discriminant_status.get(name, DiscriminantEvidence.NOT_EXECUTED)
        if isinstance(status, str):
            status = DiscriminantEvidence(status)
        if status is not DiscriminantEvidence.SATISFIED:
            missing.append(name)
    if missing or not AUTHORISING_PILEUP_LIKE:
        return PileupLikeAuthorization(
            authorized=False,
            status="BLOCKED_MECHANISM_UNDISCRIMINATED",
            missing_discriminants=tuple(missing),
        )
    return PileupLikeAuthorization(
        authorized=True,
        status="AUTHORIZED",
        missing_discriminants=tuple(),
    )


def assert_pileup_like_authorized(
    discriminant_status: Mapping[str, DiscriminantEvidence | str],
) -> PileupLikeAuthorization:
    decision = authorize_pileup_like_wording(discriminant_status)
    if not decision.authorized:
        missing = ", ".join(decision.missing_discriminants) or "authorising flag false"
        raise PileupLikeAuthorizationError(
            "microscopic pile-up-like wording blocked (#968): "
            f"{decision.status}; missing={missing}"
        )
    return decision


def classify_b2_broad_residual_support(
    waveform: np.ndarray,
    *,
    duplicate_parity_mismatch: bool | None = None,
    discriminant_status: Mapping[str, DiscriminantEvidence | str] | None = None,
    selector_diagnostics: Mapping[str, object] | None = None,
) -> MechanismSupportTable:
    """Mechanism-neutral B2 broad-residual support table."""
    observables = compute_mechanism_neutral_observables(
        waveform,
        duplicate_parity_mismatch=duplicate_parity_mismatch,
        selector_diagnostics=selector_diagnostics,
    )
    support = rank_mechanism_support(observables)
    leaders = select_leading_mechanisms(support)
    decision = authorize_pileup_like_wording(discriminant_status or {})
    return MechanismSupportTable(
        observables=observables,
        support=support,
        leading_mechanisms=leaders,
        pileup_like_authorized=decision.authorized,
        authorization_status=decision.status,
        missing_discriminants=decision.missing_discriminants,
    )


def mechanism_neutral_class_label(table: MechanismSupportTable) -> str:
    """Return a non-authorizing timing-residual class label."""
    if table.pileup_like_authorized:
        return "pileup_like_authorized"
    if table.leading_mechanisms == (BroadResidualMechanism.UNRESOLVED,):
        return "b2_broad_residual_unresolved"
    return "b2_broad_residual_mechanism_ambiguous"
