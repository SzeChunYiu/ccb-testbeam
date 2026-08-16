#!/usr/bin/env python3
"""
Phase 1B Delta Table: Compute all counts/rates/ε_HRD/purity with binomial errors
from BOTH ROOT files (historical + authorising). Reproducible markdown output.

Input files:
  Historical: /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root
    sha256: 2b62403f0aa7ecc8c6fc8ffb5006b59d833ff1a31a95a8f389f88f45a18542cc
  Authorising: /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M_authorising.root
    sha256: 19cd97c1106632e9746dd76a683105186484aa34aa74be8617973072ebcf84ea
"""

import argparse
import sys
from typing import NamedTuple

try:
    import uproot
    import awkward as ak
except ImportError:
    print("ERROR: uproot and awkward required. On LUNARC, system python3 has uproot 5.6.4.")
    sys.exit(1)


# --- Helper functions -------------------------------------------------

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
    # Special case: for parts-per-thousand or parts-per-million
    if err_mag < 0.001:
        prec = max(prec, 4)
    return f"{value:.{prec}f} ±{error:.{prec}f}"


def propagate_error(err_a: float, err_b: float) -> float:
    """Propagation for independent errors: σ_diff = sqrt(σ_A² + σ_B²)."""
    return (err_a**2 + err_b**2) ** 0.5


def rate_with_error(count: int, total: int) -> tuple[float, float]:
    """Return (rate, error) where rate = count/total with binomial error."""
    if total == 0:
        return 0.0, 0.0
    p = count / total
    return p, binomial_error(p, total)


# --- Data structures -------------------------------------------------

class MCStats(NamedTuple):
    """Statistics for one ROOT file."""
    n_events: int
    n_deuterons: int
    n_protons: int
    n_enter_a: int  # Events with any hit in A-arm (LayerID 0-3)
    n_enter_b: int  # Events with any hit in B-arm (LayerID 4-7)
    n_coincidence: int  # Events with hits in BOTH arms
    n_b_only: int  # Events with B-arm hits but NO A-arm hits
    purity_n: int  # Denominator for purity calculation
    purity_signal: int  # Signal events for purity

    @property
    def deuteron_rate(self) -> tuple[float, float]:
        return rate_with_error(self.n_deuterons, self.n_events)

    @property
    def proton_rate(self) -> tuple[float, float]:
        return rate_with_error(self.n_protons, self.n_events)

    @property
    def enter_a_rate(self) -> tuple[float, float]:
        return rate_with_error(self.n_enter_a, self.n_events)

    @property
    def enter_b_rate(self) -> tuple[float, float]:
        return rate_with_error(self.n_enter_b, self.n_events)

    @property
    def coincidence_rate(self) -> tuple[float, float]:
        return rate_with_error(self.n_coincidence, self.n_events)

    @property
    def b_only_rate(self) -> tuple[float, float]:
        return rate_with_error(self.n_b_only, self.n_events)

    @property
    def purity(self) -> tuple[float, float]:
        """Purity = signal / purity_n."""
        return rate_with_error(self.purity_signal, self.purity_n)

    @property
    def efficiency_hrd(self) -> tuple[float, float]:
        """ε_HRD = coincidence / deuterons."""
        return rate_with_error(self.n_coincidence, self.n_deuterons)


# --- Analysis ---------------------------------------------------------

def analyze_root(path: str) -> MCStats:
    """Open ROOT file, extract hibeam TTree, compute all statistics."""
    print(f"Reading {path}...", flush=True)
    with uproot.open(path) as f:
        tree = f["hibeam"]
        n_events = int(tree.num_entries)

        # Primary PDG array: nested list per event, first element always 2212 (proton)
        primary_pdg = tree["PrimaryPDG"].array()

        # Sci_bar LayerID array: nested list per event
        layer_id = tree["Sci_bar_LayerID"].array()

        # Identify deuterons (PDG = 1000010020) as second element of PrimaryPDG
        # PrimaryPDG structure: [[2212, 1000010020], [2212, ...]] for deuterons
        # Create per-event boolean mask: True if event has deuteron primary
        event_has_deuteron = ak.num(primary_pdg[primary_pdg == 1000010020], axis=1) > 0
        n_deuterons = int(ak.sum(event_has_deuteron))

        # Count protons from first element of each event
        # First element is always 2212, so n_protons = n_events (one primary proton per event)
        n_protons = n_events

        # A-arm hits: LayerID 0-3
        has_a = ak.any((layer_id >= 0) & (layer_id <= 3), axis=1)
        n_enter_a = int(ak.sum(has_a))

        # B-arm hits: LayerID 4-7
        has_b = ak.any((layer_id >= 4) & (layer_id <= 7), axis=1)
        n_enter_b = int(ak.sum(has_b))

        # Coincidence: both arms
        has_coincidence = has_a & has_b
        n_coincidence = int(ak.sum(has_coincidence))

        # B-only: B without A
        has_b_only = has_b & ~has_a
        n_b_only = int(ak.sum(has_b_only))

        # Purity: denominator = all events with ANY B-arm hit
        # Signal = events with B-arm hit AND (not A-arm hit) = B-only
        # This matches "Sample II" definition from the findings
        purity_n = n_enter_b
        purity_signal = n_b_only

    print(f"  n_events={n_events}, n_deuterons={n_deuterons}, n_protons={n_protons}", flush=True)
    print(f"  Enter A={n_enter_a}, Enter B={n_enter_b}, Coincidence={n_coincidence}, B-only={n_b_only}", flush=True)
    print(f"  Purity: {purity_signal}/{purity_n}", flush=True)

    return MCStats(
        n_events=n_events,
        n_deuterons=n_deuterons,
        n_protons=n_protons,
        n_enter_a=n_enter_a,
        n_enter_b=n_enter_b,
        n_coincidence=n_coincidence,
        n_b_only=n_b_only,
        purity_n=purity_n,
        purity_signal=purity_signal,
    )


def analyze_species_breakdown(path: str) -> dict:
    """Compute species-specific Enter B, Sample I, ε_HRD."""
    print(f"Computing species breakdown for {path}...", flush=True)
    with uproot.open(path) as f:
        tree = f["hibeam"]
        n_events = int(tree.num_entries)

        primary_pdg = tree["PrimaryPDG"].array()
        layer_id = tree["Sci_bar_LayerID"].array()

        # A-arm hits: LayerID 0-3
        has_a = ak.any((layer_id >= 0) & (layer_id <= 3), axis=1)

        # B-arm hits: LayerID 4-7
        has_b = ak.any((layer_id >= 4) & (layer_id <= 7), axis=1)

        # Coincidence: both arms
        has_coincidence = has_a & has_b

        # Identify events with deuteron primary (second element of PrimaryPDG)
        event_has_deuteron = ak.num(primary_pdg[primary_pdg == 1000010020], axis=1) > 0

        # Deuteron-specific metrics
        deuteron_has_b = event_has_deuteron & has_b
        deuteron_coincidence = event_has_deuteron & has_coincidence
        n_deuteron_enter_b = int(ak.sum(deuteron_has_b))
        n_deuteron_sample_i = int(ak.sum(deuteron_coincidence))

        # Proton-specific metrics (all events have a proton primary)
        proton_has_b = has_b  # All events
        proton_coincidence = has_coincidence
        n_proton_enter_b = int(ak.sum(proton_has_b))
        n_proton_sample_i = int(ak.sum(proton_coincidence))

        # For completeness: other species (C12, alpha, etc.)
        # These are rare; we count them by PDG in PrimaryPDG excluding 2212 and 1000010020
        other_pdgs = ak.flatten(primary_pdg[(primary_pdg != 2212) & (primary_pdg != 1000010020)])
        other_counts = {}
        for pdg in [1000060120, 1000020040]:  # C12, alpha
            n = int(ak.sum(other_pdgs == pdg))
            if n > 0:
                other_counts[pdg] = n

    print(f"  Deuteron: Enter B={n_deuteron_enter_b}, Sample I={n_deuteron_sample_i}", flush=True)
    print(f"  Proton: Enter B={n_proton_enter_b}, Sample I={n_proton_sample_i}", flush=True)

    return {
        "deuteron": {"enter_b": n_deuteron_enter_b, "sample_i": n_deuteron_sample_i},
        "proton": {"enter_b": n_proton_enter_b, "sample_i": n_proton_sample_i},
        "other": other_counts,
    }


def compute_delta(auth: MCStats, hist: MCStats) -> dict:
    """Compute deltas (auth - hist) with propagated errors."""
    delta = {}

    # Helper for delta with error propagation
    def diff(a_val: float, a_err: float, b_val: float, b_err: float) -> tuple[float, float]:
        return (a_val - b_val), propagate_error(a_err, b_err)

    # Deuteron count
    delta["deuteron_n"] = (auth.n_deuterons - hist.n_deuterons, 0)

    # Deuteron rate
    d_rate, d_err = auth.deuteron_rate
    h_rate, h_err = hist.deuteron_rate
    delta["deuteron_rate"] = diff(d_rate, d_err, h_rate, h_err)

    # ε_HRD (coincidence/deuterons)
    d_eff, d_err = auth.efficiency_hrd
    h_eff, h_err = hist.efficiency_hrd
    delta["efficiency_hrd"] = diff(d_eff, d_err, h_eff, h_err)

    # Enter B count
    delta["enter_b_n"] = (auth.n_enter_b - hist.n_enter_b, 0)

    # Enter B rate
    d_rate, d_err = auth.enter_b_rate
    h_rate, h_err = hist.enter_b_rate
    delta["enter_b_rate"] = diff(d_rate, d_err, h_rate, h_err)

    # Coincidence count
    delta["coincidence_n"] = (auth.n_coincidence - hist.n_coincidence, 0)

    # Coincidence rate
    d_rate, d_err = auth.coincidence_rate
    h_rate, h_err = hist.coincidence_rate
    delta["coincidence_rate"] = diff(d_rate, d_err, h_rate, h_err)

    # Sample I (coincidence) purity
    d_pur, d_err = auth.purity
    h_pur, h_err = hist.purity
    delta["purity"] = diff(d_pur, d_err, h_pur, h_err)

    # Sample II (B-only) count
    delta["b_only_n"] = (auth.n_b_only - hist.n_b_only, 0)

    # Sample II (B-only) rate
    d_rate, d_err = auth.b_only_rate
    h_rate, h_err = hist.b_only_rate
    delta["b_only_rate"] = diff(d_rate, d_err, h_rate, h_err)

    return delta


def print_markdown_table(auth: MCStats, hist: MCStats, delta: dict):
    """Print the markdown delta table."""
    print("\n## Delta Table (Authorising - Historical)\n")
    print("| Quantity | Historical | Authorising | Delta |")
    print("|----------|-----------|-------------|-------|")

    # Total events
    print(f"| N_events | {hist.n_events:,} | {auth.n_events:,} | {auth.n_events - hist.n_events:+,} |")

    # Deuteron species
    d_rate, d_err = hist.deuteron_rate
    print(f"| Deuteron n | {hist.n_deuterons:,} | {auth.n_deuterons:,} | {delta['deuteron_n'][0]:+,} |")
    print(f"| Deuteron rate | {fmt_err(d_rate*100, d_err*100, 3)}% | "
          f"{fmt_err(*auth.deuteron_rate, 3)}% | "
          f"{fmt_err(delta['deuteron_rate'][0]*100, delta['deuteron_rate'][1]*100, 4)}% |")

    # Proton species
    p_rate, p_err = hist.proton_rate
    print(f"| Proton n | {hist.n_protons:,} | {auth.n_protons:,} | {auth.n_protons - hist.n_protons:+,} |")
    print(f"| Proton rate | {fmt_err(p_rate*100, p_err*100, 3)}% | "
          f"{fmt_err(*auth.proton_rate, 3)}% | "
          f"N/A (both 100%) |")

    # Enter B
    e_rate, e_err = hist.enter_b_rate
    print(f"| Enter B n | {hist.n_enter_b:,} | {auth.n_enter_b:,} | {delta['enter_b_n'][0]:+,} |")
    print(f"| Enter B rate | {fmt_err(e_rate*100, e_err*100, 4)}% | "
          f"{fmt_err(*auth.enter_b_rate, 4)}% | "
          f"{fmt_err(delta['enter_b_rate'][0]*100, delta['enter_b_rate'][1]*100, 5)}% |")

    # Coincidence
    c_rate, c_err = hist.coincidence_rate
    print(f"| Coincidence n | {hist.n_coincidence:,} | {auth.n_coincidence:,} | {delta['coincidence_n'][0]:+,} |")
    print(f"| Coincidence rate | {fmt_err(c_rate*100, c_err*100, 4)}% | "
          f"{fmt_err(*auth.coincidence_rate, 4)}% | "
          f"{fmt_err(delta['coincidence_rate'][0]*100, delta['coincidence_rate'][1]*100, 5)}% |")

    # ε_HRD (coincidence/deuterons)
    h_eff, h_err = hist.efficiency_hrd
    a_eff, a_err = auth.efficiency_hrd
    print(f"| ε_HRD (coincidence/deuterons) | {fmt_err(h_eff*100, h_err*100, 4)}% | "
          f"{fmt_err(a_eff*100, a_err*100, 4)}% | "
          f"{fmt_err(delta['efficiency_hrd'][0]*100, delta['efficiency_hrd'][1]*100, 5)}% |")

    # Sample I purity (coincidence/enter_b)
    h_pur, h_err = hist.purity
    a_pur, a_err = auth.purity
    print(f"| Sample I purity (coincidence/Enter B) | {fmt_err(h_pur*100, h_err*100, 4)}% | "
          f"{fmt_err(a_pur*100, a_err*100, 4)}% | "
          f"{fmt_err(delta['purity'][0]*100, delta['purity'][1]*100, 5)}% |")

    # Sample II (B-only)
    b_rate, b_err = hist.b_only_rate
    print(f"| Sample II n (B-only) | {hist.n_b_only:,} | {auth.n_b_only:,} | {delta['b_only_n'][0]:+,} |")
    print(f"| Sample II rate (B-only) | {fmt_err(b_rate*100, b_err*100, 4)}% | "
          f"{fmt_err(*auth.b_only_rate, 4)}% | "
          f"{fmt_err(delta['b_only_rate'][0]*100, delta['b_only_rate'][1]*100, 5)}% |")

    print()


# --- Main ------------------------------------------------------------

def print_species_table(hist_species: dict, auth_species: dict):
    """Print species-specific breakdown table."""
    print("\n## Species-Specific Breakdown (Authorising MC)\n")
    print("| Species | Enter B | Sample I (A+B) | ε_HRD (± binomial) |")
    print("|---------|---------|----------------|--------------------|")

    for species, label in [("deuteron", "Deuteron"), ("proton", "Proton")]:
        a_enter = auth_species[species]["enter_b"]
        a_sample = auth_species[species]["sample_i"]
        h_enter = hist_species[species]["enter_b"]
        h_sample = hist_species[species]["sample_i"]

        # ε_HRD = Sample I / Enter B
        if a_enter > 0:
            a_eff = a_sample / a_enter
            a_err = binomial_error(a_eff, a_enter)
        else:
            a_eff = 0.0
            a_err = 0.0

        print(f"| {label} | {a_enter:,} | {a_sample:,} | {fmt_err(a_eff*100, a_err*100, 3)}% |")

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

    hist_stats = analyze_root(args.historical)
    auth_stats = analyze_root(args.authorising)
    delta = compute_delta(auth_stats, hist_stats)

    print_markdown_table(auth_stats, hist_stats, delta)

    # Compute species-specific breakdown
    hist_species = analyze_species_breakdown(args.historical)
    auth_species = analyze_species_breakdown(args.authorising)
    print_species_table(hist_species, auth_species)

    # Flag any count changes (for explicit reporting)
    count_changes = []
    if auth_stats.n_deuterons != hist_stats.n_deuterons:
        count_changes.append(f"deuteron: {hist_stats.n_deuterons} -> {auth_stats.n_deuterons}")
    if auth_stats.n_enter_b != hist_stats.n_enter_b:
        count_changes.append(f"Enter B: {hist_stats.n_enter_b} -> {auth_stats.n_enter_b}")
    if auth_stats.n_coincidence != hist_stats.n_coincidence:
        count_changes.append(f"coincidence: {hist_stats.n_coincidence} -> {auth_stats.n_coincidence}")
    if auth_stats.n_b_only != hist_stats.n_b_only:
        count_changes.append(f"B-only: {hist_stats.n_b_only} -> {auth_stats.n_b_only}")

    if count_changes:
        print("\n## Count Changes Detected")
        for change in count_changes:
            print(f"  - {change}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
