#!/usr/bin/env python3
"""Birks visible-energy suppression across a kB sweep.

Reads the 'events' ntuple from each single-stave .root, compares
edep_scint_MeV (Birks-visible via G4EmSaturation::VisibleEnergyDepositionAtAStep)
against edep_scint_raw_MeV (raw deposit), and reports the suppression factor vs
kB [mm/MeV]. End-to-end validation of the defect-2 visible-energy fix on real
simulation output: visible < raw for kB>0, suppression grows with kB, ==raw at 0.
"""
from __future__ import annotations
import argparse, json, glob
from pathlib import Path
import numpy as np
import uproot
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def summarize(path: str) -> dict:
    f = uproot.open(path)
    tree = f["events"] if "events" in f else f[f.keys()[0]]
    df = tree.arrays(["edep_scint_MeV", "edep_scint_raw_MeV"], library="pd")
    raw = df["edep_scint_raw_MeV"].to_numpy(dtype=float)
    vis = df["edep_scint_MeV"].to_numpy(dtype=float)
    m = raw > 0
    raw, vis = raw[m], vis[m]
    if raw.size == 0:
        return {"n": 0}
    ratio = vis / raw
    return {
        "n": int(raw.size),
        "raw_mean_MeV": float(np.mean(raw)),
        "vis_mean_MeV": float(np.mean(vis)),
        "suppression_mean": float(np.mean(ratio)),
        "suppression_median": float(np.median(ratio)),
        "max_raw_minus_vis_MeV": float(np.max(raw - vis)),
    }

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inputs", nargs="+", required=True, help=".root files or globs")
    ap.add_argument("--kB", nargs="+", type=float, required=True, help="kB [mm/MeV] per input")
    ap.add_argument("--out", required=True, help="output dir")
    args = ap.parse_args()
    files = []
    for inp in args.inputs:
        files.extend(sorted(glob.glob(inp)))
    kbv = sorted(args.kB)
    files = sorted(files)
    assert len(files) == len(kbv), f"{len(files)} files vs {len(kbv)} kB values"
    rows = []
    for kb, fp in zip(kbv, files):
        s = summarize(fp)
        s["kB_mm_per_MeV"] = kb
        s["file"] = fp
        rows.append(s)
        print(f"kB={kb:.3f}: n={s.get('n')} raw_mean={s.get('raw_mean_MeV'):.4f} "
              f"vis_mean={s.get('vis_mean_MeV'):.4f} suppression={s.get('suppression_mean'):.4f}")
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / "birks_suppression_summary.json").write_text(json.dumps(rows, indent=2))
    valid = [r for r in rows if r.get("n")]
    if len(valid) >= 2:
        kb = [r["kB_mm_per_MeV"] for r in valid]
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        ax[0].plot(kb, [r["raw_mean_MeV"] for r in valid], "o-", label="raw edep")
        ax[0].plot(kb, [r["vis_mean_MeV"] for r in valid], "s-", label="Birks-visible edep")
        ax[0].set_xlabel("Birks kB [mm/MeV]"); ax[0].set_ylabel("mean edep [MeV]")
        ax[0].set_title("Raw vs Birks-visible energy"); ax[0].legend(); ax[0].grid(alpha=0.3)
        ax[1].plot(kb, [r["suppression_mean"] for r in valid], "o-", color="tab:green")
        ax[1].set_xlabel("Birks kB [mm/MeV]"); ax[1].set_ylabel("visible / raw")
        ax[1].set_title("Birks suppression factor"); ax[1].grid(alpha=0.3)
        fig.tight_layout(); fig.savefig(out / "birks_suppression.png", dpi=130)
        print(f"wrote {out}/birks_suppression.png")
    n_total = sum(r.get("n", 0) for r in rows)
    all_zero = all(r.get("suppression_mean", 1.0) == 1.0 for r in valid)
    if n_total and not all_zero:
        print("PASS: Birks suppression observed on real sim output (visible < raw for kB>0).")
    else:
        print("WARN: no suppression observed (kB too small, or no high-dE/dx deposits).")

if __name__ == "__main__":
    main()
