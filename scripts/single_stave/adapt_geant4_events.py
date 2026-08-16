#!/usr/bin/env python3
"""Convert current single-stave Geant4 event output to the analysis contract.

The converter is intentionally explicit. It maps the current ``events`` ntuple
branches written by ``geant4/single_stave/src/RunAction.cc`` to the normalized
columns consumed by ``analyze_single_stave.py``. It does not guess aliases or
silently drop conflicting columns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

VERSION = "1.1.0"
POLICY = "CURRENT_GEANT4_EVENT_TREE_MUST_MAP_EXPLICITLY_TO_ANALYSIS_CONTRACT"

CURRENT_TO_NORMALIZED = {
    "event": "event_id",
    "ke_MeV": "kinetic_energy_MeV",
    "arrival_readout": "n_end_selected",
    "detected_readout": "n_detected_pe",
}

REQUIRED_CURRENT = {
    "event",
    "particle",
    "ke_MeV",
    "edep_scint_MeV",
    "n_scint_generated",
    "n_wls_generated",
    "n_cerenkov_generated",
    "arrival_readout",
    "detected_readout",
}

COUNT_COLUMNS = [
    "n_scint_generated",
    "n_wls_generated",
    "n_cerenkov_generated",
    "n_end_selected",
    "n_detected_pe",
]


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(chunk_size):
            digest.update(block)
    return digest.hexdigest()


def read_table(path: Path, tree: str | None) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt", ".dat"}:
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix == ".root":
        try:
            import uproot
        except ImportError as exc:
            raise SystemExit("ROOT input requires uproot") from exc
        with uproot.open(path) as root_file:
            if tree is None:
                candidates = [
                    key.split(";")[0]
                    for key, obj in root_file.items()
                    if hasattr(obj, "arrays")
                ]
                if candidates == ["events"]:
                    tree = "events"
                elif len(candidates) == 1:
                    tree = candidates[0]
                else:
                    raise SystemExit(
                        f"Specify --tree. Candidate ROOT trees: {candidates}"
                    )
            return root_file[tree].arrays(library="pd")
    raise SystemExit(f"Unsupported input extension: {suffix}")


def _require_unambiguous_columns(df: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_CURRENT - set(df.columns))
    if missing:
        raise ValueError("missing current Geant4 columns: " + ", ".join(missing))
    conflicts = [
        f"{source}/{target}"
        for source, target in CURRENT_TO_NORMALIZED.items()
        if source in df.columns and target in df.columns
    ]
    if conflicts:
        raise ValueError(
            "ambiguous source and normalized columns coexist: " + ", ".join(conflicts)
        )
    if "track_len_scint_mm" in df.columns and "track_length_scint_cm" in df.columns:
        raise ValueError(
            "ambiguous source and normalized columns coexist: "
            "track_len_scint_mm/track_length_scint_cm"
        )


def _coerce_finite_numeric(df: pd.DataFrame, columns: list[str]) -> None:
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce")
        finite = np.isfinite(values.to_numpy(dtype=float))
        if not finite.all():
            bad_rows = np.flatnonzero(~finite)[:10].tolist()
            raise ValueError(f"{column} contains nonfinite or nonnumeric rows: {bad_rows}")
        df[column] = values


def _validate_counts(df: pd.DataFrame) -> None:
    for column in COUNT_COLUMNS:
        values = df[column].to_numpy(dtype=float)
        if (values < 0).any():
            raise ValueError(f"{column} contains negative values")
        if not np.equal(values, np.floor(values)).all():
            raise ValueError(f"{column} contains non-integer counts")
        df[column] = values.astype(np.int64)

    total = (
        df["n_scint_generated"]
        + df["n_wls_generated"]
        + df["n_cerenkov_generated"]
    )
    df["n_optical_generated_total"] = total.astype(np.int64)
    if (df["n_end_selected"] > total).any():
        raise ValueError(
            "n_end_selected exceeds total generated optical tracks "
            "(scintillation + WLS + Cerenkov)"
        )
    if (df["n_detected_pe"] > df["n_end_selected"]).any():
        raise ValueError("n_detected_pe exceeds n_end_selected")


def adapt_current_events(df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    """Return a normalized copy of a current Geant4 ``events`` table."""
    _require_unambiguous_columns(df)
    out = df.copy()
    out = out.rename(columns=CURRENT_TO_NORMALIZED)

    if "track_len_scint_mm" in out.columns:
        track_mm = pd.to_numeric(out.pop("track_len_scint_mm"), errors="coerce")
        if not np.isfinite(track_mm.to_numpy(dtype=float)).all():
            raise ValueError("track_len_scint_mm contains nonfinite or nonnumeric rows")
        out["track_length_scint_cm"] = track_mm / 10.0

    mapping = {"proton": 2212, "deuteron": 1000010020}
    particle = out["particle"].astype(str)
    pdg = particle.map(mapping)
    if pdg.isna().any():
        bad = sorted(particle[pdg.isna()].unique().tolist())
        raise ValueError(f"unknown particle labels: {bad}")
    out["particle_pdg"] = pdg.astype(np.int64)
    out["run_id"] = str(run_id)

    numeric = [
        "event_id",
        "kinetic_energy_MeV",
        "edep_scint_MeV",
        *COUNT_COLUMNS,
    ]
    _coerce_finite_numeric(out, numeric)
    event_values = out["event_id"].to_numpy(dtype=float)
    if (event_values < 0).any() or not np.equal(event_values, np.floor(event_values)).all():
        raise ValueError("event_id must contain nonnegative integer values")
    out["event_id"] = event_values.astype(np.int64)
    if (out["kinetic_energy_MeV"] <= 0).any():
        raise ValueError("kinetic_energy_MeV must be positive")
    if (out["edep_scint_MeV"] < 0).any():
        raise ValueError("edep_scint_MeV contains negative values")
    _validate_counts(out)

    duplicate_count = int(out.duplicated(["run_id", "event_id"]).sum())
    if duplicate_count:
        raise ValueError(f"{duplicate_count} duplicate (run_id,event_id) rows")
    return out


def _write_table_atomic(df: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.is_dir():
        raise ValueError(f"output is a directory: {output}")
    suffix = output.suffix.lower()
    if suffix not in {".csv", ".parquet", ".pq"}:
        raise ValueError("output extension must be .csv, .parquet, or .pq")

    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        if suffix == ".csv":
            df.to_csv(temp, index=False)
        else:
            df.to_parquet(temp, index=False)
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def _json_atomic(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, output)
    finally:
        temp.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map current Geant4 single-stave events to the analysis contract."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--tree", default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--metadata", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    metadata_path = (
        args.metadata.resolve()
        if args.metadata is not None
        else output_path.with_suffix(output_path.suffix + ".meta.json")
    )
    if output_path == input_path or metadata_path == input_path:
        raise SystemExit("output and metadata paths must not alias the input")
    if metadata_path == output_path:
        raise SystemExit("metadata path must differ from output path")
    existing = [path for path in (output_path, metadata_path) if path.exists()]
    if existing and not args.overwrite:
        joined = ", ".join(str(path) for path in existing)
        raise SystemExit(f"refusing to overwrite existing output(s): {joined}")

    run_id = args.run_id or input_path.stem
    input_sha_before = sha256(input_path)
    input_bytes_before = input_path.stat().st_size
    raw = read_table(input_path, args.tree)
    input_sha_after = sha256(input_path)
    input_bytes_after = input_path.stat().st_size
    if (input_sha_before, input_bytes_before) != (input_sha_after, input_bytes_after):
        raise SystemExit("input changed while it was being read")
    try:
        normalized = adapt_current_events(raw, run_id)
        _write_table_atomic(normalized, output_path)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"event-contract conversion failed: {exc}") from exc

    payload = {
        "schema": "ccb-single-stave-event-adapter/2",
        "version": VERSION,
        "policy": POLICY,
        "input": {
            "path": str(input_path),
            "bytes": input_bytes_before,
            "sha256": input_sha_before,
            "identity_check": "SHA256_AND_BYTE_SIZE_EQUAL_BEFORE_AFTER_READ",
            "tree": args.tree or "AUTO",
        },
        "output": {
            "path": str(output_path),
            "bytes": output_path.stat().st_size,
            "sha256": sha256(output_path),
            "rows": int(len(normalized)),
        },
        "run_id": run_id,
        "mapping": {
            **CURRENT_TO_NORMALIZED,
            "particle": "particle_pdg via explicit proton/deuteron map",
            "track_len_scint_mm": "track_length_scint_cm = mm / 10 when present",
        },
        "selected_sensor": "readout = fibre 1, +x physical readout",
        "generated_optical_bound": (
            "n_scint_generated + n_wls_generated + n_cerenkov_generated"
        ),
        "analysis_compatibility": "SCHEMA_AND_OPTICAL_BOOKKEEPING_COMPATIBLE",
        "downstream_analyzer_contract": {
            "version": "2.1.0",
            "policy": (
                "ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL_AND_DECLARE_EXPLICIT_ENERGY_TARGET"
            ),
            "optical_generation_contract": "CURRENT_COMPONENT_SUM",
            "collection_efficiency_denominator": "n_optical_generated_total",
            "acceptance": "SOFTWARE_CONTRACT_VALIDATED_REAL_ROOT_PENDING",
        },
        "scientific_boundary": (
            "Immutable real ROOT adapter-to-analyzer execution with producer sidecar, "
            "content hashes, row-count closure, result/manifest hashes, and reviewed "
            "diagnostics remains required before physics claims."
        ),
        "status": "VALIDATED",
    }
    _json_atomic(payload, metadata_path)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
