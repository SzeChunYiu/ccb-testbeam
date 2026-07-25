#!/usr/bin/env python3
"""Aggregate the sys_birks_smoke2 single-stave systematic campaign.

Three Birks kB settings (0.100, 0.126, 0.160 mm/MeV) on 100 MeV protons.
Produces:
  * fig_birks_raw_vs_birks_edep.png   edep_scint_MeV (with Birks) vs edep_scint_raw_MeV
  * fig_birks_suppression.png         suppression ratio vs dE/dx (raw -> with-Birks)
  * fig_birks_pe_yield.png            detected PE per event vs kB
Reads from /projects/hep/fs10/shared/nnbar/billy/ccb-runs/an3/sys_birks_smoke2.
"""
from __future__ import annotations
import os, sys, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import iter_birks, load_events, ccb_style
plt = ccb_style()

OUT = sys.argv[1] if len(sys.argv) > 1 else "reports/studies/clusterD/figures"
os.makedirs(OUT, exist_ok=True)

runs = iter_birks()
print(f"[birks] {len(runs)} runs")
# parse kB from meta (preferred) or filename
for r in runs:
    r.kB = float(r.meta.get("birks_kB_mm_per_MeV", 0.0))
    if r.kB == 0.0:
        # fall back to filename parse
        import re
        m = re.search(r"kB(\d+)_", os.path.basename(r.path))
        if m: r.kB = int(m.group(1)) / 1000.0
    print(f"  seed={r.seed}  kB={r.kB:.3f}  n_events_meta={r.meta.get('n_events')}")

# === Raw vs Birks-suppressed EDep scatter + suppression curve ===
fig, axs = plt.subplots(1, 2, figsize=(12, 5))
colors = {0.100: "C2", 0.126: "C0", 0.160: "C3"}
for r in sorted(runs, key=lambda x: x.kB):
    ev = load_events(r.path)
    raw = ev["edep_scint_raw_MeV"]
    birks = ev["edep_scint_MeV"]
    trklen = ev["track_len_scint_mm"]
    c = colors.get(r.kB, "gray")
    # scatter raw vs Birks (subsample 200 pts for plot)
    n = min(200, raw.size)
    idx = np.linspace(0, raw.size - 1, n).astype(int)
    axs[0].scatter(raw[idx], birks[idx], s=10, alpha=0.5, color=c,
                   label=f"kB={r.kB:.3f} mm/MeV")
    # suppression ratio: birks/raw vs dE/dx (raw per length)
    nonzero = raw > 0
    if nonzero.any():
        dedx = raw[nonzero] / np.clip(trklen[nonzero], 1e-3, None)  # MeV/mm
        ratio = birks[nonzero] / raw[nonzero]
        order = np.argsort(dedx)
        dedx_s, ratio_s = dedx[order], ratio[order]
        # binned median
        bins = np.linspace(dedx_s.min(), dedx_s.max(), 12)
        centers, medians = [], []
        for i in range(len(bins) - 1):
            m = (dedx_s >= bins[i]) & (dedx_s < bins[i+1])
            if m.sum() >= 3:
                centers.append(np.median(dedx_s[m]))
                medians.append(np.median(ratio_s[m]))
        axs[1].plot(centers, medians, "o-", color=c, label=f"kB={r.kB:.3f}")

axs[0].plot([0, max(raw.max() for r in runs if True) if runs else 1],
            [0, max(raw.max() for r in runs if True) if runs else 1],
            "k--", lw=1, label="y=x (no suppression)")
axs[0].set_xlabel("Raw scintillator EDep (MeV, no Birks)")
axs[0].set_ylabel("Birks-suppressed EDep (MeV)")
axs[0].set_title("(a) Birks suppression at 100 MeV proton")
axs[0].legend(loc="lower right", fontsize=8)
axs[1].set_xlabel("dE/dx raw (MeV/mm)")
axs[1].set_ylabel("Suppression ratio (Birks / raw)")
axs[1].set_title("(b) Quenching vs ionisation density")
axs[1].axhline(1.0, color="k", lw=0.8, ls=":")
axs[1].legend(loc="best", fontsize=8)
fig.suptitle("VIS-MC: Birks systematic grid (sys_birks_smoke2)", fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_birks_raw_vs_birks_edep.png"))
print("[birks] wrote fig_birks_raw_vs_birks_edep.png")
plt.close(fig)

# === PE yield per kB ===
fig, ax = plt.subplots(figsize=(8, 5.5))
kbs = sorted({r.kB for r in runs})
pe_means, pe_errs = [], []
for kb in kbs:
    matches = [r for r in runs if abs(r.kB - kb) < 1e-6]
    all_pe = np.concatenate([load_events(r.path)["detected_readout"] for r in matches])
    pe_means.append(all_pe.mean())
    pe_errs.append(all_pe.std(ddof=1) / np.sqrt(all_pe.size) if all_pe.size > 1 else 0)
ax.errorbar(kbs, pe_means, yerr=pe_errs, fmt="o-", color="C0", capsize=3)
for kb, m in zip(kbs, pe_means):
    ax.annotate(f"{m:.1f}", (kb, m), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
ax.set_xlabel("Birks coefficient kB (mm/MeV)")
ax.set_ylabel("Detected photo-electrons at readout")
ax.set_title("i885/sys_birks: detected PE yield vs kB (100 MeV protons)")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_birks_pe_yield.png"))
print("[birks] wrote fig_birks_pe_yield.png")
plt.close(fig)

summary = {
    "n_runs": len(runs),
    "kB_values": kbs,
    "pe_per_event_by_kB": {f"{kb:.3f}": float(m) for kb, m in zip(kbs, pe_means)},
}
with open(os.path.join(OUT, "fig_birks_summary.json"), "w") as fh:
    json.dump(summary, fh, indent=2)
print("[birks] wrote fig_birks_summary.json")
