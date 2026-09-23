#!/usr/bin/env python3
"""
Check T1/T2 node names in the new geometry.
"""
import sys
from pathlib import Path

ROOT_PATH = Path("/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env")
sys.path.insert(0, str(ROOT_PATH / "lib"))

import ROOT

NEW = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root")

print(f"Loading: {NEW}")
gGeoManager = ROOT.TGeoManager.Import(str(NEW))

# List ALL nodes
print("\n=== All nodes ===")
def list_all_nodes(node, depth=0, max_depth=3):
    indent = "  " * depth
    print(f"{indent}{node.GetName()} (vol: {node.GetVolume().GetName()})")
    
    if depth < max_depth:
        daughter = node.GetVolume()
        if daughter:
            for i in range(daughter.GetNdaughters()):
                list_all_nodes(daughter.GetNode(i), depth + 1, max_depth)

list_all_nodes(gGeoManager.GetTopNode())

# Search for T1/T2 volumes
print("\n=== Searching for T1/T2 ===")
t1_vol = gGeoManager.GetVolume("T1_trigger_log")
t2_vol = gGeoManager.GetVolume("T2_trigger_log")
print(f"T1_trigger_log volume: {t1_vol is not None}")
print(f"T2_trigger_log volume: {t2_vol is not None}")

# List volumes with "T1" or "T2" in name
print("\n=== Volumes with T1/T2 in name ===")
volumes = gGeoManager.GetListOfVolumes()
for i in range(volumes.GetEntries()):
    vol = volumes.At(i)
    name = vol.GetName()
    if "T1" in name or "T2" in name:
        print(f"{i}: {name} — Material: {vol.GetMaterial().GetName()}, Shape: {vol.GetShape().ClassName()}")
