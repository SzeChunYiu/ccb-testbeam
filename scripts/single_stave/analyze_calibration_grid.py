#!/usr/bin/env python3
"""Single-stave calibration analysis (#796): deposited energy -> detected PE."""
import glob, json, os
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

GRID = "/projects/hep/fs10/shared/nnbar/billy/ccb_calib_grid"
OUT = "/projects/hep/fs10/shared/nnbar/billy/ccb_calib_report"
os.makedirs(OUT, exist_ok=True)

files = sorted(glob.glob(GRID + "/*.root"))
part, ke, ed, arr, pe = [], [], [], [], []
for f in files:
    t = uproot.open(f)["events"]
    d = t.arrays(["particle", "ke_MeV", "edep_scint_MeV",
                  "arrival_readout", "detected_readout"], library="np")
    p = d["particle"]
    p = [x.decode() if isinstance(x, bytes) else str(x) for x in p]
    part += p
    ke += list(d["ke_MeV"]); ed += list(d["edep_scint_MeV"])
    arr += list(d["arrival_readout"]); pe += list(d["detected_readout"])
part = np.array(part); ke = np.array(ke, float)
ed = np.array(ed, float); arr = np.array(arr, float); pe = np.array(pe, float)
n = len(ed)

# Light yield: PE = m*edep + b (all events, all species pooled)
m, b = np.polyfit(ed, pe, 1)
resid = pe - (m * ed + b)
r2 = 1 - np.var(resid) / np.var(pe)

# Per (species, KE) point summary
points = []
for sp in sorted(set(part)):
    for e in sorted(set(ke[part == sp])):
        sel = (part == sp) & (ke == e)
        edp, pep, arp = ed[sel], pe[sel], arr[sel]
        points.append(dict(
            species=sp, ke_MeV=float(e), n=int(sel.sum()),
            edep_mean_MeV=float(edp.mean()), edep_std_MeV=float(edp.std()),
            arrival_mean=float(arp.mean()),
            pe_mean=float(pep.mean()), pe_std=float(pep.std()),
            pe_over_edep=float(pep.mean() / edp.mean()) if edp.mean() else 0.0,
            resolution=float(pep.std() / pep.mean()) if pep.mean() else 0.0,
        ))

result = dict(
    n_events=n, n_files=len(files),
    light_yield_PE_per_MeV=float(m), offset_PE=float(b), fit_r2=float(r2),
    pooled_pe_per_edep=float((pe / ed)[ed > 0].mean()),
    points=points,
    definition="detected_readout PE vs edep_scint (Birks-quenched) MeV, single-stave optical mode",
)
with open(OUT + "/result.json", "w") as fh:
    json.dump(result, fh, indent=2)

# source-data table
with open(OUT + "/calibration_source.csv", "w") as fh:
    fh.write("species,ke_MeV,edep_scint_MeV,arrival_readout,detected_pe\n")
    for i in range(n):
        fh.write(f"{part[i]},{ke[i]:.1f},{ed[i]:.4f},{arr[i]:.0f},{pe[i]:.0f}\n")

# Figure 1: deposited energy vs detected PE (the calibration)
plt.figure(figsize=(6, 4.5))
for sp, mk in [("proton", "o"), ("deuteron", "s")]:
    s = part == sp
    if s.any():
        plt.scatter(ed[s], pe[s], s=6, alpha=0.35, marker=mk, label=sp)
xs = np.linspace(ed.min(), ed.max(), 50)
plt.plot(xs, m * xs + b, "k-", lw=1.5,
         label=f"fit: {m:.1f} PE/MeV (r^2={r2:.3f})")
plt.xlabel("deposited energy (Birks-quenched) [MeV]")
plt.ylabel("detected photoelectrons")
plt.title("Single-stave calibration: Edep -> PE")
plt.legend(fontsize=8); plt.tight_layout()
plt.savefig(OUT + "/G4CAL-01_edep_vs_pe.png", dpi=130)
plt.savefig(OUT + "/G4CAL-01_edep_vs_pe.pdf")

# Figure 2: mean PE vs KE per species (with resolution error bars)
plt.figure(figsize=(6, 4.5))
for sp, mk in [("proton", "o"), ("deuteron", "s")]:
    ps = [p for p in points if p["species"] == sp]
    if ps:
        x = [p["ke_MeV"] for p in ps]; y = [p["pe_mean"] for p in ps]
        yerr = [p["pe_std"] for p in ps]
        plt.errorbar(x, y, yerr=yerr, marker=mk, capsize=3, label=sp)
plt.xlabel("kinetic energy [MeV]"); plt.ylabel("mean detected PE")
plt.title("Mean PE vs beam energy"); plt.legend(fontsize=8); plt.tight_layout()
plt.savefig(OUT + "/G4CAL-02_pe_vs_ke.png", dpi=130)

print(json.dumps({k: result[k] for k in
      ("n_events", "light_yield_PE_per_MeV", "fit_r2",
       "pooled_pe_per_edep")}, indent=2))
print("POINTS:")
for p in points:
    print(f"  {p['species']:8s} KE={p['ke_MeV']:5.0f}  edep={p['edep_mean_MeV']:6.2f}"
          f"  PE={p['pe_mean']:6.1f}+-{p['pe_std']:5.1f}"
          f"  yield={p['pe_over_edep']:5.2f} PE/MeV  res={p['resolution']:.3f}")
print("CALIB_ANALYSIS_DONE")
