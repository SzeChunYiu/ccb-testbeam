#!/usr/bin/env python3
"""
Dump full volume inventory of krakow ROOT geometry
"""
import sys
from pathlib import Path

ROOT_PATH = Path("/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env")
sys.path.insert(0, str(ROOT_PATH / "lib"))

import ROOT

Geometry_file = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root")

print(f"Loading geometry: {Geometry_file}")
gGeoManager = ROOT.TGeoManager.Import(str(Geometry_file))
print(f"Geometry loaded: {gGeoManager.GetName()}")
print(f"Top volume: {gGeoManager.GetTopVolume().GetName()}")

# Get all volumes
print("\n=== All volumes ===")
volumes = gGeoManager.GetListOfVolumes()
for i in range(volumes.GetEntries()):
    vol = volumes.At(i)
    print(f"{i}: {vol.GetName()} - Material: {vol.GetMaterial().GetName()}, Shape: {vol.GetShape().ClassName()}")

# Get all nodes in the tree
print("\n=== All nodes in tree ===")
def list_all_nodes(node, depth=0, max_depth=10):
    indent = "  " * depth
    name = node.GetName()
    vol = node.GetVolume()
    matrix = node.GetMatrix()
    trans = matrix.GetTranslation() if matrix else (0,0,0)
    print(f"{indent}{name} (vol: {vol.GetName()}) pos=({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f})")
    
    if depth < max_depth:
        daughter = node.GetVolume()
        if daughter:
            for i in range(daughter.GetNdaughters()):
                list_all_nodes(daughter.GetNode(i), depth + 1, max_depth)

top_node = gGeoManager.GetTopNode()
list_all_nodes(top_node, max_depth=5)

# Check for any angle info in the geometry name or materials
print("\n=== Checking geometry name and config ===")
print(f"Geometry file name: {Geometry_file.name}")
print(f"Contains '109': {('109' in Geometry_file.name)}")
print(f"Contains '8-38deg': {('8-38deg' in Geometry_file.name)}")
print(f"Contains '4-71deg': {('4-71deg' in Geometry_file.name)}")
