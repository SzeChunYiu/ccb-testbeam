#!/usr/bin/env python3
"""
Inspect krakow ROOT geometry to understand HRD/Sci_bar placements
for deriving T1/T2 trigger volume positions.
"""
import sys
from pathlib import Path

# Use hibeam_env ROOT
ROOT_PATH = Path("/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env")
sys.path.insert(0, str(ROOT_PATH / "lib"))

import ROOT

Geometry_file = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root")

print(f"Loading geometry: {Geometry_file}")
gGeoManager = ROOT.TGeoManager.Import(str(Geometry_file))
print(f"Geometry loaded: {gGeoManager.GetName()}")
print(f"Top volume: {gGeoManager.GetTopVolume().GetName()}")

# Find HRD and Sci_bar nodes
print("\n=== Searching for HRD and Sci_bar nodes ===")
hrd_nodes = []
scibar_nodes = []

def find_nodes(node, depth=0):
    name = node.GetName()
    if "HRD" in name:
        hrd_nodes.append((depth, name, node))
        print(f"  HRD: {name} at depth {depth}")
    if "Sci_bar" in name or "SciBar" in name or "scibar" in name:
        scibar_nodes.append((depth, name, node))
        print(f"  SciBar: {name} at depth {depth}")
    
    # Recurse into children
    daughter = node.GetVolume()
    if daughter:
        for i in range(daughter.GetNdaughters()):
            find_nodes(daughter.GetNode(i), depth + 1)

# Start from top volume
top_node = gGeoManager.GetTopNode()
find_nodes(top_node)

print(f"\n=== Found {len(hrd_nodes)} HRD nodes ===")
for depth, name, node in hrd_nodes[:5]:  # First 5
    vol = node.GetVolume()
    print(f"  {name}")
    print(f"    Volume: {vol.GetName()}")
    print(f"    Material: {vol.GetMaterial().GetName()}")
    print(f"    Shape: {vol.GetShape().ClassName()}")
    matrix = node.GetMatrix()
    if matrix:
        print(f"    Translation: ({matrix.GetTranslation()[0]:.3f}, {matrix.GetTranslation()[1]:.3f}, {matrix.GetTranslation()[2]:.3f}) cm")
        print(f"    Rotation:")
        rot = matrix.GetRotationMatrix()
        print(f"      [{rot[0]:.3f}, {rot[1]:.3f}, {rot[2]:.3f}]")
        print(f"      [{rot[3]:.3f}, {rot[4]:.3f}, {rot[5]:.3f}]")
        print(f"      [{rot[6]:.3f}, {rot[7]:.3f}, {rot[8]:.3f}]")

print(f"\n=== Found {len(scibar_nodes)} Sci_bar nodes ===")
for depth, name, node in scibar_nodes[:5]:  # First 5
    vol = node.GetVolume()
    print(f"  {name}")
    print(f"    Volume: {vol.GetName()}")
    print(f"    Material: {vol.GetMaterial().GetName()}")
    print(f"    Shape: {vol.GetShape().ClassName()}")
    matrix = node.GetMatrix()
    if matrix:
        print(f"    Translation: ({matrix.GetTranslation()[0]:.3f}, {matrix.GetTranslation()[1]:.3f}, {matrix.GetTranslation()[2]:.3f}) cm")
        print(f"    Rotation:")
        rot = matrix.GetRotationMatrix()
        print(f"      [{rot[0]:.3f}, {rot[1]:.3f}, {rot[2]:.3f}]")
        print(f"      [{rot[3]:.3f}, {rot[4]:.3f}, {rot[5]:.3f}]")
        print(f"      [{rot[6]:.3f}, {rot[7]:.3f}, {rot[8]:.3f}]")
        
# Get total volume count
print(f"\n=== Geometry summary ===")
print(f"Total volumes: {gGeoManager.GetListOfVolumes().GetEntries()}")
print(f"Total materials: {gGeoManager.GetListOfMaterials().GetEntries()}")
print(f"Total shapes: {gGeoManager.GetListOfShapes().GetEntries()}")
