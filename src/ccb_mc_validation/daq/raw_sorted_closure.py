"""Exact raw→sorted waveform-word closure (#953).

A scalar ``hrdMax`` count match is not closure. Authorising production requires
either:

1. exact equality of every preserved ADC word for every event/channel/sample, or
2. an explicit irreversible-transform contract plus equality of every intermediate
   quantity required to reconstruct each derived feature.

This module implements (1) for in-memory arrays and records mismatch evidence.
Real-run ROOT orchestration is wired by S00; CI uses synthetic adversarial
fixtures so the gate fails closed without inventing sorter physics.
"""

from __future__ import annotations

from typing import Any

import numpy as np


SCHEMA = "ccb-raw-sorted-word-closure/1"
GATE_PASS = "PASS"
GATE_FAIL = "FAIL"
GATE_INCOMPLETE_SCALAR_PROXY = "INCOMPLETE_SCALAR_PROXY"


class RawSortedClosureError(RuntimeError):
    """Raised when raw→sorted word closure cannot authorise production."""


def compare_waveform_words(
    raw: np.ndarray,
    sorted_arr: np.ndarray,
    *,
    event_keys: np.ndarray | None = None,
    max_mismatch_examples: int = 8,
) -> dict[str, Any]:
    """Compare raw vs sorted waveform tensors for exact word equality.

    Parameters
    ----------
    raw, sorted_arr:
        Arrays shaped ``(n_events, n_channels, n_samples)`` with identical dtype
        after integer casting.
    event_keys:
        Optional length-``n_events`` identity labels used in mismatch examples.
    """
    raw_a = np.asarray(raw)
    sorted_a = np.asarray(sorted_arr)
    if raw_a.shape != sorted_a.shape:
        return {
            "schema": SCHEMA,
            "gate_state": GATE_FAIL,
            "equal": False,
            "reason": f"shape mismatch raw={raw_a.shape} sorted={sorted_a.shape}",
            "n_mismatched_words": None,
            "mismatch_examples": [],
        }
    if raw_a.size == 0:
        return {
            "schema": SCHEMA,
            "gate_state": GATE_PASS,
            "equal": True,
            "reason": "empty domain",
            "n_mismatched_words": 0,
            "mismatch_examples": [],
        }

    raw_i = np.asarray(raw_a, dtype=np.int64)
    sorted_i = np.asarray(sorted_a, dtype=np.int64)
    diff = raw_i != sorted_i
    n_bad = int(diff.sum())
    examples: list[dict[str, Any]] = []
    if n_bad:
        bad_idx = np.argwhere(diff)
        for coords in bad_idx[: max(0, int(max_mismatch_examples))]:
            e, c, s = (int(coords[0]), int(coords[1]), int(coords[2]))
            key = None if event_keys is None else event_keys[e]
            examples.append(
                {
                    "event_index": e,
                    "event_key": None if key is None else str(key),
                    "channel": c,
                    "sample": s,
                    "raw": int(raw_i[e, c, s]),
                    "sorted": int(sorted_i[e, c, s]),
                }
            )
    return {
        "schema": SCHEMA,
        "gate_state": GATE_PASS if n_bad == 0 else GATE_FAIL,
        "equal": n_bad == 0,
        "reason": "exact word equality" if n_bad == 0 else "waveform word mismatches",
        "n_events": int(raw_i.shape[0]),
        "n_channels": int(raw_i.shape[1]),
        "n_samples": int(raw_i.shape[2]),
        "n_mismatched_words": n_bad,
        "mismatch_examples": examples,
    }


def closure_report(
    *,
    word_closure: dict[str, Any] | None,
    scalar_proxy_used: bool,
) -> dict[str, Any]:
    """Combine word-closure and scalar-proxy status into an authorising gate."""
    if scalar_proxy_used and word_closure is None:
        return {
            "schema": SCHEMA,
            "gate_state": GATE_INCOMPLETE_SCALAR_PROXY,
            "authorising": False,
            "reason": (
                "Only scalar hrdMax/selected-count proxy was computed. "
                "Issue #953 requires exact per-word ADC closure before physics."
            ),
        }
    if word_closure is None:
        return {
            "schema": SCHEMA,
            "gate_state": GATE_FAIL,
            "authorising": False,
            "reason": "word closure missing",
        }
    ok = bool(word_closure.get("equal"))
    return {
        "schema": SCHEMA,
        "gate_state": GATE_PASS if ok else GATE_FAIL,
        "authorising": ok,
        "word_closure": word_closure,
        "reason": word_closure.get("reason"),
    }


def adversarial_fixtures() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Deterministic fixtures that must fail word closure while scalar counts can pass."""
    base = np.arange(2 * 8 * 4, dtype=np.int16).reshape(2, 8, 4)
    fixtures: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    rotated = base.copy()
    rotated[..., :] = np.roll(base, 1, axis=-1)
    fixtures["rotate_samples"] = (base, rotated)

    swapped = base.copy()
    swapped[:, [0, 1], :] = base[:, [1, 0], :]
    fixtures["swap_channels"] = (base, swapped)

    zero_ch7 = base.copy()
    zero_ch7[:, 7, :] = 0
    fixtures["zero_channel_7"] = (base, zero_ch7)

    one_word = base.copy()
    one_word[0, 0, 0] = int(base[0, 0, 0]) + 1
    fixtures["single_word_flip"] = (base, one_word)

    reordered = base[::-1].copy()
    fixtures["reorder_events"] = (base, reordered)

    inverted = (-base).astype(np.int16)
    fixtures["invert_polarity"] = (base, inverted)

    return fixtures
