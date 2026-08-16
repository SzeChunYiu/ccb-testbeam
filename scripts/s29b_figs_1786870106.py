#!/usr/bin/env python3
"""s29b figures — delay spectra, stratum calibration, manifold, load split,
secondary-rate bands (#1400).

All values read from result.json (no hardcoded numbers); layout constants only.
Writes PNGs next to result.json and figures.json with per-figure sha256s.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path("/home/billy/ccb-testbeam")
TICKET = "1786870106.1400000.68374937"
OUT = ROOT / f"reports/{TICKET}__s29b_b2_injected_correlated_noise_mc"
NS = 10.0

r = json.loads((OUT / "result.json").read_text())
m = r["measured"]["per_stave"]
hist = r["metrics"]
K = np.arange(1, 17)


def dens(h):
    h = np.asarray(h, dtype=float)
    return h / max(h.sum(), 1.0)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


figs = {}

# --- Fig 1: B2 delay spectra — measured vs V0 / V5 / NC2 ----------------------
fig, ax = plt.subplots(figsize=(7.0, 4.2))
ax.bar(K, dens(m["B2"]["delay_hist"]), width=0.8, color="0.82",
       label="measured B2 (S29a selection)")
for v, c, ls in (("V0", "#888888", "--"), ("V5", "#d62728", "-"),
                 ("NC2", "#1f77b4", "-.")):
    ax.step(K, dens(hist[v]["delay_hist"]["B2"]), where="mid", color=c, ls=ls,
            label=f"{v} (KS vs meas {hist[v]['ks_b2_vs_measured']:.3f})")
island = sum(dens(m["B2"]["delay_hist"])[8:11])
ax.axvspan(9, 11, color="gold", alpha=0.18,
           label=f"measured d=9–11 island ({island*100:.1f}%)")
ax.set_xlabel("secondary-peak delay (samples)")
ax.set_ylabel("fraction of unsaturated secondaries")
ax.set_title("B2 secondary-peak delay — predicted vs measured (delay never fitted)")
ax.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(OUT / "fig1_delay_spectra.png", dpi=180)
plt.close(fig)
figs["fig1_delay_spectra"] = sha256(OUT / "fig1_delay_spectra.png")

# --- Fig 2: calibration — (a) mean deficit, (b) piecewise p(A) ----------------
v5 = r["calibration"]["v5"]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.8))
kk = np.arange(len(v5["v0_deficit"]))
win = v5["island_window_k"]
a1.bar(kk, np.array(v5["v0_deficit"]) * 100, color="#d62728", alpha=0.65,
       label="B2 − V0 mean deficit (×100)")
a1.axvspan(win[0] - 0.5, win[1] + 0.5, color="gold", alpha=0.18,
           label=f"island window k={win[0]}–{win[1]}")
a1.axhline(0, color="k", lw=0.6)
a1.set_xlabel("sample k")
a1.set_ylabel("deficit ×100")
a1.set_title(f"mean-template deficit; closure {v5['mean_closure_tail']:.2f}")
a1.legend(fontsize=8, frameon=False)
pb = v5["p_bins"]
cx = [b["center_adc"] for b in pb]
pv = [b["p"] for b in pb]
a2.step(cx, pv, where="mid", color="#1f77b4", alpha=0.5)
a2.plot(cx, pv, "o", color="#1f77b4",
        label="per-amp-bin p (used: piecewise)")
for b in pb:
    a2.annotate(f"{b['p']:.2f}", (b["center_adc"], b["p"]),
                textcoords="offset points", xytext=(0, 5),
                ha="center", fontsize=7)
ex = v5.get("p_bins_excluded", [])
if ex:
    a2.plot([0.5 * (b["lo"] + b["hi"]) for b in ex], [0.0] * len(ex), "x",
            color="gray", label=f"excluded bins ({len(ex)}): elevation below floor")
a2.axhline(v5["p_hat"], color="gray", ls=":",
           label=f"p̂={v5['p_hat']:.3f} (stratum, NC2 constant)")
a2.set_xlabel("pulse amplitude (ADC)")
a2.set_ylabel("smooth-stratum probability p(A)")
a2.set_ylim(-0.05, 1.1)
a2.set_title(f"piecewise p(A) — stratum q*={v5['smooth_quantile']}, "
             f"kpk∈{v5['stratum_kpk_window'][0]}–{v5['stratum_kpk_window'][1]} "
             f"({v5['stratum_n_shapes']} shapes)")
a2.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(OUT / "fig2_calibration.png", dpi=180)
plt.close(fig)
figs["fig2_calibration"] = sha256(OUT / "fig2_calibration.png")

# --- Fig 3: manifold test (family discriminator) ------------------------------
mf = r["calibration"]["manifold"]
fig, (b1, b2) = plt.subplots(1, 2, figsize=(9.0, 3.6))
names = ["island (d=9–11)\nvs downstream lib", "non-island (d=2–6)\nvs downstream lib",
         "downstream\nself-distances"]
vals = [mf["island_nn"]["med"], mf["nonisland_nn"]["med"], mf["dn_self_nn"]["med"]]
p90s = [mf["island_nn"]["p90"], mf["nonisland_nn"]["p90"], mf["dn_self_nn"]["p90"]]
xs = np.arange(3)
b1.bar(xs, vals, 0.55, color=["#d62728", "#7f7f7f", "#1f77b4"], alpha=0.8)
b1.errorbar(xs, vals, yerr=[np.array(p90s) - np.array(vals)],
            fmt="none", ecolor="k", capsize=4, lw=1)
scale = max(vals[1], vals[2])
b1.axhline(2 * scale, color="green", ls="--", lw=1.2,
           label=f"OUTSIDE threshold (2× scale = {2*scale:.3f})")
b1.set_xticks(xs)
b1.set_xticklabels(names, fontsize=8)
b1.set_ylabel("amplitude-windowed NN L2 (median, bar; p90, whisker)")
b1.set_title(f"island NN ratio {mf['island_over_scale_ratio']:.2f} → "
             f"{'OUTSIDE' if mf['island_outside_manifold'] else 'WITHIN'} manifold")
b1.legend(fontsize=8, frameon=False)
rl = mf["dn_lib_R"]
qs = [("min", rl["min"]), ("q01", rl["q01"]), ("q10", rl["q10"]), ("med", rl["med"])]
for lab, v in qs:
    b2.axvline(v, color="#1f77b4", ls=":", lw=1)
    b2.text(v, 0.62, lab, rotation=90, fontsize=7, color="#1f77b4",
            va="top", ha="right")
b2.axvline(mf["island_R"]["med"], color="#d62728", lw=1.6,
           label=f"island R med {mf['island_R']['med']:.4f}")
b2.axvline(mf["island_R"]["q10"], color="#d62728", ls="--", lw=1.2,
           label=f"island R q10 {mf['island_R']['q10']:.4f}")
b2.set_xlim(0, max(rl["med"], mf["island_R"]["med"]) * 1.6)
b2.set_ylim(0, 1)
b2.set_yticks([])
b2.set_xlabel("tail roughness R (second-difference energy / norm²)")
b2.set_title(f"roughness support — frac(island R < lib min) = "
             f"{mf['island_frac_R_below_dn_min']:.3f}")
b2.legend(fontsize=8, frameon=False)
fig.suptitle("Stage 1.5 manifold test — can any reweighting of downstream shapes "
             "produce the island?", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "fig3_manifold.png", dpi=180)
plt.close(fig)
figs["fig3_manifold"] = sha256(OUT / "fig3_manifold.png")

# --- Fig 4: load split — per-stave measured + variants ------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.0))
labels, vals, cols = [], [], []
for s in ("B4", "B6", "B8", "B2"):
    labels.append(f"{s} measured")
    vals.append(m[s]["delay_sat_split_ns"])
    cols.append("#7f7f7f" if s != "B2" else "0.6")
labels.append("pooled downstream\nmeasured")
vals.append(r["measured"]["pooled_downstream_sat_split_ns"])
cols.append("#2ca02c")
for v in ("V0", "V5", "NC2"):
    if v in hist:
        labels.append(f"{v} (B2 syn)")
        vals.append(hist[v]["sat_split_ns"])
        cols.append({"V0": "#888888", "V5": "#d62728", "NC2": "#1f77b4"}[v])
xs = np.arange(len(labels))
ax.bar(xs, vals, 0.6, color=cols)
meas_split = m["B2"]["delay_sat_split_ns"]
ax.axhline(meas_split, color="k", lw=1.2, label=f"measured B2 {meas_split:+.1f} ns")
ax.axhspan(meas_split - 2.0, meas_split + 2.0, color="green", alpha=0.12,
           label="±2 ns gate")
g1b = r["g1b"]
ax.annotate(f"G1b: V0 {g1b['v0_split_ns']:+.1f} vs pooled downstream "
            f"{g1b['pooled_downstream_split_ns']:+.1f} (|Δ| {g1b['abs_diff_ns']} ns)",
            (0.02, 0.04), xycoords="axes fraction", fontsize=8,
            color="green" if g1b["pass"] else "#d62728")
ax.set_xticks(xs)
ax.set_xticklabels(labels, fontsize=7.5, rotation=20, ha="right")
ax.set_ylabel("high-load − low-load delay (ns)")
ax.set_title("Load split: universal downstream shift vs B2-specific reduction")
ax.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(OUT / "fig4_load_split.png", dpi=180)
plt.close(fig)
figs["fig4_load_split"] = sha256(OUT / "fig4_load_split.png")

# --- Fig 5: secondary rate by load band — population separation ---------------
fig, (c1, c2) = plt.subplots(1, 2, figsize=(9.0, 3.6), sharey=True)
staves = ("B2", "B4", "B6", "B8")
xs = np.arange(4)
w = 0.35
c1.bar(xs - w / 2, [m[s]["secondary_rate_by_band"]["midhigh"] for s in staves],
       w, color="#1f77b4", label="mid-high [4.5k, 7k) ADC")
c1.bar(xs + w / 2, [m[s]["secondary_rate_by_band"]["sat"] for s in staves],
       w, color="#d62728", label="sat ≥7k ADC")
c1.set_xticks(xs)
c1.set_xticklabels(staves)
c1.set_ylabel("fraction of interior-peak pulses with ≥2 eligible maxima")
c1.set_title("measured secondary RATE by load band")
c1.legend(fontsize=8, frameon=False)
srs = [hist[v]["secondary_rate_by_band"]["B2"] for v in ("V0", "V5", "NC2")]
xs2 = np.arange(3)
c2.bar(xs2 - w / 2, [d["midhigh"] for d in srs], w, color="#1f77b4")
c2.bar(xs2 + w / 2, [d["sat"] for d in srs], w, color="#d62728")
c2.set_xticks(xs2)
c2.set_xticklabels(["V0", "V5", "NC2"])
c2.set_title("synthetic B2 secondary RATE by load band")
mb = m["B2"]["secondary_rate_by_band"]
c2.axhline(mb["midhigh"], color="#1f77b4", ls=":", lw=1,
           label=f"measured B2 mid-high {mb['midhigh']:.3f}")
c2.axhline(mb["sat"], color="#d62728", ls=":", lw=1,
           label=f"measured B2 sat {mb['sat']:.3f}")
c2.legend(fontsize=8, frameon=False)
fig.suptitle("Secondary eligibility vs load — template excess grows into "
             "saturation, delay island does not", fontsize=10)
fig.tight_layout()
fig.savefig(OUT / "fig5_secondary_rate.png", dpi=180)
plt.close(fig)
figs["fig5_secondary_rate"] = sha256(OUT / "fig5_secondary_rate.png")

# --- Fig 6: island kpk mix (internal d-distribution) --------------------------
fig, ax = plt.subplots(figsize=(7.0, 3.8))
kk = np.arange(5, 15)
series = [("BOOT (measured-faithful)", "#7f7f7f", r["g1"]["boot_island_kpk_hist"]["B2"])]
for v, c in (("V0", "#888888"), ("V5", "#d62728"), ("NC2", "#1f77b4")):
    if v in hist:
        series.append((v, c, hist[v]["kpk_island_hist"]["B2"]))
for lab, c, hh in series:
    ax.step(kk, dens(hh), where="mid", color=c, label=lab)
ax.set_xlabel("island pulse peak index kpk")
ax.set_ylabel("fraction of island pulses")
ax.set_title("Island peak-position mix — decides internal d via delay = second − kpk")
ax.legend(fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(OUT / "fig6_island_kpk.png", dpi=180)
plt.close(fig)
figs["fig6_island_kpk"] = sha256(OUT / "fig6_island_kpk.png")

(OUT / "figures.json").write_text(json.dumps(figs, indent=1))
print("wrote", ", ".join(figs), "->", OUT)
