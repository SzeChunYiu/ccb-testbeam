#!/usr/bin/env python3
"""MC-side ΔE-E with the resolved layer->stave mapping + PrimaryWeight (A-002/A-003).

B2/B4/B6/B8 = MC B-arm LayerID 1,3,5,7 (every other, per #869). Weighted by
PrimaryWeight (A-003, ESS=35%). deltaE_mc=edep(B2); E_mc=edep(B4+B6+B8).
Computes the alternate {0,2,4,6} mapping too for the honest offset caveat.
"""
import json, os
import numpy as np
import awkward as ak
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root"
OUT = "/projects/hep/fs10/shared/nnbar/billy/ccb_mc_deltae"
os.makedirs(OUT, exist_ok=True)

t = uproot.open(ROOT)["hibeam"]
arm = t["Sci_bar_LayerID1"].array()
lay = t["Sci_bar_LayerID"].array()
ed = t["Sci_bar_EDep"].array()
pw = t["PrimaryWeight"].array()
# event weight = first primary weight per event (beam primary)
w_evt = ak.to_numpy(ak.firsts(pw, axis=1))
n_evt = len(w_evt)

def edep_in_layer(L):
    mask = (arm == 1) & (lay == L)
    return ak.to_numpy(ak.sum(ed[mask], axis=1))  # MeV per event

# per-event edep in each candidate B layer
E = {L: edep_in_layer(L) for L in range(8)}

def build(map_layers, tag):
    b2, b4, b6, b8 = (E[l] for l in map_layers)
    deltaE = b2
    Efull = b4 + b6 + b8
    sel = (deltaE > 0) & (Efull > 0)  # events with a ΔE hit and downstream E
    w = w_evt[sel]
    w = np.where(np.isfinite(w), w, 0.0)
    de, ee = deltaE[sel], Efull[sel]
    # weighted medians via cumulative weight
    def wmed(x, w):
        o = np.argsort(x); xs, ws = x[o], w[o]
        cw = np.cumsum(ws) / ws.sum()
        return float(np.interp(0.5, cw, xs))
    res = dict(mapping=tag, layers=list(map_layers), n_events=int(sel.sum()),
               deltaE_wmedian_MeV=wmed(de, w), E_wmedian_MeV=wmed(ee, w),
               # anti-correlation (stopping signature): corr(deltaE, E)
               corr_deltaE_E=float(np.corrcoef(de, ee)[0, 1]))
    return res, de, ee, w

primary, de, ee, w = build([1, 3, 5, 7], "B2/B4/B6/B8 = LayerID 1,3,5,7 (#869)")
alt, _, _, _ = build([0, 2, 4, 6], "alt LayerID 0,2,4,6")

result = dict(
    root=ROOT, mapping_primary=primary, mapping_alternate=alt,
    weight="PrimaryWeight applied (A-003); event weight = first primary",
    note="deltaE_mc=edep(B2)=LayerID1; E_mc=edep(B4+B6+B8)=LayerID3+5+7. "
         "Physical offset (1,3,5,7 vs 0,2,4,6) still to be pinned from DAQ drawings.",
    units="MeV (MC edep; data side is ADC in deltaE_a002)",
)
with open(OUT + "/result.json", "w") as fh:
    json.dump(result, fh, indent=2)

# weighted ΔE-E density (primary mapping)
plt.figure(figsize=(6, 4.5))
plt.hexbin(ee, de, C=w, reduce_C_function=np.sum, gridsize=45, mincnt=1,
           bins="log", cmap="viridis")
plt.colorbar(label="Σ weight (log)")
plt.xlabel("E = edep(B4+B6+B8) [MeV]")
plt.ylabel("ΔE = edep(B2) [MeV]")
plt.title("MC ΔE-E (weighted, LayerID 1,3,5,7)")
plt.tight_layout()
plt.savefig(OUT + "/DE-MC-01_deltaE_E_mc.png", dpi=130)

print(json.dumps(result, indent=2))
print("MC_DELTAE_DONE")
