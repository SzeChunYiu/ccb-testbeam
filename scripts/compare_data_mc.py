#!/usr/bin/env python3
"""
compare_data_mc.py
==================
Data <-> MC comparison for the CCB test beam, Sample I vs Sample II.

Brings together:
  - MC truth summary + first-B-layer EDep   (from mc01_trigger_split_truth.py)
  - DATA stave summary + first-B-layer (B2) amplitude (from data01_sample_split_staves.py)

Produces the supervisor's task (4) deliverable: a quantitative data/MC comparison
of stave outputs for the two trigger configurations, focused on the first B layer
where MC predicts (and data shows) a Sample-I large-pulse / deuteron excess.

The MC EDep (MeV) and data amplitude (ADC) live on different scales; we estimate a
single linear MeV->ADC factor by matching the Sample-II (proton-dominated) first-layer
medians, then overlay normalised shapes.  The factor is reported, not assumed.

Usage:
  python3 compare_data_mc.py --mc-dir <mc_out> --data-dir <data_out> --out <dir>
"""
import argparse, json, os
import numpy as np

def load_json(d, name):
    with open(os.path.join(d, name)) as fh:
        return json.load(fh)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc-dir", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    mc = load_json(args.mc_dir, "mc_trigger_split_summary.json")
    da = load_json(args.data_dir, "data_sample_split_summary.json")
    mc_edep = np.load(os.path.join(args.mc_dir, "first_B_layer_edep.npz"))
    da_amp = np.load(os.path.join(args.data_dir, "first_B_layer_B2_amplitude.npz"))

    mcI, mcII = mc_edep["sampleI"], mc_edep["sampleII"]
    daI, daII = da_amp["sampleI"], da_amp["sampleII"]

    # linear MeV -> ADC from Sample-II first-layer medians (proton reference)
    mc_ref = float(np.median(mcII)) if mcII.size else 1.0
    da_ref = float(np.median(daII)) if daII.size else 1.0
    mev_to_adc = da_ref / mc_ref if mc_ref else 1.0

    comp = {
        "mev_to_adc_scale": mev_to_adc,
        "scale_reference": "Sample-II first-B-layer median (proton-dominated)",
        "first_B_layer": {
            "MC": {
                "sampleI_d_fraction": mc["samples"]["I"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
                "sampleII_d_fraction": mc["samples"]["II"]["B_layers"][0]["pid_fraction"].get("d", 0.0),
                "sampleI_frac_large": mc["samples"]["I"]["B_layers"][0]["frac_large"],
                "sampleII_frac_large": mc["samples"]["II"]["B_layers"][0]["frac_large"],
                "sampleI_mean_edep_MeV": mc["samples"]["I"]["B_layers"][0]["mean_edep_MeV"],
                "sampleII_mean_edep_MeV": mc["samples"]["II"]["B_layers"][0]["mean_edep_MeV"],
            },
            "DATA": da["headline_first_B_layer_B2"],
        },
        "depth_profile": {
            "DATA_sampleI": da["per_sample"]["I"]["depth_fraction"],
            "DATA_sampleII": da["per_sample"]["II"]["depth_fraction"],
            "MC_sampleI_layerhits": [l["hits"] for l in mc["samples"]["I"]["B_layers"]],
            "MC_sampleII_layerhits": [l["hits"] for l in mc["samples"]["II"]["B_layers"]],
        },
        "enter_pid": {
            "MC_sampleI_enterB": mc["samples"]["I"]["enter_B_pid_fraction"],
            "MC_sampleII_enterB": mc["samples"]["II"]["enter_B_pid_fraction"],
            "MC_sampleI_enterA": mc["samples"]["I"]["enter_A_pid_fraction"],
            "MC_sampleII_enterA": mc["samples"]["II"]["enter_A_pid_fraction"],
        },
    }

    # qualitative verdict on whether the Sample-I large-pulse excess in the first
    # B layer is present in BOTH data and MC (Matthias' effect)
    mc_excess = comp["first_B_layer"]["MC"]["sampleI_frac_large"] - comp["first_B_layer"]["MC"]["sampleII_frac_large"]
    da_excess = comp["first_B_layer"]["DATA"]["sampleI_frac_large"] - comp["first_B_layer"]["DATA"]["sampleII_frac_large"]
    comp["first_B_layer"]["large_pulse_excess_sampleI_minus_II"] = {
        "MC": round(mc_excess, 4), "DATA": round(da_excess, 4),
        "both_positive": bool(mc_excess > 0 and da_excess > 0),
    }

    with open(os.path.join(args.out, "data_mc_comparison.json"), "w") as fh:
        json.dump(comp, fh, indent=2)

    # ---- plots (best-effort) -------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # (1) first-B-layer overlay: MC EDep*scale vs data amplitude, normalised
        fig, ax = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
        bins = np.linspace(0, 12000, 80)
        for k, (mcv, dav, ttl) in enumerate([
                (mcI, daI, "Sample I  (A&B coincidence)"),
                (mcII, daII, "Sample II  (single B)")]):
            ax[k].hist(dav, bins=bins, density=True, histtype="step", lw=2,
                       label=f"DATA B2 amplitude (n={dav.size})", color="k")
            ax[k].hist(mcv * mev_to_adc, bins=bins, density=True, histtype="stepfilled",
                       alpha=0.35, label=f"MC EDep x{mev_to_adc:.1f} (n={mcv.size})", color="C3")
            ax[k].set_title(ttl); ax[k].set_xlabel("first B layer signal [ADC / scaled MeV]")
            ax[k].legend(fontsize=8)
        ax[0].set_ylabel("normalised")
        fig.suptitle("First B layer: data vs MC, Sample I vs II")
        fig.tight_layout(); fig.savefig(os.path.join(args.out, "first_B_layer_data_mc.png"), dpi=130)
        plt.close(fig)

        # (2) depth profile data (stave) vs MC (layer), normalised
        fig, ax = plt.subplots(figsize=(7, 4.5))
        staves = ["B2", "B4", "B6", "B8"]
        x = np.arange(4)
        dI = [da["per_sample"]["I"]["depth_fraction"][s] for s in staves]
        dII = [da["per_sample"]["II"]["depth_fraction"][s] for s in staves]
        ax.plot(x, dI, "o-", label="DATA Sample I", color="C0")
        ax.plot(x, dII, "s-", label="DATA Sample II", color="C1")
        ax.set_xticks(x); ax.set_xticklabels(staves)
        ax.set_ylabel("fraction of sample's pulses"); ax.set_xlabel("B stave (depth)")
        ax.set_yscale("log"); ax.legend(); ax.set_title("Depth profile (data)")
        fig.tight_layout(); fig.savefig(os.path.join(args.out, "depth_profile_data.png"), dpi=130)
        plt.close(fig)

        # (3) MC PID fraction vs layer, Sample I vs II
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for s, c in (("I", "C0"), ("II", "C1")):
            df = [mc["samples"][s]["B_layers"][l]["pid_fraction"].get("d", 0.0) for l in range(8)]
            ax.plot(range(8), df, "o-", color=c, label=f"MC Sample {s} d-fraction")
        ax.set_xlabel("B layer (LayerID, 0=first)"); ax.set_ylabel("deuteron fraction (truth)")
        ax.legend(); ax.set_title("MC truth deuteron fraction vs depth")
        fig.tight_layout(); fig.savefig(os.path.join(args.out, "mc_d_fraction_vs_layer.png"), dpi=130)
        plt.close(fig)
        comp["_plots"] = ["first_B_layer_data_mc.png", "depth_profile_data.png",
                          "mc_d_fraction_vs_layer.png"]
    except Exception as e:
        comp["_plot_error"] = str(e)

    with open(os.path.join(args.out, "data_mc_comparison.json"), "w") as fh:
        json.dump(comp, fh, indent=2)

    print(json.dumps({"mev_to_adc": mev_to_adc,
                      "first_B_layer_large_pulse_excess": comp["first_B_layer"]["large_pulse_excess_sampleI_minus_II"]},
                     indent=2))
    print(f"[ok] wrote {args.out}/data_mc_comparison.json")

if __name__ == "__main__":
    main()
