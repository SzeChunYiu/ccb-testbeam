#!/usr/bin/env python3
"""Regenerate VIS-MC-002 with the canonical PSTAR reference contract.

This is a diagnostic comparison of local unquenched deposited energy per scored
track length with NIST PSTAR total stopping power. It is not an accepted
projectile stopping-power closure and does not evaluate a complete uncertainty
model.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from _common import (  # noqa: E402
    ccb_style,
    iter_i885,
    load_events,
    pstar_dEdx_MeV_per_mm,
    pstar_reference_provenance,
)

TOOL_VERSION = "1.0.0"
POLICY = "CLUSTERD_VIS_MC_002_MUST_USE_CANONICAL_VALIDATED_PSTAR_REFERENCE"
ESTIMAND = "RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED"
SUMMATION_METHOD = "MATH_FSUM_PER_EXACT_CONFIGURED_ENERGY"
UNCERTAINTY_METHOD = "NOT_EVALUATED"
SCIENTIFIC_STATUS = "DIAGNOSTIC_PROXY_NOT_ACCEPTED_STOPPING_POWER_CLOSURE"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomically(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def summarize_proxy(
    energies: np.ndarray,
    raw_deposit: np.ndarray,
    track_length: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return exact-energy ratio-of-sums proxy and sufficient statistics."""
    energies = np.asarray(energies, dtype=float)
    raw_deposit = np.asarray(raw_deposit, dtype=float)
    track_length = np.asarray(track_length, dtype=float)
    if any(array.ndim != 1 for array in (energies, raw_deposit, track_length)):
        raise ValueError("VIS-MC-002 inputs must be one-dimensional")
    if not (energies.size == raw_deposit.size == track_length.size):
        raise ValueError("VIS-MC-002 inputs must be row-aligned")
    if energies.size == 0:
        raise ValueError("VIS-MC-002 has no accepted proton events")
    if not all(np.isfinite(array).all() for array in (energies, raw_deposit, track_length)):
        raise ValueError("VIS-MC-002 inputs must be finite")
    if (energies <= 0).any() or (raw_deposit < 0).any() or (track_length <= 0).any():
        raise ValueError("VIS-MC-002 inputs violate physical-domain constraints")

    unique = np.unique(energies)
    proxy = []
    deposit_sums = []
    length_sums = []
    counts = []
    for energy in unique:
        selected = energies == energy
        deposit_sum = math.fsum(raw_deposit[selected].tolist())
        length_sum = math.fsum(track_length[selected].tolist())
        if length_sum <= 0:
            raise ValueError(f"nonpositive total track length at {energy} MeV")
        deposit_sums.append(deposit_sum)
        length_sums.append(length_sum)
        proxy.append(deposit_sum / length_sum)
        counts.append(int(selected.sum()))
    return (
        unique,
        np.asarray(proxy),
        np.asarray(deposit_sums),
        np.asarray(length_sums),
        np.asarray(counts, dtype=int),
    )


def collect_i885_proton_rows() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    energies: list[float] = []
    deposits: list[float] = []
    lengths: list[float] = []
    source_paths: list[str] = []
    for run in iter_i885():
        if run.particle != "proton":
            continue
        events = load_events(run.path)
        track_length = np.asarray(events["track_len_scint_mm"], dtype=float)
        raw_deposit = np.asarray(events["edep_scint_raw_MeV"], dtype=float)
        accepted = (
            np.isfinite(track_length)
            & np.isfinite(raw_deposit)
            & (track_length > 0.5)
            & (raw_deposit >= 0)
        )
        energies.extend([run.ke_MeV] * int(accepted.sum()))
        deposits.extend(raw_deposit[accepted].tolist())
        lengths.extend(track_length[accepted].tolist())
        source_paths.append(run.path)
    return np.asarray(energies), np.asarray(deposits), np.asarray(lengths), source_paths


def render(output_directory: Path) -> dict[str, object]:
    energies, deposits, lengths, source_paths = collect_i885_proton_rows()
    unique, local_proxy, deposit_sums, length_sums, counts = summarize_proxy(
        energies, deposits, lengths
    )
    reference = pstar_dEdx_MeV_per_mm(unique)
    ratio = local_proxy / reference

    plt = ccb_style()
    figure, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    axes[0].plot(
        unique,
        local_proxy,
        "o",
        label="Geant4 local raw EDep / scored track length",
    )
    grid = np.logspace(np.log10(unique.min()), np.log10(unique.max()), 100)
    axes[0].plot(grid, pstar_dEdx_MeV_per_mm(grid), "-", label="Canonical NIST PSTAR total")
    axes[0].set_xscale("log")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Configured proton kinetic energy (MeV)")
    axes[0].set_ylabel("Local-deposit proxy or PSTAR total (MeV/mm)")
    axes[0].set_title("(a) Diagnostic local-deposit proxy vs PSTAR")
    axes[0].legend(loc="best")

    axes[1].plot(unique, ratio, "o")
    axes[1].axhline(1.0, linewidth=0.8, linestyle="--")
    axes[1].set_xscale("log")
    axes[1].set_xlabel("Configured proton kinetic energy (MeV)")
    axes[1].set_ylabel("Local-deposit proxy / PSTAR total")
    axes[1].set_title("(b) Descriptive ratio; no acceptance statistic")
    axes[1].text(
        0.05,
        0.95,
        "median ratio = "
        f"{np.median(ratio):.3f}\nrange = [{ratio.min():.3f}, {ratio.max():.3f}]\n"
        "uncertainty model: NOT EVALUATED",
        transform=axes[1].transAxes,
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round", "fc": "white", "ec": "gray"},
    )
    figure.suptitle(
        "VIS-MC-002 — diagnostic local-deposit proxy vs canonical NIST PSTAR",
        fontsize=13,
    )
    provenance = pstar_reference_provenance()
    figure.text(
        0.5,
        -0.01,
        "Canonical reference: data/reference/stopping_power/pstar_polystyrene.csv; "
        f"SHA-256 {provenance['input_sha256'][:12]}…; "
        f"{provenance['rows_validated']} validated rows. Diagnostic only: local deposit is "
        "not projectile total energy loss; production ROOT paths are not content-addressed.",
        ha="center",
        va="top",
        fontsize=8.3,
        style="italic",
    )
    figure.tight_layout()
    output_directory.mkdir(parents=True, exist_ok=True)
    plot_path = output_directory / "VIS-MC-002_transport_vs_pstar_canonical.png"
    figure.savefig(plot_path)
    plt.close(figure)

    payload: dict[str, object] = {
        "schema_version": 1,
        "tool": "scripts/single_stave/campaign_plots/vis_mc_002_transport.py",
        "tool_version": TOOL_VERSION,
        "policy": POLICY,
        "status": SCIENTIFIC_STATUS,
        "estimand": ESTIMAND,
        "summation_method": SUMMATION_METHOD,
        "energy_grouping": "EXACT_CONFIGURED_ENERGY",
        "uncertainty_method": UNCERTAINTY_METHOD,
        "uncertainty_evaluated": False,
        "acceptance_statistic": "NONE",
        "reference": provenance,
        "external_input_provenance": {
            "status": "EXTERNAL_PATHS_NOT_CONTENT_ADDRESSED",
            "run_paths": source_paths,
        },
        "energy_MeV": unique.tolist(),
        "n_events": counts.tolist(),
        "raw_deposit_sum_MeV": deposit_sums.tolist(),
        "track_length_sum_mm": length_sums.tolist(),
        "local_proxy_MeV_per_mm": local_proxy.tolist(),
        "pstar_total_MeV_per_mm": reference.tolist(),
        "ratio": ratio.tolist(),
        "plot_path": str(plot_path),
        "plot_bytes": plot_path.stat().st_size,
        "plot_sha256": _sha256(plot_path),
        "generation_command": (
            "python scripts/single_stave/campaign_plots/vis_mc_002_transport.py "
            "reports/studies/clusterD/figures"
        ),
    }
    _write_json_atomically(
        output_directory / "VIS-MC-002_transport_vs_pstar_canonical.json", payload
    )
    return payload


def main() -> int:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "reports/studies/clusterD/figures")
    result = render(output)
    print(
        "[vis-mc-002] wrote canonical diagnostic: "
        f"energies={len(result['energy_MeV'])} status={result['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
