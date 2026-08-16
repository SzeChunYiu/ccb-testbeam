#!/usr/bin/env python3
"""
plot_trigger_migration.py

Generate figures for trigger migration analysis:
- Efficiency vs threshold curves (per species)
- Efficiency vs coincidence window curves (per species)
- Migration matrix heatmap/table

Figure output follows repo plot conventions (matplotlib, deterministic).
No seaborn styling surprises.

Governance: HISTORICAL_DIAGNOSTIC input cannot authorise paper figures.
Figure-registry integration (figures.yaml) waits for authorising 1M data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.figure import Figure


# Use deterministic backend
matplotlib.use("Agg")


# Repo plot conventions
FIG_DPI = 150
FIG_WIDTH = 6.0
FIG_HEIGHT = 4.0
LABEL_FONT = 11
TITLE_FONT = 12
LEGEND_FONT = 10


def setup_figure() -> Figure:
    """Create a figure with repo-standard styling."""
    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.set_xlabel("Threshold (MeV)", fontsize=LABEL_FONT)
    ax.set_ylabel("Efficiency", fontsize=LABEL_FONT)
    ax.tick_params(labelsize=LABEL_FONT - 1)
    return fig


def plot_efficiency_vs_threshold(
    migration_data: dict,
    output_path: str,
) -> None:
    """Plot efficiency vs threshold curves for each species."""
    curve_data = migration_data["efficiency_vs_threshold"]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))

    # Sort thresholds for proper line plotting
    thresholds = sorted(curve_data.keys())

    # Get all species present in the data
    all_species = set()
    for thresh_data in curve_data.values():
        all_species.update(thresh_data.keys())

    # Plot each species
    for species in sorted(all_species):
        effs = []
        for thresh in thresholds:
            effs.append(curve_data.get(thresh, {}).get(species, np.nan))
        ax.plot(thresholds, effs, "o-", label=species, markersize=4)

    ax.set_xlabel("Threshold (MeV)", fontsize=LABEL_FONT)
    ax.set_ylabel("Efficiency", fontsize=LABEL_FONT)
    ax.set_title("Trigger Efficiency vs Threshold", fontsize=TITLE_FONT)
    ax.legend(fontsize=LEGEND_FONT)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, None)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_efficiency_vs_coincidence(
    migration_data: dict,
    output_path: str,
) -> None:
    """Plot efficiency vs coincidence window curves for each species."""
    curve_data = migration_data["efficiency_vs_coincidence"]

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))

    # Sort windows for proper line plotting
    windows = sorted(curve_data.keys())

    # Get all species present in the data
    all_species = set()
    for win_data in curve_data.values():
        all_species.update(win_data.keys())

    # Plot each species
    for species in sorted(all_species):
        effs = []
        for win in windows:
            effs.append(curve_data.get(win, {}).get(species, np.nan))
        ax.plot(windows, effs, "o-", label=species, markersize=4)

    ax.set_xlabel("Coincidence Window (ns)", fontsize=LABEL_FONT)
    ax.set_ylabel("Efficiency", fontsize=LABEL_FONT)
    ax.set_title("Trigger Efficiency vs Coincidence Window", fontsize=TITLE_FONT)
    ax.legend(fontsize=LEGEND_FONT)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, None)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def plot_migration_matrix_table(
    migration_data: dict,
    output_path: str,
) -> None:
    """Create a table visualization of the migration matrix."""
    species_data = migration_data["species_migration"]

    # Sort species by name for consistency
    species_names = sorted(species_data.keys())

    # Build table data
    table_data = []
    table_data.append(["Species", "Both", "Neither", "Proxy-Only", "Hardware-Only", "Loss%"])

    for species in species_names:
        s = species_data[species]
        q = s["quadrants"]
        loss_pct = s["migration_loss_fraction"] * 100
        table_data.append([
            species,
            str(q["both"]),
            str(q["neither"]),
            str(q["proxy_only"]),
            str(q["hardware_only"]),
            f"{loss_pct:.1f}",
        ])

    # Also add aggregate row
    agg = migration_data["aggregate_migration"]
    q_agg = agg["quadrants"]
    agg_loss = agg["migration_loss_fraction"] * 100
    table_data.append([
        "TOTAL",
        str(q_agg["both"]),
        str(q_agg["neither"]),
        str(q_agg["proxy_only"]),
        str(q_agg["hardware_only"]),
        f"{agg_loss:.1f}",
    ])

    fig, ax = plt.subplots(figsize=(8, 2 + len(species_names) * 0.4))
    ax.axis("tight")
    ax.axis("off")

    table = ax.table(
        cellText=table_data,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)

    # Highlight header row
    for i in range(len(table_data[0])):
        table[(0, i)].set_facecolor("#e0e0e0")
        table[(0, i)].set_text_props(weight="bold")

    # Highlight total row
    total_row_idx = len(species_names)
    for i in range(len(table_data[0])):
        table[(total_row_idx, i)].set_facecolor("#f0f0f0")
        table[(total_row_idx, i)].set_text_props(weight="bold")

    ax.set_title("Trigger Migration Matrix", fontsize=TITLE_FONT, pad=20)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate figures for trigger migration analysis"
    )
    parser.add_argument(
        "--migration-json",
        required=True,
        help="Path to migration_matrix.json output from trigger_migration_matrix.py",
    )
    parser.add_argument(
        "--output-dir",
        default="research/trigger_migration_study/phase4/figures",
        help="Output directory for figures",
    )
    args = parser.parse_args()

    # Load migration data
    with open(args.migration_json, "r", encoding="utf-8") as f:
        migration_data = json.load(f)

    # Generate figures
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("Generating trigger migration figures...")
    print("=" * 60)

    plot_efficiency_vs_threshold(
        migration_data,
        output_dir / "efficiency_vs_threshold.png",
    )

    plot_efficiency_vs_coincidence(
        migration_data,
        output_dir / "efficiency_vs_coincidence.png",
    )

    plot_migration_matrix_table(
        migration_data,
        output_dir / "migration_matrix_table.png",
    )

    print()
    print("Figure generation complete.")
    print(f"Output directory: {output_dir}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
