#!/usr/bin/env python3
"""
trigger_migration_matrix.py

Analyze trigger migration from proxy (historical) to hardware response.

Consumes one or more threshold-scan JSON outputs and computes:
- Per-species migration matrix (quadrants: both/neither/proxy-only/hardware-only)
- Efficiency vs threshold curves
- Efficiency vs coincidence window curves
- Headline migration metrics (fraction of proxy-selected events that FAIL hardware)

Output: migration_matrix_*.json + figures for paper-_candidate plots.

Governance: This script produces diagnostics only. Input data tagged
HISTORICAL_DIAGNOSTIC cannot authorise paper figures. Figure-registry
integration (figures.yaml) waits for authorising 1M data.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np


# Hardware constants (mirrored from trigger_baseline_characterization.py)
A_ARM = 2
B_ARM = 1
COINC_NS = 15.0


@dataclass
class MigrationQuadrant:
    """Quadrant counts for migration matrix."""
    both: int
    neither: int
    proxy_only: int
    hardware_only: int

    @property
    def total(self) -> int:
        return self.both + self.neither + self.proxy_only + self.hardware_only


@dataclass
class SpeciesMigration:
    """Migration statistics per species."""
    species: str
    quadrants: MigrationQuadrant
    proxy_efficiency: float
    hardware_efficiency: float
    migration_loss_fraction: float


@dataclass
class MigrationMatrixOutput:
    """Output structure for migration matrix analysis."""
    proxy_config: dict[str, Any]
    hardware_config: dict[str, Any]
    reference_threshold_mev: float
    reference_coinc_ns: float
    species_migration: dict[str, dict]
    aggregate_migration: dict
    efficiency_vs_threshold: dict
    efficiency_vs_coincidence: dict
    headline_metrics: dict


def load_scan_results(path: str) -> dict:
    """Load a threshold-scan JSON output."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_reference_config(
    results: list[dict],
    threshold_mev: float | None = None,
    coinc_ns: float | None = None,
) -> dict:
    """Find the reference configuration in scan results.

    If threshold_mev and coinc_ns are both None, use the baseline:
    threshold=1.0 MeV (proxy threshold-equivalent) and coinc=15 ns.
    """
    if threshold_mev is None:
        threshold_mev = 1.0
    if coinc_ns is None:
        coinc_ns = COINC_NS

    for r in results:
        if r["threshold_mev"] == threshold_mev and r["coinc_ns"] == coinc_ns:
            return r

    raise ValueError(
        f"Reference config not found: threshold={threshold_mev}, coinc={coinc_ns}"
    )


def compute_species_counts(scan_result: dict) -> dict[str, dict[str, int]]:
    """Extract per-species enter/pass counts from a scan result.

    Returns: {species: {"n_enter": int, "n_pass": int}}
    """
    return {
        species: {"n_enter": data["n_enter"], "n_pass": data["n_pass"]}
        for species, data in scan_result["species_breakdown"].items()
        if data["n_enter"] > 0  # Only include species with entries
    }


def compute_migration_quadrant(
    proxy_counts: dict[str, int],
    hardware_counts: dict[str, int],
) -> MigrationQuadrant:
    """Compute migration quadrant from proxy and hardware pass/enter counts.

    Assumes n_enter is the same for both proxy and hardware (same event sample).
    """
    n_enter = proxy_counts["n_enter"]
    proxy_pass = proxy_counts["n_pass"]
    hardware_pass = hardware_counts["n_pass"]

    both = min(proxy_pass, hardware_pass)
    neither = n_enter - max(proxy_pass, hardware_pass)
    proxy_only = proxy_pass - both
    hardware_only = hardware_pass - both

    return MigrationQuadrant(
        both=both,
        neither=neither,
        proxy_only=proxy_only,
        hardware_only=hardware_only,
    )


def compute_species_migration(
    species: str,
    proxy_counts: dict[str, int],
    hardware_counts: dict[str, int],
) -> SpeciesMigration:
    """Compute migration statistics for one species."""
    quadrants = compute_migration_quadrant(proxy_counts, hardware_counts)
    n_enter = proxy_counts["n_enter"]

    proxy_eff = proxy_counts["n_pass"] / n_enter if n_enter > 0 else 0.0
    hw_eff = hardware_counts["n_pass"] / n_enter if n_enter > 0 else 0.0

    migration_loss = (
        quadrants.proxy_only / (quadrants.proxy_only + quadrants.both)
        if (quadrants.proxy_only + quadrants.both) > 0
        else 0.0
    )

    return SpeciesMigration(
        species=species,
        quadrants=quadrants,
        proxy_efficiency=proxy_eff,
        hardware_efficiency=hw_eff,
        migration_loss_fraction=migration_loss,
    )


def extract_curve_data(
    results: list[dict],
    x_field: str,  # "threshold_mev" or "coinc_ns"
) -> dict[str, list]:
    """Extract curve data from scan results.

    Returns: {x_value: {species: efficiency}}
    """
    curve_data: dict[str, dict] = {}

    for r in results:
        x_val = r[x_field]
        if x_val not in curve_data:
            curve_data[x_val] = {}

        for species, data in r["species_breakdown"].items():
            if data["n_enter"] > 0:
                eff = data["n_pass"] / data["n_enter"]
                curve_data[x_val][species] = eff

    return curve_data


def run_migration_analysis(
    proxy_json: str,
    hardware_json: str,
    reference_threshold_mev: float | None = None,
    reference_coinc_ns: float | None = None,
) -> MigrationMatrixOutput:
    """Run migration matrix analysis on proxy and hardware scan results."""

    # Load scan results
    proxy_data = load_scan_results(proxy_json)
    hardware_data = load_scan_results(hardware_json)

    # Find reference configurations
    proxy_ref = find_reference_config(
        proxy_data["results"],
        reference_threshold_mev,
        reference_coinc_ns,
    )
    hardware_ref = find_reference_config(
        hardware_data["results"],
        reference_threshold_mev,
        reference_coinc_ns,
    )

    # Extract species counts
    proxy_species = compute_species_counts(proxy_ref)
    hardware_species = compute_species_counts(hardware_ref)

    # Compute per-species migration
    species_migration: dict[str, dict] = {}
    for species in proxy_species.keys():
        if species in hardware_species:
            migration = compute_species_migration(
                species,
                proxy_species[species],
                hardware_species[species],
            )
            species_migration[species] = asdict(migration)

    # Aggregate migration
    agg_proxy = compute_species_counts(proxy_ref)
    agg_hw = compute_species_counts(hardware_ref)
    total_proxy_pass = sum(s["n_pass"] for s in agg_proxy.values())
    total_hw_pass = sum(s["n_pass"] for s in agg_hw.values())
    total_enter = sum(s["n_enter"] for s in agg_proxy.values())

    agg_quadrant = compute_migration_quadrant(
        {"n_enter": total_enter, "n_pass": total_proxy_pass},
        {"n_enter": total_enter, "n_pass": total_hw_pass},
    )

    aggregate_migration = {
        "total_events": total_enter,
        "quadrants": asdict(agg_quadrant),
        "proxy_efficiency": total_proxy_pass / total_enter if total_enter > 0 else 0.0,
        "hardware_efficiency": total_hw_pass / total_enter if total_enter > 0 else 0.0,
        "migration_loss_fraction": (
            agg_quadrant.proxy_only / (agg_quadrant.proxy_only + agg_quadrant.both)
            if (agg_quadrant.proxy_only + agg_quadrant.both) > 0
            else 0.0
        ),
    }

    # Extract curve data
    eff_vs_threshold = extract_curve_data(
        hardware_data["results"], "threshold_mev"
    )
    eff_vs_coinc = extract_curve_data(
        hardware_data["results"], "coinc_ns"
    )

    # Headline metrics
    headline_metrics = {
        "migration_loss_percent": aggregate_migration["migration_loss_fraction"] * 100,
        "proxy_efficiency_percent": aggregate_migration["proxy_efficiency"] * 100,
        "hardware_efficiency_percent": aggregate_migration["hardware_efficiency"] * 100,
        "dominant_loss_species": max(
            [
                (s, m["migration_loss_fraction"])
                for s, m in species_migration.items()
            ],
            key=lambda x: x[1],
        )[0]
        if species_migration
        else None,
    }

    return MigrationMatrixOutput(
        proxy_config=proxy_data["scan_config"],
        hardware_config=hardware_data["scan_config"],
        reference_threshold_mev=reference_threshold_mev or 1.0,
        reference_coinc_ns=reference_coinc_ns or COINC_NS,
        species_migration=species_migration,
        aggregate_migration=aggregate_migration,
        efficiency_vs_threshold=eff_vs_threshold,
        efficiency_vs_coincidence=eff_vs_coinc,
        headline_metrics=headline_metrics,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze trigger migration from proxy to hardware response"
    )
    parser.add_argument(
        "--proxy-json",
        required=True,
        help="Path to proxy-mode scan results JSON",
    )
    parser.add_argument(
        "--hardware-json",
        required=True,
        help="Path to hardware-mode scan results JSON",
    )
    parser.add_argument(
        "--output",
        default="research/trigger_migration_study/phase4/migration_matrix.json",
        help="Output path for migration matrix results",
    )
    parser.add_argument(
        "--reference-threshold",
        type=float,
        default=None,
        help="Reference threshold (MeV) for quadrant analysis [default: 1.0]",
    )
    parser.add_argument(
        "--reference-coinc",
        type=float,
        default=None,
        help="Reference coincidence window (ns) [default: 15.0]",
    )
    args = parser.parse_args()

    # Run analysis
    result = run_migration_analysis(
        args.proxy_json,
        args.hardware_json,
        args.reference_threshold,
        args.reference_coinc,
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, indent=2)

    print()
    print("Migration Matrix Analysis Complete")
    print("=" * 60)
    n_events_str = str(output_path)
    print("Output: " + n_events_str)
    print()
    print("Headline Metrics:")
    proxy_eff = result.headline_metrics["proxy_efficiency_percent"]
    hw_eff = result.headline_metrics["hardware_efficiency_percent"]
    loss = result.headline_metrics["migration_loss_percent"]
    dom = result.headline_metrics["dominant_loss_species"]
    print("  Proxy efficiency: " + f"{proxy_eff:.2f}%")
    print("  Hardware efficiency: " + f"{hw_eff:.2f}%")
    print("  Migration loss: " + f"{loss:.2f}%")
    print("  Dominant loss species: " + str(dom))
    print()
    print("Aggregate Quadrants:")
    q = result.aggregate_migration["quadrants"]
    print("  Both: " + str(q["both"]))
    print("  Neither: " + str(q["neither"]))
    print("  Proxy-only (loss): " + str(q["proxy_only"]))
    print("  Hardware-only (gain): " + str(q["hardware_only"]))
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
