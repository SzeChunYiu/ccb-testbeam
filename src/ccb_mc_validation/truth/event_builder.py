"""Event-level truth rows with stable identifiers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from ccb_mc_validation.truth.trigger import process_chunk

DEFAULT_TREE_NAME: str = "hibeam"


def compute_content_fingerprint(path: str | Path) -> str:
    """SHA-256 of the raw bytes of an MC file (content, not path, based).

    This makes :func:`stable_event_id` invariant to path spelling / symlinks
    while still uniquely binding the id to a specific production file.  It is
    O(filesize); callers that stream many files should cache the result.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def stable_event_id(content_fingerprint: str, tree_name: str, entry_index: int) -> str:
    """Deterministic 16-hex event id from MC **content** fingerprint + tree + entry.

    The id intentionally depends on the file *content* (sha-256) and tree name,
    not on the filesystem path, so renaming / symlinking an MC file does not
    re-identify its events (TRU-008).
    """
    if not content_fingerprint:
        raise ValueError("content_fingerprint must be a non-empty sha-256 hex string")
    key = f"{content_fingerprint}:{tree_name}:{int(entry_index)}".encode()
    return hashlib.sha256(key).hexdigest()[:16]


def build_event_rows(
    chunk: dict[str, np.ndarray],
    *,
    content_fingerprint: str,
    tree_name: str = DEFAULT_TREE_NAME,
    coinc_ns: float,
    entry_offset: int = 0,
    source: str = "",
) -> list[dict[str, Any]]:
    """Build one event-level row per ``hibeam`` entry, **including zero-hit events**.

    Parameters
    ----------
    chunk:
        Dict of jagged branch arrays for at least ``Sci_bar_LayerID``,
        ``Sci_bar_LayerID1``, ``Sci_bar_PDG``, and ``Sci_bar_Time``.
    content_fingerprint:
        SHA-256 of the MC file bytes (see :func:`compute_content_fingerprint`).
        Drives ``event_id`` so the id is path-independent.
    tree_name:
        ROOT tree name the chunk was read from (default ``hibeam``).
    coinc_ns:
        Sample I coincidence window [ns].
    entry_offset:
        Global entry index of ``chunk[0]`` within the ROOT tree.
    source:
        Human-readable provenance (path / dataset id); recorded for audit, not
        used to hash the event id.

    Notes
    -----
    Empty (zero-hit) truth entries are **retained** with ``n_hits == 0`` and all
    trigger flags False (TRU-009), so efficiency / acceptance denominators are
    not silently inflated by dropping events that produced no Sci_bar hits.
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
        layer_i = np.asarray(layer[i])
        n_hits = int(layer_i.size)
        entry_index = int(entry_offset + i)
        rows.append(
            {
                "event_id": stable_event_id(content_fingerprint, tree_name, entry_index),
                "entry_index": entry_index,
                "content_fingerprint": str(content_fingerprint),
                "tree_name": str(tree_name),
                "source": str(source),
                "sample_I": bool(flags["sample_I"][i]),
                "sample_II": bool(flags["sample_II"][i]),
                "enter_B": bool(flags["enter_B"][i]),
                "enter_A": bool(flags["enter_A"][i]),
                "has_hits": n_hits > 0,
                "n_hits": n_hits,
            }
        )
    return rows
