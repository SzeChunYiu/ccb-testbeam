#!/usr/bin/env python3
"""Baseline HRD Proxy Characterization for Issue #1045 Trigger Migration Study.

Provenance contract: efficiencies produced from a legacy MC (e.g. the June-era
output_krakow_1M.root, a superseded uniform-source product) are HISTORICAL
DIAGNOSTICS, not validated efficiencies — see geant4/REPRODUCTION_STATUS.md and
research/trigger_migration_study/PHASE1B_NONAUTHORISING_MC_NOTICE.md. An
authorising baseline requires the Phase-1B corrected-source MC.
"""

import json
import sys
from pathlib import Path

try:
    import uproot
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

# Constants
A_ARM = 2
B_ARM = 1
COINC_NS = 15.0

# Particle PDG codes
PDG_PROTON = 2212
PDG_DEUTERON = 1000010020
PDG_ALPHA = 1000020040
PDG_C12 = 1000060120

CHARGED_PDG = {
    2212, 1000010020, 1000010030, 1000020030, 1000020040,
    11, -11, 13, -13, 211, -211, 321, -321,
    1000060120, 1000060130, 1000060140,
}

def is_charged(pdg: int) -> bool:
    return pdg in CHARGED_PDG

def classify_event_hrd_proxy(layer, layer1, pdg, time, coinc_ns=COINC_NS):
    if len(layer) == 0:
        return {"enter_B": False, "enter_A": False, "sample_I": False, "sample_II": False}
    
    charged = np.array([is_charged(int(p)) for p in pdg])
    is_b = np.array(layer1) == B_ARM
    is_a = np.array(layer1) == A_ARM
    first_b = is_b & (np.array(layer) == 0) & charged
    first_a = is_a & (np.array(layer) == 0) & charged
    
    enter_b = bool(first_b.any())
    enter_a = bool(first_a.any())
    
    if enter_b and enter_a:
        t_b = float(np.array(time)[first_b].min())
        t_a = float(np.array(time)[first_a].min())
        if np.isfinite(t_a) and np.isfinite(t_b):
            coinc = abs(t_a - t_b) < coinc_ns
        else:
            coinc = False
    else:
        coinc = False
    
    return {"enter_B": enter_b, "enter_A": enter_a, "sample_I": coinc, "sample_II": enter_b}

def get_primary_species(pdg_array):
    if len(pdg_array) == 0:
        return None
    for p in pdg_array:
        if is_charged(int(p)):
            return int(p)
    return None

def process_mc_file(file_path, max_events=None):
    print(f"Processing {file_path}...")
    
    with uproot.open(file_path) as f:
        tree = f["hibeam"]
        n_entries = int(tree.num_entries)
        print(f"Total entries: {n_entries:,}")
        
        if max_events:
            n_entries = min(n_entries, max_events)
            print(f"Processing {n_entries:,} events (max_events={max_events})")
        
        stats = {
            "n_events_processed": 0,
            "n_enter_B": 0,
            "n_enter_A": 0,
            "n_sample_I": 0,
            "n_sample_II": 0,
            "species_counts": {
                "proton": {"enter_B": 0, "sample_I": 0, "sample_II": 0},
                "deuteron": {"enter_B": 0, "sample_I": 0, "sample_II": 0},
                "alpha": {"enter_B": 0, "sample_I": 0, "sample_II": 0},
                "C12": {"enter_B": 0, "sample_I": 0, "sample_II": 0},
            },
            "coinc_ns_used": COINC_NS,
        }
        
        chunk_size = 10000
        for start in range(0, n_entries, chunk_size):
            end = min(start + chunk_size, n_entries)
            
            chunk = tree.arrays(
                ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_Time"],
                entry_start=start, entry_stop=end, library="np"
            )
            
            for i in range(len(chunk["Sci_bar_LayerID"])):
                layer = chunk["Sci_bar_LayerID"][i]
                layer1 = chunk["Sci_bar_LayerID1"][i]
                pdg = chunk["Sci_bar_PDG"][i]
                time = chunk["Sci_bar_Time"][i]
                
                flags = classify_event_hrd_proxy(layer, layer1, pdg, time)
                stats["n_events_processed"] += 1
                
                if flags["enter_B"]:
                    stats["n_enter_B"] += 1
                if flags["enter_A"]:
                    stats["n_enter_A"] += 1
                if flags["sample_I"]:
                    stats["n_sample_I"] += 1
                if flags["sample_II"]:
                    stats["n_sample_II"] += 1
                
                primary_pdg = get_primary_species(pdg)
                if primary_pdg == PDG_PROTON:
                    species_key = "proton"
                elif primary_pdg == PDG_DEUTERON:
                    species_key = "deuteron"
                elif primary_pdg == PDG_ALPHA:
                    species_key = "alpha"
                elif primary_pdg == PDG_C12:
                    species_key = "C12"
                else:
                    species_key = None
                
                if species_key and flags["enter_B"]:
                    stats["species_counts"][species_key]["enter_B"] += 1
                    if flags["sample_I"]:
                        stats["species_counts"][species_key]["sample_I"] += 1
                    if flags["sample_II"]:
                        stats["species_counts"][species_key]["sample_II"] += 1
            
            if start > 0 and start % 100000 == 0:
                pct = 100 * end / n_entries
                print(f"Processed {end:,}/{n_entries:,} events ({pct:.1f}%)")
    
    return stats

# Defaults are the historical Phase-1 inputs (a NONAUTHORISING MC -- pass the
# Phase-1B corrected-source file explicitly once it exists).
DEFAULT_MC = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root"
DEFAULT_OUTPUT = "research/trigger_migration_study/baseline_hrd_proxy.json"


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=DEFAULT_MC, help="truth-level MC ROOT file")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="output JSON path (repo-relative)")
    parser.add_argument("--repo-root", default="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam",
                        help="repository root the output path is resolved against")
    args = parser.parse_args()

    mc_file = args.input
    output_file = args.output
    
    stats = process_mc_file(mc_file)
    
    output_path = Path(args.repo_root) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(stats, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Baseline characterization complete!")
    print(f"Results saved to: {output_file}")
    print(f"\nSummary:")
    print(f"  Events processed: {stats['n_events_processed']:,}")
    print(f"  Enter B: {stats['n_enter_B']:,} ({100*stats['n_enter_B']/stats['n_events_processed']:.2f}%)")
    print(f"  Sample I: {stats['n_sample_I']:,} ({100*stats['n_sample_I']/stats['n_events_processed']:.2f}%)")
    print(f"  Sample II: {stats['n_sample_II']:,} ({100*stats['n_sample_II']/stats['n_events_processed']:.2f}%)")
    print(f"\nSpecies breakdown (enter_B events):")
    for species, counts in stats['species_counts'].items():
        if counts['enter_B'] > 0:
            i_frac = 100*counts['sample_I']/counts['enter_B'] if counts['enter_B'] > 0 else 0
            print(f"  {species}: {counts['enter_B']:6,} | Sample I: {counts['sample_I']:6,} ({i_frac:5.1f}%) | Sample II: {counts['sample_II']:6,}")

if __name__ == "__main__":
    main()
