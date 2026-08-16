#!/usr/bin/env python3
"""Phase 3 Threshold/Coincidence Scan Harness for Issue #1045.

Computes trigger efficiency and migration matrix across threshold/coincidence
parameter space using T1/T2 trigger scintillator truth hits.

Provenance contract: this harness is deterministic for a given input ROOT file
and configuration grid. Results are reproducible across runs.

Schema tolerance:
- If trigger branches (T1/T2 EDep/Time) are present → full hardware-response mode
- If only HRD proxy branches are present → proxy-mode (computes proxy efficiency)
- Grid scan proceeds in either mode.

Hardware constants from trigger_baseline_characterization.py:
- A_ARM = 2 (first A-arm bar layer ID)
- B_ARM = 1 (first B-arm bar layer ID)
- COINC_NS = 15.0 (historical coincidence window)

Grid defaults (configurable via TRIGGER_THRESHOLD_SCAN_* env vars):
- THRESHOLDS: 0.5, 1.0, 2.0, 5.0 MeV
- COINCIDENCE_WINDOWS: 5, 10, 15, 20, 30 ns
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, List, Any

try:
    import uproot
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}", file=sys.stderr)
    sys.exit(1)


# Hardware constants (from trigger_baseline_characterization.py)
A_ARM = 2
B_ARM = 1
COINC_NS = 15.0

# T1/T2 sensitive-detector branch names as actually written by the Phase 2
# trigger-logging SD (verified against output_krakow_phase2_10k.root):
# T1_trigger_log_EDep / T1_trigger_log_Time / T2_trigger_log_EDep /
# T2_trigger_log_Time. Internal keys stay short ("T1_EDep" ...); the mapping
# is applied only at the uproot boundary.
HARDWARE_BRANCH_MAP = {
    "T1_EDep": "T1_trigger_log_EDep",
    "T1_Time": "T1_trigger_log_Time",
    "T2_EDep": "T2_trigger_log_EDep",
    "T2_Time": "T2_trigger_log_Time",
}
HARDWARE_BRANCHES = list(HARDWARE_BRANCH_MAP.values())

# HRD proxy branches; when present alongside the T1/T2 branches they give
# hardware mode the same per-species "enter" denominator as proxy mode, so
# the Phase 4 quadrant comparison is exact rather than interval-bounded.
PROXY_BRANCHES = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_Time"]


# Config-driven grid defaults (can be overridden via env vars)
DEFAULT_THRESHOLDS = [float(x) for x in os.getenv(
    "TRIGGER_THRESHOLD_SCAN_THRESHOLDS", "0.5,1.0,2.0,5.0"
).split(",")]
DEFAULT_COINCIDENCE_WINDOWS = [float(x) for x in os.getenv(
    "TRIGGER_THRESHOLD_SCAN_COINCIDENCE_WINDOWS", "5,10,15,20,30"
).split(",")]


@dataclass
class ScanResult:
    """Result of a single threshold/coincidence configuration."""
    threshold_mev: float
    coinc_ns: float
    n_events: int
    n_trigger_pass: int
    efficiency: float
    species_breakdown: Dict[str, Dict[str, int]]


@dataclass
class ScanConfig:
    """Configuration for the threshold scan."""
    input_file: str
    output_file: str
    repo_root: str
    thresholds: List[float]
    coincidence_windows: List[float]
    max_events: Optional[int] = None


def classify_event_hardware_response(
    t1_edep: np.ndarray,
    t1_time: np.ndarray,
    t2_edep: np.ndarray,
    t2_time: np.ndarray,
    threshold_mev: float,
    coinc_ns: float,
) -> Dict[str, bool]:
    """Classify event using hardware-response T1/T2 truth hits.
    
    Args:
        t1_edep: Energy deposits in T1 (MeV)
        t1_time: Hit times in T1 (ns)
        t2_edep: Energy deposits in T2 (MeV)
        t2_time: Hit times in T2 (ns)
        threshold_mev: Energy threshold for trigger (MeV)
        coinc_ns: Coincidence window (ns)
    
    Returns:
        Dict with keys: t1_above_threshold, t2_above_threshold, coincidence
    """
    t1_pass = (t1_edep >= threshold_mev).any() if len(t1_edep) > 0 else False
    t2_pass = (t2_edep >= threshold_mev).any() if len(t2_edep) > 0 else False
    
    if t1_pass and t2_pass:
        t1_earliest = float(t1_time[t1_edep >= threshold_mev].min())
        t2_earliest = float(t2_time[t2_edep >= threshold_mev].min())
        if np.isfinite(t1_earliest) and np.isfinite(t2_earliest):
            coinc = abs(t1_earliest - t2_earliest) < coinc_ns
        else:
            coinc = False
    else:
        coinc = False
    
    return {
        "t1_above_threshold": t1_pass,
        "t2_above_threshold": t2_pass,
        "coincidence": coinc,
    }


def classify_event_proxy(
    layer: np.ndarray,
    layer1: np.ndarray,
    pdg: np.ndarray,
    time: np.ndarray,
    coinc_ns: float,
) -> Dict[str, bool]:
    """Classify event using HRD proxy (for baseline comparison).
    
    This mirrors trigger_baseline_characterization.py logic for consistency.
    """
    CHARGED_PDG = {
        2212, 1000010020, 1000010030, 1000020030, 1000020040,
        11, -11, 13, -13, 211, -211, 321, -321,
        1000060120, 1000060130, 1000060140,
    }
    
    if len(layer) == 0:
        return {"enter_B": False, "enter_A": False, "sample_I": False, "sample_II": False}
    
    charged = np.array([p in CHARGED_PDG for p in pdg])
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
    
    return {
        "enter_B": enter_b,
        "enter_A": enter_a,
        "sample_I": coinc,
        "sample_II": enter_b,
    }


def get_primary_species(pdg_array: np.ndarray) -> Optional[int]:
    """Get primary charged species PDG code from event."""
    if len(pdg_array) == 0:
        return None
    CHARGED_PDG = {
        2212, 1000010020, 1000010030, 1000020030, 1000020040,
        11, -11, 13, -13, 211, -211, 321, -321,
        1000060120, 1000060130, 1000060140,
    }
    for p in pdg_array:
        if int(p) in CHARGED_PDG:
            return int(p)
    return None


def pdg_to_species(pdg: int) -> str:
    """Convert PDG code to species name."""
    species_map = {
        2212: "proton",
        1000010020: "deuteron",
        1000010030: "triton",
        1000020030: "he3",
        1000020040: "alpha",
        1000060120: "C12",
        1000060130: "C13",
        1000060140: "C14",
        11: "electron",
        -11: "positron",
        13: "muon_minus",
        -13: "muon_plus",
    }
    return species_map.get(pdg, f"PDG_{pdg}")


def run_threshold_scan(config: ScanConfig, mode: str) -> List[ScanResult]:
    """Run threshold scan over configured grid.
    
    Args:
        config: Scan configuration
        mode: "hardware" for T1/T2 branches, "proxy" for HRD proxy branches
    
    Returns:
        List of scan results, one per (threshold, coinc_ns) pair
    """
    print(f"Running threshold scan in {mode}-response mode")
    print(f"Thresholds: {config.thresholds}")
    print(f"Coincidence windows: {config.coincidence_windows}")
    
    results = []
    
    with uproot.open(config.input_file) as f:
        tree = f["hibeam"]
        n_entries = int(tree.num_entries)
        
        if config.max_events:
            n_entries = min(n_entries, config.max_events)
        
        print(f"Total entries to process: {n_entries:,}")
        
        # Determine branches based on mode
        if mode == "hardware":
            required_branches = HARDWARE_BRANCHES
        else:  # proxy mode
            required_branches = PROXY_BRANCHES

        # Check branch presence
        available_branches = tree.keys()
        missing = [b for b in required_branches if b not in available_branches]
        if missing:
            raise ValueError(f"Missing required branches for {mode}-response mode: {missing}")

        # In hardware mode, load the HRD proxy branches alongside T1/T2 when
        # present so the species breakdown uses the same "enter" denominator
        # as proxy mode (enables exact Phase 4 quadrants).
        hrd_join = (
            mode == "hardware"
            and all(b in available_branches for b in PROXY_BRANCHES)
        )
        load_branches = list(required_branches) + (PROXY_BRANCHES if hrd_join else [])

        chunk_size = 10000

        for threshold_mev in config.thresholds:
            for coinc_ns in config.coincidence_windows:
                print(f"  Scanning: threshold={threshold_mev} MeV, coinc={coinc_ns} ns")

                stats = {
                    "n_events": 0,
                    "n_pass": 0,
                    "species": {},
                }

                for start in range(0, n_entries, chunk_size):
                    end = min(start + chunk_size, n_entries)

                    chunk = tree.arrays(
                        load_branches,
                        entry_start=start, entry_stop=end, library="np"
                    )

                    for i in range(len(chunk[load_branches[0]])):
                        stats["n_events"] += 1

                        if mode == "hardware":
                            t1_edep = chunk[HARDWARE_BRANCH_MAP["T1_EDep"]][i]
                            t1_time = chunk[HARDWARE_BRANCH_MAP["T1_Time"]][i]
                            t2_edep = chunk[HARDWARE_BRANCH_MAP["T2_EDep"]][i]
                            t2_time = chunk[HARDWARE_BRANCH_MAP["T2_Time"]][i]

                            flags = classify_event_hardware_response(
                                t1_edep, t1_time, t2_edep, t2_time,
                                threshold_mev, coinc_ns
                            )
                            pass_trigger = flags["coincidence"]

                            # Species breakdown in hardware mode: only when the
                            # HRD proxy branches are present in the same file.
                            # n_enter mirrors proxy mode's enter_B so the
                            # Phase 4 quadrant denominators match exactly.
                            if hrd_join:
                                layer = chunk["Sci_bar_LayerID"][i]
                                layer1 = chunk["Sci_bar_LayerID1"][i]
                                pdg = chunk["Sci_bar_PDG"][i]
                                htime = chunk["Sci_bar_Time"][i]

                                pflags = classify_event_proxy(layer, layer1, pdg, htime, coinc_ns)
                                primary_pdg = get_primary_species(pdg)
                                if primary_pdg and pflags["enter_B"]:
                                    species = pdg_to_species(primary_pdg)
                                    if species not in stats["species"]:
                                        stats["species"][species] = {"n_enter": 0, "n_pass": 0}
                                    stats["species"][species]["n_enter"] += 1
                                    if pass_trigger:
                                        stats["species"][species]["n_pass"] += 1
                        else:  # proxy mode
                            layer = chunk["Sci_bar_LayerID"][i]
                            layer1 = chunk["Sci_bar_LayerID1"][i]
                            pdg = chunk["Sci_bar_PDG"][i]
                            time = chunk["Sci_bar_Time"][i]
                            
                            flags = classify_event_proxy(layer, layer1, pdg, time, coinc_ns)
                            pass_trigger = flags["sample_I"]
                            
                            # Species breakdown for proxy mode
                            primary_pdg = get_primary_species(pdg)
                            if primary_pdg:
                                species = pdg_to_species(primary_pdg)
                                if species not in stats["species"]:
                                    stats["species"][species] = {"n_enter": 0, "n_pass": 0}
                                if flags["enter_B"]:
                                    stats["species"][species]["n_enter"] += 1
                                    if pass_trigger:
                                        stats["species"][species]["n_pass"] += 1
                        
                        if pass_trigger:
                            stats["n_pass"] += 1
                
                efficiency = stats["n_pass"] / stats["n_events"] if stats["n_events"] > 0 else 0.0
                results.append(ScanResult(
                    threshold_mev=threshold_mev,
                    coinc_ns=coinc_ns,
                    n_events=stats["n_events"],
                    n_trigger_pass=stats["n_pass"],
                    efficiency=efficiency,
                    species_breakdown=stats["species"],
                ))
                
                n_pass_str = str(stats["n_pass"])
                n_events_str = str(stats["n_events"])
                print(f"    Efficiency: {efficiency:.4f} ({n_pass_str}/{n_events_str})")
    
    return results


def detect_mode(tree) -> str:
    """Detect whether file has hardware-response or proxy branches."""
    branches = tree.keys()
    if all(b in branches for b in HARDWARE_BRANCHES):
        return "hardware"
    elif "Sci_bar_LayerID" in branches and "Sci_bar_LayerID1" in branches:
        return "proxy"
    else:
        raise ValueError("Cannot determine input schema: missing both hardware and proxy branches")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="truth-level MC ROOT file (Phase 1B baseline or Phase 2 with trigger branches)",
    )
    parser.add_argument(
        "--output",
        default="research/trigger_migration_study/phase3/threshold_scan_results.json",
        help="output JSON path (repo-relative)",
    )
    parser.add_argument(
        "--repo-root",
        default="/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam",
        help="repository root the output path is resolved against",
    )
    parser.add_argument(
        "--thresholds",
        default=None,
        help=f"comma-separated threshold values in MeV (default: from env or {DEFAULT_THRESHOLDS})",
    )
    parser.add_argument(
        "--coincidence-windows",
        default=None,
        help=f"comma-separated coincidence windows in ns (default: from env or {DEFAULT_COINCIDENCE_WINDOWS})",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="maximum events to process (for testing)",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "hardware", "proxy"],
        default="auto",
        help="force mode or auto-detect from branch presence",
    )
    
    args = parser.parse_args()
    
    # Parse thresholds and coincidence windows
    if args.thresholds:
        thresholds = [float(x) for x in args.thresholds.split(",")]
    else:
        thresholds = DEFAULT_THRESHOLDS
    
    if args.coincidence_windows:
        coinc_windows = [float(x) for x in args.coincidence_windows.split(",")]
    else:
        coinc_windows = DEFAULT_COINCIDENCE_WINDOWS
    
    config = ScanConfig(
        input_file=args.input,
        output_file=args.output,
        repo_root=args.repo_root,
        thresholds=thresholds,
        coincidence_windows=coinc_windows,
        max_events=args.max_events,
    )
    
    # Detect mode
    with uproot.open(config.input_file) as f:
        tree = f["hibeam"]
        if args.mode == "auto":
            mode = detect_mode(tree)
        else:
            mode = args.mode
            # Verify mode is valid
            branches = tree.keys()
            if mode == "hardware" and not all(b in branches for b in HARDWARE_BRANCHES):
                raise ValueError(f"Requested hardware mode but T1/T2 branches not found")
            if mode == "proxy" and not all(b in branches for b in PROXY_BRANCHES):
                raise ValueError(f"Requested proxy mode but HRD branches not found")
    
    print(f"Mode: {mode}-response")
    print(f"Input: {config.input_file}")
    
    results = run_threshold_scan(config, mode)
    
    # Convert results to dict for JSON serialization
    output_data = {
        "scan_config": {
            "input_file": config.input_file,
            "mode": mode,
            "thresholds_mev": config.thresholds,
            "coincidence_windows_ns": config.coincidence_windows,
            "max_events": config.max_events,
        },
        "results": [asdict(r) for r in results],
    }
    
    output_path = Path(config.repo_root) / config.output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)
    
    print()
    print(f"Results saved to: {config.output_file}")
    print(f"\nSummary:")
    print(f"  Total configurations scanned: {len(results)}")
    
    # Print efficiency table
    print(f"\nEfficiency table:")
    print(f"  Threshold (MeV) | Coinc (ns) | Efficiency")
    print("  " + "-" * 45)
    for r in results:
        print(f"  {r.threshold_mev:13.1f} | {r.coinc_ns:10.0f} | {r.efficiency:.4f}")


if __name__ == "__main__":
    main()
