#!/usr/bin/env python3
"""Content-addressed fail-closed runner for the A-002 ΔE-E data bridge.

The underlying bridge owns the scientific transformation from pulse rows to one
row per ``(source_file_id, run, evt)``. This runner adds immutable input
identity, explicit amplitude semantics, clean-code provenance, output-table
validation, and protected transactional publication of the JSON/CSV/SVG bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT_PATH = Path(__file__).resolve()
BRIDGE_PATH = SCRIPT_PATH.with_name("deltaE_E_data_bridge.py")
REPOSITORY_ROOT = SCRIPT_PATH.parents[2]
POLICY = "DELTAE_BRIDGE_CONTENT_ADDRESSED_TRANSACTIONAL_RERUN"
VERSION = "1.0.0"
OUTPUT_JSON = "result.json"
OUTPUT_CSV = "deltaE_E_events_data.csv"
OUTPUT_SVG = "DE-01_deltaE_E_data.svg"


class StrictBridgeError(RuntimeError):
    """Raised when the strict rerun cannot preserve its evidence contract."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snapshot_file(path: Path | str) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve(strict=True)
    data = file_path.read_bytes()
    return {
        "path": str(file_path),
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
        "data": data,
    }


def _public_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != "data"}


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise StrictBridgeError(f"cannot import bridge module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_provenance(repository_root: Path) -> dict[str, Any]:
    root = repository_root.expanduser().resolve(strict=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    if status:
        raise StrictBridgeError(
            "tracked worktree is not clean; refusing a content-addressed scientific rerun"
        )
    return {
        "repository_root": str(root),
        "commit": commit,
        "tracked_worktree_clean": True,
        "status_policy": "GIT_STATUS_PORCELAIN_TRACKED_FILES_ONLY_MUST_BE_EMPTY",
    }


def runtime_provenance() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "matplotlib": matplotlib.__version__,
    }


def _path_within(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
    except ValueError:
        return False
    return True


def _assert_safe_bundle_dir(output_dir: Path, protected_paths: Sequence[Path]) -> Path:
    final_dir = output_dir.expanduser().resolve()
    for protected in protected_paths:
        protected_path = protected.expanduser().resolve()
        if final_dir == protected_path or _path_within(protected_path, final_dir):
            raise StrictBridgeError(
                "output bundle directory contains a protected input/code path: "
                f"{protected_path}"
            )
    return final_dir


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_staged_file(path: Path, data: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def publish_bundle_transactionally(
    output_dir: Path,
    files: Mapping[str, bytes],
    *,
    overwrite: bool,
    protected_paths: Sequence[Path],
) -> dict[str, dict[str, Any]]:
    final_dir = _assert_safe_bundle_dir(output_dir, protected_paths)
    parent = final_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists() and not final_dir.is_dir():
        raise StrictBridgeError(f"output bundle path exists and is not a directory: {final_dir}")
    if final_dir.exists() and not overwrite:
        raise StrictBridgeError(
            f"output bundle already exists; pass --overwrite for replacement: {final_dir}"
        )

    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{final_dir.name}.", suffix=".tmp", dir=parent)
    )
    backup_dir = parent / f".{final_dir.name}.backup.{uuid.uuid4().hex}"
    moved_existing = False
    published_new = False
    try:
        for name, data in files.items():
            if Path(name).name != name:
                raise StrictBridgeError(f"bundle file name must be a basename: {name}")
            _write_staged_file(staging_dir / name, data)
        _fsync_directory(staging_dir)

        if final_dir.exists():
            os.replace(final_dir, backup_dir)
            moved_existing = True
        os.replace(staging_dir, final_dir)
        published_new = True
        _fsync_directory(parent)
        if moved_existing:
            shutil.rmtree(backup_dir)
            moved_existing = False
    except Exception:
        if published_new and final_dir.exists():
            shutil.rmtree(final_dir)
        if moved_existing and backup_dir.exists():
            os.replace(backup_dir, final_dir)
            _fsync_directory(parent)
            moved_existing = False
        raise
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        if backup_dir.exists() and not moved_existing:
            shutil.rmtree(backup_dir)

    publications: dict[str, dict[str, Any]] = {}
    for name, expected_bytes in files.items():
        snapshot = snapshot_file(final_dir / name)
        if snapshot["bytes"] != len(expected_bytes):
            raise StrictBridgeError(f"published byte count mismatch for {name}")
        if snapshot["sha256"] != _sha256_bytes(expected_bytes):
            raise StrictBridgeError(f"published SHA-256 mismatch for {name}")
        publications[name] = _public_snapshot(snapshot)
    return publications


def _read_pulse_table(input_path: Path, exact_bytes: bytes) -> pd.DataFrame:
    compression = "gzip" if input_path.name.lower().endswith(".gz") else None
    try:
        return pd.read_csv(io.BytesIO(exact_bytes), compression=compression)
    except Exception as exc:  # pandas uses several parser/decompression exception types
        raise StrictBridgeError(f"cannot parse exact input bytes as CSV: {exc}") from exc


def _validate_wide_table(
    wide: pd.DataFrame,
    bridge_result: Mapping[str, Any],
    *,
    source_file_id: str,
) -> None:
    required = {
        "source_file_id",
        "run",
        "evt",
        "amp_B2",
        "amp_B4",
        "amp_B6",
        "amp_B8",
        "deltaE_data_adc",
        "E_data_adc",
        "stopping_layer",
        "category",
    }
    missing = sorted(required.difference(wide.columns))
    if missing:
        raise StrictBridgeError(f"bridge output is missing required columns: {missing}")
    if wide.empty:
        raise StrictBridgeError("bridge output must contain at least one physical event")
    if wide[["source_file_id", "run", "evt"]].isna().any().any():
        raise StrictBridgeError("bridge output contains missing composite-key values")
    if wide.duplicated(["source_file_id", "run", "evt"]).any():
        raise StrictBridgeError("bridge output contains duplicate physical composite keys")
    if set(wide["source_file_id"].astype(str)) != {source_file_id}:
        raise StrictBridgeError(
            "bridge output source_file_id does not match the requested identity"
        )
    numeric_columns = [
        "amp_B2",
        "amp_B4",
        "amp_B6",
        "amp_B8",
        "deltaE_data_adc",
        "E_data_adc",
    ]
    numeric = wide[numeric_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan)).all():
        raise StrictBridgeError("bridge output contains nonfinite or nonnumeric ADC values")
    expected_events = int(bridge_result.get("n_events_composite_key", -1))
    if len(wide) != expected_events:
        raise StrictBridgeError(
            f"bridge output has {len(wide)} rows but reports {expected_events} physical events"
        )
    stopping_total = int(bridge_result.get("stopping_distribution_total", -1))
    if stopping_total != expected_events:
        raise StrictBridgeError(
            "bridge stopping-distribution total does not match the physical-event count"
        )


def _metadata_columns(
    wide: pd.DataFrame,
    *,
    input_snapshot: Mapping[str, Any],
    git_info: Mapping[str, Any],
    bridge_snapshot: Mapping[str, Any],
    runner_snapshot: Mapping[str, Any],
    command: str,
) -> pd.DataFrame:
    enriched = wide.copy()
    metadata = {
        "provenance_policy": POLICY,
        "provenance_runner_version": VERSION,
        "provenance_input_sha256": input_snapshot["sha256"],
        "provenance_input_bytes": input_snapshot["bytes"],
        "provenance_repository_commit": git_info["commit"],
        "provenance_bridge_sha256": bridge_snapshot["sha256"],
        "provenance_runner_sha256": runner_snapshot["sha256"],
        "provenance_generation_command": command,
        "provenance_python": platform.python_version(),
        "provenance_pandas": pd.__version__,
    }
    for name, value in metadata.items():
        enriched[name] = value
    return enriched


def _render_svg(
    wide: pd.DataFrame,
    *,
    provenance: Mapping[str, Any],
) -> bytes:
    selected = wide[wide["category"] == "ok"]
    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    if selected.empty:
        ax.text(0.5, 0.5, "No category=ok events", ha="center", va="center")
    else:
        artist = ax.hexbin(
            selected["E_data_adc"],
            selected["deltaE_data_adc"],
            gridsize=40,
            mincnt=1,
            bins="log",
            cmap="viridis",
        )
        fig.colorbar(artist, ax=ax, label="log10 event count per hexagonal bin")
    ax.set_xlabel("E = amp(B4+B6+B8) [ADC]")
    ax.set_ylabel("ΔE = amp(B2) [ADC]")
    ax.set_title(f"ΔE-E composite-key rerun ({len(wide)} physical events)")
    input_hash = str(provenance["input"]["sha256"])
    commit = str(provenance["git"]["commit"])
    footer = (
        f"policy={POLICY}; input_sha256={input_hash}; commit={commit}; "
        f"python={provenance['runtime']['python']}; pandas={provenance['runtime']['pandas']}"
    )
    fig.text(0.01, 0.01, footer, fontsize=6, ha="left", va="bottom", wrap=True)
    fig.tight_layout(rect=(0.0, 0.06, 1.0, 1.0))
    stream = io.BytesIO()
    metadata = {
        "Title": "Strict content-addressed A-002 ΔE-E rerun",
        "Description": json.dumps(provenance, sort_keys=True, ensure_ascii=False),
    }
    fig.savefig(stream, format="svg", metadata=metadata)
    plt.close(fig)
    return stream.getvalue()


def _publication_entry(final_dir: Path, name: str, data: bytes) -> dict[str, Any]:
    return {
        "path": str((final_dir / name).resolve()),
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
    }


def run_strict_bridge(
    *,
    input_path: Path,
    output_dir: Path,
    expected_input_sha256: str,
    expected_repo_commit: str,
    amplitude_column: str,
    amplitude_convention: str,
    amplitude_polarity: str | None,
    threshold_adc: float,
    source_file_id: str,
    overwrite: bool,
    command: str,
    bridge_path: Path = BRIDGE_PATH,
    repository_root: Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    if not np.isfinite(threshold_adc) or threshold_adc < 0.0:
        raise StrictBridgeError("threshold_adc must be finite and nonnegative")
    if not source_file_id.strip():
        raise StrictBridgeError("source_file_id must not be empty")

    exact_input = snapshot_file(input_path)
    if exact_input["sha256"] != expected_input_sha256.lower():
        raise StrictBridgeError(
            "input SHA-256 mismatch: "
            f"expected {expected_input_sha256.lower()}, measured {exact_input['sha256']}"
        )

    bridge_file = bridge_path.expanduser().resolve(strict=True)
    runner_file = SCRIPT_PATH.resolve(strict=True)
    bridge_snapshot = snapshot_file(bridge_file)
    runner_snapshot = snapshot_file(runner_file)
    git_info = git_provenance(repository_root)
    if git_info["commit"] != expected_repo_commit:
        raise StrictBridgeError(
            "repository commit mismatch: "
            f"expected {expected_repo_commit}, measured {git_info['commit']}"
        )

    final_dir = _assert_safe_bundle_dir(
        output_dir,
        [Path(exact_input["path"]), bridge_file, runner_file],
    )
    pulses = _read_pulse_table(Path(exact_input["path"]), exact_input["data"])
    bridge = _load_module(bridge_file, "ccb_deltae_data_bridge_strict_target")
    wide, bridge_result = bridge.build_event_table(
        pulses,
        source_file_id=source_file_id,
        threshold_adc=float(threshold_adc),
        amplitude_column=amplitude_column,
        amplitude_convention=amplitude_convention,
        amplitude_polarity=amplitude_polarity,
    )
    _validate_wide_table(wide, bridge_result, source_file_id=source_file_id)

    after_input = snapshot_file(Path(exact_input["path"]))
    if (
        after_input["bytes"] != exact_input["bytes"]
        or after_input["sha256"] != exact_input["sha256"]
    ):
        raise StrictBridgeError("input path changed while the bridge was running")

    provenance = {
        "policy": POLICY,
        "runner_version": VERSION,
        "input": _public_snapshot(exact_input),
        "input_identity_policy": "SHA256_EXPECTED_AND_BEFORE_AFTER_READ_MUST_MATCH",
        "git": git_info,
        "bridge_script": _public_snapshot(bridge_snapshot),
        "runner_script": _public_snapshot(runner_snapshot),
        "runtime": runtime_provenance(),
        "generation_command": command,
        "amplitude_column": amplitude_column,
        "amplitude_convention": amplitude_convention,
        "amplitude_polarity": amplitude_polarity,
        "threshold_adc": float(threshold_adc),
        "source_file_id": source_file_id,
    }
    enriched = _metadata_columns(
        wide,
        input_snapshot=exact_input,
        git_info=git_info,
        bridge_snapshot=bridge_snapshot,
        runner_snapshot=runner_snapshot,
        command=command,
    )
    csv_bytes = enriched.to_csv(index=False, lineterminator="\n").encode("utf-8")
    svg_bytes = _render_svg(wide, provenance=provenance)
    output_validation = {
        "event_rows": len(wide),
        "unique_composite_keys": int(
            wide[["source_file_id", "run", "evt"]].drop_duplicates().shape[0]
        ),
        "stopping_distribution_total": int(bridge_result["stopping_distribution_total"]),
        "event_csv": _publication_entry(final_dir, OUTPUT_CSV, csv_bytes),
        "plot_svg": _publication_entry(final_dir, OUTPUT_SVG, svg_bytes),
        "bundle_publication_policy": (
            "COMPLETE_STAGED_DIRECTORY_RENAME_WITH_IN_PROCESS_ROLLBACK; "
            "RESULT_JSON_IS_THE_BUNDLE_COMMIT_MARKER"
        ),
    }
    result_payload = {
        "status": "VALIDATED_SOFTWARE_RERUN_OUTPUT",
        "scientific_acceptance": "BLOCKED_PENDING_A002_EVIDENCE_AND_CLOSURE",
        "provenance": provenance,
        "bridge_result": dict(bridge_result),
        "output_validation": output_validation,
    }
    result_bytes = json.dumps(
        result_payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    files = {
        OUTPUT_CSV: csv_bytes,
        OUTPUT_SVG: svg_bytes,
        OUTPUT_JSON: result_bytes,
    }
    publications = publish_bundle_transactionally(
        final_dir,
        files,
        overwrite=overwrite,
        protected_paths=[Path(exact_input["path"]), bridge_file, runner_file],
    )
    return {
        "result": result_payload,
        "published_bundle": publications,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-input-sha256", required=True)
    parser.add_argument("--expected-repo-commit", required=True)
    parser.add_argument("--source-file-id", required=True)
    parser.add_argument("--amplitude-column", required=True)
    parser.add_argument("--amplitude-convention", choices=("absolute", "net"), required=True)
    parser.add_argument("--amplitude-polarity", choices=("positive", "negative"))
    parser.add_argument("--threshold-adc", type=float, default=200.0)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    effective_argv = list(sys.argv if argv is None else [str(SCRIPT_PATH), *argv])
    command = shlex.join(effective_argv)
    try:
        payload = run_strict_bridge(
            input_path=args.input,
            output_dir=args.output_dir,
            expected_input_sha256=args.expected_input_sha256,
            expected_repo_commit=args.expected_repo_commit,
            amplitude_column=args.amplitude_column,
            amplitude_convention=args.amplitude_convention,
            amplitude_polarity=args.amplitude_polarity,
            threshold_adc=args.threshold_adc,
            source_file_id=args.source_file_id,
            overwrite=args.overwrite,
            command=command,
        )
    except Exception as exc:
        error_payload = {
            "status": "ERROR",
            "policy": POLICY,
            "runner_version": VERSION,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print(json.dumps(error_payload, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("DELTAE_STRICT_RERUN_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
