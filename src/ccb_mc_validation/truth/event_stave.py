"""Event/stave truth aggregation with explicit generator-event semantics.

This module supplies the level-H3 intermediate required by issues #1052/#1164:
one row per generator event, with B-stave deposited energy aggregated over
transport records. It is deliberately a truth diagnostic, not a detector
response analogue; quenching, optical transport, SiPM/electronics response,
sampling, digitization, and DATA reconstruction remain downstream.
"""

from __future__ import annotations

import errno
import hashlib
import math
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import numpy as np

from ccb_mc_validation.constants import B_ARM, NB_LAYERS
from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.event_builder import build_event_rows
from ccb_mc_validation.truth.pdg import is_charged
from ccb_mc_validation.truth.weight_adapter import (
    MODE_DIRECT_UNIT,
    WEIGHT_ADAPTER_SCHEMA,
    adapt_raw_primary_weight,
    resolve_adapter_id,
)

EVENT_STAVE_SCHEMA_ID = "mc_event_stave_edep_v1"
STATISTICAL_UNIT = "generator_event"
EVENT_KEY_TYPE = "sha256_file_tree_entry_v1"
AGGREGATION_RULE = "sum_all_sci_bar_edep_per_generator_event_b_stave"
CHARGED_DIAGNOSTIC_RULE = "sum_charged_sci_bar_edep_per_generator_event_b_stave"
AUTHORISATION_STATE = "NONAUTHORISING_TRUTH_DIAGNOSTIC"
# Legacy fallback text kept only for comparison exports built without an
# explicit adapter provenance source. New products bind a versioned
# weight_adapter_id instead (issue #880).
PRIMARY_WEIGHT_SEMANTICS = "first_primary_PrimaryWeight_once_per_generator_event"
UNIT_WEIGHT_DIAGNOSTIC_SEMANTICS = "unit_weight_explicit_no_weight_mode"
LEGACY_SEMANTICS_UNBOUND = "unbound_legacy_first_primary_semantics"


@dataclass(frozen=True)
class EventStaveEDep:
    """Deposited-energy summaries for one generator event across B staves."""

    total_edep_mev: np.ndarray
    charged_edep_mev: np.ndarray
    hit_count: np.ndarray
    charged_hit_count: np.ndarray


@dataclass(frozen=True)
class FingerprintedSource:
    """Content and descriptor identity of the exact opened source object."""

    sha256: str
    bytes: int
    source_dev: int
    source_ino: int
    source_nlink: int
    source_mtime_ns: int
    source_ctime_ns: int


def _descriptor_identity(info: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        int(info.st_dev),
        int(info.st_ino),
        int(info.st_nlink),
        int(info.st_size),
        int(info.st_mtime_ns),
        int(info.st_ctime_ns),
    )


@contextmanager
def fingerprinted_regular_file_stream(
    path: str | Path,
    *,
    block_size: int = 1 << 20,
) -> Iterator[tuple[BinaryIO, FingerprintedSource]]:
    """Yield a seekable stream whose digest and consumer share one opened file.

    The file is opened once with ``O_NOFOLLOW``. SHA-256 and byte count are
    measured from that descriptor, then Uproot (or another consumer) may read a
    duplicate seekable stream. Descriptor metadata must remain unchanged until
    the consumer exits. Scientific output should only be written after this
    context has exited successfully.
    """
    if isinstance(block_size, bool) or not isinstance(block_size, (int, np.integer)):
        raise ValueError("block_size must be a positive integer")
    block = int(block_size)
    if block <= 0:
        raise ValueError("block_size must be a positive integer")

    source_path = Path(path)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is None:
        raise DataContractError("fingerprinted input requires os.O_NOFOLLOW")
    try:
        descriptor = os.open(source_path, os.O_RDONLY | nofollow)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise DataContractError(
                f"input final path component must not be a symlink: {source_path}"
            ) from exc
        raise

    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise DataContractError(f"input is not a regular file: {source_path}")

        digest = hashlib.sha256()
        byte_count = 0
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            payload = os.read(descriptor, block)
            if not payload:
                break
            digest.update(payload)
            byte_count += len(payload)
        verified = os.fstat(descriptor)
        if _descriptor_identity(verified) != _descriptor_identity(before):
            raise DataContractError(
                f"input changed while content fingerprint was measured: {source_path}"
            )
        if byte_count != int(verified.st_size):
            raise DataContractError(
                f"input byte count changed while fingerprinting: "
                f"{byte_count} != {verified.st_size}"
            )

        source = FingerprintedSource(
            sha256=digest.hexdigest(),
            bytes=byte_count,
            source_dev=int(verified.st_dev),
            source_ino=int(verified.st_ino),
            source_nlink=int(verified.st_nlink),
            source_mtime_ns=int(verified.st_mtime_ns),
            source_ctime_ns=int(verified.st_ctime_ns),
        )
        os.lseek(descriptor, 0, os.SEEK_SET)
        consumer_descriptor = os.dup(descriptor)
        with os.fdopen(consumer_descriptor, "rb") as stream:
            yield stream, source

        final = os.fstat(descriptor)
        if _descriptor_identity(final) != _descriptor_identity(verified):
            raise DataContractError(
                f"input changed while the consumer held the opened stream: {source_path}"
            )
    finally:
        os.close(descriptor)


def _as_1d(name: str, values: Any, *, dtype: Any | None = None) -> np.ndarray:
    arr = np.asarray(values, dtype=dtype)
    if arr.ndim != 1:
        raise DataContractError(f"{name} must be one-dimensional, got shape {arr.shape}")
    return arr


def _integer_codes(name: str, values: Any) -> np.ndarray:
    arr = _as_1d(name, values)
    try:
        numeric = arr.astype(float)
    except (TypeError, ValueError) as exc:
        raise DataContractError(f"{name} must contain finite integer-valued codes") from exc
    if numeric.size and not np.all(np.isfinite(numeric)):
        raise DataContractError(f"{name} contains non-finite values")
    rounded = np.rint(numeric)
    if numeric.size and not np.array_equal(numeric, rounded):
        raise DataContractError(f"{name} contains non-integer values")
    return rounded.astype(np.int64)


def aggregate_b_stave_edep(
    layer: Any,
    layer1: Any,
    pdg: Any,
    edep_mev: Any,
    *,
    n_b_layers: int = NB_LAYERS,
    b_arm: int = B_ARM,
) -> EventStaveEDep:
    """Aggregate all B-arm deposited energy for one generator event.

    Trigger classification may use charged particles, but deposited-energy
    conservation is defined here over *all* ``Sci_bar_EDep`` records in the B
    arm. A parallel charged-only diagnostic is retained to expose that
    distinction.
    """
    if not isinstance(n_b_layers, (int, np.integer)) or isinstance(n_b_layers, bool):
        raise DataContractError("n_b_layers must be a positive integer")
    n_layers = int(n_b_layers)
    if n_layers <= 0:
        raise DataContractError("n_b_layers must be a positive integer")

    layers = _integer_codes("Sci_bar_LayerID", layer)
    arms = _integer_codes("Sci_bar_LayerID1", layer1)
    pdgs = _integer_codes("Sci_bar_PDG", pdg)
    edep = _as_1d("Sci_bar_EDep", edep_mev, dtype=float)

    n = layers.size
    for name, arr in (
        ("Sci_bar_LayerID1", arms),
        ("Sci_bar_PDG", pdgs),
        ("Sci_bar_EDep", edep),
    ):
        if arr.size != n:
            raise DataContractError(
                f"jagged length mismatch: Sci_bar_LayerID has {n} entries "
                f"but {name} has {arr.size}"
            )
    if edep.size and not np.all(np.isfinite(edep)):
        raise DataContractError("Sci_bar_EDep contains non-finite values")
    if edep.size and np.any(edep < 0.0):
        raise DataContractError("Sci_bar_EDep contains negative deposited energy")

    in_b = arms == int(b_arm)
    invalid_b_layer = in_b & ((layers < 0) | (layers >= n_layers))
    if np.any(invalid_b_layer):
        bad = np.unique(layers[invalid_b_layer]).tolist()
        raise DataContractError(
            f"B-arm Sci_bar_LayerID outside [0,{n_layers - 1}]: {bad}"
        )

    total = np.zeros(n_layers, dtype=np.float64)
    charged_total = np.zeros(n_layers, dtype=np.float64)
    hit_count = np.zeros(n_layers, dtype=np.int64)
    charged_hit_count = np.zeros(n_layers, dtype=np.int64)

    if np.any(in_b):
        b_layers = layers[in_b]
        np.add.at(total, b_layers, edep[in_b])
        np.add.at(hit_count, b_layers, 1)

        charged = np.fromiter(
            (is_charged(int(code)) for code in pdgs),
            dtype=bool,
            count=pdgs.size,
        )
        charged_b = in_b & charged
        if np.any(charged_b):
            cb_layers = layers[charged_b]
            np.add.at(charged_total, cb_layers, edep[charged_b])
            np.add.at(charged_hit_count, cb_layers, 1)

    return EventStaveEDep(
        total_edep_mev=total,
        charged_edep_mev=charged_total,
        hit_count=hit_count,
        charged_hit_count=charged_hit_count,
    )




def validate_event_stave_product(
    *,
    event_id: Any,
    entry_index: Any,
    sample_i: Any,
    sample_ii: Any,
    event_weight: Any,
    total_edep_mev: Any,
    charged_edep_mev: Any,
    hit_count: Any,
    charged_hit_count: Any,
    n_b_layers: int = NB_LAYERS,
) -> None:
    """Fail closed on event-level identity, topology, weight, and matrix errors."""
    event_ids = _as_1d("event_id", event_id)
    entries = _as_1d("entry_index", entry_index)
    si = _as_1d("sample_I", sample_i)
    sii = _as_1d("sample_II", sample_ii)
    weights = _as_1d("event_weight", event_weight, dtype=float)
    n = event_ids.size
    for name, arr in (
        ("entry_index", entries),
        ("sample_I", si),
        ("sample_II", sii),
        ("event_weight", weights),
    ):
        if arr.size != n:
            raise DataContractError(f"{name} length {arr.size} != event_id length {n}")

    if len(set(map(str, event_ids.tolist()))) != n:
        raise DataContractError("event_id values must be unique")
    try:
        entry_float = entries.astype(float)
    except (TypeError, ValueError) as exc:
        raise DataContractError("entry_index must be finite integer-valued") from exc
    if entry_float.size and (
        not np.all(np.isfinite(entry_float))
        or not np.array_equal(entry_float, np.rint(entry_float))
        or np.any(entry_float < 0)
    ):
        raise DataContractError("entry_index must be finite non-negative integers")
    if len(set(np.rint(entry_float).astype(np.int64).tolist())) != n:
        raise DataContractError("entry_index values must be unique")

    si_bool = si.astype(bool)
    sii_bool = sii.astype(bool)
    if not np.array_equal(si, si_bool):
        raise DataContractError("sample_I must contain only boolean/0/1 values")
    if not np.array_equal(sii, sii_bool):
        raise DataContractError("sample_II must contain only boolean/0/1 values")
    if np.any(si_bool & ~sii_bool):
        raise DataContractError("Sample I must be a subset of Sample II")
    if np.any(~sii_bool):
        raise DataContractError("event/stave product contains a row outside Sample II")

    if weights.size and (not np.all(np.isfinite(weights)) or np.any(weights < 0.0)):
        raise DataContractError("event_weight must be finite and non-negative")

    expected = (n, int(n_b_layers))
    total = np.asarray(total_edep_mev, dtype=float)
    charged = np.asarray(charged_edep_mev, dtype=float)
    hits = np.asarray(hit_count)
    charged_hits = np.asarray(charged_hit_count)
    for name, arr in (
        ("total_edep_mev", total),
        ("charged_edep_mev", charged),
        ("hit_count", hits),
        ("charged_hit_count", charged_hits),
    ):
        if arr.shape != expected:
            raise DataContractError(f"{name} shape {arr.shape} != expected {expected}")
    if (
        not np.all(np.isfinite(total))
        or not np.all(np.isfinite(charged))
        or np.any(total < 0.0)
        or np.any(charged < 0.0)
    ):
        raise DataContractError("deposited-energy matrices must be finite and non-negative")
    tol = np.finfo(float).eps * np.maximum(1.0, np.abs(total)) * 16.0
    if np.any(charged > total + tol):
        raise DataContractError("charged deposited energy cannot exceed all-particle total")

    for name, arr in (("hit_count", hits), ("charged_hit_count", charged_hits)):
        try:
            as_float = arr.astype(float)
        except (TypeError, ValueError) as exc:
            raise DataContractError(f"{name} must contain non-negative integers") from exc
        if (
            not np.all(np.isfinite(as_float))
            or not np.array_equal(as_float, np.rint(as_float))
            or np.any(as_float < 0)
        ):
            raise DataContractError(f"{name} must contain non-negative integers")
    if np.any(charged_hits.astype(np.int64) > hits.astype(np.int64)):
        raise DataContractError("charged hit count cannot exceed total hit count")


def _stack_rows(rows: list[np.ndarray], *, n_b_layers: int, dtype: Any) -> np.ndarray:
    if not rows:
        return np.empty((0, n_b_layers), dtype=dtype)
    return np.stack(rows, axis=0).astype(dtype, copy=False)


def build_event_stave_product(
    path: str | Path,
    *,
    tree_name: str = "hibeam",
    coinc_ns: float = 15.0,
    apply_weight: bool = True,
    generator_measure_mode: str | None = None,
    weight_adapter_id: str | None = None,
    max_events: int = 0,
    step_size: str = "200 MB",
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Read one MC ROOT file and build the complete Sample-II event/stave product."""
    if isinstance(max_events, bool) or not isinstance(max_events, (int, np.integer)):
        raise DataContractError("max_events must be a non-negative integer")
    if int(max_events) < 0:
        raise DataContractError("max_events must be a non-negative integer")

    import uproot

    source_path = Path(path)
    branches = [
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "PrimaryWeight",
    ]
    event_ids: list[str] = []
    entries: list[int] = []
    sample_i_rows: list[bool] = []
    sample_ii_rows: list[bool] = []
    weights: list[float] = []
    totals: list[np.ndarray] = []
    charged_totals: list[np.ndarray] = []
    hit_counts: list[np.ndarray] = []
    charged_hit_counts: list[np.ndarray] = []
    n_entries_read = 0
    adapted_provenance: dict[str, str] = {}

    with fingerprinted_regular_file_stream(source_path) as (stream, source):
        with uproot.open(stream) as root_file:
            if tree_name not in root_file:
                raise DataContractError(f"ROOT tree {tree_name!r} is missing")
            tree = root_file[tree_name]
            stop = int(max_events) if int(max_events) > 0 else None
            entry_offset = 0
            for chunk in tree.iterate(
                branches,
                step_size=step_size,
                library="np",
                entry_stop=stop,
            ):
                rows = build_event_rows(
                    chunk,
                    content_fingerprint=source.sha256,
                    tree_name=tree_name,
                    coinc_ns=coinc_ns,
                    entry_offset=entry_offset,
                    source=str(source_path),
                )
                n_chunk = len(rows)
                for i, row in enumerate(rows):
                    if not row["sample_II"]:
                        continue
                    agg = aggregate_b_stave_edep(
                        chunk["Sci_bar_LayerID"][i],
                        chunk["Sci_bar_LayerID1"][i],
                        chunk["Sci_bar_PDG"][i],
                        chunk["Sci_bar_EDep"][i],
                    )
                    adapted = adapt_raw_primary_weight(
                        chunk["PrimaryWeight"][i],
                        generator_measure_mode=generator_measure_mode,
                        weight_adapter_id=weight_adapter_id,
                        apply_weight=apply_weight,
                    )
                    weight = adapted["event_weight"]
                    if not adapted_provenance:
                        adapted_provenance = {
                            "generator_measure_mode": adapted["generator_measure_mode"],
                            "weight_adapter_id": adapted["weight_adapter_id"],
                        }
                    event_ids.append(str(row["event_id"]))
                    entries.append(int(row["entry_index"]))
                    sample_i_rows.append(bool(row["sample_I"]))
                    sample_ii_rows.append(bool(row["sample_II"]))
                    weights.append(weight)
                    totals.append(agg.total_edep_mev)
                    charged_totals.append(agg.charged_edep_mev)
                    hit_counts.append(agg.hit_count)
                    charged_hit_counts.append(agg.charged_hit_count)
                entry_offset += n_chunk
                n_entries_read += n_chunk

    payload: dict[str, np.ndarray] = {
        "event_id": np.asarray(event_ids, dtype="U16"),
        "entry_index": np.asarray(entries, dtype=np.int64),
        "sample_I": np.asarray(sample_i_rows, dtype=bool),
        "sample_II": np.asarray(sample_ii_rows, dtype=bool),
        "event_weight": np.asarray(weights, dtype=np.float64),
        "b_stave_edep_mev": _stack_rows(
            totals, n_b_layers=NB_LAYERS, dtype=np.float64
        ),
        "b_stave_charged_edep_mev": _stack_rows(
            charged_totals, n_b_layers=NB_LAYERS, dtype=np.float64
        ),
        "b_stave_hit_count": _stack_rows(
            hit_counts, n_b_layers=NB_LAYERS, dtype=np.int64
        ),
        "b_stave_charged_hit_count": _stack_rows(
            charged_hit_counts, n_b_layers=NB_LAYERS, dtype=np.int64
        ),
    }
    validate_event_stave_product(
        event_id=payload["event_id"],
        entry_index=payload["entry_index"],
        sample_i=payload["sample_I"],
        sample_ii=payload["sample_II"],
        event_weight=payload["event_weight"],
        total_edep_mev=payload["b_stave_edep_mev"],
        charged_edep_mev=payload["b_stave_charged_edep_mev"],
        hit_count=payload["b_stave_hit_count"],
        charged_hit_count=payload["b_stave_charged_hit_count"],
    )

    w = payload["event_weight"]
    sum_w = float(math.fsum(w))
    sum_w2 = float(math.fsum(w * w))
    if sum_w == 0.0:
        raise DataContractError("total event weight is zero in weighted mode")
    if sum_w2 <= 0.0:
        raise DataContractError("sum of squared event weights is non-positive")
    ess = float(sum_w * sum_w / sum_w2)
    metadata: dict[str, Any] = {
        "schema_id": EVENT_STAVE_SCHEMA_ID,
        "statistical_unit": STATISTICAL_UNIT,
        "event_key_type": EVENT_KEY_TYPE,
        "aggregation_rule": AGGREGATION_RULE,
        "charged_diagnostic_rule": CHARGED_DIAGNOSTIC_RULE,
        "authorisation_state": AUTHORISATION_STATE,
        "source": str(source_path),
        "source_sha256": source.sha256,
        "source_bytes": source.bytes,
        "source_dev": source.source_dev,
        "source_ino": source.source_ino,
        "source_nlink": source.source_nlink,
        "source_mtime_ns": source.source_mtime_ns,
        "source_ctime_ns": source.source_ctime_ns,
        "tree_name": str(tree_name),
        "coinc_ns": float(coinc_ns),
        "n_entries_read": int(n_entries_read),
        "n_sample_II_events": int(payload["sample_II"].sum()),
        "n_sample_I_events": int(payload["sample_I"].sum()),
        "n_b_layers": NB_LAYERS,
        "weighting_enabled": bool(apply_weight),
        "generator_measure_mode": adapted_provenance.get(
            "generator_measure_mode", "unweighted_diagnostic"
        ),
        "weight_adapter_id": adapted_provenance.get(
            "weight_adapter_id", "unit_weight_diagnostic_v1"
        ),
        "weight_semantics": (
            PRIMARY_WEIGHT_SEMANTICS if apply_weight else UNIT_WEIGHT_DIAGNOSTIC_SEMANTICS
        ),
        "sum_event_weight": sum_w,
        "sum_event_weight_squared": sum_w2,
        "effective_sample_size": ess,
        "detector_closure": False,
        "missing_detector_stages": [
            "quenching",
            "optical_wls_transport",
            "sipm_response",
            "electronics",
            "digitizer_sampling",
            "data_like_reconstruction",
        ],
    }
    return payload, metadata


COMPARE_FIRST_B_PRODUCT = "first_B_layer_event_edep.npz"
COMPARE_CLUSTER_KEY = "generator_event_index"


def build_compare_first_b_event_edep(
    payload: dict[str, np.ndarray],
    *,
    weight_semantics: str = LEGACY_SEMANTICS_UNBOUND,
) -> dict[str, np.ndarray]:
    """Build compare_data_mc-compatible first-B export with cluster IDs (#1164).

    Uses ``entry_index`` as the immutable generator-event cluster key so
    cluster-bootstrap replicates preserve event identity.  Raises
    ``DataContractError`` when required arrays are missing or misaligned.
    """
    required = (
        "entry_index",
        "sample_I",
        "sample_II",
        "event_weight",
        "b_stave_edep_mev",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise DataContractError(
            f"compare first-B export incomplete: missing payload keys {missing}"
        )

    entry_index = np.asarray(payload["entry_index"], dtype=np.int64)
    sample_i = np.asarray(payload["sample_I"], dtype=bool)
    sample_ii = np.asarray(payload["sample_II"], dtype=bool)
    weights = np.asarray(payload["event_weight"], dtype=np.float64)
    edep = np.asarray(payload["b_stave_edep_mev"], dtype=np.float64)
    n = entry_index.size
    for name, arr in (
        ("sample_I", sample_i),
        ("sample_II", sample_ii),
        ("event_weight", weights),
    ):
        if arr.size != n:
            raise DataContractError(
                f"compare first-B export length mismatch: {name} has {arr.size}, "
                f"expected {n}"
            )
    if edep.ndim != 2 or edep.shape[0] != n or edep.shape[1] < 1:
        raise DataContractError(
            f"b_stave_edep_mev must be (n_events, n_layers) with n_events={n}"
        )

    cluster_ids = entry_index.copy()
    layer0 = edep[:, 0].astype(np.float32, copy=False)
    w = weights.astype(np.float32, copy=False)
    ii_mask = sample_ii
    i_mask = sample_i
    if not np.all(ii_mask):
        raise DataContractError("compare export requires every row in Sample II")
    if np.any(i_mask & ~ii_mask):
        raise DataContractError("Sample I must be a subset of Sample II for export")

    export = {
        "sampleI": layer0[i_mask],
        "sampleII": layer0[ii_mask],
        "sampleI_weights": w[i_mask],
        "sampleII_weights": w[ii_mask],
        "sampleI_cluster_id": cluster_ids[i_mask],
        "sampleII_cluster_id": cluster_ids[ii_mask],
        "sampleI_in_sample_i": np.ones(int(i_mask.sum()), dtype=bool),
        "sampleI_in_sample_ii": np.ones(int(i_mask.sum()), dtype=bool),
        "sampleII_in_sample_i": i_mask[ii_mask],
        "sampleII_in_sample_ii": np.ones(int(ii_mask.sum()), dtype=bool),
        "statistical_unit": np.asarray(["event_stave_edep"]),
        "cluster_key": np.asarray([COMPARE_CLUSTER_KEY]),
        "weight_semantics": np.asarray([weight_semantics]),
        "aggregation": np.asarray([AGGREGATION_RULE]),
        "authorising_measurand": np.asarray([False]),
        "issue_note": np.asarray(
            ["intermediate_H3_pending_digitizer_H5_issue_1164_cluster_export"]
        ),
    }
    _validate_compare_first_b_cluster_export(export)
    return export


def _validate_compare_first_b_cluster_export(export: dict[str, np.ndarray]) -> None:
    """Fail closed when compare export arrays are incomplete (#1164)."""
    required = (
        "sampleI",
        "sampleII",
        "sampleI_weights",
        "sampleII_weights",
        "sampleI_cluster_id",
        "sampleII_cluster_id",
    )
    missing = [key for key in required if key not in export]
    if missing:
        raise DataContractError(
            f"compare first-B cluster export incomplete: missing {missing}"
        )
    n_i = int(np.asarray(export["sampleI"]).size)
    n_ii = int(np.asarray(export["sampleII"]).size)
    for key in required:
        arr = np.asarray(export[key])
        if key.startswith("sampleII"):
            expected = n_ii
        else:
            expected = n_i
        if arr.size != expected:
            raise DataContractError(
                f"compare export {key} length {arr.size} != expected {expected}"
            )
    if n_ii < 1:
        raise DataContractError("compare export requires at least one Sample-II row")
    if not np.issubdtype(
        np.asarray(export["sampleII_cluster_id"]).dtype, np.integer
    ):
        raise DataContractError("sampleII_cluster_id must be integer-valued")
