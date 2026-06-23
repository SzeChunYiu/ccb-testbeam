"""Sample I / II trigger classification for HiBeam MC truth."""

from __future__ import annotations

from typing import Any

import numpy as np

from ccb_mc_validation.constants import A_ARM, B_ARM
from ccb_mc_validation.truth.pdg import is_charged


def classify_event(
    enterB: bool,
    enterA: bool,
    tA: float,
    tB: float,
    coinc_ns: float,
) -> dict[str, bool]:
    """Classify one event into Sample I and/or Sample II.

    Semantics (legacy ``mc01_trigger_split_truth.py`` line 127):

    - **Sample II** — every event with a charged first-layer B entry.
    - **Sample I** — charged B entry **and** charged A entry with
      ``|tA - tB| < coinc_ns`` (strict less-than; equality is excluded).
    """
    coinc = bool(enterB and enterA and abs(float(tA) - float(tB)) < float(coinc_ns))
    return {
        "enter_B": bool(enterB),
        "enter_A": bool(enterA),
        "sample_II": bool(enterB),
        "sample_I": coinc,
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
        Coincidence window [ns] for Sample I.

    Returns
    -------
    dict
        Boolean/int arrays keyed by ``sample_I``, ``sample_II``, ``enter_B``,
        ``enter_A`` with length ``len(layer)``.
    """
    n_events = len(layer)
    sample_i = np.zeros(n_events, dtype=bool)
    sample_ii = np.zeros(n_events, dtype=bool)
    enter_b = np.zeros(n_events, dtype=bool)
    enter_a = np.zeros(n_events, dtype=bool)

    for i in range(n_events):
        l = np.asarray(layer[i])
        if l.size == 0:
            continue
        eb, ea, ta, tb = _event_enter_flags(
            l,
            np.asarray(layer1[i]),
            np.asarray(pdg[i]),
            np.asarray(time[i]),
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
