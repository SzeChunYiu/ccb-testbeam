#!/usr/bin/env python3
"""
Add T1/T2 trigger volumes to krakow ROOT geometry via TGeo.
Places T1/T2 30 cm upstream of Sci_stack positions along the arm angles.

IMPORTANT: Geometry must be reopened before adding nodes to an already-closed geometry.
"""
import sys
import math
import hashlib
from pathlib import Path

ROOT_PATH = Path("/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env")
sys.path.insert(0, str(ROOT_PATH / "lib"))

import ROOT

# Input/output paths
INPUT_ROOT = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/configs/krakow_109_8-38deg_4-71deg.root")
OUTPUT_ROOT = Path("/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/ccb-wt-1045-phase2/geant4/configs/krakow_109_8-38deg_4-71deg_T1T2.root")

print(f"Loading geometry: {INPUT_ROOT}")
gGeoManager = ROOT.TGeoManager.Import(str(INPUT_ROOT))
print(f"Geometry loaded: {gGeoManager.GetName()}")

# Get top volume BEFORE closing
mother = gGeoManager.GetTopVolume()
print(f"Top volume: {mother.GetName()}")
print(f"Original daughters: {mother.GetNdaughters()}")

# Get or create PSci medium
psci_medium = None
mediums = gGeoManager.GetListOfMedia()
for i in range(mediums.GetEntries()):
    med = mediums.At(i)
    if med.GetMaterial().GetName() == "PSci":
        psci_medium = med
        print(f"Found existing PSci medium: {med.GetName()}")
        break

if not psci_medium:
    print("Creating new PSci medium")
    psci_mat = gGeoManager.GetMaterial("PSci")
    if not psci_mat:
        print("ERROR: PSci material not found!")
        sys.exit(1)
    psci_medium = ROOT.TGeoMedium("PSci_medium", 1, psci_mat)
    gGeoManager.AddMedium(psci_medium)
    print(f"Created PSci medium: density={psci_mat.GetDensity()} g/cm3")

# Find Sci_stack positions
sci_stack1_pos = None
sci_stack2_pos = None

nodes = gGeoManager.GetListOfNodes()
for i in range(nodes.GetEntries()):
    node = nodes.At(i)
    name = node.GetName()
    if "Sci_stack1" in name:
        matrix = node.GetMatrix()
        trans = matrix.GetTranslation()
        sci_stack1_pos = (trans[0], trans[1], trans[2])
        print(f"Sci_stack1 position: ({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm")
    elif "Sci_stack2" in name:
        matrix = node.GetMatrix()
        trans = matrix.GetTranslation()
        sci_stack2_pos = (trans[0], trans[1], trans[2])
        print(f"Sci_stack2 position: ({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm")

# Calculate unit vectors
def unit_vector(angle_deg):
    angle_rad = math.radians(angle_deg)
    return (math.sin(angle_rad), 0, math.cos(angle_rad))

# T1 on A-arm (71.5°) — upstream of Sci_stack2
t1_angle = 71.5
t1_unit = unit_vector(t1_angle)
if sci_stack2_pos:
    t1_pos = (
        sci_stack2_pos[0] - 30.0 * t1_unit[0],
        sci_stack2_pos[1] - 30.0 * t1_unit[1],
        sci_stack2_pos[2] - 30.0 * t1_unit[2]
    )
    print(f"T1 position (upstream of Sci_stack2): ({t1_pos[0]:.3f}, {t1_pos[1]:.3f}, {t1_pos[2]:.3f}) cm")

# T2 on B-arm (-38°) — upstream of Sci_stack1
t2_angle = -38.0
t2_unit = unit_vector(t2_angle)
if sci_stack1_pos:
    t2_pos = (
        sci_stack1_pos[0] - 30.0 * t2_unit[0],
        sci_stack1_pos[1] - 30.0 * t2_unit[1],
        sci_stack1_pos[2] - 30.0 * t2_unit[2]
    )
    print(f"T2 position (upstream of Sci_stack1): ({t2_pos[0]:.3f}, {t2_pos[1]:.3f}, {t2_pos[2]:.3f}) cm")

# Create T1 volume (10x10x1 cm box)
t1_shape = ROOT.TGeoBBox("T1_box", 5.0, 5.0, 0.5)  # Half-lengths
t1_volume = ROOT.TGeoVolume("T1_trigger_log", t1_shape, psci_medium)
print(f"Created T1 volume: 10x10x1 cm PSci")

# Create T2 volume (15x15x1 cm box)
t2_shape = ROOT.TGeoBBox("T2_box", 7.5, 7.5, 0.5)  # Half-lengths
t2_volume = ROOT.TGeoVolume("T2_trigger_log", t2_shape, psci_medium)
print(f"Created T2 volume: 15x15x1 cm PSci")

# CRITICAL: Geometry is already closed from Import. We need to add nodes directly
# to the volume without relying on CloseGeometry() to rebuild the structure.
print("\nAdding T1/T2 nodes to MOTHER volume...")

# Add T1 to geometry
if sci_stack2_pos:
    t1_translation = ROOT.TGeoTranslation(t1_pos[0], t1_pos[1], t1_pos[2])
    # Use AddNode with explicit copy number
    mother.AddNode(t1_volume, 100, t1_translation)
    print(f"Added T1 at ({t1_pos[0]:.3f}, {t1_pos[1]:.3f}, {t1_pos[2]:.3f}) cm")

# Add T2 to geometry
if sci_stack1_pos:
    t2_translation = ROOT.TGeoTranslation(t2_pos[0], t2_pos[1], t2_pos[2])
    mother.AddNode(t2_volume, 101, t2_translation)
    print(f"Added T2 at ({t2_pos[0]:.3f}, {t2_pos[1]:.3f}, {t2_pos[2]:.3f}) cm")

print(f"Daughters after AddNode: {mother.GetNdaughters()}")

# Export WITHOUT closing again (geometry is already structured properly)
print(f"\nExporting to: {OUTPUT_ROOT}")
gGeoManager.Export(str(OUTPUT_ROOT))
print("Export complete")

# Compute sha256
def compute_sha256(path):
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

original_sha256 = compute_sha256(INPUT_ROOT)
new_sha256 = compute_sha256(OUTPUT_ROOT)

print(f"\n=== SHA256 Hashes ===")
print(f"Original: {original_sha256}")
print(f"New T1T2: {new_sha256}")

# Reload and verify
print(f"\n=== Reloading for verification ===")
gGeoManager2 = ROOT.TGeoManager.Import(str(OUTPUT_ROOT))
mother2 = gGeoManager2.GetTopVolume()
print(f"Reloaded top volume: {mother2.GetName()}")
print(f"Daughters: {mother2.GetNdaughters()}")

# Check for T1/T2 in the daughters
print(f"\n=== Verifying T1/T2 in daughters ===")
t1_found = False
t2_found = False
for i in range(mother2.GetNdaughters()):
    node = mother2.GetNode(i)
    vol = node.GetVolume()
    if "T1" in vol.GetName():
        t1_found = True
        trans = node.GetMatrix().GetTranslation()
        print(f"T1 found: {node.GetName()} at ({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm")
    elif "T2" in vol.GetName():
        t2_found = True
        trans = node.GetMatrix().GetTranslation()
        print(f"T2 found: {node.GetName()} at ({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f}) cm")

print(f"\nT1 verified: {t1_found}")
print(f"T2 verified: {t2_found}")

if t1_found and t2_found:
    print("\n=== SUCCESS ===")
else:
    print("\n=== ERROR: T1/T2 not found in exported geometry ===")
    sys.exit(1)
