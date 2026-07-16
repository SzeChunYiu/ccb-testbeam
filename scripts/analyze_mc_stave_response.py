#!/usr/bin/env python3
"""
Analyze existing GEANT4 truth data to extract:
- Energy loss in scintillator vs photon yield at WLS end
- For protons and deuterons at typical stave-entry energies

This uses the existing GEANT4 truth output (hibeam_g4) and digitized
waveform bridge to reconstruct the stave energy response without
needing a new standalone GEANT4 compilation.

Data sources:
- /projects/hep/fs10/shared/nnbar/HIBEAM_G4/alex_output_250611/hibeam_wasa_9012_100ev_g4output.root
- reports/0000000004.1.g4truth/ (sci_bar_pid_summary.csv, primary_truth_summary.csv)
- reports/1781083265...__s17a_geant4_energy_pid_truth_bridge/
"""

import numpy as np
import pandas as pd
from pathlib import Path
import uproot
import sys

REPO = Path('/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam')
G4_TRUTH = Path('/projects/hep/fs10/shared/nnbar/HIBEAM_G4')

def analyze_g4_truth():
    """Extract energy deposition and photon yield from GEANT4 truth."""
    
    # Existing truth summary from G4-03 / G4-04 studies
    truth_dir = REPO / 'reports/0000000004.1.g4truth'
    pid_csv = truth_dir / 'sci_bar_pid_summary.csv'
    
    if pid_csv.exists():
        df = pd.read_csv(pid_csv)
        print(f"Loaded {len(df)} rows from {pid_csv}")
        print(f"Columns: {list(df.columns)}")
        print(df.describe())
    else:
        print(f"Truth summary not found at {pid_csv}")
    
    # Try to read the ROOT file directly
    root_file = G4_TRUTH / 'alex_output_250611/hibeam_wasa_9012_100ev_g4output.root'
    if root_file.exists():
        print(f"\nOpening {root_file} ({root_file.stat().st_size/1e6:.0f} MB)")
        f = uproot.open(root_file)
        print(f"Keys: {f.keys()}")
        
        for key in f.keys():
            obj = f[key]
            if hasattr(obj, 'keys'):
                print(f"  {key}: {list(obj.keys())[:10]}")
            else:
                print(f"  {key}: {type(obj).__name__}")
    
    return None

def analyze_g4_bridge_report():
    """Analyze the G4-08 digitized bridge for WLS response."""
    
    bridge_dir = REPO / 'reports/1783883140.39222.3c4045b1__g4_08_keyed_digitized_geant4_native_join'
    
    # Read truth table  
    truth_csv = bridge_dir / 'geant4_truth_table.csv'
    if truth_csv.exists():
        df = pd.read_csv(truth_csv)
        print(f"\nG4-08 truth table: {len(df)} rows")
        print(f"Columns: {list(df.columns)}")
        # Look for energy-related columns
        energy_cols = [c for c in df.columns if any(k in c.lower() for k in ['edep', 'energy', 'ke', 'mev', 'amplitude', 'photon'])]
        print(f"Energy/photon columns: {energy_cols}")
        if energy_cols:
            print(df[energy_cols].describe())
    
    # Read digitized waveform summary
    summary_csv = bridge_dir / 'digitized_root_schema.csv'
    if summary_csv.exists():
        df2 = pd.read_csv(summary_csv)
        print(f"\nDigitized schema: {len(df2)} rows")
        print(f"Columns: {list(df2.columns)}")

    return None

def main():
    print("="*60)
    print("CCB Single-Stave MC Energy Response Analysis")
    print("="*60)
    
    analyze_g4_truth()
    analyze_g4_bridge_report()
    
    print("\n" + "="*60)
    print("Next steps:")
    print("  1. Extract proton/deuteron edep per scintillator bar from G4 truth")
    print("  2. Map to expected photon yield at WLS end (BC-408: ~10k photons/MeV)")
    print("  3. Account for WLS attenuation (~17 cm/ns, Y-11 absorption ~3.5m)")
    print("  4. Account for SiPM PDE (~40% at 500nm for S13360)")
    print("  5. Compare with data digitizer gain (92 ADC/MeV)")
    print("="*60)

if __name__ == '__main__':
    main()
