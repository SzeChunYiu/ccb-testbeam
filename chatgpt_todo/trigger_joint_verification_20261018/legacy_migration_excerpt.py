"""Named-function excerpts from PR1544; not a complete module copy.
Source: scripts/trigger_migration_matrix.py, blob 04461b1326925efa5eaf231b36bb7029364b61da.
Only imports and module docstring below are harness scaffolding.
"""
from __future__ import annotations
from dataclasses import dataclass

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
