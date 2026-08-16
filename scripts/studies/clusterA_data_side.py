#!/usr/bin/env python3
"""Cluster A data-side ΔE-E diagnostics with explicit row-level semantics.

The derived pulse-feature table may contain multiple rows per composite event key.
This script therefore reports row-level distributions only. Event-level claims stay
blocked until the canonical composite merge is run on immutable source bytes.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_DATA = Path(
    "/projects/hep/fs10/shared/nnbar/billy/ccb_deltae_rerun/deltaE_E_events_data.csv"
)
DEFAULT_MC = Path(
    "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root"
)
REQUIRED_COLUMNS = {
    "run",
    "evt",
    "eventno",
    "source_file_id",
    "amp_B2",
    "amp_B4",
    "amp_B6",
    "amp_B8",
    "deltaE_data_adc",
    "E_data_adc",
    "stopping_layer",
    "category",
}
SCHEMA = "ccb-clusterA-data-side/2"
POLICY = "DATA_ROWS_MUST_BE_FINITE_AND_ROW_LEVEL_RESULTS_MUST_NOT_POSE_AS_EVENTS"


class InputError(RuntimeError):
    """Controlled invalid-input failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strict_int(value: str, field: str, line_no: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"line {line_no}: {field} is not an integer: {value!r}") from exc


def strict_float(value: str, field: str, line_no: int) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise InputError(f"line {line_no}: {field} is not numeric: {value!r}") from exc
    if not math.isfinite(result):
        raise InputError(f"line {line_no}: {field} is nonfinite: {value!r}")
    return result


def load_data_rows(path: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise InputError(f"invalid UTF-8 in {path}: {exc}") from exc

    rows: dict[str, list[Any]] = {
        "run": [],
        "evt": [],
        "eventno": [],
        "source_file_id": [],
        "amp_B2": [],
        "amp_B4": [],
        "amp_B6": [],
        "amp_B8": [],
        "deltaE_data_adc": [],
        "E_data_adc": [],
        "stopping_layer": [],
        "category": [],
    }
    reader = csv.DictReader(text.splitlines())
    missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
    if missing:
        raise InputError(f"missing required columns: {sorted(missing)}")

    for line_no, row in enumerate(reader, start=2):
        rows["run"].append(strict_int(row["run"], "run", line_no))
        rows["evt"].append(strict_int(row["evt"], "evt", line_no))
        rows["eventno"].append(strict_int(row["eventno"], "eventno", line_no))
        rows["source_file_id"].append(row["source_file_id"])
        for field in (
            "amp_B2",
            "amp_B4",
            "amp_B6",
            "amp_B8",
            "deltaE_data_adc",
            "E_data_adc",
        ):
            rows[field].append(strict_float(row[field], field, line_no))
        rows["stopping_layer"].append(row["stopping_layer"])
        rows["category"].append(row["category"])

    arrays = {
        name: np.asarray(values, dtype=float if name.startswith("amp_") else None)
        for name, values in rows.items()
    }
    arrays["deltaE_data_adc"] = np.asarray(rows["deltaE_data_adc"], dtype=float)
    arrays["E_data_adc"] = np.asarray(rows["E_data_adc"], dtype=float)
    arrays["run"] = np.asarray(rows["run"], dtype=np.int64)
    arrays["evt"] = np.asarray(rows["evt"], dtype=np.int64)
    arrays["eventno"] = np.asarray(rows["eventno"], dtype=np.int64)

    provenance = {
        "path": str(path),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "snapshot_policy": "SINGLE_READ_STRICT_UTF8",
        "rows": len(rows["run"]),
    }
    return arrays, provenance


def summarize_data(arrays: dict[str, np.ndarray], threshold_adc: float) -> dict[str, Any]:
    n_rows = len(arrays["run"])
    keys = list(
        zip(
            arrays["source_file_id"].tolist(),
            arrays["run"].tolist(),
            arrays["evt"].tolist(),
            strict=True,
        )
    )
    unique_keys = len(set(keys))
    eventno_unique = int(np.unique(arrays["eventno"]).size)
    de = arrays["deltaE_data_adc"]
    energy = arrays["E_data_adc"]
    selected = (de > 0.0) & (energy > 0.0)
    selected_de = de[selected]
    selected_energy = energy[selected]
    if selected_de.size == 0:
        raise InputError("no data rows have both positive deltaE and E")
    correlation = (
        float(np.corrcoef(selected_de, selected_energy)[0, 1])
        if selected_de.size > 1
        else None
    )

    stopping_values, stopping_counts = np.unique(
        arrays["stopping_layer"], return_counts=True
    )
    category_values, category_counts = np.unique(arrays["category"], return_counts=True)
    return {
        "schema": SCHEMA,
        "policy": POLICY,
        "units": "ADC (derived beam-data rows; never relabelled MeV)",
        "table_granularity": "MULTI_ROW_PER_COMPOSITE_EVENT_KEY",
        "event_level_claims_authorized": False,
        "event_level_blocker": (
            "Run the canonical composite merge on hash-bound inputs before quoting "
            "event-level correlations, efficiencies, or stopping fractions."
        ),
        "n_rows": n_rows,
        "composite_key_columns": ["source_file_id", "run", "evt"],
        "n_unique_composite_keys": unique_keys,
        "n_rows_beyond_first_per_composite_key": n_rows - unique_keys,
        "eventno_unique": eventno_unique,
        "n_rows_beyond_first_per_eventno": n_rows - eventno_unique,
        "selected_rows_dE_E": int(selected.sum()),
        "deltaE_adc_row_median": float(np.median(selected_de)),
        "E_adc_row_median": float(np.median(selected_energy)),
        "corr_dE_E_across_rows": correlation,
        "threshold_adc": threshold_adc,
        "rows_passing_either_threshold": int(
            ((de >= threshold_adc) | (energy >= threshold_adc)).sum()
        ),
        "stopping_layer_row_counts": {
            str(key): int(value)
            for key, value in zip(stopping_values, stopping_counts, strict=True)
        },
        "category_row_counts": {
            str(key): int(value)
            for key, value in zip(category_values, category_counts, strict=True)
        },
    }


def align_primary_weights(
    event_indices: np.ndarray,
    entry_offset: int,
    primary_weights: np.ndarray,
) -> np.ndarray:
    weights = np.asarray(primary_weights, dtype=float)
    if weights.ndim != 1:
        raise InputError(f"PrimaryWeight must be 1D, got shape {weights.shape}")
    if not np.all(np.isfinite(weights)) or np.any(weights < 0.0):
        raise InputError("PrimaryWeight must be finite and nonnegative")
    local = np.asarray(event_indices, dtype=np.int64) - int(entry_offset)
    if np.any(local < 0) or np.any(local >= len(weights)):
        raise InputError("track event_index falls outside the current PrimaryWeight chunk")
    return weights[local]


def weighted_hexbin(ax: Any, energy: np.ndarray, de: np.ndarray, weights: np.ndarray) -> Any:
    if not (len(energy) == len(de) == len(weights)):
        raise InputError("MC energy, deltaE, and PrimaryWeight lengths differ")
    return ax.hexbin(
        energy,
        de,
        C=weights,
        reduce_C_function=np.sum,
        gridsize=55,
        mincnt=1,
        bins="log",
        cmap="viridis",
    )


def load_mc_arrays(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    import uproot

    from ccb_mc_validation.constants import NB_LAYERS
    from ccb_mc_validation.truth.track_builder import build_track_records

    tree = uproot.open(path)["hibeam"]
    de_chunks: list[np.ndarray] = []
    e_chunks: list[np.ndarray] = []
    weight_chunks: list[np.ndarray] = []
    entry_offset = 0
    branches = [
        "Sci_bar_TrackID",
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_TrackLength",
        "Sci_bar_Momentum_X",
        "Sci_bar_Momentum_Y",
        "Sci_bar_Momentum_Z",
        "PrimaryWeight",
    ]
    for chunk in tree.iterate(branches, step_size="200 MB", library="np"):
        n_events = len(chunk["Sci_bar_LayerID"])
        records = build_track_records(chunk, source=str(path), entry_offset=entry_offset)
        if records:
            event_index = np.asarray([item["event_index"] for item in records], dtype=np.int64)
            layers = np.asarray([item["edep_per_layer"] for item in records], dtype=float)
            order = np.argsort(event_index)
            unique_events, inverse = np.unique(event_index[order], return_inverse=True)
            summed = np.zeros((len(unique_events), NB_LAYERS), dtype=float)
            np.add.at(summed, inverse, layers[order])
            de = summed[:, 0] + summed[:, 1]
            energy = summed[:, 2:].sum(axis=1)
            selected = (de > 0.0) & (energy > 0.0)
            event_weights = align_primary_weights(
                unique_events,
                entry_offset,
                np.asarray(chunk["PrimaryWeight"], dtype=float),
            )
            de_chunks.append(de[selected])
            e_chunks.append(energy[selected])
            weight_chunks.append(event_weights[selected])
        entry_offset += n_events

    if not de_chunks:
        raise InputError("no MC events with positive deltaE and E were found")
    de_all = np.concatenate(de_chunks)
    e_all = np.concatenate(e_chunks)
    w_all = np.concatenate(weight_chunks)
    if not np.any(w_all > 0.0):
        raise InputError("selected MC PrimaryWeight vector has no positive weight")
    return de_all, e_all, w_all, {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "tree": "hibeam",
        "selected_events": len(de_all),
        "weight_policy": "PrimaryWeight summed per plotted hexbin",
    }


def plot_data(arrays: dict[str, np.ndarray], summary: dict[str, Any], output: Path) -> None:
    de = arrays["deltaE_data_adc"]
    energy = arrays["E_data_adc"]
    selected = (de > 0.0) & (energy > 0.0)
    de = de[selected]
    energy = energy[selected]
    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    image = ax.hexbin(energy, de, gridsize=60, mincnt=1, bins="log", cmap="magma")
    ax.set_xlabel("E = amp_B4 + amp_B6 + amp_B8 [ADC]")
    ax.set_ylabel("ΔE = amp_B2 [ADC]")
    ax.set_title("VIS-DE-001-DATA derived beam-data rows (not unique events)")
    fig.colorbar(image, ax=ax, fraction=0.046).set_label("row count (log)")
    correlation = summary["corr_dE_E_across_rows"]
    corr_text = "undefined (one selected row)" if correlation is None else f"{correlation:+.3f}"
    text = (
        f"rows={summary['n_rows']:,}; unique composite keys="
        f"{summary['n_unique_composite_keys']:,}\n"
        f"selected rows={summary['selected_rows_dE_E']:,}; "
        f"corr across rows={corr_text}\n"
        "Event-level claims BLOCKED pending canonical composite merge."
    )
    ax.text(
        0.015,
        0.985,
        text,
        transform=ax.transAxes,
        va="top",
        fontsize=7.5,
        bbox={"boxstyle": "round", "fc": "white", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def plot_mc_vs_data(
    arrays: dict[str, np.ndarray],
    summary: dict[str, Any],
    mc_path: Path,
    output: Path,
) -> dict[str, Any]:
    de_mc, e_mc, weights, mc_provenance = load_mc_arrays(mc_path)
    de = arrays["deltaE_data_adc"]
    energy = arrays["E_data_adc"]
    selected = (de > 0.0) & (energy > 0.0)
    fig, (ax_mc, ax_data) = plt.subplots(1, 2, figsize=(12.2, 5.0))
    image_mc = weighted_hexbin(ax_mc, e_mc, de_mc, weights)
    fig.colorbar(image_mc, ax=ax_mc, fraction=0.046).set_label("sum PrimaryWeight (log)")
    ax_mc.set_xlabel("E = edep(B4+B6+B8) [MeV]")
    ax_mc.set_ylabel("ΔE = edep(B2) [MeV]")
    ax_mc.set_title(f"MC PrimaryWeight-weighted density; N={len(de_mc):,}")
    image_data = ax_data.hexbin(
        energy[selected], de[selected], gridsize=55, mincnt=1, bins="log", cmap="magma"
    )
    fig.colorbar(image_data, ax=ax_data, fraction=0.046).set_label("row count (log)")
    ax_data.set_xlabel("E = amp_B4+amp_B6+amp_B8 [ADC]")
    ax_data.set_ylabel("ΔE = amp_B2 [ADC]")
    ax_data.set_title(
        f"DATA derived rows; N={summary['selected_rows_dE_E']:,}; not event-level"
    )
    fig.suptitle("VIS-DE-003 topology comparison: MC events vs multi-row DATA table")
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return mc_provenance


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--mc", type=Path, default=DEFAULT_MC)
    parser.add_argument("--out", type=Path, default=Path("reports/studies/clusterA"))
    parser.add_argument("--threshold-adc", type=float, default=200.0)
    parser.add_argument("--skip-mc-plot", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        arrays, data_provenance = load_data_rows(args.data)
        summary = summarize_data(arrays, args.threshold_adc)
        args.out.mkdir(parents=True, exist_ok=True)
        plot_data(arrays, summary, args.out / "VIS-DE-001-DATA_deltaE_E_adc.png")
        mc_provenance = None
        if not args.skip_mc_plot:
            mc_provenance = plot_mc_vs_data(
                arrays,
                summary,
                args.mc,
                args.out / "VIS-DE-003_mc_vs_data.png",
            )
        payload = {
            "schema": SCHEMA,
            "policy": POLICY,
            "data_source": data_provenance,
            "mc_source": mc_provenance,
            "data_side": summary,
            "scientific_boundary": (
                "Row-level diagnostics are descriptive only. Event-level physics requires the "
                "canonical composite merge and independent data/MC closure."
            ),
        }
        atomic_json(args.out / "clusterA_data_side_validation.json", payload)
    except (OSError, InputError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
