#!/usr/bin/env python3
"""Build the non-authorising MC event/stave deposited-energy product.

The output is the H3 truth intermediate required by issues #1052/#1164:
one row per Sample-II generator event with Sample-I membership retained as a
bit. It is not a DATA pulse analogue and must not be used to authorize detector
performance until the downstream response/digitization chain is complete.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np

from ccb_mc_validation.truth.event_stave import (
    AUTHORISATION_STATE,
    EVENT_STAVE_SCHEMA_ID,
    build_event_stave_product,
)


def _sha256(path: Path, block_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_npz_atomic(path: Path, payload: dict[str, np.ndarray]) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp.npz", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            np.savez_compressed(handle, **payload)
            handle.flush()
            os.fsync(handle.fileno())
        size = tmp.stat().st_size
        digest = _sha256(tmp)
        os.replace(tmp, path)
        return int(size), digest
    finally:
        tmp.unlink(missing_ok=True)


def _write_json_atomic(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mc", required=True, type=Path, help="MC ROOT file")
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    parser.add_argument("--tree", default="hibeam")
    parser.add_argument("--coinc-ns", type=float, default=15.0)
    parser.add_argument("--max-events", type=int, default=0, help="0 = complete tree")
    parser.add_argument(
        "--no-weight",
        action="store_true",
        help="Explicit diagnostic mode: replace PrimaryWeight with unit weights.",
    )
    args = parser.parse_args()

    payload, metadata = build_event_stave_product(
        args.mc,
        tree_name=args.tree,
        coinc_ns=args.coinc_ns,
        apply_weight=not args.no_weight,
        max_events=args.max_events,
    )
    archive_payload = {
        **payload,
        "__schema_id": np.asarray(EVENT_STAVE_SCHEMA_ID),
        "__authorisation_state": np.asarray(AUTHORISATION_STATE),
    }
    product_path = args.out / f"{EVENT_STAVE_SCHEMA_ID}.npz"
    manifest_path = args.out / f"{EVENT_STAVE_SCHEMA_ID}.manifest.json"
    product_bytes, product_sha256 = _write_npz_atomic(product_path, archive_payload)

    manifest = {
        **metadata,
        "product": str(product_path),
        "product_bytes": product_bytes,
        "product_sha256": product_sha256,
        "max_events": int(args.max_events),
        "population_scope": "FULL_TREE" if args.max_events == 0 else "PREFIX_DIAGNOSTIC",
        "claim_policy": (
            "Truth deposited-energy intermediate only. Do not compare as a detector-response "
            "closure or restore an authorising DATA/MC p-value."
        ),
    }
    _write_json_atomic(manifest_path, manifest)
    print(
        json.dumps(
            {
                "product": str(product_path),
                "manifest": str(manifest_path),
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
