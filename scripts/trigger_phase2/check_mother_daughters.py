#!/usr/bin/env python3
"""
Check MOTHER volume daughters to find T1/T2 nodes.
"""
import sys
from pathlib import Path

ROOT_PATH = Path("/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env")
sys.path.insert(0, str(ROOT_PATH / "lib"))

import ROOT

NEW = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root")

print(f"Loading: {NEW}")
gGeoManager = ROOT.TGeoManager.Import(str(NEW))

mother = gGeoManager.GetTopVolume()
print(f"\nTop volume: {mother.GetName()}")
print(f"Number of daughters: {mother.GetNdaughters()}")

print("\n=== All MOTHER daughters ===")
for i in range(mother.GetNdaughters()):
    node = mother.GetNode(i)
    vol = node.GetVolume()
    matrix = node.GetMatrix()
    trans = matrix.GetTranslation()
    shape = vol.GetShape()
    
    print(f"{i}: {node.GetName()}")
    print(f"   Volume: {vol.GetName()}, Material: {vol.GetMaterial().GetName()}")
    print(f"   Shape: {shape.ClassName()}")
    if hasattr(shape, "GetDX"):
        print(f"   Dims: {shape.GetDX()*2:.1f}×{shape.GetDY()*2:.1f}×{shape.GetDZ()*2:.1f} cm")
    print(f"   Position: ({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm")
    print(f"   Copy number: {node.GetNumber()}")
