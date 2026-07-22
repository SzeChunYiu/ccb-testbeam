#!/usr/bin/env python3
"""Data-driven deployed-geometry inventory (#844 CCB-844-GEOM).

Enumerates the Sci_bar layer structure from the deployed krakow MC truth:
per arm (LayerID1: 1=B, 2=A) list each LayerID, its depth (mean global Z),
transverse extent, and hit count. Verifies the steering request of 8 B + 4 A bars.
"""
import json
import numpy as np
import uproot

ROOT = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root"
OUT = "/projects/hep/fs10/shared/nnbar/billy/ccb_geom_inventory.json"

t = uproot.open(ROOT)["hibeam"]
br = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_LayerID2",
      "Sci_bar_GlobalPosition_X", "Sci_bar_GlobalPosition_Y",
      "Sci_bar_GlobalPosition_Z", "Sci_bar_EDep"]
import awkward as ak
lay = ak.flatten(t["Sci_bar_LayerID"].array()).to_numpy()
arm = ak.flatten(t["Sci_bar_LayerID1"].array()).to_numpy()
l2 = ak.flatten(t["Sci_bar_LayerID2"].array()).to_numpy()
gz = ak.flatten(t["Sci_bar_GlobalPosition_Z"].array()).to_numpy()
gx = ak.flatten(t["Sci_bar_GlobalPosition_X"].array()).to_numpy()
gy = ak.flatten(t["Sci_bar_GlobalPosition_Y"].array()).to_numpy()
ed = ak.flatten(t["Sci_bar_EDep"].array()).to_numpy()

arm_name = {1: "B", 2: "A"}
inv = {"root": ROOT, "n_hits": int(len(lay)), "arms": {}}
print(f"total Sci_bar hits: {len(lay)}")
print(f"unique LayerID1 (arm): {sorted(set(arm.tolist()))}")
print(f"unique LayerID: {sorted(set(lay.tolist()))}")
print(f"unique LayerID2: {sorted(set(l2.tolist()))[:20]}")

for a in sorted(set(arm.tolist())):
    am = arm == a
    layers = []
    for L in sorted(set(lay[am].tolist())):
        s = am & (lay == L)
        layers.append(dict(
            layer_id=int(L), n_hits=int(s.sum()),
            depth_z_mm_mean=float(np.mean(gz[s])),
            depth_z_mm_std=float(np.std(gz[s])),
            x_extent_mm=[float(np.min(gx[s])), float(np.max(gx[s]))],
            y_extent_mm=[float(np.min(gy[s])), float(np.max(gy[s]))],
            edep_mean_MeV=float(np.mean(ed[s])),
        ))
    inv["arms"][arm_name.get(a, str(a))] = dict(
        arm_id=int(a), n_layers=len(layers), layers=layers)
    print(f"\n=== ARM {arm_name.get(a, a)} (LayerID1={a}): {len(layers)} layers ===")
    for L in layers:
        print(f"  layer {L['layer_id']:2d}: z={L['depth_z_mm_mean']:8.1f}+-{L['depth_z_mm_std']:5.1f} mm"
              f"  hits={L['n_hits']:7d}  edep_mean={L['edep_mean_MeV']:.4f}")

nb = inv["arms"].get("B", {}).get("n_layers", 0)
na = inv["arms"].get("A", {}).get("n_layers", 0)
inv["verify_8B_4A"] = {"B_layers": nb, "A_layers": na,
                       "matches_steering": (nb == 8 and na == 4)}
print(f"\nVERIFY steering (8 B + 4 A): B={nb} A={na} -> "
      f"{'MATCH' if (nb==8 and na==4) else 'MISMATCH'}")
with open(OUT, "w") as fh:
    json.dump(inv, fh, indent=2)
print("GEOM_INVENTORY_DONE")
