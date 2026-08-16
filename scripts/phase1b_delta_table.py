#!/usr/bin/env python3
"""
Phase 1B Delta Table: Compute all counts/rates/ε_HRD/purity with binomial errors
from BOTH ROOT files (historical + authorising). Reproducible markdown output.

This script IMPORTS and CALLS process_mc_file() from scripts/trigger_baseline_characterization.py
to ensure same-origin methodology and reproduce manifest counts exactly.

Input files:
  Historical: /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root
    sha256: 2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc
  Authorising: /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M_authorising.root
    sha256: 19cd97c1106632e9746dd76a683105186484aa34aa74be8617973072ebcf84ea
"""

import argparse
import sys
from pathlib import Path

# Import the original processing function
sys.path.insert(0, str(Path(__file__).parent))
try:
    from trigger_baseline_characterization import process_mc_file, PDG_PROTON, PDG_DEUTERON
except ImportError as e:
    print(f"ERROR: Cannot import from trigger_baseline_characterization.py: {e}")
    sys.exit(1)


def binomial_error(p: float, n: int) -> float:
    """Binomial standard error σ = sqrt(p(1-p)/n)."""
    if n == 0:
        return 0.0
    return (p * (1.0 - p) / n) ** 0.5


def fmt_err(value: float, error: float, precision: int = 2) -> str:
    """Format value ± error with appropriate precision."""
    if error == 0:
        return f"{value:.{precision}f}"
    # Determine precision from error magnitude
    err_mag = abs(error)
    if err_mag >= 1:
        prec = 0
    elif err_mag >= 0.1:
        prec = 1
    elif err_mag >= 0.01:
        prec = 2
    elif err_mag >= 0.001:
        prec = 3
    elif err_mag >= 0.0001:
        prec = 4
    else:
        prec = 5
    return f"{value:.{prec}f} ±{error:.{prec}f}"


def rate_with_error(count: int, total: int) -> tuple[float, float]:
    """Return (rate, error) where rate = count/total with binomial error."""
    if total == 0:
        return 0.0, 0.0
    p = count / total
    return p, binomial_error(p, total)


def propagate_error(err_a: float, err_b: float) -> float:
    """Propagation for independent errors: σ_diff = sqrt(σ_A² + σ_B²)."""
    return (err_a**2 + err_b**2) ** 0.5


def print_markdown_table(hist_stats: dict, auth_stats: dict):
    """Print the markdown delta table with binomial errors."""
    print("\n## Delta Table (Authorising - Historical)\n")
    print("| Quantity | Historical | Authorising | Delta |")
    print("|----------|-----------|-------------|-------|")

    n_hist = hist_stats["n_events_processed"]
    n_auth = auth_stats["n_events_processed"]

    # Total events
    print(f"| N_events | {n_hist:,} | {n_auth:,} | {n_auth - n_hist:+,} |")

    # Enter B
    h_enter_b = hist_stats["n_enter_B"]
    a_enter_b = auth_stats["n_enter_B"]
    h_rate, h_err = rate_with_error(h_enter_b, n_hist)
    a_rate, a_err = rate_with_error(a_enter_b, n_auth)
    delta_rate = a_rate - h_rate
    delta_err = propagate_error(a_err, h_err)
    print(f"| Enter B n | {h_enter_b:,} | {a_enter_b:,} | {a_enter_b - h_enter_b:+,} |")
    print(f"| Enter B rate | {fmt_err(h_rate*100, h_err*100, 4)}% | "
          f"{fmt_err(a_rate*100, a_err*100, 4)}% | "
          f"{fmt_err(delta_rate*100, delta_err*100, 5)}% |")

    # Sample I (A+B coincidence)
    h_sample_i = hist_stats["n_sample_I"]
    a_sample_i = auth_stats["n_sample_I"]
    h_rate, h_err = rate_with_error(h_sample_i, n_hist)
    a_rate, a_err = rate_with_error(a_sample_i, n_auth)
    delta_rate = a_rate - h_rate
    delta_err = propagate_error(a_err, h_err)
    print(f"| Sample I n (A+B) | {h_sample_i:,} | {a_sample_i:,} | {a_sample_i - h_sample_i:+,} |")
    print(f"| Sample I rate | {fmt_err(h_rate*100, h_err*100, 4)}% | "
          f"{fmt_err(a_rate*100, a_err*100, 4)}% | "
          f"{fmt_err(delta_rate*100, delta_err*100, 5)}% |")

    # Sample II (B-only, same as Enter B by definition)
    h_sample_ii = hist_stats["n_sample_II"]
    a_sample_ii = auth_stats["n_sample_II"]
    h_rate, h_err = rate_with_error(h_sample_ii, n_hist)
    a_rate, a_err = rate_with_error(a_sample_ii, n_auth)
    delta_rate = a_rate - h_rate
    delta_err = propagate_error(a_err, h_err)
    print(f"| Sample II n (B-only) | {h_sample_ii:,} | {a_sample_ii:,} | {a_sample_ii - h_sample_ii:+,} |")
    print(f"| Sample II rate | {fmt_err(h_rate*100, h_err*100, 4)}% | "
          f"{fmt_err(a_rate*100, a_err*100, 4)}% | "
          f"{fmt_err(delta_rate*100, delta_err*100, 5)}% |")

    # Purity (Sample I / Enter B)
    h_pur = h_sample_i / h_enter_b if h_enter_b > 0 else 0.0
    a_pur = a_sample_i / a_enter_b if a_enter_b > 0 else 0.0
    h_pur_err = binomial_error(h_pur, h_enter_b)
    a_pur_err = binomial_error(a_pur, a_enter_b)
    delta_pur = a_pur - h_pur
    delta_pur_err = propagate_error(a_pur_err, h_pur_err)
    print(f"| Purity (Sample I / Enter B) | {fmt_err(h_pur*100, h_pur_err*100, 4)}% | "
          f"{fmt_err(a_pur*100, a_pur_err*100, 4)}% | "
          f"{fmt_err(delta_pur*100, delta_pur_err*100, 5)}% |")

    print()


def print_species_table(hist_stats: dict, auth_stats: dict):
    """Print species-specific breakdown table with binomial errors."""
    print("\n## Species-Specific Breakdown (Both MC)\n")
    print("| Species | Historical Enter B | Historical Sample I | Historical ε_HRD | Auth Enter B | Auth Sample I | Auth ε_HRD |")
    print("|---------|-------------------|--------------------|------------------|--------------|---------------|------------|")

    for species in ["proton", "deuteron", "alpha", "C12"]:
        h_enter = hist_stats["species_counts"][species]["enter_B"]
        h_sample = hist_stats["species_counts"][species]["sample_I"]
        a_enter = auth_stats["species_counts"][species]["enter_B"]
        a_sample = auth_stats["species_counts"][species]["sample_I"]

        # ε_HRD = Sample I / Enter B
        h_eff = h_sample / h_enter if h_enter > 0 else 0.0
        h_eff_err = binomial_error(h_eff, h_enter) if h_enter > 0 else 0.0
        a_eff = a_sample / a_enter if a_enter > 0 else 0.0
        a_eff_err = binomial_error(a_eff, a_enter) if a_enter > 0 else 0.0

        if h_enter > 0 or a_enter > 0:
            print(f"| {species.capitalize()} | {h_enter:,} | {h_sample:,} | "
                  f"{fmt_err(h_eff*100, h_eff_err*100, 3)}% | "
                  f"{a_enter:,} | {a_sample:,} | "
                  f"{fmt_err(a_eff*100, a_eff_err*100, 3)}% |")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Compute Phase 1B delta table with binomial errors from both ROOT files."
    )
    parser.add_argument(
        "--historical",
        default="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root",
        help="Path to historical ROOT file",
    )
    parser.add_argument(
        "--authorising",
        default="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M_authorising.root",
        help="Path to authorising ROOT file",
    )
    args = parser.parse_args()

    print("# Phase 1B Delta Table")
    print(f"# Historical: {args.historical}")
    print(f"#   sha256: 2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc")
    print(f"# Authorising: {args.authorising}")
    print(f"#   sha256: 19cd97c1106632e9746dd76a683105186484aa34aa74be8617973072ebcf84ea")
    print()

    # Process both files using the original function
    hist_stats = process_mc_file(args.historical)
    auth_stats = process_mc_file(args.authorising)

    # Sanity gate: verify manifest counts
    print("\n## Sanity Check (vs Manifest Counts)")
    manifest_h_enter_b = 237098
    manifest_h_sample_i = 64762
    manifest_a_enter_b = 7100
    manifest_a_sample_i = 554

    print(f"Historical Enter B: computed={hist_stats['n_enter_B']:,}, manifest={manifest_h_enter_b:,}, "
          f"match={hist_stats['n_enter_B'] == manifest_h_enter_b}")
    print(f"Historical Sample I: computed={hist_stats['n_sample_I']:,}, manifest={manifest_h_sample_i:,}, "
          f"match={hist_stats['n_sample_I'] == manifest_h_sample_i}")
    print(f"Authorising Enter B: computed={auth_stats['n_enter_B']:,}, manifest={manifest_a_enter_b:,}, "
          f"match={auth_stats['n_enter_B'] == manifest_a_enter_b}")
    print(f"Authorising Sample I: computed={auth_stats['n_sample_I']:,}, manifest={manifest_a_sample_i:,}, "
          f"match={auth_stats['n_sample_I'] == manifest_a_sample_i}")

    if (hist_stats['n_enter_B'] != manifest_h_enter_b or
        hist_stats['n_sample_I'] != manifest_h_sample_i or
        auth_stats['n_enter_B'] != manifest_a_enter_b or
        auth_stats['n_sample_I'] != manifest_a_sample_i):
        print("\n!!! SANITY CHECK FAILED - Computed counts do NOT match manifest values !!!")
        print("This is a finding to escalate, not to paper over.")
        return 1

    print("\n✓ Sanity check PASSED - counts match manifest")
    print()

    print_markdown_table(hist_stats, auth_stats)
    print_species_table(hist_stats, auth_stats)

    # Flag any count changes
    count_changes = []
    if auth_stats['n_enter_B'] != hist_stats['n_enter_B']:
        count_changes.append(f"Enter B: {hist_stats['n_enter_B']:,} -> {auth_stats['n_enter_B']:,}")
    if auth_stats['n_sample_I'] != hist_stats['n_sample_I']:
        count_changes.append(f"Sample I: {hist_stats['n_sample_I']:,} -> {auth_stats['n_sample_I']:,}")

    if count_changes:
        print("\n## Count Changes Detected")
        for change in count_changes:
            print(f"  - {change}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
