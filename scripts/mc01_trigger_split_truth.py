#!/usr/bin/env python3
"""
mc01_trigger_split_truth.py
===========================
MC trigger-split truth analysis for the CCB (Krakow) test beam.

Answers the supervisor's tasks on the *MC* side:
  (1) stave (B-layer) outputs for Sample I vs Sample II,
  (2) the effect of mimicking the hardware trigger in MC,
  (3) truth-level particle ID of particles ENTERING A and B per trigger config,
and tests Matthias' prediction that Sample I is deuteron-enriched in the
*first B layer* (large pulses) while Sample II is not.

Detector encoding (decoded from output_krakow_1M.root, tree `hibeam`):
  Sci_bar_LayerID1 == 1  -> B-stack (8 layers, downstream arm @ -38 deg)   [MAIN]
  Sci_bar_LayerID1 == 2  -> A-stack (4 layers, recoil arm @ +71.5 deg)
  Sci_bar_LayerID       == depth in the stack (0 = first layer)
  Sci_bar_PDG           == true particle (2212=p, 1000010020=d, 1000020040=alpha, ...)
  Sci_bar_EDep          == energy deposited [MeV]   (MC proxy for pulse amplitude)
  Sci_bar_Time          == hit time [ns]

Trigger mimicry (per the supervisor):
  ENTER B  = a CHARGED Sci_bar hit with L1==1 and LayerID==0
  ENTER A  = a CHARGED Sci_bar hit with L1==2 and LayerID==0
  Sample II (single B trigger)   : ENTER B
  Sample I  (A&B coincidence)    : ENTER A and ENTER B with |t_A - t_B| < COINC_NS

Usage:
  python3 mc01_trigger_split_truth.py --mc output_krakow_1M.root --out <dir> [--coinc-ns 15]
"""
import argparse, json, os, sys
from functools import lru_cache
import numpy as np

B_ARM, A_ARM = 1, 2          # Sci_bar_LayerID1 values
NB_LAYERS = 8                # B-stack depth
COINC_DEFAULT = 15.0         # ns

PDG_NAME = {
    2212: "p", 1000010020: "d", 1000010030: "t",
    1000020030: "He3", 1000020040: "alpha",
    2112: "n", 22: "gamma", 11: "e-", -11: "e+",
    211: "pi+", -211: "pi-", 13: "mu-", -13: "mu+",
}

@lru_cache(maxsize=None)
def pdg_charge(pdg):
    """Electric charge (units of e) for a PDG code; handles nuclei (10-digit 100ZZZAAAI)."""
    pdg = int(pdg)
    apdg = abs(pdg)
    if apdg > 1_000_000_000:                 # nucleus 10LZZZAAAI
        Z = (apdg // 10_000) % 1000
        return float(Z)                       # nuclei are positive
    table = {2212: 1, 2112: 0, 22: 0, 11: -1, -11: 1, 13: -1, -13: 1,
             211: 1, -211: -1, 111: 0, 130: 0, 310: 0, 321: 1, -321: -1,
             12: 0, 14: 0, 16: 0, -12: 0, -14: 0, -16: 0}
    if pdg in table:
        return float(table[pdg])
    if apdg in table:
        return -float(table[apdg]) if pdg < 0 else float(table[apdg])
    return 0.0  # unknown -> treat as neutral (conservative for a charged trigger)

@lru_cache(maxsize=None)
def is_charged(pdg):
    return abs(pdg_charge(int(pdg))) > 0.5

def species_label(pdg):
    return PDG_NAME.get(int(pdg), f"pdg{int(pdg)}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True, help="MC ROOT file (tree 'hibeam')")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--coinc-ns", type=float, default=COINC_DEFAULT)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0, help="0 = all")
    ap.add_argument("--edep-large-mev", type=float, default=15.0,
                    help="EDep threshold defining a 'large pulse' in first B layer")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    import uproot
    branches = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG",
                "Sci_bar_EDep", "Sci_bar_Time"]

    # accumulators -------------------------------------------------------
    # per-sample, per-layer (B-stack): hits, sum_edep, sumsq, pid counter, edep list (capped)
    def new_layer_acc():
        return {"hits": 0, "sum_edep": 0.0, "n_charged": 0,
                "pid": {}, "edep": []}
    samples = {"I": {"n_events": 0, "B_layers": [new_layer_acc() for _ in range(NB_LAYERS)],
                     "enterB_pid": {}, "enterA_pid": {}},
               "II": {"n_events": 0, "B_layers": [new_layer_acc() for _ in range(NB_LAYERS)],
                      "enterB_pid": {}, "enterA_pid": {}}}
    EDEP_CAP = 400_000   # cap stored EDep values per layer (for histograms) to bound memory
    n_total = 0
    n_enterB = n_enterA = n_coinc = 0

    def bump(d, k, v=1):
        d[k] = d.get(k, 0) + v

    fobj = uproot.open(args.mc)
    tree = fobj[args.tree]
    stop = args.max_events if args.max_events > 0 else None
    for chunk in tree.iterate(branches, step_size="200 MB", library="np", entry_stop=stop):
        L  = chunk["Sci_bar_LayerID"]
        L1 = chunk["Sci_bar_LayerID1"]
        PD = chunk["Sci_bar_PDG"]
        ED = chunk["Sci_bar_EDep"]
        TM = chunk["Sci_bar_Time"]
        nev = len(L)
        for i in range(nev):
            n_total += 1
            l, l1, pd, ed, tm = L[i], L1[i], PD[i], ED[i], TM[i]
            if len(l) == 0:
                continue
            charged = np.array([is_charged(p) for p in pd], dtype=bool)
            isB = (l1 == B_ARM); isA = (l1 == A_ARM)
            firstB = isB & (l == 0) & charged
            firstA = isA & (l == 0) & charged
            enterB = firstB.any()
            enterA = firstA.any()
            tB = tm[firstB].min() if enterB else np.nan
            tA = tm[firstA].min() if enterA else np.nan
            if enterB: n_enterB += 1
            if enterA: n_enterA += 1
            coinc = enterB and enterA and abs(tA - tB) < args.coinc_ns
            if coinc: n_coinc += 1

            # which samples does this event belong to?
            belongs = []
            if enterB:
                belongs.append("II")              # single-B trigger
            if coinc:
                belongs.append("I")               # A&B coincidence

            for s in belongs:
                S = samples[s]
                S["n_events"] += 1
                # PID of the particle(s) entering B / A (first-layer charged hits)
                for p in pd[firstB]:
                    bump(S["enterB_pid"], species_label(p))
                for p in pd[firstA]:
                    bump(S["enterA_pid"], species_label(p))
                # per-B-layer charged deposits
                for lid in range(NB_LAYERS):
                    mask = isB & (l == lid) & charged
                    if not mask.any():
                        continue
                    acc = S["B_layers"][lid]
                    e = ed[mask]
                    acc["hits"] += int(mask.sum())
                    acc["n_charged"] += int(mask.sum())
                    acc["sum_edep"] += float(e.sum())
                    if len(acc["edep"]) < EDEP_CAP:
                        acc["edep"].extend(e.tolist())
                    for p in pd[mask]:
                        bump(acc["pid"], species_label(p))

    # ---- reduce to a JSON-friendly summary -----------------------------
    def layer_summary(acc, large_mev):
        e = np.asarray(acc["edep"], dtype=float)
        d = {
            "hits": acc["hits"],
            "mean_edep_MeV": float(e.mean()) if e.size else 0.0,
            "median_edep_MeV": float(np.median(e)) if e.size else 0.0,
            "p95_edep_MeV": float(np.percentile(e, 95)) if e.size else 0.0,
            "frac_large": float((e > large_mev).mean()) if e.size else 0.0,
            "pid_fraction": {},
        }
        tot = sum(acc["pid"].values()) or 1
        for k, v in sorted(acc["pid"].items(), key=lambda kv: -kv[1]):
            d["pid_fraction"][k] = round(v / tot, 4)
        return d

    out = {
        "mc_file": os.path.abspath(args.mc),
        "tree": args.tree,
        "coinc_ns": args.coinc_ns,
        "edep_large_mev": args.edep_large_mev,
        "n_events_read": n_total,
        "trigger_counts": {"enter_B": n_enterB, "enter_A": n_enterA,
                           "coincidence_AB": n_coinc},
        "samples": {},
    }
    for s in ("I", "II"):
        S = samples[s]
        tot_b = sum(S["enterB_pid"].values()) or 1
        tot_a = sum(S["enterA_pid"].values()) or 1
        out["samples"][s] = {
            "n_events": S["n_events"],
            "enter_B_pid_fraction": {k: round(v / tot_b, 4)
                                     for k, v in sorted(S["enterB_pid"].items(), key=lambda kv: -kv[1])},
            "enter_A_pid_fraction": {k: round(v / tot_a, 4)
                                     for k, v in sorted(S["enterA_pid"].items(), key=lambda kv: -kv[1])},
            "B_layers": [layer_summary(S["B_layers"][l], args.edep_large_mev)
                         for l in range(NB_LAYERS)],
        }

    # headline: first-B-layer (layer 0) deuteron enrichment & large-pulse fraction
    l0_I  = out["samples"]["I"]["B_layers"][0]
    l0_II = out["samples"]["II"]["B_layers"][0]
    out["headline_first_B_layer"] = {
        "sampleI_d_fraction":  out["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
        "sampleII_d_fraction": out["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
        "sampleI_frac_large":  l0_I["frac_large"],
        "sampleII_frac_large": l0_II["frac_large"],
        "sampleI_mean_edep_MeV":  l0_I["mean_edep_MeV"],
        "sampleII_mean_edep_MeV": l0_II["mean_edep_MeV"],
    }

    with open(os.path.join(args.out, "mc_trigger_split_summary.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    # save raw first-B-layer EDep arrays for plotting (data/MC overlay later)
    np.savez_compressed(
        os.path.join(args.out, "first_B_layer_edep.npz"),
        sampleI=np.asarray(samples["I"]["B_layers"][0]["edep"], dtype=np.float32),
        sampleII=np.asarray(samples["II"]["B_layers"][0]["edep"], dtype=np.float32),
    )

    print(json.dumps(out["headline_first_B_layer"], indent=2))
    print(f"[ok] wrote {args.out}/mc_trigger_split_summary.json  "
          f"(events read={n_total}, enterB={n_enterB}, coinc={n_coinc})")

if __name__ == "__main__":
    main()
