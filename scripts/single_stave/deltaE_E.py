#!/usr/bin/env python3
"""Canonical DeltaE-E front door with lossless table input handling.

The numerical and plotting implementation is retained in ``_deltaE_E_core``.
This front door owns the input boundary so CSV event identifiers, Parquet rows,
present detector-signal cells, and event-table outputs are validated before any
uniqueness check, sample selection, stopping statistic, data/MC join, or artifact
publication.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

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
# input/provenance, signal-value, and event-table-output boundaries.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

CSV_KEY_POLICY = "DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT"
CSV_SNAPSHOT_POLICY = "SINGLE_READ_STRICT_UTF8"
PARQUET_PROVENANCE_POLICY = (
    "DELTAE_PARQUET_ROWS_AND_PROVENANCE_MUST_SHARE_ONE_BYTE_SNAPSHOT"
)
PARQUET_SNAPSHOT_POLICY = "SINGLE_READ_EXACT_BYTES"
SIGNAL_VALUE_POLICY = "DELTAE_PRESENT_SIGNAL_CELLS_MUST_BE_FINITE_NUMERIC"
MISSING_LAYER_POLICY = "ZERO_ONLY_WHEN_SUPPORTED_COLUMN_IS_ABSENT"
EVENT_TABLE_OUTPUT_POLICY = (
    "DELTAE_EVENT_TABLE_OUTPUT_MUST_FAIL_CLOSED_AND_NOT_ALIAS_INPUT"
)
EVENT_TABLE_PUBLICATION_POLICY = "SAME_DIRECTORY_TEMP_FSYNC_OS_REPLACE"
PARQUET_FALLBACK_POLICY = "CSV_GZIP_ONLY_WHEN_PARQUET_ENGINE_UNAVAILABLE"
CSV_KEY_DTYPES: dict[str, str] = {key: "string" for key in KEY_COLS}
_INPUT_SNAPSHOTS: dict[Path, dict[str, Any]] = {}
_CORE_ANALYZE = _core.analyze
_CORE_SHA256 = _core.sha256


class SignalValueError(ValueError):
    """Raised when a present detector-signal cell is not finite numeric input."""


class EventTableOutputError(RuntimeError):
    """Raised when event-table publication cannot satisfy its integrity contract."""


def input_snapshot(path: Path) -> dict[str, Any] | None:
    """Return a copy of the retained same-snapshot provenance for ``path``."""
    record = _INPUT_SNAPSHOTS.get(Path(path).resolve())
    return dict(record) if record is not None else None


def _retain_snapshot(
    path: Path,
    raw: bytes,
    *,
    table_format: str,
    snapshot_policy: str,
    extra: dict[str, Any] | None = None,
) -> None:
    resolved = Path(path).resolve()
    record: dict[str, Any] = {
        "path": str(resolved),
        "format": table_format,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_policy": snapshot_policy,
    }
    if extra:
        record.update(extra)
    _INPUT_SNAPSHOTS[resolved] = record


def read_table(path: Path) -> pd.DataFrame:
    """Read supported tables from one exact byte snapshot."""
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"Input table not found: {path}")
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".pq"}:
        raw = path.read_bytes()
        table = pd.read_parquet(io.BytesIO(raw))
        _retain_snapshot(
            path,
            raw,
            table_format="parquet",
            snapshot_policy=PARQUET_SNAPSHOT_POLICY,
            extra={"reader": "pandas.read_parquet(io.BytesIO)"},
        )
        return table
    if suffix in {".csv", ".txt", ".dat"}:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SystemExit(f"CSV input is not valid UTF-8: {path}: {exc}") from exc
        table = pd.read_csv(io.StringIO(text), dtype=CSV_KEY_DTYPES)
        _retain_snapshot(
            path,
            raw,
            table_format="csv",
            snapshot_policy=CSV_SNAPSHOT_POLICY,
            extra={
                "encoding": "utf-8",
                "decode_errors": "strict",
                "key_policy": CSV_KEY_POLICY,
                "key_dtypes": dict(CSV_KEY_DTYPES),
            },
        )
        return table
    raise SystemExit(f"Unsupported input extension: {suffix} (use .parquet or .csv)")


def _coerce_present_finite_signals(
    df: pd.DataFrame,
    columns: Sequence[str],
    *,
    table_name: str,
) -> pd.DataFrame:
    """Coerce present signal columns and reject every nonfinite or malformed cell."""
    out = df.copy()
    for column in columns:
        if column not in out.columns:
            continue
        numeric = pd.to_numeric(out[column], errors="coerce")
        values = numeric.to_numpy(dtype=float, na_value=np.nan)
        invalid = ~np.isfinite(values)
        if invalid.any():
            positions = np.flatnonzero(invalid)
            row_labels = [str(out.index[int(pos)]) for pos in positions[:5]]
            raise SignalValueError(
                f"{table_name}: column {column!r} contains {len(positions)} "
                "nonnumeric or nonfinite value(s); first row indices "
                f"{row_labels}"
            )
        out[column] = values
    return out


def fill_missing_layers(df: pd.DataFrame, cols: Sequence[str]) -> pd.DataFrame:
    """Fill only wholly absent supported layers; present cells must be finite."""
    out = _coerce_present_finite_signals(
        df,
        cols,
        table_name="signal table",
    )
    for column in cols:
        if column not in out.columns:
            out[column] = 0.0
    return out


def prepare_data_side(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate data keys and present ADC cells before any absent-layer fill."""
    missing = [column for column in REQUIRED_DATA if column not in raw.columns]
    if missing:
        raise SystemExit(f"DATA table missing required columns: {missing}")
    validate_event_keys(raw, "DATA")
    signal_columns = ("amp_B2", *FILLABLE_DATA_LAYERS)
    validated = _coerce_present_finite_signals(
        raw,
        signal_columns,
        table_name="DATA",
    )
    data = fill_missing_layers(validated, FILLABLE_DATA_LAYERS)
    data = fill_missing_flags(data, DATA_SAT_COLS)
    data = fill_missing_flags(data, DATA_THRPASS_COLS)
    return derive_data_columns(data)


def prepare_mc_side(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate MC keys and every present ``edep_B*`` cell before layer fill."""
    missing = [column for column in REQUIRED_MC if column not in raw.columns]
    if missing:
        raise SystemExit(f"MC table missing required columns: {missing}")
    resolve_mc_weight_column(raw)
    validate_event_keys(raw, "MC")
    validated = _coerce_present_finite_signals(
        raw,
        mc_layer_columns(raw),
        table_name="MC",
    )
    mc = fill_missing_layers(validated, FILLABLE_MC_LAYERS)
    mc = derive_mc_columns(mc)
    return attach_mc_weights(mc)


def _event_table_output_contract() -> dict[str, str]:
    return {
        "policy": EVENT_TABLE_OUTPUT_POLICY,
        "publication": EVENT_TABLE_PUBLICATION_POLICY,
        "parquet_fallback": PARQUET_FALLBACK_POLICY,
        "stale_alternate_format": "REJECT",
    }


def analyze(
    data_raw: pd.DataFrame,
    mc_raw: pd.DataFrame,
    stop_thresholds: Sequence[float],
    data_thresholds: Sequence[float],
    sample: str,
    seed: int,
) -> dict:
    """Run the established analysis and publish strict boundary contracts."""
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
        "parquet_provenance_policy": PARQUET_PROVENANCE_POLICY,
        "parquet_snapshot_policy": PARQUET_SNAPSHOT_POLICY,
        "csv_key_dtypes": dict(CSV_KEY_DTYPES),
        "signal_value_policy": SIGNAL_VALUE_POLICY,
        "missing_layer_policy": MISSING_LAYER_POLICY,
    }
    bundle["result"]["event_table_output_contract"] = _event_table_output_contract()
    return bundle


def _paths_alias(left: Path, right: Path) -> bool:
    left_resolved = Path(left).resolve()
    right_resolved = Path(right).resolve()
    if left_resolved == right_resolved:
        return True
    try:
        return left_resolved.exists() and right_resolved.exists() and os.path.samefile(
            left_resolved,
            right_resolved,
        )
    except OSError:
        return False


def _reject_output_aliases(candidates: Sequence[Path]) -> None:
    for candidate in candidates:
        for input_path in _INPUT_SNAPSHOTS:
            if _paths_alias(candidate, input_path):
                raise EventTableOutputError(
                    f"event-table output {candidate} aliases validated input {input_path}"
                )


def _temporary_output_path(final_path: Path) -> Path:
    suffixes = "".join(final_path.suffixes)
    stem = final_path.name[: -len(suffixes)] if suffixes else final_path.name
    return final_path.with_name(f".{stem}.{uuid.uuid4().hex}.tmp{suffixes}")


def _fsync_file(path: Path) -> None:
    with Path(path).open("rb") as handle:
        os.fsync(handle.fileno())


def _atomic_table_write(final_path: Path, writer: Callable[[Path], None]) -> None:
    final_path = Path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_output_path(final_path)
    try:
        writer(temporary)
        if not temporary.is_file():
            raise EventTableOutputError(
                f"table writer returned without creating temporary artifact {temporary}"
            )
        _fsync_file(temporary)
        os.replace(temporary, final_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _parquet_engine_unavailable(exc: ImportError) -> bool:
    message = str(exc).lower()
    markers = (
        "unable to find a usable engine",
        "missing optional dependency",
        "pyarrow",
        "fastparquet",
    )
    return any(marker in message for marker in markers)


def _write_table(df: pd.DataFrame, base: Path) -> Path:
    """Publish one event table without broad fallback, aliasing, or stale ambiguity."""
    parquet_path = Path(base).with_suffix(".parquet")
    csv_path = Path(base).with_suffix(".csv.gz")
    _reject_output_aliases((parquet_path, csv_path))
    if csv_path.exists():
        raise EventTableOutputError(
            f"stale alternate-format event table exists: {csv_path}"
        )
    try:
        _atomic_table_write(
            parquet_path,
            lambda path: df.to_parquet(path, index=False),
        )
        return parquet_path
    except ImportError as exc:
        if not _parquet_engine_unavailable(exc):
            raise EventTableOutputError("unexpected Parquet import failure") from exc
    except Exception as exc:
        raise EventTableOutputError("Parquet event-table publication failed") from exc

    if parquet_path.exists():
        raise EventTableOutputError(
            f"stale alternate-format event table exists: {parquet_path}"
        )
    try:
        _atomic_table_write(
            csv_path,
            lambda path: df.to_csv(
                path,
                index=False,
                compression="gzip",
            ),
        )
    except Exception as exc:
        raise EventTableOutputError("CSV fallback publication failed") from exc
    return csv_path


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
    """Write the established manifest with strict input/output contracts."""
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
            "parquet_provenance_policy": PARQUET_PROVENANCE_POLICY,
            "parquet_snapshot_policy": PARQUET_SNAPSHOT_POLICY,
            "csv_key_dtypes": dict(CSV_KEY_DTYPES),
            "signal_value_policy": SIGNAL_VALUE_POLICY,
            "missing_layer_policy": MISSING_LAYER_POLICY,
        },
        "event_table_output_contract": _event_table_output_contract(),
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
    """Clear retained inputs, then run the established CLI with strict boundaries."""
    _INPUT_SNAPSHOTS.clear()
    try:
        return _core.main(argv)
    except SignalValueError as exc:
        raise SystemExit(f"Signal-value validation failed: {exc}") from exc
    except EventTableOutputError as exc:
        raise SystemExit(f"Event-table output validation failed: {exc}") from exc


_core.read_table = read_table
_core.fill_missing_layers = fill_missing_layers
_core.prepare_data_side = prepare_data_side
_core.prepare_mc_side = prepare_mc_side
_core.analyze = analyze
_core._write_table = _write_table
_core.write_manifest = write_manifest


if __name__ == "__main__":
    raise SystemExit(main())
