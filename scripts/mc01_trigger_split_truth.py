#!/usr/bin/env python3
"""
mc01_trigger_split_truth.py  (v2 — extended with supervisor deliverables)
=========================================================================
MC trigger-split truth analysis for the CCB (Krakow) test beam.

Answers the supervisor's tasks on the *MC* side:
  (1) stave (B-layer) outputs for Sample I vs Sample II,
  (2) the effect of mimicking the hardware trigger in MC,
  (3) truth-level particle ID of particles ENTERING A and B per trigger config,
and tests Matthias' prediction that Sample I is deuteron-enriched in the
*first B layer* (large pulses) while Sample II is not.

v2 NEW — per supervisor request:
  - ΔE vs E plane (EDep[layer0] vs EDep[layer1]) per sample
  - Per-stave deuteron and proton counts, energy spectra, penetration depths
  - Stopping-layer distribution per species per sample
  - All figures generated as PNGs

Detector encoding (decoded from output_krakow_1M.root, tree `hibeam`):
  Sci_bar_LayerID1 == 1  -> B-stack (8 layers, downstream arm @ -38 deg)   [MAIN]
  Sci_bar_LayerID1 == 2  -> A-stack (4 layers, recoil arm @ +71.5 deg)
  Sci_bar_LayerID       == depth in the stack (0 = first layer)
  Sci_bar_PDG           == true particle (2212=p, 1000010020=d, 1000020040=alpha, ...)
  Sci_bar_EDep          == energy deposited [MeV]
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

B_ARM, A_ARM = 1, 2
NB_LAYERS = 8
COINC_DEFAULT = 15.0  # ns

PDG_NAME = {
    2212: "p", 1000010020: "d", 1000010030: "t",
    1000020030: "He3", 1000020040: "alpha",
    2112: "n", 22: "gamma", 11: "e-", -11: "e+",
    211: "pi+", -211: "pi-", 13: "mu-", -13: "mu+",
}

MASS = {2212: 938.272, 1000010020: 1875.613, 1000010030: 2808.921,
        1000020030: 2808.391, 1000020040: 3727.379}


@lru_cache(maxsize=None)
def mass_of(pdg):
    pdg = int(pdg)
    if pdg in MASS:
        return MASS[pdg]
    if abs(pdg) > 1_000_000_000:
        A = (abs(pdg) // 10) % 1000
        return A * 931.494
    return 0.511 if abs(pdg) == 11 else 139.57


@lru_cache(maxsize=None)
def pdg_charge(pdg):
    pdg = int(pdg)
    apdg = abs(pdg)
    if apdg > 1_000_000_000:
        Z = (apdg // 10_000) % 1000
        return float(Z)
    table = {2212: 1, 2112: 0, 22: 0, 11: -1, -11: 1, 13: -1, -13: 1,
             211: 1, -211: -1, 111: 0, 130: 0, 310: 0, 321: 1, -321: -1,
             12: 0, 14: 0, 16: 0, -12: 0, -14: 0, -16: 0}
    if pdg in table:
        return float(table[pdg])
    if apdg in table:
        return -float(table[apdg]) if pdg < 0 else float(table[apdg])
    return 0.0


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
    ap.add_argument("--edep-large-mev", type=float, default=15.0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    import uproot
    branches = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG",
                "Sci_bar_EDep", "Sci_bar_Time", "Sci_bar_TrackID",
                "Sci_bar_Momentum_X", "Sci_bar_Momentum_Y", "Sci_bar_Momentum_Z",
                "Sci_bar_TrackLength"]

    def new_layer_acc():
        return {"hits": 0, "sum_edep": 0.0, "n_charged": 0,
                "pid": {}, "edep": []}

    def new_track_acc():
        return {"pdg": [], "ekin": [], "edep_l0": [], "edep_l1": [],
                "edep_tot": [], "stop_layer": [], "nlayers": [],
                "tracklen": [], "edep_per_layer": []}

    samples = {
        "I": {"n_events": 0,
              "B_layers": [new_layer_acc() for _ in range(NB_LAYERS)],
              "enterB_pid": {}, "enterA_pid": {},
              "tracks": new_track_acc()},
        "II": {"n_events": 0,
               "B_layers": [new_layer_acc() for _ in range(NB_LAYERS)],
               "enterB_pid": {}, "enterA_pid": {},
               "tracks": new_track_acc()},
    }

    per_stave_species = {"I": {f"B{(l+1)*2}": {} for l in range(NB_LAYERS)},
                         "II": {f"B{(l+1)*2}": {} for l in range(NB_LAYERS)}}
    stopping_depth = {"I": {}, "II": {}}
    deltaE_E = {"I": {"edep_l0": [], "edep_l1": [], "pdg": []},
                "II": {"edep_l0": [], "edep_l1": [], "pdg": []}}

    EDEP_CAP = 600_000
    n_total = 0
    n_enterB = n_enterA = n_coinc = 0

    def bump(d, k, v=1):
        d[k] = d.get(k, 0) + v

    fobj = uproot.open(args.mc)
    tree = fobj[args.tree]
    stop = args.max_events if args.max_events > 0 else None
    for chunk in tree.iterate(branches, step_size="200 MB", library="np", entry_stop=stop):
        L = chunk["Sci_bar_LayerID"]
        L1 = chunk["Sci_bar_LayerID1"]
        PD = chunk["Sci_bar_PDG"]
        ED = chunk["Sci_bar_EDep"]
        TM = chunk["Sci_bar_Time"]
        TID = chunk["Sci_bar_TrackID"]
        MX = chunk["Sci_bar_Momentum_X"]
        MY = chunk["Sci_bar_Momentum_Y"]
        MZ = chunk["Sci_bar_Momentum_Z"]
        TL = chunk["Sci_bar_TrackLength"]
        nev = len(L)
        for i in range(nev):
            n_total += 1
            l, l1, pd, ed, tm = L[i], L1[i], PD[i], ED[i], TM[i]
            if len(l) == 0:
                continue
            charged = np.array([is_charged(p) for p in pd], dtype=bool)
            isB = (l1 == B_ARM)
            isA = (l1 == A_ARM)
            firstB = isB & (l == 0) & charged
            firstA = isA & (l == 0) & charged
            enterB = firstB.any()
            enterA = firstA.any()
            tB = tm[firstB].min() if enterB else np.nan
            tA = tm[firstA].min() if enterA else np.nan
            if enterB:
                n_enterB += 1
            if enterA:
                n_enterA += 1
            coinc = enterB and enterA and abs(tA - tB) < args.coinc_ns
            if coinc:
                n_coinc += 1

            belongs = []
            if enterB:
                belongs.append("II")
            if coinc:
                belongs.append("I")

            tid = TID[i]
            for s in belongs:
                S = samples[s]
                S["n_events"] += 1
                for p in pd[firstB]:
                    bump(S["enterB_pid"], species_label(p))
                for p in pd[firstA]:
                    bump(S["enterA_pid"], species_label(p))

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

                # ── per-track reconstruction ──
                b_hits = isB & charged
                if b_hits.any():
                    b_tids = tid[b_hits]
                    for trk in np.unique(b_tids):
                        trk_mask = b_hits & (tid == trk)
                        p0 = int(pd[trk_mask][0])
                        if pdg_charge(p0) < 1:
                            continue
                        layers = l[trk_mask]
                        eds = ed[trk_mask]
                        order = np.argsort(layers)
                        entry_idx = np.where(trk_mask)[0][order[0]]
                        px, py, pz = MX[i][entry_idx], MY[i][entry_idx], MZ[i][entry_idx]
                        pmag = float(np.sqrt(px * px + py * py + pz * pz))
                        mm = mass_of(p0)
                        ekin = float(np.sqrt(pmag * pmag + mm * mm) - mm)
                        el = {}
                        for lay, e in zip(layers, eds):
                            el[int(lay)] = el.get(int(lay), 0.0) + float(e)
                        T = S["tracks"]
                        T["pdg"].append(p0)
                        T["ekin"].append(ekin)
                        T["edep_l0"].append(el.get(0, 0.0))
                        T["edep_l1"].append(el.get(1, 0.0))
                        T["edep_tot"].append(float(eds.sum()))
                        T["stop_layer"].append(int(layers.max()))
                        T["nlayers"].append(int(len(set(layers.tolist()))))
                        T["tracklen"].append(float(TL[i][trk_mask].sum()))
                        T["edep_per_layer"].append(el)

                        sp = species_label(p0)
                        for lay_int, edep_val in el.items():
                            stave_name = f"B{(lay_int + 1) * 2}"
                            ps = per_stave_species[s]
                            ps[stave_name].setdefault(sp, []).append(edep_val)

                        stop_l = int(layers.max())
                        stopping_depth[s].setdefault(sp, []).append(stop_l)

                        if 0 in el and 1 in el:
                            deltaE_E[s]["edep_l0"].append(el[0])
                            deltaE_E[s]["edep_l1"].append(el[1])
                            deltaE_E[s]["pdg"].append(p0)

    # ── convert accumulators to arrays ───────────────────────────────────
    for s in ("I", "II"):
        for k in samples[s]["tracks"]:
            samples[s]["tracks"][k] = np.asarray(samples[s]["tracks"][k], dtype=float)
        for k in deltaE_E[s]:
            deltaE_E[s][k] = np.asarray(deltaE_E[s][k], dtype=float)

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

    per_stave_summary = {}
    for s in ("I", "II"):
        per_stave_summary[s] = {}
        for stave_name in per_stave_species[s]:
            sp_dict = per_stave_species[s][stave_name]
            per_stave_summary[s][stave_name] = {}
            for sp_name, edep_list in sp_dict.items():
                arr = np.asarray(edep_list, dtype=float)
                per_stave_summary[s][stave_name][sp_name] = {
                    "count": int(len(arr)),
                    "mean_edep_MeV": float(arr.mean()) if len(arr) > 0 else 0.0,
                    "median_edep_MeV": float(np.median(arr)) if len(arr) > 0 else 0.0,
                    "std_edep_MeV": float(arr.std()) if len(arr) > 0 else 0.0,
                }

    stopping_summary = {}
    for s in ("I", "II"):
        stopping_summary[s] = {}
        for sp_name, stop_layers in stopping_depth[s].items():
            arr = np.asarray(stop_layers, dtype=int)
            stopping_summary[s][sp_name] = {
                "count": int(len(arr)),
                "mean_stop_layer": float(arr.mean()) if len(arr) > 0 else 0.0,
                "median_stop_layer": float(np.median(arr)) if len(arr) > 0 else 0.0,
                "stop_distribution": {int(l): int((arr == l).sum())
                                      for l in range(NB_LAYERS)},
            }

    for s in ("I", "II"):
        S = samples[s]
        tot_b = sum(S["enterB_pid"].values()) or 1
        tot_a = sum(S["enterA_pid"].values()) or 1
        T = S["tracks"]
        out["samples"][s] = {
            "n_events": S["n_events"],
            "n_tracks": int(len(T["pdg"])),
            "enter_B_pid_fraction": {k: round(v / tot_b, 4)
                                     for k, v in sorted(S["enterB_pid"].items(), key=lambda kv: -kv[1])},
            "enter_A_pid_fraction": {k: round(v / tot_a, 4)
                                     for k, v in sorted(S["enterA_pid"].items(), key=lambda kv: -kv[1])},
            "B_layers": [layer_summary(S["B_layers"][l], args.edep_large_mev)
                         for l in range(NB_LAYERS)],
            "per_stave_species": per_stave_summary[s],
            "stopping_depth": stopping_summary[s],
        }

    for s in ("I", "II"):
        arr0 = deltaE_E[s]["edep_l0"]
        arr1 = deltaE_E[s]["edep_l1"]
        out["samples"][s]["deltaE_E"] = {
            "n_tracks": int(len(arr0)),
            "edep_l0_mean_MeV": float(arr0.mean()) if len(arr0) > 0 else 0.0,
            "edep_l1_mean_MeV": float(arr1.mean()) if len(arr1) > 0 else 0.0,
            "correlation_pearson": float(np.corrcoef(arr0, arr1)[0, 1])
            if len(arr0) > 2 else 0.0,
        }

    l0_I = out["samples"]["I"]["B_layers"][0]
    l0_II = out["samples"]["II"]["B_layers"][0]
    out["headline_first_B_layer"] = {
        "sampleI_d_fraction": l0_I["pid_fraction"].get("d", 0.0),
        "sampleII_d_fraction": l0_II["pid_fraction"].get("d", 0.0),
        "sampleI_frac_large": l0_I["frac_large"],
        "sampleII_frac_large": l0_II["frac_large"],
        "sampleI_mean_edep_MeV": l0_I["mean_edep_MeV"],
        "sampleII_mean_edep_MeV": l0_II["mean_edep_MeV"],
    }

    with open(os.path.join(args.out, "mc_trigger_split_summary.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    np.savez_compressed(
        os.path.join(args.out, "first_B_layer_edep.npz"),
        sampleI=np.asarray(samples["I"]["B_layers"][0]["edep"], dtype=np.float32),
        sampleII=np.asarray(samples["II"]["B_layers"][0]["edep"], dtype=np.float32),
    )
    for s in ("I", "II"):
        ps_data = {}
        for stave_name in per_stave_species[s]:
            for sp_name, edep_list in per_stave_species[s][stave_name].items():
                ps_data[f"{stave_name}_{sp_name}"] = np.asarray(edep_list, dtype=np.float32)
        np.savez_compressed(os.path.join(args.out, f"per_stave_species_edep_{s}.npz"), **ps_data)
    for s in ("I", "II"):
        np.savez_compressed(
            os.path.join(args.out, f"deltaE_E_{s}.npz"),
            edep_l0=deltaE_E[s]["edep_l0"].astype(np.float32),
            edep_l1=deltaE_E[s]["edep_l1"].astype(np.float32),
            pdg=deltaE_E[s]["pdg"].astype(np.int64),
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  PLOTS
    # ═══════════════════════════════════════════════════════════════════════
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Figure 1: ΔE-E plane per sample
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for si, s in enumerate(("I", "II")):
            ax = axes[si]
            ed0 = deltaE_E[s]["edep_l0"]
            ed1 = deltaE_E[s]["edep_l1"]
            pdg_a = deltaE_E[s]["pdg"]
            is_p = pdg_a == 2212
            is_d = pdg_a == 1000010020
            other = ~(is_p | is_d)
            n_pts = min(8000, len(ed0))
            idx = np.random.choice(len(ed0), n_pts, replace=False) if len(ed0) > n_pts else np.arange(len(ed0))
            ax.scatter(ed0[idx][other[idx]], ed1[idx][other[idx]], s=2, alpha=0.25,
                       color="gray", label="other", rasterized=True)
            ax.scatter(ed0[idx][is_p[idx]], ed1[idx][is_p[idx]], s=2, alpha=0.35,
                       color="C0", label="p", rasterized=True)
            ax.scatter(ed0[idx][is_d[idx]], ed1[idx][is_d[idx]], s=2, alpha=0.35,
                       color="C3", label="d", rasterized=True)
            ax.set_xlabel("EDep Layer 0 (B2) [MeV]")
            ax.set_ylabel("EDep Layer 1 (B4) [MeV]")
            ax.set_title(f"MC Sample {s} — ΔE-E Plane (truth)")
            ax.legend(loc="upper right", markerscale=3)
        fig.suptitle("MC Truth ΔE vs E: Sample I (coincidence) vs Sample II (single-B trigger)",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "deltaE_E_per_sample.png"), dpi=150)
        plt.close(fig)

        # Figure 2: First B layer EDep spectrum
        fig, ax = plt.subplots(figsize=(10, 5.5))
        colors = {"I": "C0", "II": "C3"}
        for s, label, ls in (("I", "Sample I (coincidence)", "-"),
                              ("II", "Sample II (single-B)", "--")):
            e = np.asarray(samples[s]["B_layers"][0]["edep"], dtype=float)
            ax.hist(e, bins=80, range=(0, 100), histtype="step", linewidth=2,
                    color=colors[s], linestyle=ls, label=label, density=True)
        ax.set_xlabel("EDep first B layer (B2) [MeV]")
        ax.set_ylabel("Normalised counts")
        ax.set_title("MC: First B-Layer (B2) Energy Deposit — Sample I vs Sample II")
        ax.legend()
        ax.set_xlim(0, 80)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "first_B_layer_edep_spectrum.png"), dpi=150)
        plt.close(fig)

        # Figure 3: Per-stave deuteron/proton fraction
        fig, ax = plt.subplots(figsize=(9, 5))
        for s, label, marker in (("I", "Sample I", "o"), ("II", "Sample II", "s")):
            d_fracs, p_fracs = [], []
            for lid in range(NB_LAYERS):
                pid_frac = out["samples"][s]["B_layers"][lid]["pid_fraction"]
                d_fracs.append(pid_frac.get("d", 0))
                p_fracs.append(pid_frac.get("p", 0))
            x = np.arange(NB_LAYERS)
            ax.plot(x, d_fracs, marker=marker, color="C3", linestyle="-", linewidth=2,
                    label=f"{label} d fraction")
            ax.plot(x, p_fracs, marker=marker, color="C0", linestyle="--", linewidth=2,
                    label=f"{label} p fraction")
        ax.set_xticks(x)
        ax.set_xticklabels([f"B{(l+1)*2}" for l in range(NB_LAYERS)])
        ax.set_xlabel("B-stack stave")
        ax.set_ylabel("Fraction of charged hits")
        ax.set_title("MC: Deuteron & Proton Fraction per B-Stave — Sample I vs Sample II")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "deuteron_proton_fraction_per_stave.png"), dpi=150)
        plt.close(fig)

        # Figure 4: Stopping-depth distribution per species
        fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
        for si, s in enumerate(("I", "II")):
            ax = axes[si]
            x = np.arange(NB_LAYERS)
            width = 0.35
            for sp, color, offset, label in (("p", "C0", -width / 2, "proton"),
                                              ("d", "C3", width / 2, "deuteron")):
                if sp in stopping_summary[s]:
                    dist = stopping_summary[s][sp]["stop_distribution"]
                    vals = [dist.get(l, 0) for l in range(NB_LAYERS)]
                    total = max(sum(vals), 1)
                    vals_norm = [v / total for v in vals]
                    ax.bar(x + offset, vals_norm, width, color=color, alpha=0.7, label=label)
            ax.set_xticks(x)
            ax.set_xticklabels([f"B{(l+1)*2}" for l in range(NB_LAYERS)])
            ax.set_xlabel("Stop layer")
            ax.set_ylabel("Fraction of tracks")
            ax.set_title(f"MC Sample {s} — Stopping Depth")
            ax.legend()
            ax.grid(True, alpha=0.2, axis="y")
        fig.suptitle("MC Truth Stopping-Depth Distribution: p vs d — Sample I vs Sample II",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "stopping_depth_per_sample.png"), dpi=150)
        plt.close(fig)

        # Figure 5: Per-stave energy spectra (all charged)
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, lid in enumerate(range(4)):
            ax = axes[idx // 2][idx % 2]
            stave_name = f"B{(lid+1)*2}"
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                e = np.asarray(samples[s]["B_layers"][lid]["edep"], dtype=float)
                if e.size > 0:
                    ax.hist(e, bins=60, range=(0, 80), histtype="step", linewidth=2,
                            color=color, linestyle=ls, label=label, density=True)
            ax.set_xlabel(f"EDep {stave_name} [MeV]")
            ax.set_ylabel("Normalised counts")
            ax.set_title(f"MC: {stave_name} Energy Deposit")
            ax.legend()
            ax.set_xlim(0, 60)
        fig.suptitle("MC: Per-Stave Energy Deposit Spectra — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "per_stave_edep_spectra.png"), dpi=150)
        plt.close(fig)

        # Figure 6: Depth profile
        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(NB_LAYERS)
        for s, label, marker in (("I", "Sample I", "o"), ("II", "Sample II", "s")):
            hits_per_layer = [out["samples"][s]["B_layers"][l]["hits"] for l in range(NB_LAYERS)]
            n_events = out["samples"][s]["n_events"]
            frac = [h / max(n_events, 1) for h in hits_per_layer]
            ax.plot(x, frac, marker=marker, linewidth=2, label=label)
        ax.set_xticks(x)
        ax.set_xticklabels([f"B{(l+1)*2}" for l in range(NB_LAYERS)])
        ax.set_xlabel("B-stack stave")
        ax.set_ylabel("Fraction of events with ≥1 charged hit")
        ax.set_title("MC: Depth Profile — Fraction of Events per Stave")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "depth_profile_mc.png"), dpi=150)
        plt.close(fig)

        # Figure 7: Deuteron EDep per stave
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, stave_name in enumerate(("B2", "B4", "B6", "B8")):
            ax = axes[idx // 2][idx % 2]
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                key = f"{stave_name}_d"
                if key in per_stave_species[s][stave_name]:
                    arr = np.asarray(per_stave_species[s][stave_name]["d"], dtype=float)
                    if len(arr) > 0:
                        ax.hist(arr, bins=50, range=(0, 70), histtype="step", linewidth=2,
                                color=color, linestyle=ls, label=f"{label} (n={len(arr)})",
                                density=True)
            ax.set_xlabel(f"Deuteron EDep {stave_name} [MeV]")
            ax.set_ylabel("Normalised counts")
            ax.set_title(f"MC: Deuteron Energy Deposit — {stave_name}")
            ax.legend(fontsize=8)
            ax.set_xlim(0, 50)
        fig.suptitle("MC: Deuteron Energy Deposit per Stave — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "deuteron_edep_per_stave.png"), dpi=150)
        plt.close(fig)

        # Figure 8: Proton EDep per stave
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, stave_name in enumerate(("B2", "B4", "B6", "B8")):
            ax = axes[idx // 2][idx % 2]
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                key = f"{stave_name}_p"
                if key in per_stave_species[s][stave_name]:
                    arr = np.asarray(per_stave_species[s][stave_name]["p"], dtype=float)
                    if len(arr) > 0:
                        ax.hist(arr, bins=50, range=(0, 50), histtype="step", linewidth=2,
                                color=color, linestyle=ls, label=f"{label} (n={len(arr)})",
                                density=True)
            ax.set_xlabel(f"Proton EDep {stave_name} [MeV]")
            ax.set_ylabel("Normalised counts")
            ax.set_title(f"MC: Proton Energy Deposit — {stave_name}")
            ax.legend(fontsize=8)
            ax.set_xlim(0, 30)
        fig.suptitle("MC: Proton Energy Deposit per Stave — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "proton_edep_per_stave.png"), dpi=150)
        plt.close(fig)

        print("[plots] All 8 MC figures generated.")
    except Exception as e:
        out["_plot_error"] = str(e)
        with open(os.path.join(args.out, "mc_trigger_split_summary.json"), "w") as fh:
            json.dump(out, fh, indent=2)
        print(f"[plot_error] {e}", file=sys.stderr)

    print(json.dumps(out["headline_first_B_layer"], indent=2))
    print(f"[ok] wrote {args.out}/mc_trigger_split_summary.json  "
          f"(events read={n_total}, enterB={n_enterB}, coinc={n_coinc})")


if __name__ == "__main__":
    main()
