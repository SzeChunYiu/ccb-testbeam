#!/usr/bin/env python3
"""Install the reviewed ScatteringGenerator sources into an external hibeam_g4 tree.

The tracked ``ScatteringGenerator.cc/.hh`` files are the authoritative patch
payload. Installing those exact bytes avoids a split-brain state where an
external text-rewrite helper retains an older sampler/readiness mechanism than
the reviewed source. The destination root is mandatory so a run cannot silently
patch a historical checkout chosen by a hard-coded path.

A successful install is still only a source-deployment step: the external
Geant4 tree must be provenance-bound, compiled, and runtime-tested separately.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAYLOADS = {
    Path("include/ScatteringGenerator.hh"): HERE / "ScatteringGenerator.hh",
    Path("src/ScatteringGenerator.cc"): HERE / "ScatteringGenerator.cc",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_replace_bytes(destination: Path, data: bytes) -> None:
    if not destination.parent.is_dir():
        raise RuntimeError(f"target directory does not exist: {destination.parent}")

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, destination)
    finally:
        if tmp.exists():
            tmp.unlink()


def install_reviewed_sources(src_root: Path) -> list[dict[str, str | int]]:
    """Atomically install and verify the exact tracked source bytes."""

    records: list[dict[str, str | int]] = []
    for relative, source in PAYLOADS.items():
        payload = source.read_bytes()
        destination = src_root / relative
        _atomic_replace_bytes(destination, payload)
        installed = destination.read_bytes()
        if installed != payload:
            raise RuntimeError(f"post-install byte mismatch: {destination}")
        records.append(
            {
                "path": str(relative),
                "bytes": len(payload),
                "sha256": _sha256_bytes(payload),
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--src-root",
        type=Path,
        required=True,
        help="exact external hibeam_g4 source root containing include/ and src/",
    )
    args = parser.parse_args()

    records = install_reviewed_sources(args.src_root)
    for record in records:
        print("OK {path}: bytes={bytes} sha256={sha256}".format(**record))
    print(
        "DONE: exact tracked ScatteringGenerator source installed; "
        "compile/runtime validation still required"
    )


if __name__ == "__main__":
    main()
