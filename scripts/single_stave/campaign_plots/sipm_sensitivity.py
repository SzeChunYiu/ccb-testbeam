#!/usr/bin/env python3
"""Aggregate the sipm-p2-001 single-stave SiPM sensitivity campaign.

Parses the per-knob SUMMARY.md tables (which already contain adc_readout,
pe_sat_readout, frac_clipped, elasticity) and produces:
  * fig_sipm_cross_knob_elasticity.png   d(ln ADC)/d(ln knob) for all 12 knobs
  * fig_sipm_adc_vs_knob.png             per-knob ADC + PE response (small multiples)
  * fig_sipm_clipped_fractions.png       fraction of clipped (saturated) events per knob
The per-knob PNGs are referenced from the campaign dir; this script does not
re-execute the campaign.
"""
from __future__ import annotations
import os, sys, json, re, glob
from pathlib import Path
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import SIPM, ccb_style
plt = ccb_style()

OUT = sys.argv[1] if len(sys.argv) > 1 else "reports/studies/clusterD/figures"
os.makedirs(OUT, exist_ok=True)


def parse_knob_summary(md_path: str) -> dict:
    """Parse per-knob SUMMARY.md into rows + elasticity."""
    txt = open(md_path).read()
    # unit
    unit_m = re.search(r"\*\*unit\*\*:\s*([^\n]+)", txt)
    unit = unit_m.group(1).strip() if unit_m else ""
    # table rows
    rows = []
    for line in txt.splitlines():
        m = re.match(r"\|\s*([-\d.eE]+)\s*\|\s*(\d+)\s*\|\s*([-\d.eE]+)\s*\|\s*([-\d.eE]+)\s*\|\s*([-\d.eE]+)\s*\|\s*([-\d.eE]+)\s*\|\s*([-\d.eE]+)\s*\|", line)
        if m:
            rows.append({
                "value": float(m.group(1)),
                "n_events": int(m.group(2)),
                "adc_readout": float(m.group(3)),
                "pe_sat_readout": float(m.group(4)),
                "detected_readout": float(m.group(5)),
                "edep_scint_MeV": float(m.group(6)),
                "frac_clipped": float(m.group(7)),
            })
    # elasticity for adc_readout
    el_m = re.search(r"adc_readout.*?elasticity[^=]*=\s*([-\d.]+)", txt)
    elasticity = float(el_m.group(1)) if el_m else float("nan")
    return {"unit": unit, "rows": rows, "elasticity_adc": elasticity}


subs = sorted([d for d in os.listdir(SIPM) if os.path.isdir(os.path.join(SIPM, d))])
knobs = []
for sub in subs:
    md = os.path.join(SIPM, sub, "SUMMARY.md")
    if not os.path.exists(md):
        continue
    info = parse_knob_summary(md)
    if not info["rows"]:
        continue
    info["knob"] = sub
    knobs.append(info)
print(f"[sipm] parsed {len(knobs)} knobs")

# === Cross-knob elasticity bar chart ===
fig, ax = plt.subplots(figsize=(9, 5.5))
valid = [k for k in knobs if not np.isnan(k["elasticity_adc"])]
valid.sort(key=lambda k: k["elasticity_adc"])
names = [k["knob"] for k in valid]
els = [k["elasticity_adc"] for k in valid]
colors = ["C3" if abs(e) > 1 else ("C1" if abs(e) > 0.3 else "C0") for e in els]
ax.barh(names, els, color=colors)
for i, (n, e) in enumerate(zip(names, els)):
    ax.text(e + (0.05 if e >= 0 else -0.05), i, f"{e:+.2f}",
            va="center", ha="left" if e >= 0 else "right", fontsize=9)
ax.axvline(0, color="k", lw=0.8)
ax.set_xlabel(r"Elasticity  $d(\ln\,\mathrm{ADC}) / d(\ln\,\mathrm{knob})$")
ax.set_title("VIS-MC: SiPM sensitivity — cross-knob elasticity (sipm-p2-001)")
fig.text(0.5, -0.01,
         "Color code: |η|>1 red (highly non-linear), 0.3<|η|≤1 orange, |η|≤0.3 blue (linear). "
         "Source: per-knob SUMMARY.md tables in ccb-runs/sipm-p2-001/.",
         ha="center", va="top", fontsize=8.5, style="italic", color="#444",
         bbox=dict(boxstyle="round,pad=0.4", fc="#f4f4f4", ec="#bbb"))
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_sipm_cross_knob_elasticity.png"))
plt.close(fig)
print("[sipm] wrote fig_sipm_cross_knob_elasticity.png")

# === Per-knob small multiples (ADC + PE) ===
n = len(knobs)
ncol = 4; nrow = int(np.ceil(n / ncol))
fig, axs = plt.subplots(nrow, ncol, figsize=(13, 2.8 * nrow), squeeze=False)
for i, k in enumerate(knobs):
    r, c = divmod(i, ncol)
    ax = axs[r][c]
    rows = sorted(k["rows"], key=lambda x: x["value"])
    xs = [r["value"] for r in rows]
    adc = [r["adc_readout"] for r in rows]
    pe = [r["pe_sat_readout"] for r in rows]
    clip = [r["frac_clipped"] for r in rows]
    # normalise each to max for shape comparison
    if max(adc) > 0: adc_n = np.array(adc) / max(adc)
    else: adc_n = np.array(adc)
    if max(pe) > 0: pe_n = np.array(pe) / max(pe)
    else: pe_n = np.array(pe)
    x_idx = np.arange(len(xs))
    ax.plot(x_idx, adc_n, "o-", color="C0", label="ADC (norm)")
    ax.plot(x_idx, pe_n, "s--", color="C2", label="PE (norm)")
    ax.set_title(f"{k['knob']}  η={k['elasticity_adc']:.2f}", fontsize=10)
    ax.tick_params(labelsize=8)
    ax.set_xticks(x_idx)
    ax.set_xticklabels([f"{x:.2g}" for x in xs], rotation=45, fontsize=7)
    if i == 0:
        ax.legend(loc="best", fontsize=8)
for j in range(len(knobs), nrow * ncol):
    r, c = divmod(j, ncol)
    axs[r][c].axis("off")
fig.suptitle("SiPM sensitivity campaign — ADC vs PE response per knob (normalised; x-axis = knob value)",
             fontsize=12)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_sipm_adc_vs_knob.png"))
plt.close(fig)
print("[sipm] wrote fig_sipm_adc_vs_knob.png")

# === Clipped fraction per knob ===
fig, ax = plt.subplots(figsize=(9, 5))
names = [k["knob"] for k in knobs]
clips = [float(np.mean([r["frac_clipped"] for r in k["rows"]])) for k in knobs]
order = np.argsort(clips)
ax.barh([names[i] for i in order], [clips[i] for i in order], color="C4")
ax.set_xlabel("Mean clipped/saturated fraction (per knob)")
ax.set_title("SiPM campaign — saturation onset per knob")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_sipm_clipped_fractions.png"))
plt.close(fig)
print("[sipm] wrote fig_sipm_clipped_fractions.png")

summary = {
    "n_knobs": len(knobs),
    "source": "parsed from ccb-runs/sipm-p2-001/<knob>/SUMMARY.md",
    "knobs": [{"knob": k["knob"], "unit": k["unit"], "elasticity_adc": k["elasticity_adc"],
               "adc_min": min(r["adc_readout"] for r in k["rows"]),
               "adc_max": max(r["adc_readout"] for r in k["rows"]),
               "frac_clipped_mean": float(np.mean([r["frac_clipped"] for r in k["rows"]]))}
              for k in knobs],
}
with open(os.path.join(OUT, "fig_sipm_summary.json"), "w") as fh:
    json.dump(summary, fh, indent=2)
print("[sipm] wrote fig_sipm_summary.json")
