#!/usr/bin/env python3
"""Aggregate the i885_v1 single-stave calibration campaign into diagnostic plots."""
from __future__ import annotations
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import iter_i885, load_events, load_photons, ccb_style
plt = ccb_style()

OUT = sys.argv[1] if len(sys.argv) > 1 else "reports/studies/clusterD/figures"
os.makedirs(OUT, exist_ok=True)

runs = iter_i885()
print(f"[i885] {len(runs)} runs discovered")
particles = sorted({r.particle for r in runs})

agg: dict[tuple[str, float], dict[str, list[float]]] = {}
for r in runs:
    ev = load_events(r.path)
    n = ev["event"].size
    key = (r.particle, r.ke_MeV)
    a = agg.setdefault(key, {"n_scint": [], "n_wls": [], "n_cer": [],
                              "det_ro": [], "det_f1far": [], "det_f2near": [], "det_f2far": [],
                              "pe_ro": [], "pe_f1far": [], "edep": [], "trklen": []})
    a["n_scint"].extend(ev["n_scint_generated"])
    a["n_wls"].extend(ev["n_wls_generated"])
    a["n_cer"].extend(ev["n_cerenkov_generated"])
    a["det_ro"].extend(ev["detected_readout"])
    a["det_f1far"].extend(ev["detected_f1far"])
    a["det_f2near"].extend(ev["detected_f2near"])
    a["det_f2far"].extend(ev["detected_f2far"])
    a["pe_ro"].extend(ev["pe_sat_readout"])
    a["pe_f1far"].extend(ev["pe_sat_f1far"])
    a["edep"].extend(ev["edep_scint_MeV"])
    a["trklen"].extend(ev["track_len_scint_mm"])

def ms(arr):
    a = np.asarray(arr, dtype=float)
    if a.size == 0: return float("nan"), float("nan")
    m = float(a.mean())
    s = float(a.std(ddof=1) / np.sqrt(a.size)) if a.size > 1 else 0.0
    return m, s

particle_colors = {"proton": "C0", "deuteron": "C1"}

# === KE-vs-light 4-panel ===
fig, ax = plt.subplots(2, 2, figsize=(11, 8))
plotted_legend = set()
for (p, ke), a in sorted(agg.items()):
    c = particle_colors.get(p, "gray")
    n_scint_m, n_scint_e = ms(a["n_scint"])
    n_wls_m, n_wls_e = ms(a["n_wls"])
    det_ro_m, det_ro_e = ms(a["det_ro"])
    edep_m, edep_e = ms(a["edep"])
    lbl = f"{p} (N={len(a['n_scint'])})" if p not in plotted_legend else None
    if p not in plotted_legend: plotted_legend.add(p)
    ax[0,0].errorbar(ke, n_scint_m, yerr=n_scint_e, fmt="o", color=c, label=lbl)
    ax[0,1].errorbar(ke, n_wls_m, yerr=n_wls_e, fmt="o", color=c)
    ax[1,0].errorbar(ke, det_ro_m, yerr=det_ro_e, fmt="o", color=c)
    ax[1,1].errorbar(ke, edep_m, yerr=edep_e, fmt="o", color=c)
ax[0,0].set_xlabel("Kinetic energy (MeV)"); ax[0,0].set_ylabel("Scint photons generated")
ax[0,0].set_title("(a) Scintillator photon yield vs KE"); ax[0,0].legend(loc="best")
ax[0,1].set_xlabel("Kinetic energy (MeV)"); ax[0,1].set_ylabel("WLS photons generated")
ax[0,1].set_title("(b) WLS photons vs KE")
ax[1,0].set_xlabel("Kinetic energy (MeV)"); ax[1,0].set_ylabel("Detected at readout (PE)")
ax[1,0].set_title("(c) Detected photo-electrons vs KE (readout)")
ax[1,1].set_xlabel("Kinetic energy (MeV)"); ax[1,1].set_ylabel("Scintillator EDep (MeV)")
ax[1,1].set_title("(d) Scintillator energy deposition vs KE")
fig.suptitle("i885 single-stave calibration campaign — light yield vs KE", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_i885_ke_vs_light.png"))
plt.close(fig)
print("[i885] wrote fig_i885_ke_vs_light.png")

# === PE per sensor (protons only) ===
fig, ax = plt.subplots(figsize=(8, 5.5))
for (p, ke), a in sorted(agg.items()):
    if p != "proton": continue
    c = particle_colors.get(p, "gray")
    for col, lbl, mk in (("det_ro", "readout", "o"), ("det_f1far", "fibre-1 far", "s"),
                         ("det_f2near", "fibre-2 near", "^"), ("det_f2far", "fibre-2 far", "D")):
        if col in a and len(a[col]):
            m, e = ms(a[col])
            ax.errorbar(ke, m, yerr=e, fmt=mk, color=c, alpha=0.85,
                        label=f"{lbl}" if ke == min(k for (pp,k) in agg if pp==p) else None)
ax.set_xlabel("Kinetic energy (MeV)")
ax.set_ylabel("Detected photo-electrons per event")
ax.set_title("i885: PE yield per sensor location vs KE (protons)")
ax.legend(loc="best", fontsize=8, ncol=2)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_i885_ke_vs_pe_per_sensor.png"))
plt.close(fig)
print("[i885] wrote fig_i885_ke_vs_pe_per_sensor.png")

# === Linearity log-log ===
fig, ax = plt.subplots(figsize=(8, 5.5))
for p in particles:
    kes, means = [], []
    for (pp, ke), a in sorted(agg.items()):
        if pp != p: continue
        m, _ = ms(a["n_scint"])
        kes.append(ke); means.append(m)
    kes = np.array(kes); means = np.array(means)
    if len(kes) < 2: continue
    c = particle_colors.get(p, "gray")
    ax.loglog(kes, means, "o-", color=c, label=f"{p} n_scint")
    if len(kes) >= 4:
        mask = kes >= 5
        if mask.sum() >= 3:
            slope, intercept = np.polyfit(np.log(kes[mask]), np.log(means[mask]), 1)
            ax.loglog(kes, np.exp(intercept) * kes**slope, "--", color=c, alpha=0.5,
                      label=f"{p} slope={slope:.2f}")
ax.set_xlabel("KE (MeV)"); ax.set_ylabel("Scint photons / event")
ax.set_title("i885: scintillation yield linearity (log-log)")
ax.legend(loc="best", fontsize=9); fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_i885_linearity.png")); plt.close(fig)
print("[i885] wrote fig_i885_linearity.png")

# === Timing: photon arrivals (one run per particle) ===
fig, ax = plt.subplots(figsize=(8, 5.5))
sensor_labels = {0: "readout", 1: "f1far", 2: "f2near", 3: "f2far"}
seen = set()
for r in runs:
    if r.particle in seen: continue
    seen.add(r.particle)
    ph = load_photons(r.path)
    det_mask = ph["detected"] == 1
    for sid, lbl in sensor_labels.items():
        m = det_mask & (ph["sensor"] == sid)
        if m.sum() > 0:
            t = ph["time_ns"][m]
            t = t[(t >= 0) & (t < 80)]
            ax.hist(t, bins=40, range=(0, 80), histtype="step", density=True,
                    label=f"{r.particle} {lbl} (N={m.sum()})", alpha=0.85)
ax.set_xlabel("Photon arrival time (ns)"); ax.set_ylabel("Density")
ax.set_title("i885: photon arrival-time distributions (5 MeV run, by sensor)")
ax.legend(loc="upper right", fontsize=8, ncol=2); fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_i885_timing.png")); plt.close(fig)
print("[i885] wrote fig_i885_timing.png")

# === Attenuation: x-scan ===
fig, ax = plt.subplots(figsize=(8, 5.5))
have_any = False
for r in runs:
    ev = load_events(r.path)
    xs = ev["entry_x_cm"]
    if xs.size == 0 or np.allclose(xs, 0): continue
    ax.scatter(xs, ev["detected_readout"], s=8, alpha=0.4, label=r.particle)
    have_any = True
if not have_any:
    ax.text(0.5, 0.5, "i885_v1 campaign is at fixed x=0;\nno attenuation scan data in this campaign.",
            ha="center", va="center", transform=ax.transAxes, fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
else:
    ax.set_xlabel("Entry x (cm)"); ax.set_ylabel("Detected at readout (PE)")
ax.set_title("i885: attenuation scan (entry-x vs detected PE)")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig_i885_attenuation.png")); plt.close(fig)
print("[i885] wrote fig_i885_attenuation.png")

summary = {
    "n_runs": len(runs), "particles": particles,
    "kes_MeV": sorted({r.ke_MeV for r in runs}),
    "seeds": sorted({r.seed for r in runs}),
    "per_particle_ke_mean_n_scint": {
        f"{p}_{ke}": float(np.mean(agg[(p, ke)]["n_scint"]))
        for (p, ke) in sorted(agg)
    },
}
with open(os.path.join(OUT, "fig_i885_summary.json"), "w") as fh:
    json.dump(summary, fh, indent=2)
print("[i885] wrote fig_i885_summary.json")
