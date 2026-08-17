"""Sample I / II trigger classification for HiBeam MC truth."""

from __future__ import annotations

from typing import Any

import numpy as np

from ccb_mc_validation.constants import A_ARM, B_ARM
from ccb_mc_validation.exceptions import ConfigurationError, DataContractError
from ccb_mc_validation.truth.pdg import is_charged


# Fail-closed evidence labelling for #1045 / ADR-0002 + ADR-1045.
# The classifier below implements the HRD first-stack-layer charged-hit proxy
# only. It is NOT a validated hardware-trigger response model: the MC-side
# proxy -> instrumented-hardware-response migration has been quantified
# (ADR-1045, evidence_state MIGRATION_VALIDATED), but real-data
# hardware-trigger claims remain forbidden and Sample I/II production
# membership continues to use this proxy.
TRIGGER_EVIDENCE_STATE = "MIGRATION_VALIDATED"
TRIGGER_LABEL = "MC_TRIGGER_PROXY"
TRIGGER_HARDWARE_DEFINITION_STATUS = "GEOMETRY_SOURCE_BOUND_ELECTRONICS_UNVALIDATED"
_FORBIDDEN_HARDWARE_CLAIM_TOKENS = (
    "hardware-trigger reproduction",
    "hardware_trigger_validated",
    "validated hardware trigger",
)


def trigger_provenance() -> dict[str, str]:
    """Machine-readable provenance for Sample I/II MC membership."""
    return {
        "evidence_state": TRIGGER_EVIDENCE_STATE,
        "label": TRIGGER_LABEL,
        "hardware_definition_status": TRIGGER_HARDWARE_DEFINITION_STATUS,
        "proxy_id": "HRD_FIRST_STACK_LAYER_CHARGED_HIT",
        "contract": "docs/contracts/TRIGGER_HARDWARE_RESPONSE.json",
        "adr": "docs/mc_validation/ADR-0002-trigger-hardware-proxy-blocked.md",
        "migration_adr": "docs/mc_validation/adr/ADR-1045-migration-validated.md",
    }


def assert_not_hardware_trigger_claim(text: str) -> None:
    """Fail closed if narrative text asserts a validated hardware trigger."""
    lowered = str(text).lower()
    for token in _FORBIDDEN_HARDWARE_CLAIM_TOKENS:
        if token in lowered:
            raise DataContractError(
                "forbidden hardware-trigger claim (real-data hardware-trigger "
                f"claims remain forbidden at evidence_state={TRIGGER_EVIDENCE_STATE}): "
                f"{token!r}"
            )



def _validate_coinc_ns(coinc_ns: float) -> float:
    """Coincidence window must be a finite, strictly-positive number of ns."""
    c = float(coinc_ns)
    if not np.isfinite(c):
        raise ConfigurationError(f"coinc_ns must be finite, got {coinc_ns!r}")
    if c <= 0.0:
        raise ConfigurationError(f"coinc_ns must be > 0 ns, got {c}")
    return c


def _validate_event_row(
    layer: np.ndarray, layer1: np.ndarray, pdg: np.ndarray, time: np.ndarray
) -> None:
    """Validate per-event jagged shapes and finite/range constraints (TRU-010)."""
    names = ("layer", "layer1", "pdg", "time")
    arrays = (layer, layer1, pdg, time)
    n = int(np.asarray(layer).size)
    for name, arr in zip(names, arrays):
        a = np.asarray(arr)
        if int(a.size) != n:
            raise DataContractError(
                f"jagged length mismatch: layer has {n} entries but {name} has {int(a.size)}"
            )
    t = np.asarray(time, dtype=float)
    if t.size and not np.all(np.isfinite(t)):
        raise DataContractError("non-finite value in Sci_bar_Time for event")
    # Layer/arm indices are small non-negative integers; flag corruption.
    for name, arr in (("layer", layer), ("layer1", layer1)):
        a = np.asarray(arr)
        if a.size and (np.nanmin(a.astype(float)) < 0 or not np.all(np.isfinite(a.astype(float)))):
            raise DataContractError(f"non-finite/negative value in {name} for event")


def classify_event(
    enterB: bool,
    enterA: bool,
    tA: float,
    tB: float,
    coinc_ns: float,
) -> dict[str, bool]:
    """Classify one event into Sample I and/or Sample II (HRD proxy only).

    Sample I/II membership uses the ``MC_TRIGGER_PROXY`` definition; the
    MC-side migration study (ADR-1045) does not change this classifier and
    real-data hardware-trigger claims remain forbidden (ADR-0002).

    Semantics (legacy ``mc01_trigger_split_truth.py`` line 127):

    - **Sample II** — every event with a charged first-layer B entry.
    - **Sample I** — charged B entry **and** charged A entry with
      ``|tA - tB| < coinc_ns`` (strict less-than; equality is excluded).
    """
    coinc_ns = _validate_coinc_ns(coinc_ns)
    if not (enterB and enterA):
        coinc = False
    else:
        ta = float(tA)
        tb = float(tB)
        if not (np.isfinite(ta) and np.isfinite(tb)):
            raise DataContractError(f"non-finite trigger time(s): tA={tA!r} tB={tB!r}")
        coinc = abs(ta - tb) < coinc_ns
    return {
        "enter_B": bool(enterB),
        "enter_A": bool(enterA),
        "sample_II": bool(enterB),
        "sample_I": bool(coinc),
    }


def _event_enter_flags(
    layer: np.ndarray,
    layer1: np.ndarray,
    pdg: np.ndarray,
    time: np.ndarray,
    *,
    b_arm: int = B_ARM,
    a_arm: int = A_ARM,
) -> tuple[bool, bool, float, float]:
    charged = np.fromiter((is_charged(int(p)) for p in pdg), dtype=bool, count=len(pdg))
    is_b = layer1 == b_arm
    is_a = layer1 == a_arm
    first_b = is_b & (layer == 0) & charged
    first_a = is_a & (layer == 0) & charged
    enter_b = bool(first_b.any())
    enter_a = bool(first_a.any())
    t_b = float(time[first_b].min()) if enter_b else float("nan")
    t_a = float(time[first_a].min()) if enter_a else float("nan")
    return enter_b, enter_a, t_a, t_b


def process_chunk(
    layer: np.ndarray,
    layer1: np.ndarray,
    pdg: np.ndarray,
    time: np.ndarray,
    coinc_ns: float,
    *,
    b_arm: int = B_ARM,
    a_arm: int = A_ARM,
) -> dict[str, np.ndarray]:
    """Vectorized Sample I/II classification for jagged ``hibeam`` chunk arrays.

    Parameters
    ----------
    layer, layer1, pdg, time:
        Per-event jagged arrays (object dtype or list-like), one row per MC event.
    coinc_ns:
        Coincidence window [ns] for Sample I (must be finite and > 0).

    Returns
    -------
    dict
        Boolean/int arrays keyed by ``sample_I``, ``sample_II``, ``enter_B``,
        ``enter_A`` with length ``len(layer)``.

    Raises
    ------
    ConfigurationError
        If ``coinc_ns`` is non-finite or non-positive.
    DataContractError
        If per-event jagged lengths disagree or any time/arm value is
        non-finite (TRU-010).
    """
    coinc_ns = _validate_coinc_ns(coinc_ns)
    n_events = len(layer)
    sample_i = np.zeros(n_events, dtype=bool)
    sample_ii = np.zeros(n_events, dtype=bool)
    enter_b = np.zeros(n_events, dtype=bool)
    enter_a = np.zeros(n_events, dtype=bool)

    for i in range(n_events):
        layer_i = np.asarray(layer[i])
        l1 = np.asarray(layer1[i])
        pd = np.asarray(pdg[i])
        tm = np.asarray(time[i])
        if layer_i.size == 0:
            # Empty event: validate the sibling arrays are also empty, then
            # leave all trigger flags at their (False) defaults.
            if l1.size or pd.size or tm.size:
                raise DataContractError(
                    f"event {i}: layer is empty but a sibling branch is non-empty"
                )
            continue
        _validate_event_row(layer_i, l1, pd, tm)
        eb, ea, ta, tb = _event_enter_flags(
            layer_i,
            l1,
            pd,
            tm,
            b_arm=b_arm,
            a_arm=a_arm,
        )
        flags = classify_event(eb, ea, ta, tb, coinc_ns)
        sample_i[i] = flags["sample_I"]
        sample_ii[i] = flags["sample_II"]
        enter_b[i] = flags["enter_B"]
        enter_a[i] = flags["enter_A"]

    return {
        "sample_I": sample_i,
        "sample_II": sample_ii,
        "enter_B": enter_b,
        "enter_A": enter_a,
    }


def summarize_chunk(flags: dict[str, np.ndarray]) -> dict[str, Any]:
    """Aggregate trigger flags for logging or cutflow tables."""
    return {
        "n_events": int(len(flags["sample_I"])),
        "n_sample_I": int(flags["sample_I"].sum()),
        "n_sample_II": int(flags["sample_II"].sum()),
        "n_enter_B": int(flags["enter_B"].sum()),
        "n_enter_A": int(flags["enter_A"].sum()),
    }
