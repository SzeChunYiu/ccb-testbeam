"""Event-level truth rows with stable identifiers."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from ccb_mc_validation.truth.trigger import process_chunk


def stable_event_id(source: str, entry_index: int) -> str:
    """Deterministic 16-hex event id from MC file path and tree entry index."""
    key = f"{source}:{int(entry_index)}".encode()
    return hashlib.sha256(key).hexdigest()[:16]


def build_event_rows(
    chunk: dict[str, np.ndarray],
    *,
    source: str,
    entry_offset: int = 0,
    coinc_ns: float,
) -> list[dict[str, Any]]:
    """Build one event-level row per non-empty ``hibeam`` entry.

    Parameters
    ----------
    chunk:
        Dict of jagged branch arrays for at least ``Sci_bar_LayerID``,
        ``Sci_bar_LayerID1``, ``Sci_bar_PDG``, and ``Sci_bar_Time``.
    source:
        Absolute or repo-relative MC file path used for ``event_id`` hashing.
    entry_offset:
        Global entry index of ``chunk[0]`` within the ROOT tree.
    coinc_ns:
        Sample I coincidence window [ns].
    """
    layer = chunk["Sci_bar_LayerID"]
    flags = process_chunk(
        layer,
        chunk["Sci_bar_LayerID1"],
        chunk["Sci_bar_PDG"],
        chunk["Sci_bar_Time"],
        coinc_ns,
    )
    rows: list[dict[str, Any]] = []
    for i in range(len(layer)):
        l = np.asarray(layer[i])
        if l.size == 0:
            continue
        entry_index = entry_offset + i
        rows.append(
            {
                "event_id": stable_event_id(source, entry_index),
                "entry_index": entry_index,
                "source": source,
                "sample_I": bool(flags["sample_I"][i]),
                "sample_II": bool(flags["sample_II"][i]),
                "enter_B": bool(flags["enter_B"][i]),
                "enter_A": bool(flags["enter_A"][i]),
                "n_hits": int(l.size),
            }
        )
    return rows
