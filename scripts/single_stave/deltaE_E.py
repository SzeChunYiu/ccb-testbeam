#!/usr/bin/env python3
"""Canonical DeltaE-E front door with lossless CSV composite-key handling.

The numerical and plotting implementation is retained in ``_deltaE_E_core``.
This front door owns the input boundary so CSV event identifiers are decoded
from one exact UTF-8 byte snapshot and parsed as text before any uniqueness
check, sample selection, or data/MC join.
"""
from __future__ import annotations

import hashlib
import io
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

if __package__:
    from . import _deltaE_E_core as _core
else:
    _ROOT = Path(__file__).resolve().parents[2]
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    from scripts.single_stave import _deltaE_E_core as _core

# Preserve the established public module surface while replacing only the
# input/provenance boundary. Single-underscore helpers remain import-compatible.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

CSV_KEY_POLICY = "DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT"
CSV_SNAPSHOT_POLICY = "SINGLE_READ_STRICT_UTF8"
CSV_KEY_DTYPES: dict[str, str] = {key: "string" for key in KEY_COLS}
_INPUT_SNAPSHOTS: dict[Path, dict[str, Any]] = {}
_CORE_ANALYZE = _core.analyze
_CORE_SHA256 = _core.sha256


def _snapshot_csv(path: Path) -> str:
    """Read one exact CSV byte snapshot, decode strict UTF-8, and retain provenance."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"CSV input is not valid UTF-8: {path}: {exc}") from exc
    resolved = path.resolve()
    _INPUT_SNAPSHOTS[resolved] = {
        "path": str(resolved),
        "format": "csv",
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_policy": CSV_SNAPSHOT_POLICY,
        "encoding": "utf-8",
        "decode_errors": "strict",
        "key_policy": CSV_KEY_POLICY,
        "key_dtypes": dict(CSV_KEY_DTYPES),
    }
    return text


def input_snapshot(path: Path) -> dict[str, Any] | None:
    """Return a copy of the retained same-snapshot provenance for ``path``."""
    record = _INPUT_SNAPSHOTS.get(Path(path).resolve())
    return dict(record) if record is not None else None


def read_table(path: Path) -> pd.DataFrame:
    """Read Parquet directly or CSV from one strict UTF-8, lossless-key snapshot."""
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"Input table not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".csv", ".txt", ".dat"}:
        text = _snapshot_csv(path)
        return pd.read_csv(io.StringIO(text), dtype=CSV_KEY_DTYPES)
    raise SystemExit(f"Unsupported input extension: {suffix} (use .parquet or .csv)")


def analyze(
    data_raw: pd.DataFrame,
    mc_raw: pd.DataFrame,
    stop_thresholds: Sequence[float],
    data_thresholds: Sequence[float],
    sample: str,
    seed: int,
) -> dict:
    """Run the established analysis and publish the reader contract in ``result``."""
    bundle = _CORE_ANALYZE(
        data_raw,
        mc_raw,
        stop_thresholds,
        data_thresholds,
        sample,
        seed,
    )
    bundle["result"]["input_reader_contract"] = {
        "csv_key_policy": CSV_KEY_POLICY,
        "csv_snapshot_policy": CSV_SNAPSHOT_POLICY,
        "csv_key_dtypes": dict(CSV_KEY_DTYPES),
    }
    return bundle


def _input_manifest_record(path: Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    snap = _INPUT_SNAPSHOTS.get(resolved)
    if snap is not None:
        return dict(snap)
    path = Path(path)
    return {
        "path": str(resolved),
        "format": path.suffix.lower().lstrip("."),
        "bytes": path.stat().st_size,
        "sha256": _CORE_SHA256(path),
        "snapshot_policy": "POST_READ_FILE_HASH",
    }


def write_manifest(out: Path, args, inputs: list[Path]) -> None:
    """Write the established manifest with same-snapshot CSV byte provenance."""
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _core.git_commit(),
        "command": sys.argv,
        "args": {
            "data_table": str(args.data_table),
            "mc_table": str(args.mc_table),
            "out": str(args.out),
            "stop_thresholds": args.stop_thresholds,
            "data_thresholds": args.data_thresholds,
            "sample": args.sample,
            "seed": args.seed,
            "bins": args.bins,
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "input_reader_contract": {
            "csv_key_policy": CSV_KEY_POLICY,
            "csv_snapshot_policy": CSV_SNAPSHOT_POLICY,
            "csv_key_dtypes": dict(CSV_KEY_DTYPES),
        },
        "inputs": [_input_manifest_record(path) for path in inputs],
        "outputs": [],
    }
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"].append(
                {"path": str(path.relative_to(out)), "sha256": _CORE_SHA256(path)}
            )
    (out / "manifest.json").write_text(
        json.dumps(_core._json_safe(manifest), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Clear stale snapshots, then run the established CLI with the strict boundary."""
    _INPUT_SNAPSHOTS.clear()
    return _core.main(argv)


_core.read_table = read_table
_core.analyze = analyze
_core.write_manifest = write_manifest


if __name__ == "__main__":
    raise SystemExit(main())
