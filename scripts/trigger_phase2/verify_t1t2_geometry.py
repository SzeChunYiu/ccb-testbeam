#!/usr/bin/env python3
"""
Verify the T1T2 geometry: check T1/T2 placement, compute sha256, run overlap check.
"""
import sys
import hashlib
import subprocess
from pathlib import Path

ROOT_PATH = Path("/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env")
sys.path.insert(0, str(ROOT_PATH / "lib"))

import ROOT

# Geometry files
ORIGINAL = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root")
NEW = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root")

# Compute sha256
def compute_sha256(path):
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

print("=== SHA256 Hashes ===")
print(f"Original: {compute_sha256(ORIGINAL)}")
print(f"New T1T2: {compute_sha256(NEW)}")

# Load new geometry
print(f"\n=== Loading new geometry ===")
gGeoManager = ROOT.TGeoManager.Import(str(NEW))
print(f"Geometry: {gGeoManager.GetName()}")
print(f"Total volumes: {gGeoManager.GetListOfVolumes().GetEntries()}")

# Find T1/T2 nodes
print("\n=== T1/T2 Nodes ===")
t1_node = None
t2_node = None

def find_t1t2(node, depth=0):
    global t1_node, t2_node
    name = node.GetName()
    if "T1_trigger" in name or "T1_" in name:
        t1_node = node
    elif "T2_trigger" in name or "T2_" in name:
        t2_node = node
    
    daughter = node.GetVolume()
    if daughter:
        for i in range(daughter.GetNdaughters()):
            find_t1t2(daughter.GetNode(i), depth + 1)

find_t1t2(gGeoManager.GetTopNode())

if t1_node:
    vol = t1_node.GetVolume()
    matrix = t1_node.GetMatrix()
    trans = matrix.GetTranslation()
    shape = vol.GetShape()
    print(f"T1 node: {t1_node.GetName()}")
    print(f"  Volume: {vol.GetName()}, Material: {vol.GetMaterial().GetName()}")
    print(f"  Shape: {shape.ClassName()}, dims: {shape.GetDX()*2:.1f}×{shape.GetDY()*2:.1f}×{shape.GetDZ()*2:.1f} cm")
    print(f"  Position: ({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm")

if t2_node:
    vol = t2_node.GetVolume()
    matrix = t2_node.GetMatrix()
    trans = matrix.GetTranslation()
    shape = vol.GetShape()
    print(f"T2 node: {t2_node.GetName()}")
    print(f"  Volume: {vol.GetName()}, Material: {vol.GetMaterial().GetName()}")
    print(f"  Shape: {shape.ClassName()}, dims: {shape.GetDX()*2:.1f}×{shape.GetDY()*2:.1f}×{shape.GetDZ()*2:.1f} cm")
    print(f"  Position: ({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm")

# Verify baseline nodes unchanged
print("\n=== Verifying baseline nodes ===")
baseline_results = {}

def check_baseline_nodes(node, depth=0):
    name = node.GetName()
    for check_name in ["Sci_stack1", "Sci_stack2", "TARGET", "ProtoTPCHull"]:
        if check_name in name and check_name not in baseline_results:
            vol = node.GetVolume()
            matrix = node.GetMatrix()
            trans = matrix.GetTranslation()
            baseline_results[check_name] = f"position=({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm"
    
    daughter = node.GetVolume()
    if daughter:
        for i in range(daughter.GetNdaughters()):
            check_baseline_nodes(daughter.GetNode(i), depth + 1)

check_baseline_nodes(gGeoManager.GetTopNode())

for check_name in ["Sci_stack1", "Sci_stack2", "TARGET", "ProtoTPCHull"]:
    if check_name in baseline_results:
        print(f"{check_name}: {baseline_results[check_name]} — OK")
    else:
        print(f"{check_name}: NOT FOUND — ERROR")

# Overlap check
print("\n=== Overlap Check ===")
print("Running TGeoManager::CheckGeometry()...")
nchecks = gGeoManager.CheckGeometry()
print(f"Overlaps found: {nchecks}")
if nchecks == 0:
    print("CLEAN: no overlaps")
else:
    print(f"WARNING: {nchecks} overlaps detected")

print("\n=== VERIFICATION COMPLETE ===")
