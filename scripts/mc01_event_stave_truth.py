#!/usr/bin/env python3
"""Build the non-authorising MC event/stave deposited-energy product.

The output is the H3 truth intermediate required by issues #1052/#1164:
one row per Sample-II generator event with Sample-I membership retained as a
bit. It is not a DATA pulse analogue and must not be used to authorize detector
performance until the downstream response/digitization chain is complete.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Iterator

import numpy as np

import ccb_mc_validation.constants as constants_module
import ccb_mc_validation.truth.event_builder as event_builder_module
import ccb_mc_validation.truth.event_stave as event_stave_module
import ccb_mc_validation.truth.pdg as pdg_module
import ccb_mc_validation.truth.trigger as trigger_module
from ccb_mc_validation.exceptions import DataContractError
from ccb_mc_validation.truth.event_stave import (
    AUTHORISATION_STATE,
    COMPARE_FIRST_B_PRODUCT,
    EVENT_STAVE_SCHEMA_ID,
    build_compare_first_b_event_edep,
    build_event_stave_product,
)
from ccb_mc_validation.truth.weight_adapter import (
    MODE_COMMON_REPLICATED,
    MODE_DIRECT_UNIT,
    MODE_SCALAR,
)

try:
    import fcntl
except ImportError:  # pragma: no cover - CI/production are POSIX.
    fcntl = None  # type: ignore[assignment]


def _sha256(path: Path, block_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _producer_source_hashes() -> dict[str, str]:
    sources = {
        "script": Path(__file__).resolve(),
        "constants": Path(constants_module.__file__).resolve(),
        "event_builder": Path(event_builder_module.__file__).resolve(),
        "event_stave": Path(event_stave_module.__file__).resolve(),
        "pdg": Path(pdg_module.__file__).resolve(),
        "trigger": Path(trigger_module.__file__).resolve(),
    }
    return {name: _sha256(path) for name, path in sorted(sources.items())}


def _runtime_versions() -> dict[str, str]:
    try:
        uproot_version = importlib_metadata.version("uproot")
    except importlib_metadata.PackageNotFoundError:
        uproot_version = "NOT_INSTALLED"
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "uproot": uproot_version,
    }


def _generation_identity(
    metadata: dict[str, object],
    *,
    max_events: int,
    producer_source_sha256: dict[str, str],
    runtime_versions: dict[str, str],
) -> dict[str, object]:
    return {
        "schema_id": EVENT_STAVE_SCHEMA_ID,
        "source_sha256": metadata["source_sha256"],
        "tree_name": metadata["tree_name"],
        "coinc_ns": metadata["coinc_ns"],
        "weighting_enabled": metadata["weighting_enabled"],
        "max_events": int(max_events),
        "producer_source_sha256": producer_source_sha256,
        "runtime_versions": runtime_versions,
    }


def _generation_id(identity: dict[str, object]) -> str:
    canonical = json.dumps(
        identity,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@contextmanager
def _publication_lock(generations_root: Path) -> Iterator[None]:
    if fcntl is None:
        raise DataContractError("event/stave publication requires POSIX flock support")
    generations_root.mkdir(parents=True, exist_ok=True)
    lock_path = generations_root / ".publish.lock"
    with lock_path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_product(path: Path, payload: dict[str, np.ndarray]) -> tuple[int, str]:
    with path.open("wb") as handle:
        np.savez_compressed(handle, **payload)
        handle.flush()
        os.fsync(handle.fileno())
    return int(path.stat().st_size), _sha256(path)


def _write_manifest(path: Path, record: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _publish_generation(
    out_root: Path,
    payload: dict[str, np.ndarray],
    metadata: dict[str, object],
    *,
    max_events: int,
) -> tuple[Path, Path, dict[str, object]]:
    """Publish one complete immutable generation with no mutable latest alias."""
    producer_hashes = _producer_source_hashes()
    runtime_versions = _runtime_versions()
    identity = _generation_identity(
        metadata,
        max_events=max_events,
        producer_source_sha256=producer_hashes,
        runtime_versions=runtime_versions,
    )
    generation_id = _generation_id(identity)
    generations_root = out_root / "generations"
    final_dir = generations_root / generation_id

    with _publication_lock(generations_root):
        if final_dir.exists():
            raise DataContractError(
                f"immutable event/stave generation already exists: {final_dir}"
            )
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{generation_id}.staging-",
                dir=generations_root,
            )
        )
        try:
            product_name = f"{EVENT_STAVE_SCHEMA_ID}.npz"
            manifest_name = f"{EVENT_STAVE_SCHEMA_ID}.manifest.json"
            product_path = staging / product_name
            manifest_path = staging / manifest_name
            archive_payload = {
                **payload,
                "__schema_id": np.asarray(EVENT_STAVE_SCHEMA_ID),
                "__authorisation_state": np.asarray(AUTHORISATION_STATE),
            }
            product_bytes, product_sha256 = _write_product(product_path, archive_payload)
            manifest: dict[str, object] = {
                **metadata,
                "generation_id": generation_id,
                "generation_identity": identity,
                "product": product_name,
                "product_bytes": product_bytes,
                "product_sha256": product_sha256,
                "max_events": int(max_events),
                "population_scope": (
                    "FULL_TREE" if max_events == 0 else "PREFIX_DIAGNOSTIC"
                ),
                "producer_source_sha256": producer_hashes,
                "runtime_versions": runtime_versions,
                "claim_policy": (
                    "Truth deposited-energy intermediate only. Do not compare as a "
                    "detector-response closure or restore an authorising DATA/MC p-value."
                ),
            }
            _write_manifest(manifest_path, manifest)
            _fsync_directory(staging)
            os.rename(staging, final_dir)
            _fsync_directory(generations_root)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    return (
        final_dir / f"{EVENT_STAVE_SCHEMA_ID}.npz",
        final_dir / f"{EVENT_STAVE_SCHEMA_ID}.manifest.json",
        manifest,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mc", required=True, type=Path, help="MC ROOT file")
    parser.add_argument("--out", required=True, type=Path, help="output root")
    parser.add_argument("--tree", default="hibeam")
    parser.add_argument("--coinc-ns", type=float, default=15.0)
    parser.add_argument("--max-events", type=int, default=0, help="0 = complete tree")
    parser.add_argument(
        "--no-weight",
        action="store_true",
        help="Explicit diagnostic mode: replace PrimaryWeight with unit weights.",
    )
    parser.add_argument(
        "--generator-measure-mode",
        type=str,
        default=None,
        choices=[MODE_SCALAR, MODE_COMMON_REPLICATED, MODE_DIRECT_UNIT],
        help=(
            "Generator-event measure mode for PrimaryWeight adaptation. "
            "Required when --no-weight is not set. "
            f"Choices: {MODE_SCALAR}, {MODE_COMMON_REPLICATED}, {MODE_DIRECT_UNIT}."
        ),
    )
    args = parser.parse_args()

    payload, metadata = build_event_stave_product(
        args.mc,
        tree_name=args.tree,
        coinc_ns=args.coinc_ns,
        apply_weight=not args.no_weight,
        generator_measure_mode=args.generator_measure_mode,
        max_events=args.max_events,
    )
    product_path, manifest_path, manifest = _publish_generation(
        args.out,
        payload,
        metadata,
        max_events=args.max_events,
    )
    compare_export = build_compare_first_b_event_edep(payload)
    compare_product = product_path.parent / COMPARE_FIRST_B_PRODUCT
    _write_product(compare_product, compare_export)
    print(
        json.dumps(
            {
                "product": str(product_path),
                "manifest": str(manifest_path),
                "generation_id": manifest["generation_id"],
                "schema_id": EVENT_STAVE_SCHEMA_ID,
                "n_sample_II_events": metadata["n_sample_II_events"],
                "n_sample_I_events": metadata["n_sample_I_events"],
                "effective_sample_size": metadata["effective_sample_size"],
                "authorisation_state": AUTHORISATION_STATE,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
